"""Learner store, routes area (requirement 71 WP5; design C1 A33-A40): route attempts, feedback and agent links.

Three C1 stores in one module, composed into the learner store (see ``stores/learner/__init__.py``):

* ``RouteAttemptStore``  start / resume, owner-scoped read, assist (hint + step advance), list own attempts   (A33, A34, T27, T28)
* ``FeedbackStore``      submit (duplicate = same report), own list, withdraw, admin queue, review, retrieval examples/exclusion
                         (A35-A37, T29-T31)
* ``AgentLinkStore``     register (409 when another student owns the session), owner lookup, own / admin lists, unlink
                         (A38-A40, T32, T33)

``RoutesPostgres`` calls today's functions at call time (``route_runtime``, ``db.topic_pedagogy``, ``agent_transcripts``) so behaviour and
monkeypatching tests are unchanged. ``RoutesDynamoDB`` is the ``mb-learner`` implementation: one transaction per operation through
``LearnerUnitOfWork`` (receipt in the same transaction when an ``Idempotency-Key`` is given), ``version = :seen`` on ROUTE / FEEDBACK,
content foreign keys validated through ``stores.get_store("content")`` BEFORE the transaction, no scans and no PostgreSQL. A method
name starts with a ``stores.READ_PREFIXES`` entry exactly when it is a read, so a ``frozen`` store serves reads and rejects writes.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from collections.abc import Iterator
from typing import Any, NamedTuple

from mathbank_rest.models.ddb.learner import LearnerGap, LearnerProblem, LearnerProfile
from mathbank_rest.models.manual.learner_routes import (
    WITHDRAWN_NOTE,
    AgentLinkItem,
    FeedbackAudit,
    FeedbackItem,
    FeedbackOwner,
    RetrievalExclusion,
    RouteItem,
    UniqueAgentSession,
    UniqueFeedback,
    UniqueOpenRoute,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    InvalidToken,
    StoreUnavailable,
    UniqueViolation,
    ValidationFailed,
)
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork, run_idempotent, with_retries

CTX = "learner"
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
AUDIT_RETENTION_DAYS = 400
MAX_LOADED = 5000                       # bound of the low-cardinality admin lists (feedback queue, agent links)
OPEN_GAP_STATUSES = ("UNRESOLVED", "CONFIRMED")
AUDIT_NULLABLE_KEYS = ("requested_node_id", "structural_validation", "retrieval_score")   # null in the PostgreSQL jsonb, dropped by DynamoDB


class RouteStart(NamedTuple):
    """``view`` is the route-attempt payload; ``created`` is False when an open attempt was resumed; ``replayed`` when the
    ``Idempotency-Key`` receipt answered."""

    view: dict
    created: bool
    replayed: bool


def _content():
    from mathbank_rest import stores

    return stores.get_store("content")


def _rt():
    """``route_runtime``: its learner-state functions are the PostgreSQL implementation and its pure helpers are shared."""
    from mathbank_rest import route_runtime

    return route_runtime


def _at():
    from mathbank_rest import agent_transcripts

    return agent_transcripts


def _errors():
    from mathbank_rest import step_runtime

    return step_runtime


def _pg_engine():
    from mathbank_rest.db import postgres

    return postgres.engine


def _topic():
    from mathbank_rest.db import topic_pedagogy

    return topic_pedagogy


# --------------------------------------------------------------------------------------------------------- shared helpers

def _scope_offset(token: str | None, scope: dict) -> int:
    """Offset carried by a signed token bound to ``scope`` (user, filters); a foreign or tampered token is 400."""
    if not token:
        return 0
    offset = ddb.verify_token(token, **scope).get("o")
    if not isinstance(offset, int) or offset < 0:
        raise InvalidToken("invalid or expired next_token")
    return offset


def _slice(items: list, limit: int, token: str | None, scope: dict) -> tuple[list, str | None]:
    start = _scope_offset(token, scope)
    nxt = start + limit
    return items[start:nxt], ddb.sign_token({**scope, "o": nxt}) if nxt < len(items) else None


def _pages(model, pk: str, *, sk_begins: str | None = None, index: str | None = None, forward: bool = True,
           cap: int = MAX_LOADED, consistent: bool | None = None) -> Iterator[Any]:
    token, seen = None, 0
    while seen < cap:
        kw: dict[str, Any] = {"limit": 200, "forward": forward, "next_token": token}
        if sk_begins:
            kw["sk_begins"] = sk_begins
        if index:
            kw["index"] = index
        if consistent is not None:
            kw["consistent"] = consistent
        page = typed.query(model, pk, **kw)
        yield from page.items
        seen += len(page.items)
        token = page.next_token
        if not token:
            return


def _ts(value: Any) -> float:
    import datetime as dt

    if isinstance(value, dt.datetime):
        return (value if value.tzinfo else value.replace(tzinfo=dt.UTC)).timestamp()
    return 0.0


def _wrap(response: dict) -> dict:
    """Receipts drop ``None`` inside maps; a JSON document keeps the response shape exactly."""
    return {"doc": json.dumps(response, default=str, sort_keys=True)}


def _unwrap(wrapped: dict) -> dict:
    return json.loads(wrapped["doc"])


def _feedback_hash(topic: str, reason: str) -> str:
    return hashlib.sha256(f"{topic}|{reason}".encode()).hexdigest()


def _route_item(row: dict) -> dict:
    return {"route_attempt_id": str(row["route_attempt_id"]), "route_release_id": str(row["route_release_id"]),
            "problem_code": row.get("problem_code"), "status": row["status"], "current_step": row["current_step"],
            "tutor_explained_steps": list(row["tutor_explained_steps"] or []), "version": row["version"],
            "created_at": row["created_at"], "updated_at": row["updated_at"], "finished_at": row.get("finished_at")}


def _feedback_item(row: dict) -> dict:
    return {"feedback_id": str(row["feedback_id"]), "problem_code": row.get("problem_code"), "topic": row["topic"],
            "reason": row["reason"], "status": row["status"], "created_at": row["created_at"],
            "review_note": row.get("review_note"), "reviewed_at": row.get("reviewed_at"),
            "retrieval_verdict": row["retrieval_verdict"], "error_kind": row["error_kind"]}


# ============================================================================================================== PostgreSQL

class RoutesPostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""

    # ---- route attempts (A33, A34)
    def start_route_attempt(self, student_id, problem_code: str, route_release_id=None, *,
                            idempotency_key: str | None = None) -> RouteStart:
        rt = _rt()
        with rt.engine.begin() as conn:
            return RouteStart(rt.start_attempt(conn, student_id, problem_code, route_release_id), True, False)

    def get_route_attempt(self, student_id, attempt_id) -> dict | None:
        try:
            return self.get_owned_route_attempt(student_id, attempt_id)
        except _errors().NotFound:
            return None

    def get_owned_route_attempt(self, student_id, attempt_id) -> dict:
        rt = _rt()
        with rt.engine.connect() as conn:
            return rt.owned_attempt(conn, student_id, attempt_id, lock=False)

    def get_route_attempt_view(self, student_id, attempt_id) -> dict:
        rt = _rt()
        with rt.engine.connect() as conn:
            return rt.current_view(conn, rt.owned_attempt(conn, student_id, attempt_id, lock=False))

    def assist_route_attempt(self, student_id, attempt_id, expected_version: int, hint_level: int, advance: bool, *,
                             idempotency_key: str | None = None) -> dict:
        rt = _rt()
        with rt.engine.begin() as conn:
            return rt.assist(conn, student_id, attempt_id, expected_version, hint_level, advance)

    def list_route_attempts(self, student_id, *, route_release_id=None, status: str | None = None, limit: int = 50,
                            next_token: str | None = None) -> dict:
        from sqlalchemy import text

        rt = _rt()
        scope = {"k": "routes", "sid": str(student_id), "rid": str(route_release_id or ""), "st": status or ""}
        _scope_offset(next_token, scope)
        sql = """
            SELECT ra.route_attempt_id,ra.route_release_id,p.canonical_code AS problem_code,ra.current_step,ra.version,
                   ra.tutor_explained_steps,ra.created_at,ra.updated_at,
                   EXISTS (SELECT 1 FROM pedagogy.solution_step_instruction si
                           WHERE si.route_release_id=ra.route_release_id AND si.step_index=ra.current_step) AS has_instruction
            FROM learner.route_attempt ra
            LEFT JOIN pedagogy.solution_route_release rr ON rr.route_release_id=ra.route_release_id
            LEFT JOIN core.problem p ON p.problem_id=rr.problem_id
            WHERE ra.student_id=:s"""
        params: dict[str, Any] = {"s": student_id}
        if route_release_id:
            sql += " AND ra.route_release_id=:r"
            params["r"] = route_release_id
        sql += " ORDER BY ra.created_at DESC,ra.route_attempt_id"
        with rt.engine.connect() as conn:
            rows = [dict(r) for r in conn.execute(text(sql), params).mappings()]
        items = []
        for row in rows:
            row["status"] = "IN_PROGRESS" if row.pop("has_instruction") else "FINISHED"
            if status and row["status"] != status:
                continue
            row["finished_at"] = row["updated_at"] if row["status"] == "FINISHED" else None
            items.append(_route_item(row))
        page, token = _slice(items, limit, next_token, scope)
        return {"items": page, "next_token": token}

    # ---- feedback (A35-A37)
    def submit_feedback(self, student_id, problem_code: str, topic: str, reason: str, *, node: dict | None = None,
                        idempotency_key: str | None = None) -> dict | None:
        return _topic()._pg_submit_feedback(student_id, problem_code, topic, reason, node)

    def list_my_feedback(self, student_id, *, limit: int = 50, next_token: str | None = None) -> dict:
        from sqlalchemy import text

        scope = {"k": "feedback", "sid": str(student_id)}
        _scope_offset(next_token, scope)
        with _pg_engine().connect() as conn:
            rows = [dict(r) for r in conn.execute(text("""
                SELECT f.feedback_id,p.canonical_code AS problem_code,f.topic,f.reason,f.status,f.created_at,f.review_note,
                       f.reviewed_at,f.retrieval_verdict,f.error_kind
                FROM learner.pedagogy_feedback f JOIN core.problem p USING(problem_id)
                WHERE f.student_id=:s ORDER BY f.created_at DESC,f.feedback_id"""), {"s": student_id}).mappings()]
        page, token = _slice([_feedback_item(r) for r in rows], limit, next_token, scope)
        return {"items": page, "next_token": token}

    def withdraw_feedback(self, student_id, feedback_id) -> dict:
        from sqlalchemy import text

        errors = _errors()
        with _pg_engine().begin() as conn:
            row = conn.execute(text("""
                UPDATE learner.pedagogy_feedback SET status='DISMISSED',review_note=:note,reviewed_at=now()
                WHERE feedback_id=:id AND student_id=:s AND status='PENDING' RETURNING feedback_id,status"""),
                {"id": feedback_id, "s": student_id, "note": WITHDRAWN_NOTE}).mappings().first()
            if row is None:
                owned = conn.execute(text("SELECT 1 FROM learner.pedagogy_feedback WHERE feedback_id=:id AND student_id=:s"),
                                     {"id": feedback_id, "s": student_id}).scalar()
                if not owned:
                    raise errors.NotFound("Feedback not found.")
                raise errors.InvalidTransition("Only a pending report can be withdrawn.")
            return {"feedback_id": str(row["feedback_id"]), "status": row["status"]}

    def list_feedback_queue(self, limit: int, offset: int, *, status: str | None = None, student_id=None,
                            q: str | None = None) -> dict:
        return _topic()._pg_feedback_queue(limit, offset, status=status, student_id=student_id, q=q)

    def resolve_feedback(self, feedback_id, status: str, note: str, retrieval_verdict: str = "UNCLASSIFIED",
                         error_kind: str = "UNCLASSIFIED", actor: str | None = None) -> dict | None:
        return _topic()._pg_resolve_feedback(feedback_id, status, note, retrieval_verdict, error_kind, actor)

    def list_retrieval_examples(self, limit: int = 100) -> list[dict]:
        return _topic()._pg_retrieval_examples(limit)

    def list_excluded_problem_codes(self, node_id: str) -> list[str]:
        from sqlalchemy import text

        with _pg_engine().connect() as conn:
            return list(conn.execute(text("""
                SELECT p.canonical_code FROM learner.pedagogy_feedback f JOIN core.problem p USING(problem_id)
                WHERE f.status='RESOLVED' AND f.retrieval_verdict='IRRELEVANT'
                  AND f.audit_snapshot->>'requested_node_id'=:node ORDER BY p.canonical_code"""), {"node": node_id}).scalars())

    def get_topic_learner_state(self, student_id) -> dict:
        """``{"exposed_codes": [...], "gap_skill_ids": [...]}`` of one learner for topic practice (A9, A20)."""
        return _topic()._pg_learner_state(student_id)

    # ---- agent links (A38-A40)
    def register_agent_link(self, student_id, session_id: str, *, app_name: str | None = None, surface: str = "HOME_CHAT",
                            context: dict | None = None) -> dict:
        at = _at()
        with _pg_engine().begin() as conn:
            return at.register_link(conn, student_id, session_id, app_name=app_name or at.DEFAULT_APP_NAME, surface=surface,
                                    context=context)

    def get_agent_link(self, app_name: str, session_id: str) -> dict | None:
        at = _at()
        with _pg_engine().connect() as conn:
            if not at._agent_schema_present(conn):
                return None
            return at._pg_link(conn, app_name, session_id)

    def get_link_owner(self, app_name: str, session_id: str) -> str | None:
        link = self.get_agent_link(app_name, session_id)
        return link["student_id"] if link else None

    def list_student_sessions(self, student_id, limit: int = 50) -> list[dict]:
        with _pg_engine().connect() as conn:
            return _at().list_student_sessions(conn, student_id, limit)

    def list_all_sessions(self, student: str | None = None, limit: int = 100, next_token: str | None = None) -> dict:
        if next_token:
            raise InvalidToken("this backend does not page the agent session list")
        with _pg_engine().connect() as conn:
            return _at().list_all_sessions(conn, student, limit)

    def unlink_agent_session(self, student_id, session_id: str, *, app_name: str | None = None) -> bool:
        from sqlalchemy import text

        at = _at()
        with _pg_engine().begin() as conn:
            return bool(conn.execute(text(
                "DELETE FROM learner.agent_session_link WHERE student_id=:s AND agent_app_name=:a AND agent_session_id=:sid "
                "RETURNING 1"), {"s": student_id, "a": app_name or at.DEFAULT_APP_NAME, "sid": session_id}).first())


# ============================================================================================================== DynamoDB

class RoutesDynamoDB:
    """DynamoDB backend over mb-learner."""

    # ------------------------------------------------------------------------------------------------ route attempts

    @staticmethod
    def _route_as_dict(item: RouteItem) -> dict:
        return {"route_attempt_id": item.route_attempt_id, "route_release_id": item.route_release_id, "student_id": item.student_id,
                "problem_code": item.problem_code, "current_step": item.current_step, "version": item.version,
                "tutor_explained_steps": list(item.tutor_explained_steps), "status": item.status,
                "created_at": item.created_at, "updated_at": item.updated_at, "finished_at": item.finished_at}

    def _route_load(self, student_id, attempt_id) -> RouteItem | None:
        if not UUID_RE.match(str(attempt_id)):
            return None
        return typed.get(RouteItem, ddb.student_pk(student_id), f"ROUTE#{attempt_id}")

    def get_route_attempt(self, student_id, attempt_id) -> dict | None:
        item = self._route_load(student_id, attempt_id)
        return None if item is None else self._route_as_dict(item)

    def get_owned_route_attempt(self, student_id, attempt_id) -> dict:
        """A foreign (or unknown) attempt id has no item under the learner's partition: 404."""
        found = self.get_route_attempt(student_id, attempt_id)
        if found is None:
            raise _errors().NotFound("Route attempt not found.")
        return found

    def _route_view(self, attempt: dict) -> dict:
        instruction = _content().get_route_step_instruction(attempt["route_release_id"], attempt["current_step"])
        return _rt().attempt_view(attempt, instruction)

    def get_route_attempt_view(self, student_id, attempt_id) -> dict:
        return self._route_view(self.get_owned_route_attempt(student_id, attempt_id))

    def _route_open(self, student_id, release_id: str) -> tuple[RouteItem | None, UniqueOpenRoute | None]:
        """The IN_PROGRESS attempt of the release through its sentinel; a sentinel without such an attempt is stale (returned too)."""
        pk = ddb.student_pk(student_id)
        sentinel = typed.get(UniqueOpenRoute, pk, f"UNIQUE#open_route#{release_id}")
        if sentinel is None:
            return None, None
        item = typed.get(RouteItem, pk, f"ROUTE#{sentinel.route_attempt_id}")
        return (item if item is not None and item.status == "IN_PROGRESS" else None), sentinel

    def start_route_attempt(self, student_id, problem_code: str, route_release_id=None, *,
                            idempotency_key: str | None = None) -> RouteStart:
        """Resume the open attempt of the release (sentinel) or create ROUTE + sentinel in one transaction."""
        errors, content = _errors(), _content()
        release = (content.get_published_route(problem_code, route_release_id) if route_release_id
                   else content.find_published_route(problem_code))
        if not release:
            raise errors.NotFound("No reviewed published route is available for this problem.")
        release_id = str(release["route_release_id"])
        pk, sid = ddb.student_pk(student_id), str(student_id)

        def build(uow: LearnerUnitOfWork) -> dict:
            open_item, sentinel = self._route_open(student_id, release_id)
            if open_item is not None:
                return _wrap({"view": self._route_view(self._route_as_dict(open_item)), "created": False})
            attempt_id, now = ddb.uuid7(), ddb.now_iso()
            item = RouteItem(PK=pk, SK=f"ROUTE#{attempt_id}", student_id=sid, route_attempt_id=attempt_id,
                             route_release_id=release_id, problem_code=problem_code, current_step=1, tutor_explained_steps=[],
                             status="IN_PROGRESS", created_at=now, updated_at=now, version=1)
            marker = UniqueOpenRoute(PK=pk, SK=f"UNIQUE#open_route#{release_id}", route_attempt_id=attempt_id, student_id=sid)
            clash = UniqueViolation("open_route", release_id)
            if sentinel is None:
                uow.put_new(marker, conflict=clash)
            else:    # stale sentinel (its attempt finished or vanished): take it over only if nobody did meanwhile
                uow.put(marker, cond=ddb.Cond("#ra = :old", {"#ra": "route_attempt_id"}, {":old": str(sentinel.route_attempt_id)}),
                        conflict=clash)
            uow.put_new(item)
            return _wrap({"view": self._route_view(self._route_as_dict(item)), "created": True})

        wrapped, replayed = with_retries(
            lambda: run_idempotent(student_id, key=idempotency_key, operation="start_route_attempt",
                                   body={"problem_code": problem_code, "route_release_id": release_id}, build=build),
            on=(UniqueViolation, StoreUnavailable))
        doc = _unwrap(wrapped)
        return RouteStart(self._route_fill(doc["view"]), bool(doc["created"]), replayed)

    @staticmethod
    def _route_fill(view: dict) -> dict:
        """The nullable keys of a view, restored in the order of ``route_runtime.attempt_view``."""
        keys = ("route_attempt_id", "route_release_id", "version", "current_step", "status", "goal", "student_prompt",
                "tutor_explained_steps", "mastery_recorded")
        return {**{k: view.get(k) for k in keys}, **{k: v for k, v in view.items() if k not in keys}}

    def assist_route_attempt(self, student_id, attempt_id, expected_version: int, hint_level: int, advance: bool, *,
                             idempotency_key: str | None = None) -> dict:
        errors, content, rt = _errors(), _content(), _rt()
        pk = ddb.student_pk(student_id)

        def build(uow: LearnerUnitOfWork) -> dict:
            attempt = self.get_owned_route_attempt(student_id, attempt_id)
            rt.check_assist(attempt, expected_version, hint_level, advance)
            release, step = str(attempt["route_release_id"]), attempt["current_step"]
            hint = content.get_route_step_hint(release, step, hint_level)
            if not hint:
                raise errors.NotFound("No reviewed asset is available for this current step.")
            new_step = step + 1 if advance else step
            instruction = content.get_route_step_instruction(release, new_step)
            changes: dict[str, Any] = {}
            explained = list(attempt["tutor_explained_steps"])
            if advance:
                explained.append(step)
                changes.update(current_step=new_step, tutor_explained_steps=explained)
            finished = advance and instruction is None
            if finished:
                changes.update(status="FINISHED", finished_at=ddb.now_iso())
            uow.update(RouteItem, pk, f"ROUTE#{attempt_id}", changes, expected={"version": expected_version},
                       cond=ddb.Cond("#st = :inp", {"#st": "status"}, {":inp": "IN_PROGRESS"}),
                       conflict=errors.StateVersionConflict("Checkpoint changed; reload the route attempt."))
            if finished:
                uow.delete(UniqueOpenRoute, pk, f"UNIQUE#open_route#{release}")
            updated = {**attempt, "current_step": new_step, "tutor_explained_steps": explained,
                       "version": attempt["version"] + 1}
            return _wrap({**rt.attempt_view(updated, instruction), "hint": hint, "hint_level": hint_level,
                          "source": "published-hint-library"})

        wrapped, _ = run_idempotent(student_id, key=idempotency_key, operation="assist_route_attempt",
                                    body={"attempt_id": str(attempt_id), "expected_version": expected_version,
                                          "hint_level": hint_level, "advance": advance}, build=build)
        return self._route_fill(_unwrap(wrapped))

    def list_route_attempts(self, student_id, *, route_release_id=None, status: str | None = None, limit: int = 50,
                            next_token: str | None = None) -> dict:
        scope = {"k": "routes", "sid": str(student_id), "rid": str(route_release_id or ""), "st": status or ""}
        _scope_offset(next_token, scope)            # a foreign token is rejected before any read
        items = [i for i in _pages(RouteItem, ddb.student_pk(student_id), sk_begins="ROUTE#")
                 if (not route_release_id or str(i.route_release_id) == str(route_release_id)) and (not status or i.status == status)]
        items.sort(key=lambda i: (-_ts(i.created_at), str(i.route_attempt_id)))
        page, token = _slice([_route_item(self._route_as_dict(i)) for i in items], limit, next_token, scope)
        return {"items": page, "next_token": token}

    # ------------------------------------------------------------------------------------------------ feedback

    @staticmethod
    def _feedback_audit_of(item: FeedbackItem) -> dict:
        return {**dict.fromkeys(AUDIT_NULLABLE_KEYS), **(item.resolve("audit_snapshot") or {})}

    def _feedback_reply(self, item: FeedbackItem) -> dict:
        return {"feedback_id": str(item.feedback_id), "status": item.status, "created_at": item.created_at,
                "audit": self._feedback_audit_of(item)}

    def _feedback_problem_id(self, problem_code: str) -> str | None:
        found = _content().get_solution_dag(problem_code)["problem_id"]
        if found:
            return str(found)
        from mathbank_rest.models.ddb.content import ContentProblem

        item = typed.get(ContentProblem, f"PROBLEM#{problem_code}", "META", consistent=False)
        return str(item.problem_id) if item is not None else None

    def submit_feedback(self, student_id, problem_code: str, topic: str, reason: str, *, node: dict | None = None,
                        idempotency_key: str | None = None) -> dict | None:
        """Duplicate report (same problem, topic and reason) = the existing report; unknown problem = ``None``."""
        topic, reason = topic.strip(), reason.strip()
        audit = _topic().audit_problem_content(_content(), problem_code, topic, node)
        if audit.get("error"):
            return None
        problem_id = self._feedback_problem_id(problem_code)
        if problem_id is None:
            return None
        pk, sid, digest = ddb.student_pk(student_id), str(student_id), _feedback_hash(topic, reason)
        sentinel_sk = f"UNIQUE#feedback#{problem_id}#{digest}"

        def build(uow: LearnerUnitOfWork) -> dict:
            marker = typed.get(UniqueFeedback, pk, sentinel_sk)
            if marker is not None:
                return _wrap(self._feedback_reply(typed.require(FeedbackItem, pk, f"FEEDBACK#{marker.feedback_id}")))
            fid, now = ddb.uuid7(), ddb.now_iso()
            item = FeedbackItem(
                PK=pk, SK=f"FEEDBACK#{fid}", GSI1PK="FEEDBACK#PENDING", GSI1SK=f"{now}#{fid}", student_id=sid, feedback_id=fid,
                problem_id=problem_id, problem_code=problem_code, topic=topic, reason=reason, status="PENDING", created_at=now,
                audit_snapshot=audit, requested_node_id=audit.get("requested_node_id"), version=1)
            uow.put_new(UniqueFeedback(PK=pk, SK=sentinel_sk, student_id=sid, feedback_id=fid),
                        conflict=UniqueViolation("feedback", sentinel_sk))
            uow.put_new(item)
            uow.put_new(FeedbackOwner(PK=f"FEEDBACK#{fid}", SK="OWNER", student_id=sid))
            return _wrap(self._feedback_reply(item))

        wrapped, _ = with_retries(
            lambda: run_idempotent(student_id, key=idempotency_key, operation="submit_feedback",
                                   body={"problem_code": problem_code, "topic": topic, "reason": reason}, build=build),
            on=(UniqueViolation, StoreUnavailable))
        return _unwrap(wrapped)

    def _feedback_code(self, item: FeedbackItem) -> str | None:
        if item.problem_code:
            return item.problem_code
        code = (item.resolve("audit_snapshot") or {}).get("problem_code")
        if code:
            return code
        found = _content().get_problem_by_id(str(item.problem_id))
        return found["canonical_code"] if found else None

    def list_my_feedback(self, student_id, *, limit: int = 50, next_token: str | None = None) -> dict:
        scope = {"k": "feedback", "sid": str(student_id)}
        _scope_offset(next_token, scope)
        rows = sorted(_pages(FeedbackItem, ddb.student_pk(student_id), sk_begins="FEEDBACK#"),
                      key=lambda i: (-_ts(i.created_at), str(i.feedback_id)))
        items = [_feedback_item({"feedback_id": i.feedback_id, "problem_code": self._feedback_code(i), "topic": i.topic,
                                 "reason": i.reason, "status": i.status, "created_at": i.created_at,
                                 "review_note": i.resolve("review_note"), "reviewed_at": i.reviewed_at,
                                 "retrieval_verdict": i.retrieval_verdict, "error_kind": i.error_kind}) for i in rows]
        page, token = _slice(items, limit, next_token, scope)
        return {"items": page, "next_token": token}

    def withdraw_feedback(self, student_id, feedback_id) -> dict:
        """The learner dismisses an own PENDING report (T30)."""
        errors = _errors()
        pk = ddb.student_pk(student_id)
        item = typed.get(FeedbackItem, pk, f"FEEDBACK#{feedback_id}") if UUID_RE.match(str(feedback_id)) else None
        if item is None:
            raise errors.NotFound("Feedback not found.")
        if item.status != "PENDING":
            raise errors.InvalidTransition("Only a pending report can be withdrawn.")
        uow = LearnerUnitOfWork(student_id)
        uow.update(FeedbackItem, pk, f"FEEDBACK#{feedback_id}",
                   {"status": "DISMISSED", "review_note": WITHDRAWN_NOTE, "reviewed_at": ddb.now_iso(),
                    "GSI1PK": "FEEDBACK#DISMISSED"},
                   expected={"version": item.version}, cond=ddb.Cond("#st = :p", {"#st": "status"}, {":p": "PENDING"}),
                   conflict=errors.InvalidTransition("Only a pending report can be withdrawn."))
        uow.commit()
        return {"feedback_id": str(feedback_id), "status": "DISMISSED"}

    def _feedback_queue(self) -> list[FeedbackItem]:
        """Every report, PENDING first then the reviewed ones, newest first within each (GSI1 ``FEEDBACK#<status>``)."""
        by_status = {s: list(_pages(FeedbackItem, f"FEEDBACK#{s}", index="GSI1", forward=False))
                     for s in ("PENDING", "RESOLVED", "DISMISSED")}
        reviewed = sorted(by_status["RESOLVED"] + by_status["DISMISSED"], key=lambda i: i.GSI1SK or "", reverse=True)
        return by_status["PENDING"] + reviewed

    def list_feedback_queue(self, limit: int, offset: int, *, status: str | None = None, student_id=None,
                            q: str | None = None) -> dict:
        everything = self._feedback_queue()
        related: dict[tuple[str, str], int] = {}
        for i in everything:
            related[(str(i.problem_id), i.topic)] = related.get((str(i.problem_id), i.topic), 0) + 1
        needle = (q or "").lower()
        rows = [i for i in everything
                if (not status or i.status == status) and (student_id is None or str(i.student_id) == str(student_id))
                and (not needle or needle in i.topic.lower() or needle in i.reason.lower())]
        items = [{"feedback_id": str(i.feedback_id), "canonical_code": self._feedback_code(i), "topic": i.topic, "reason": i.reason,
                  "status": i.status, "created_at": i.created_at, "review_note": i.resolve("review_note"),
                  "reviewed_at": i.reviewed_at, "audit": self._feedback_audit_of(i), "retrieval_verdict": i.retrieval_verdict,
                  "error_kind": i.error_kind, "related_report_count": related[(str(i.problem_id), i.topic)]}
                 for i in rows[offset:offset + limit]]
        return {"items": items, "total": len(rows), "limit": limit, "offset": offset}

    @staticmethod
    def _feedback_audit_op(feedback: FeedbackItem, actor: str | None, before: dict, after: dict):
        actor_id, actor_type = actor or "system", "ADMIN" if actor else "SYSTEM"
        audit_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
        at = f"AT#{int(time.time() * 1_000_000):017d}#{audit_id}"
        entry = FeedbackAudit(
            PK=f"ENTITY#FEEDBACK#{feedback.feedback_id}", SK=at, GSI1PK=f"ACTOR#{actor_type}#{actor_id}", GSI1SK=at,
            GSI2PK=f"REQ#{request_id}", GSI2SK=at, GSI3PK=f"AUDIT#{audit_id}", GSI3SK="AUDIT", audit_id=audit_id,
            actor_type=actor_type, actor_id=actor_id, action="FEEDBACK_REVIEWED", entity_type="FEEDBACK",
            entity_id=str(feedback.feedback_id), before_state=before, after_state=after, request_id=request_id,
            created_at=ddb.now_iso(), ttl=ddb.epoch_after(AUDIT_RETENTION_DAYS))
        return typed.tx_put(entry, ddb.NOT_EXISTS, label="audit")

    @staticmethod
    def _feedback_exclusion_op(node: str, problem_id: str, code: str | None, feedback_id: str, now: str):
        sets = ["#t = :t", "#n = :n", "#p = :p", "#u = :now", "#f = list_append(if_not_exists(#f, :empty), :fid)"]
        names = {"#t": "type", "#n": "requested_node_id", "#p": "problem_id", "#u": "updated_at", "#f": "feedback_ids"}
        values: dict[str, Any] = {":t": "RETRIEVAL_EXCLUSION", ":n": node, ":p": problem_id, ":now": now, ":empty": [],
                                  ":fid": [feedback_id]}
        if code:
            sets.append("#c = :c")
            names["#c"], values[":c"] = "problem_code", code
        return ddb.Update(CTX, f"RETRIEVAL_EXCLUSION#{node}", f"PROBLEM#{problem_id}", "SET " + ", ".join(sets), names=names,
                          values=values, label="retrieval_exclusion")

    def resolve_feedback(self, feedback_id, status: str, note: str, retrieval_verdict: str = "UNCLASSIFIED",
                         error_kind: str = "UNCLASSIFIED", actor: str | None = None) -> dict | None:
        """Review a PENDING report once (T31): version-guarded update, reviewer and ``mb-audit`` record in the SAME transaction, and
        the retrieval exclusion when the verdict is IRRELEVANT. ``None`` = missing or already reviewed (409 for the caller)."""
        if not UUID_RE.match(str(feedback_id)):
            return None
        owner = typed.get(FeedbackOwner, f"FEEDBACK#{feedback_id}", "OWNER")
        if owner is None:
            return None
        pk = ddb.student_pk(owner.student_id)
        item = typed.get(FeedbackItem, pk, f"FEEDBACK#{feedback_id}")
        if item is None or item.status != "PENDING":
            return None
        note, now = note.strip(), ddb.now_iso()
        changes = {"status": status, "review_note": note, "reviewed_at": now, "reviewed_by": actor or "system",
                   "retrieval_verdict": retrieval_verdict, "error_kind": error_kind, "GSI1PK": f"FEEDBACK#{status}"}
        FeedbackItem.from_item({**item.to_item(), **typed.validate_changes(FeedbackItem, changes)})   # pairing rules, before the write
        uow = LearnerUnitOfWork(owner.student_id)
        uow.update(FeedbackItem, pk, f"FEEDBACK#{feedback_id}", changes, expected={"version": item.version},
                   cond=ddb.Cond("#st = :p", {"#st": "status"}, {":p": "PENDING"}),
                   conflict=ConditionFailed("feedback already reviewed"))
        node = item.requested_node_id or (item.resolve("audit_snapshot") or {}).get("requested_node_id")
        if status == "RESOLVED" and retrieval_verdict == "IRRELEVANT" and node:
            uow.add(self._feedback_exclusion_op(node, str(item.problem_id), self._feedback_code(item), str(feedback_id), now))
        uow.add(self._feedback_audit_op(item, actor, {"status": "PENDING"},
                               {"status": status, "retrieval_verdict": retrieval_verdict, "error_kind": error_kind,
                                "reviewed_by": actor or "system"}))
        try:
            uow.commit()
        except ConditionFailed:
            return None
        return {"feedback_id": str(feedback_id), "status": status, "review_note": note,
                "retrieval_verdict": retrieval_verdict, "error_kind": error_kind}

    def list_retrieval_examples(self, limit: int = 100) -> list[dict]:
        """Reviewed, classified reports as evaluation examples (RESOLVED, verdict set), newest review first."""
        rows = [i for i in _pages(FeedbackItem, "FEEDBACK#RESOLVED", index="GSI1", forward=False)
                if i.retrieval_verdict != "UNCLASSIFIED"]
        rows.sort(key=lambda i: _ts(i.reviewed_at), reverse=True)
        return [{"query": i.topic, "canonical_code": self._feedback_code(i), "retrieval_verdict": i.retrieval_verdict,
                 "error_kind": i.error_kind, "reason": i.resolve("review_note"), "reviewed_at": i.reviewed_at,
                 "review_reference": str(i.feedback_id)} for i in rows[:limit]]

    def list_excluded_problem_codes(self, node_id: str) -> list[str]:
        """A37: problems a reviewer found irrelevant for the taxonomy node, excluded for every learner."""
        codes = []
        for row in _pages(RetrievalExclusion, f"RETRIEVAL_EXCLUSION#{node_id}", sk_begins="PROBLEM#", consistent=False):
            code = row.problem_code
            if not code:
                found = _content().get_problem_by_id(str(row.problem_id))
                code = found["canonical_code"] if found else None
            if code:
                codes.append(code)
        return sorted(set(codes))

    def get_topic_learner_state(self, student_id) -> dict:
        """Exposure (problems the learner met: ``PROBLEM#`` cursors) and open-gap skills (``GAP#``) of one learner (A9, A20)."""
        pk, content = ddb.student_pk(student_id), _content()
        codes: set[str] = set()
        for cursor in _pages(LearnerProblem, pk, sk_begins="PROBLEM#", consistent=False):
            found = content.get_problem_by_id(str(cursor.problem_id))
            if found:
                codes.add(found["canonical_code"])
        skills = {g.target_skill_id for g in _pages(LearnerGap, pk, sk_begins="GAP#")
                  if g.status in OPEN_GAP_STATUSES and g.target_skill_id}
        return {"exposed_codes": sorted(codes), "gap_skill_ids": sorted(skills)}

    # ------------------------------------------------------------------------------------------------ agent links

    @staticmethod
    def _agent_link_dict(link: AgentLinkItem, email: str | None) -> dict:
        return {"agent_session_link_id": str(link.link_id), "agent_app_name": link.agent_app_name,
                "agent_session_id": link.agent_session_id, "agent_user_id": str(link.agent_user_id),
                "student_id": str(link.student_id), "email": email, "surface": link.surface,
                "context": link.resolve("context") or {}, "created_at": link.created_at, "last_seen_at": link.last_seen_at}

    @staticmethod
    def _agent_emails(student_ids) -> dict[str, str]:
        ids = list(dict.fromkeys(str(s) for s in student_ids))
        found = typed.batch_get(LearnerProfile, [(ddb.student_pk(s), "PROFILE") for s in ids], consistent=False)
        return {str(p.student_id): p.email for p in found}

    @staticmethod
    def _agent_marker(app_name: str, session_id: str) -> UniqueAgentSession | None:
        return typed.get(UniqueAgentSession, *ddb.unique_key("agent_session", f"{app_name}#{session_id}"))

    def register_agent_link(self, student_id, session_id: str, *, app_name: str | None = None, surface: str = "HOME_CHAT",
                            context: dict | None = None) -> dict:
        """Idempotent link of an ADK session the student owns (T32). The sentinel carries the owner: another student -> 409."""
        at = _at()
        app_name = app_name or at.DEFAULT_APP_NAME
        if surface not in at.SURFACES:
            raise at.TranscriptError(f"surface must be one of {at.SURFACES}")
        if "#" in session_id or "#" in app_name:
            raise ValidationFailed("agent session ids cannot contain '#'")
        if not at.adk_sessions.available():
            raise at.NotFound("agent session store is not initialised")
        owner = str(student_id)
        if not at.adk_sessions.session_exists(app_name, owner, session_id):
            raise at.NotFound("agent session not found for this student")
        pk, sk = ddb.student_pk(student_id), f"AGENT#{app_name}#{session_id}"
        response = {"agent_session_id": session_id, "agent_app_name": app_name, "surface": surface}

        def attempt() -> dict:
            marker = self._agent_marker(app_name, session_id)
            if marker is not None and str(marker.student_id) != owner:
                raise at.Conflict("agent session is linked to another student")
            link = typed.get(AgentLinkItem, pk, sk)
            uow = LearnerUnitOfWork(student_id)
            if link is not None:
                merged = {**(link.resolve("context") or {}), **(context or {})}
                uow.update(AgentLinkItem, pk, sk, {"last_seen_at": ddb.now_iso(), "context": merged},
                           remove=("context_ref",) if link.ref("context") else ())
                uow.commit()
                return {"agent_session_link_id": str(link.link_id), "created": False, **response}
            link_id, now = str(uuid.uuid4()), ddb.now_iso()
            item = AgentLinkItem(PK=pk, SK=sk, GSI1PK="AGENTLINKS", GSI1SK=f"{now}#{link_id}", student_id=owner, link_id=link_id,
                                 agent_app_name=app_name, agent_session_id=session_id, agent_user_id=owner, surface=surface,
                                 context=context or {}, created_at=now, last_seen_at=now)
            if marker is None:
                uow.put_new(UniqueAgentSession(PK=ddb.unique_key("agent_session", f"{app_name}#{session_id}")[0], SK="UNIQUE",
                                               student_id=owner), conflict=UniqueViolation("agent_session", session_id))
            uow.put_new(item)
            uow.commit()
            return {"agent_session_link_id": link_id, "created": True, **response}

        try:
            return with_retries(attempt, on=(UniqueViolation, ConditionFailed, StoreUnavailable), attempts=5)
        except UniqueViolation:
            raise at.Conflict("agent session is linked to another student") from None

    def get_agent_link(self, app_name: str, session_id: str) -> dict | None:
        """Ownership link of an ADK session through its sentinel (A38): ``student_id``, ``agent_user_id``, ``email``, ``surface``,
        ``context``, ``created_at``; ``None`` when no student linked it."""
        if "#" in session_id or "#" in app_name:
            return None
        marker = self._agent_marker(app_name, session_id)
        if marker is None:
            return None
        link = typed.get(AgentLinkItem, ddb.student_pk(marker.student_id), f"AGENT#{app_name}#{session_id}")
        if link is None:
            return None
        return self._agent_link_dict(link, self._agent_emails([marker.student_id]).get(str(marker.student_id)))

    def get_link_owner(self, app_name: str, session_id: str) -> str | None:
        if "#" in session_id or "#" in app_name:
            return None
        marker = self._agent_marker(app_name, session_id)
        return None if marker is None else str(marker.student_id)

    def _agent_session_rows(self, links: list[AgentLinkItem]) -> list[dict]:
        """Shaped list rows: the link, the profile e-mail and the ADK session facts (updated time, event count, preview)."""
        at = _at()
        emails = self._agent_emails(link.student_id for link in links)
        facts = at.adk_sessions.facts([(i.agent_app_name, str(i.agent_user_id), i.agent_session_id) for i in links])
        rows = []
        for link in links:
            fact = facts.get((link.agent_app_name, str(link.agent_user_id), link.agent_session_id), {})
            rows.append({**self._agent_link_dict(link, emails.get(str(link.student_id))),
                         "session_updated_at": fact.get("session_updated_at"), "event_count": fact.get("event_count", 0),
                         "first_message": fact.get("first_message")})
        rows.sort(key=lambda r: _ts(r["session_updated_at"] or r["last_seen_at"]), reverse=True)
        return [at._shape(r) for r in rows]

    def list_student_sessions(self, student_id, limit: int = 50) -> list[dict]:
        if not _at().adk_sessions.available():
            return []
        return self._agent_session_rows(list(_pages(AgentLinkItem, ddb.student_pk(student_id), sk_begins="AGENT#")))[:limit]

    def list_all_sessions(self, student: str | None = None, limit: int = 100, next_token: str | None = None) -> dict:
        """Admin list (A40): every link (GSI1 ``AGENTLINKS``, newest first), optionally filtered by student uuid or e-mail
        substring, ordered by session activity like today, plus the count of ADK sessions nobody linked."""
        at = _at()
        scope = {"k": "agentlinks", "who": student or ""}
        _scope_offset(next_token, scope)
        if not at.adk_sessions.available():
            return {"linked": [], "unlinked_count": 0}
        links = list(_pages(AgentLinkItem, "AGENTLINKS", index="GSI1", forward=False))
        unlinked = at.adk_sessions.unlinked_count({(i.agent_app_name, str(i.agent_user_id), i.agent_session_id) for i in links})
        if student:
            emails, who = self._agent_emails(i.student_id for i in links), student.lower()
            links = [i for i in links if str(i.student_id) == student or who in (emails.get(str(i.student_id)) or "").lower()]
        page, token = _slice(self._agent_session_rows(links), limit, next_token, scope)
        out: dict[str, Any] = {"linked": page, "unlinked_count": unlinked}
        if token:
            out["next_token"] = token
        return out

    def unlink_agent_session(self, student_id, session_id: str, *, app_name: str | None = None) -> bool:
        """Remove the link and its sentinel in one transaction (T33); the ADK transcript is untouched."""
        app_name = app_name or _at().DEFAULT_APP_NAME
        if "#" in session_id or "#" in app_name:
            return False
        pk, sk = ddb.student_pk(student_id), f"AGENT#{app_name}#{session_id}"
        if typed.get(AgentLinkItem, pk, sk) is None:
            return False
        uow = LearnerUnitOfWork(student_id)
        uow.delete(AgentLinkItem, pk, sk, conflict=ConditionFailed("agent link changed"))
        sentinel_pk, sentinel_sk = ddb.unique_key("agent_session", f"{app_name}#{session_id}")
        uow.add(ddb.Delete(CTX, sentinel_pk, sentinel_sk, ddb.Cond("#s = :s", {"#s": "student_id"}, {":s": str(student_id)}),
                           ConditionFailed("agent session owned by another student"), label="unique:agent_session"))
        uow.commit()
        return True
