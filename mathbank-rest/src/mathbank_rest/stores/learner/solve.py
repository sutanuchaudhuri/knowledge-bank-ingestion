"""Learner store, solve area (requirement 71 WP5; requirement 70 C1 access patterns A10-A18, write paths T8-T12, T14, T15).

``SolvePostgres`` delegates to ``step_runtime`` (the SQL layer) at call time, so behaviour is unchanged and monkeypatching tests keep
working. ``SolveDynamoDB`` is the ``mb-learner`` implementation: every operation is one ``LearnerUnitOfWork`` transaction (<= 100 items,
the idempotency receipt included), the client's ``state_version`` is checked in code (409) and then enforced by a condition on the SOLVE
item, append-only items are only created, and content (steps, problem code and statement) is read through the content store before the
transaction. Nothing here imports ``db.postgres``.

Operations (a method is a read exactly when its name starts with a ``stores.READ_PREFIXES`` entry):

* writes  ``start_attempt`` (T8), ``submit_step_response`` (T9), ``request_hint`` (T10), ``record_hint_presented`` (T11),
          ``record_step_outcome`` (T12), ``submit_attempt`` (T14), ``abandon_stale_attempts`` (T15)
* reads   ``get_attempt_runtime`` (A11), ``get_attempt_owner`` (A12), ``list_solve_attempts`` (A13), ``list_events`` / ``list_events_page``
          (A16/A17), ``get_events_after``, ``get_step_tutor_state`` (hint/evaluation context)

Seams to the areas that other agents implement. All are looked up on ``self`` (the composed ``DynamoDBLearnerStore``) and are optional:

* ``stage_outcome(uow, *, problem_id, attempt_id, attempted_at, is_correct, submitted_answer, time_spent_seconds, hint_count, source,
  difficulty_band, tags, solve_attempt_id) -> StagedOutcome`` and ``finish_deferred_mastery(student_id, staged)`` (OutcomeStore, T7,
  as implemented in ``stores/learner/outcomes.py``). Called when an attempt completes (T12) or is handed in (T14, policy permitting):
  OUTCOME, the PROBLEM counter update, and MEVID/MASTERY per tag land in the same transaction. The open-session marker of the PROBLEM
  cursor is removed inside the OutcomeStore's own ``PROBLEM#<pid>`` update (guarded by the attempt id): a transaction may not
  touch an item twice, and that update is found by key, so it must stay an ``update`` op on that key. What did not fit
  (``staged.deferred``) is finished after the commit. Absent (a standalone ``SolveDynamoDB``): OUTCOME is written here and
  the PROBLEM cursor is closed by this area.
* ``hooks.run_auto_diagnose(uow, ctx)`` (DiagnosisStore, T12/T13): called LAST, after every other item of the outcome transaction, so
  ``uow.remaining()`` is the true budget and diagnosis is the first thing dropped. ``ctx`` carries ``student_id``, ``attempt_id``,
  ``solve`` and ``step_state`` (the SOLVE and STEPSTATE models AFTER the outcome), ``outcome``, ``actor``, and ``out`` (a dict the hook
  may fill: ``gap_status_changes`` and ``diagnosis``, the student view, returned in the response). The hook is called for every outcome
  (gap statuses move on success too) and MUST NOT add an operation on the SOLVE item or the current/next STEPSTATE (already written here).
* ``get_step_diagnosis_view(student_id, attempt_id, step_id) -> dict | None`` (DiagnosisStore): the student view of the latest diagnosis
  of a step, for the runtime read model. Absent: ``None``.
* ``build_abort_plan_ops(uow, *, student_id, attempt_id, plan_ids, actor, reason) -> None`` (RecoveryStore, T15): adds the PLAN updates
  (ACTIVE/SUSPENDED -> ABORTED, items SKIPPED) and RECOVERY_PLAN_ABORTED events of an abandoned attempt. Absent: plans are left as they are.

Differences from PostgreSQL that callers can observe (all listed in the WP5 report): the learner event feed shows the allow-listed
payload (LRN-F01), an early submit writes an outcome per ``SUBMIT_OUTCOME_POLICY`` (LRN-F06), ``hint_requested_count`` replaces the
event-count query, diagnosis events of an outcome follow its presentation events, a problem code of a problem without published steps is
refused before it can resume a session, and abandoned attempts get ``current_mode = ABANDONED`` (TUT-S03).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import os
import uuid
from collections.abc import Callable
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter

from mathbank_rest.config import settings
from mathbank_rest.models import base
from mathbank_rest.models.base import UtcDateTime
from mathbank_rest.models.manual.learner_idem import LearnerIdem
from mathbank_rest.models.manual.learner_solve import (
    OPEN_SOLVE_SHARDS,
    LearnerEvent,
    LearnerProblem,
    LearnerSolve,
    LearnerSolveOwner,
    LearnerStepstate,
    event_sk,
    open_solve_keys,
    owner_pk,
    problem_sk,
    skill_keys,
    solve_sk,
    solves_keys,
    step_sk,
)
from mathbank_rest.step_logic import (
    DONE_STATES,
    HELP_LEVELS,
    INTERNAL_ACTORS,
    MAX_HELP_LEVEL,
    IdempotencyKeyReused,
    InvalidTransition,
    NotFound,
    StateVersionConflict,
    attempt_is_correct,
    build_runtime_view,
    check_version,
    next_step,
    outcome_transition,
    public,
    require_current_step,
    returned_from_detour,
    steps_from_dag,
    student_event_payload,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores import errors as store_errors
from mathbank_rest.stores.errors import ConditionFailed, StoreError, ValidationFailed
from mathbank_rest.stores.learner import hooks
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork, run_idempotent, with_retries

CTX = "learner"
LOG = logging.getLogger("mathbank_rest.stores.learner.solve")
MAX_EVENTS = 500
_TS = TypeAdapter(UtcDateTime)


# ---------------------------------------------------------------------------------------------- postgres

def _engine():
    from mathbank_rest.db.postgres import engine

    return engine


def _sr():
    from mathbank_rest import step_runtime

    return step_runtime


class SolvePostgres:
    """Postgres backend: calls ``step_runtime`` at call time (monkeypatched tests keep working, behaviour unchanged)."""

    def start_attempt(self, student_id, problem_ref, idempotency_key: str | None = None) -> dict:
        sr = _sr()
        with _engine().begin() as conn:
            problem_id = sr.resolve_problem(conn, str(problem_ref))
            started = sr.start_attempt(conn, student_id, problem_id, idempotency_key)
            return {**started, "runtime": sr.get_runtime(conn, started["solve_attempt_id"], student_id)}

    def submit_step_response(self, student_id, attempt_id, step_id: str, response_text: str, state_version: int,
                             idempotency_key: str | None = None) -> dict:
        with _engine().begin() as conn:
            return _sr().submit_step_response(conn, student_id, attempt_id, step_id, response_text, state_version, idempotency_key)

    def request_hint(self, student_id, attempt_id, step_id: str, state_version: int, idempotency_key: str | None = None) -> dict:
        with _engine().begin() as conn:
            return _sr().request_hint(conn, student_id, attempt_id, step_id, state_version, idempotency_key)

    def record_hint_presented(self, student_id, attempt_id, step_id: str, level: int, hint_source: str | None) -> None:
        with _engine().begin() as conn:
            _sr().record_hint_presented(conn, student_id, attempt_id, step_id, level, hint_source)

    def record_step_outcome(self, attempt_id, step_id: str, result: str, state_version: int, *, actor: str = "TUTOR",
                            evaluation: dict | None = None, idempotency_key: str | None = None) -> dict:
        with _engine().begin() as conn:
            out = _sr().record_step_outcome(conn, attempt_id, step_id, result, state_version, actor=actor,
                                            evaluation=evaluation, idempotency_key=idempotency_key)
        if out.get("attempt_completed") and not out.get("replayed"):  # after the commit, like the router did
            from mathbank_rest import mastery

            out["updated_mastery"] = mastery.recompute_mastery_for_problem(UUID(out["student_id"]), UUID(out["problem_id"]))
        return out

    def submit_attempt(self, student_id, attempt_id, state_version: int, idempotency_key: str | None = None) -> dict:
        with _engine().begin() as conn:
            return _sr().submit_attempt(conn, student_id, attempt_id, state_version, idempotency_key)

    def abandon_stale_attempts(self, idle_days: int = 30, limit: int = 500) -> list[str]:
        with _engine().begin() as conn:
            return _sr().abandon_stale_attempts(conn, idle_days, limit)

    def get_attempt_runtime(self, attempt_id, student_id=None) -> dict:
        with _engine().begin() as conn:
            return _sr().get_runtime(conn, attempt_id, student_id)

    def get_attempt_owner(self, attempt_id) -> dict | None:
        with _engine().connect() as conn:
            return _sr().attempt_owner(conn, attempt_id)

    def list_solve_attempts(self, student_id, status: str | None = None, *, limit: int = 50, next_token: str | None = None) -> dict:
        limit = min(max(limit, 1), 200)
        offset = ddb.verify_token(next_token, s=str(student_id), st=status or "")["o"] if next_token else 0
        with _engine().connect() as conn:
            rows = _sr().list_solve_attempts(conn, student_id, status, limit=limit + 1, offset=offset)
        token = ddb.sign_token({"s": str(student_id), "st": status or "", "o": offset + limit}) if len(rows) > limit else None
        return {"items": rows[:limit], "limit": limit, "next_token": token}

    def list_events(self, student_id, *, attempt_id=None, limit: int = 100, student_view: bool = False) -> list[dict]:
        """Full payload, as today: the allow-listed learner projection (LRN-F01) is a DynamoDB-side behaviour change."""
        with _engine().begin() as conn:
            return _sr().list_events(conn, student_id, attempt_id=attempt_id, limit=limit)

    def list_events_page(self, student_id, *, attempt_id=None, limit: int = 100, next_token: str | None = None,
                         student_view: bool = False) -> dict:
        with _engine().connect() as conn:
            rows, token = _sr().list_events_page(conn, student_id, attempt_id=attempt_id, limit=limit, cursor=next_token)
        return {"items": rows, "limit": min(max(limit, 1), MAX_EVENTS), "next_token": token}

    def get_events_after(self, student_id, after: str, *, attempt_id=None, limit: int = 100, next_token: str | None = None,
                         student_view: bool = False) -> dict:
        with _engine().connect() as conn:
            rows, token = _sr().list_events_page(conn, student_id, attempt_id=attempt_id, limit=limit,
                                                 after=_iso_param(after), cursor=next_token)
        return {"items": rows, "limit": min(max(limit, 1), MAX_EVENTS), "next_token": token}

    def get_step_tutor_state(self, attempt_id, step_id: str, *, student_id=None, conn=None) -> dict:
        from sqlalchemy import text

        sql = text("SELECT last_response_text, coalesce(help_level_used, 0) AS help FROM learner.attempt_step_state "
                   " WHERE solve_attempt_id = CAST(:a AS uuid) AND solution_step_id = :s")
        params = {"a": str(attempt_id), "s": step_id}
        if conn is not None:
            return dict(conn.execute(sql, params).mappings().first() or {"last_response_text": None, "help": 0})
        with _engine().connect() as c:
            return dict(c.execute(sql, params).mappings().first() or {"last_response_text": None, "help": 0})


# ---------------------------------------------------------------------------------------------- helpers

def _iso(t: dt.datetime) -> str:
    return ddb.encode(t)


def _iso_param(value: str) -> str:
    """An ``after`` cursor (any ISO-8601 instant) as the canonical event-time text; invalid values are a 422."""
    try:
        return _iso(_TS.validate_python(value))
    except Exception:  # noqa: BLE001
        raise ValidationFailed("after must be an ISO-8601 timestamp", after=value) from None


class _Clock:
    """Strictly increasing microsecond instants inside one operation, so its events keep their causal order."""

    def __init__(self) -> None:
        self._last: dt.datetime | None = None

    def now(self) -> dt.datetime:
        t = dt.datetime.now(dt.UTC)
        if self._last is not None and t <= self._last:
            t = self._last + dt.timedelta(microseconds=1)
        self._last = t
        return t


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _submit_outcome_policy() -> str:
    """``false`` (default: the hand-in is a failed outcome), ``null`` (an ungraded outcome, no mastery) or ``off`` (none, as PostgreSQL)."""
    value = str(getattr(settings, "submit_outcome_policy", "") or os.getenv("SUBMIT_OUTCOME_POLICY") or "false").strip().lower()
    return value if value in ("false", "null", "off") else "false"


def _assert_distinct(ops: list[ddb.TxOp]) -> None:
    """DynamoDB rejects a transaction with two operations on one item; fail loudly (and under moto too) before the call."""
    seen: set[tuple[str, str, str]] = set()
    for op in ops:
        key = (op.ctx, op.pk or (op.item or {}).get("PK", ""), op.sk or (op.item or {}).get("SK", ""))
        if key in seen:
            raise StoreError(f"transaction has two operations on {key[1]} {key[2]}", pk=key[1], sk=key[2])
        seen.add(key)


class SolveDynamoDB:
    """DynamoDB backend over mb-learner."""

    # ------------------------------------------------------------------------------------------ plumbing

    @staticmethod
    def _content():
        from mathbank_rest import stores

        return stores.get_store("content")

    @staticmethod
    def _pk(student_id: Any) -> str:
        return ddb.student_pk(student_id)

    def _run(self, sid: str, key: str | None, operation: str, body: dict, build: Callable[[LearnerUnitOfWork], Any]) -> tuple[Any, bool]:
        """One transaction with the idempotency receipt in it; a reused key is the runtime's 422. When a concurrent duplicate of the
        same request wins the race, this request's own guards fail first (the version moved): its receipt is then the answer.

        The receipt keeps the response as JSON text (``{"json": ...}``): DynamoDB items drop ``null`` members, and a replay must
        return exactly what the first request returned (``hint_text: null``, ``current_step_id: null`` ...)."""
        def checked(uow: LearnerUnitOfWork) -> Any:
            out = build(uow)
            _assert_distinct(uow.ops())
            return {"json": json.dumps(public(out))}

        try:
            stored, replayed = run_idempotent(sid, key=key, operation=operation, body=body, build=checked)
        except store_errors.IdempotencyKeyReused:
            raise IdempotencyKeyReused("Idempotency-Key was already used for a different request") from None
        except (StateVersionConflict, ConditionFailed):
            winner = typed.get(LearnerIdem, self._pk(sid), f"IDEM#{key}") if key else None
            if winner is None or (winner.ttl or 1 << 62) <= dt.datetime.now(dt.UTC).timestamp():
                raise
            if winner.request_hash != ddb.request_hash({"operation": operation, "body": body}):
                raise IdempotencyKeyReused("Idempotency-Key was already used for a different request") from None
            stored, replayed = winner.resolve("response"), True
        return json.loads(stored["json"]), replayed

    def _load_solve(self, sid: str, attempt_id: str) -> LearnerSolve:
        solve = typed.get(LearnerSolve, self._pk(sid), solve_sk(attempt_id))
        if solve is None:
            raise NotFound("attempt not found")
        return solve

    def _load_steps(self, sid: str, attempt_id: str) -> dict[str, LearnerStepstate]:
        out: dict[str, LearnerStepstate] = {}
        token = None
        while True:
            page = typed.query(LearnerStepstate, self._pk(sid), sk_begins=f"{solve_sk(attempt_id)}#STEP#", limit=200, next_token=token)
            out |= {s.solution_step_id: s for s in page.items}
            token = page.next_token
            if not token:
                return out

    def _owner(self, attempt_id: str) -> LearnerSolveOwner:
        owner = typed.get(LearnerSolveOwner, owner_pk(attempt_id), "OWNER")
        if owner is None:
            raise NotFound("attempt not found")
        return owner

    def _guard(self, sid: str, attempt_id: str, step_id: str, state_version: int) -> tuple[LearnerSolve, LearnerStepstate]:
        """The aggregate guards of T9/T10/T12: version (409), IN_PROGRESS / not RECOVERY / current step (409)."""
        solve = self._load_solve(sid, attempt_id)
        check_version(solve.state_version, state_version)
        require_current_step(solve.status, solve.current_mode, solve.current_solution_step_id, step_id)
        step = typed.get(LearnerStepstate, self._pk(sid), step_sk(attempt_id, step_id))
        if step is None:
            raise InvalidTransition("step has not been presented yet")
        return solve, step

    def _event(self, uow: LearnerUnitOfWork, clock: _Clock, sid: str, attempt_id: str | None, event_type: str, actor: str, *,
               step_id: str | None = None, payload: dict | None = None, key: str | None = None) -> str:
        event_id = ddb.uuid7()
        stamp = _iso(clock.now())
        sk = event_sk(stamp, event_id)
        uow.put_new(LearnerEvent(
            PK=self._pk(sid), SK=sk, student_id=sid, event_id=event_id, event_time=stamp, event_type=event_type, actor_type=actor,
            payload=public(payload or {}), solve_attempt_id=attempt_id, solution_step_id=step_id, idempotency_key=key,
            **({"GSI1PK": f"SOLVE#{attempt_id}", "GSI1SK": sk} if attempt_id else {})))
        return event_id

    def _new_step(self, sid: str, solve_id: str, problem_id: str, step_ref: Any, row: dict, now: dt.datetime) -> LearnerStepstate:
        skill = row.get("skill_node_id")
        return LearnerStepstate(
            PK=self._pk(sid), SK=step_sk(solve_id, step_ref.solution_step_id), student_id=sid, solve_attempt_id=solve_id,
            problem_id=problem_id, solution_step_id=step_ref.solution_step_id, state="PRESENTED", first_seen_at=now,
            last_updated_at=now, attempt_count=0, help_level_used=0, returned_to_step_count=0, returned_to_problem_count=0,
            skill_node_id=skill, subconcept_node_id=row.get("subconcept_node_id"), version=1,
            **skill_keys(sid, skill, _iso(now), solve_id, step_ref.solution_step_id))

    def _update_step(self, uow: LearnerUnitOfWork, step: LearnerStepstate, now: dt.datetime, changes: dict, *,
                     increment: dict[str, int] | None = None) -> None:
        """Guarded STEPSTATE update (``last_updated_at`` and the GSI2 skill-history key move together); ``None`` removes the attribute."""
        changes = {**changes, "last_updated_at": now}
        if step.skill_node_id:
            changes["GSI2SK"] = f"{_iso(now)}#{step.solve_attempt_id}#{step.solution_step_id}"
        offloaded = tuple(f"{a}_ref" for a in ("last_response_text", "last_evaluation") if a in changes and step.ref(a) is not None)
        nulls = tuple(k for k, v in changes.items() if v is None)
        uow.update(LearnerStepstate, step.PK, step.SK, {k: v for k, v in changes.items() if v is not None},
                   expected={"version": step.version} if step.version is not None else None, increment=increment,
                   remove=offloaded + nulls, conflict=StateVersionConflict("the step changed; refetch the runtime"))

    def _update_solve(self, uow: LearnerUnitOfWork, solve: LearnerSolve, now: dt.datetime, changes: dict | None = None, *,
                      increment: dict[str, int] | None = None, remove: tuple[str, ...] = (), open_session: bool = True) -> None:
        """Guarded SOLVE update: ``state_version = :seen`` and the learner-action guards of T9/T10/T12 (409 on a race)."""
        changes = {"last_activity_at": now, **(changes or {})}
        if open_session:
            changes["GSI1SK"] = f"{_iso(now)}#{solve.solve_attempt_id}"
        nulls = tuple(k for k, v in changes.items() if v is None)
        uow.update(
            LearnerSolve, solve.PK, solve.SK, {k: v for k, v in changes.items() if v is not None},
            expected={"version": solve.version, "status": "IN_PROGRESS"}, increment=increment, remove=tuple(remove) + nulls,
            cond=ddb.Cond("#cm <> :recovery", {"#cm": "current_mode"}, {":recovery": "RECOVERY"}),
            conflict=StateVersionConflict(f"state_version {solve.state_version} is stale. Refetch the runtime."))

    def _close_problem_cursor(self, uow: LearnerUnitOfWork, sid: str, solve: LearnerSolve, now: dt.datetime, *,
                              count_outcome: bool) -> None:
        """PROBLEM cursor of a finished attempt when no OutcomeStore stages it: drop the open-session marker and, when an OUTCOME is
        written, ``outcome_count + 1`` (one operation on the item: DynamoDB allows one per item per transaction)."""
        pk, sk = self._pk(sid), problem_sk(solve.problem_id)
        cursor = typed.get(LearnerProblem, pk, sk)
        aid = str(solve.solve_attempt_id)
        stale = ConditionFailed("problem cursor changed; retry")
        if cursor is None:
            if count_outcome:
                uow.put(LearnerProblem(PK=pk, SK=sk, student_id=sid, problem_id=solve.problem_id, attempt_seq=solve.attempt_number,
                                       first_attempted_at=now, outcome_count=1), cond=ddb.NOT_EXISTS, conflict=stale)
            return
        owns_marker = cursor.open_solve_attempt_id is not None and str(cursor.open_solve_attempt_id) == aid
        if not owns_marker and not count_outcome:
            return
        uow.update(LearnerProblem, pk, sk, {}, expected={"open_solve_attempt_id": aid} if owns_marker else None,
                   increment={"outcome_count": 1} if count_outcome else None,
                   remove=("open_solve_attempt_id",) if owns_marker else (), conflict=stale)

    def _merge_open_marker_removal(self, uow: LearnerUnitOfWork, sid: str, solve: LearnerSolve) -> None:
        """The OutcomeStore stages ``PROBLEM#<pid>`` itself (``outcome_count + 1``); the open-session marker is removed in that very
        operation, guarded by the attempt id, since a transaction may not touch an item twice."""
        pk, sk, aid = self._pk(sid), problem_sk(solve.problem_id), str(solve.solve_attempt_id)
        cursor = typed.get(LearnerProblem, pk, sk)
        if cursor is None or cursor.open_solve_attempt_id is None or str(cursor.open_solve_attempt_id) != aid:
            return
        for op in uow.ops():
            if op.kind == "update" and op.pk == pk and op.sk == sk:
                op.update = f"{op.update} REMOVE #osa"
                op.names = {**op.names, "#osa": "open_solve_attempt_id"}
                op.cond = ddb.Cond("#osa = :osa", {"#osa": "open_solve_attempt_id"}, {":osa": aid})
                op.conflict = ConditionFailed("problem cursor changed; retry")
                return
        raise StoreError("the outcome builder did not stage the problem cursor; the open session would stay open", sk=sk)

    def _record_outcome_ops(self, uow: LearnerUnitOfWork, sid: str, solve: LearnerSolve, now: dt.datetime, *,
                            is_correct: bool | None, hint_count: int, post_commit: list[Callable[[], None]]) -> dict:
        """The OUTCOME of a finished attempt; with an OutcomeStore (``stage_outcome``) also its evidence, mastery and the PROBLEM
        counters, in this transaction. What did not fit (``mastery_pending``) is queued in ``post_commit``."""
        outcome_id = str(uuid.uuid4())
        spent = max(0, int((now - solve.started_at).total_seconds()))
        aid, pid = str(solve.solve_attempt_id), str(solve.problem_id)
        stage = getattr(self, "stage_outcome", None)
        if stage is not None:
            content = self._content()
            problem = content.get_problem_by_id(pid) or {}
            tags = content.get_problem_tags(problem_id=pid) if problem else {"concept_ids": [], "technique_ids": []}
            staged = stage(uow, problem_id=UUID(pid), attempt_id=UUID(outcome_id), attempted_at=now, is_correct=is_correct,
                           submitted_answer=None, time_spent_seconds=spent, hint_count=hint_count, source="step_runtime",
                           difficulty_band=problem.get("difficulty_band"), tags=tags, solve_attempt_id=UUID(aid))
            self._merge_open_marker_removal(uow, sid, solve)
            finish = getattr(self, "finish_deferred_mastery", None)
            if finish is not None and staged.deferred:
                post_commit.append(lambda: finish(sid, staged))
            return {"attempt_id": outcome_id, "updated_mastery": staged.updated_mastery}
        model = base.model_for(CTX, "OUTCOME")
        fields: dict[str, Any] = {
            "PK": self._pk(sid), "SK": f"OUTCOME#{_iso(now)}#{outcome_id}", "student_id": sid, "attempt_id": outcome_id,
            "problem_id": pid, "is_correct": is_correct, "hint_count": hint_count, "time_spent_seconds": spent,
            "attempted_at": now, "source": "step_runtime", "solve_attempt_id": aid}
        legacy = model.model_fields.get("legacy_source")
        if legacy is not None and legacy.is_required():
            fields["legacy_source"] = "step_runtime"
        uow.put_new(model(**fields))
        self._close_problem_cursor(uow, sid, solve, now, count_outcome=True)
        return {"attempt_id": outcome_id, "updated_mastery": None}

    # ------------------------------------------------------------------------------------------ T8 start

    def _resolve_problem(self, ref: str) -> tuple[str, dict]:
        """(problem uuid, published solution DAG) of a uuid or canonical code, through the content store."""
        content = self._content()
        if _is_uuid(ref):
            problem_id = str(UUID(ref))
            if content.get_problem_by_id(problem_id) is None:
                raise NotFound("problem not found")
            return problem_id, content.get_solution_dag(problem_id=problem_id)
        if not content.get_problems_by_codes([ref]):
            raise NotFound("problem not found")
        dag = content.get_solution_dag(problem_code=ref)
        if not dag.get("problem_id"):
            raise InvalidTransition("problem has no published solution steps for the step runtime")
        return str(dag["problem_id"]), dag

    def start_attempt(self, student_id, problem_ref, idempotency_key: str | None = None) -> dict:
        """Start (or resume) the learner's open solving session for a problem (uuid or canonical code); returns the runtime view."""
        sid = str(student_id)
        problem_id, dag = self._resolve_problem(str(problem_ref))
        body = {"problem_id": problem_id}

        def attempt() -> tuple[dict, bool]:
            def build(uow: LearnerUnitOfWork) -> dict:
                clock, pk, psk = _Clock(), self._pk(sid), problem_sk(problem_id)
                cursor = typed.get(LearnerProblem, pk, psk)
                if cursor is not None and cursor.open_solve_attempt_id is not None:
                    aid = str(cursor.open_solve_attempt_id)
                    uow.add(ddb.Check(CTX, pk, psk, ddb.Cond("#o = :o", {"#o": "open_solve_attempt_id"}, {":o": aid}),
                                      ConditionFailed("the open session changed; retry"), label="problem cursor"))
                    self._event(uow, clock, sid, aid, "PROBLEM_VIEWED", "STUDENT", payload={"resumed": True})
                    return {"solve_attempt_id": aid, "resumed": True}
                steps, prereqs = steps_from_dag(dag)
                if not steps:
                    raise InvalidTransition("problem has no published solution steps for the step runtime")
                first = next_step(steps, {}, prereqs)
                n = ((cursor.attempt_seq or 0) if cursor is not None else 0) + 1
                aid, now = str(uuid.uuid4()), clock.now()
                stale = ConditionFailed("the problem cursor changed; retry")
                if cursor is None:
                    uow.put(LearnerProblem(PK=pk, SK=psk, student_id=sid, problem_id=problem_id, attempt_seq=n,
                                           open_solve_attempt_id=aid, first_attempted_at=now, outcome_count=0),
                            cond=ddb.NOT_EXISTS, conflict=stale)
                else:
                    uow.update(LearnerProblem, pk, psk, {"attempt_seq": n, "open_solve_attempt_id": aid},
                               cond=ddb.Cond("attribute_not_exists(#oa) AND (attribute_not_exists(#sq) OR #sq = :prev)",
                                             {"#oa": "open_solve_attempt_id", "#sq": "attempt_seq"}, {":prev": n - 1}), conflict=stale)
                stamp = _iso(now)
                uow.put_new(LearnerSolve(
                    PK=pk, SK=solve_sk(aid), student_id=sid, solve_attempt_id=aid, problem_id=problem_id, attempt_number=n,
                    status="IN_PROGRESS", current_mode="SOLVING", current_solution_part_id=first.solution_part_id,
                    current_solution_step_id=first.solution_step_id, hint_requested_count=0, plan_ids=[], started_at=now,
                    last_activity_at=now, updated_at=now, version=2, **open_solve_keys(aid, stamp), **solves_keys(sid, aid, stamp)))
                uow.put_new(LearnerSolveOwner(PK=owner_pk(aid), SK="OWNER", student_id=sid, problem_id=problem_id))
                row = {s["solution_step_id"]: s for s in dag["steps"]}.get(first.solution_step_id) or {}
                uow.put_new(self._new_step(sid, aid, problem_id, first, row, now))
                self._event(uow, clock, sid, aid, "ATTEMPT_STARTED", "STUDENT", payload=body, key=idempotency_key)
                self._event(uow, clock, sid, aid, "PROBLEM_VIEWED", "STUDENT", payload={"resumed": False})
                self._event(uow, clock, sid, aid, "STEP_PRESENTED", "SYSTEM", step_id=first.solution_step_id)
                return {"solve_attempt_id": aid, "resumed": False}

            return self._run(sid, idempotency_key, "start_attempt", body, build)

        response, replayed = with_retries(attempt)
        return {**response, "replayed": replayed, "runtime": self.get_attempt_runtime(response["solve_attempt_id"], sid)}

    # ------------------------------------------------------------------------------------------ T9 / T10 / T11

    def submit_step_response(self, student_id, attempt_id, step_id: str, response_text: str, state_version: int,
                             idempotency_key: str | None = None) -> dict:
        """Persist a learner's response for the current step. Evaluation is a separate call."""
        sid, aid = str(student_id), str(attempt_id)
        body = {"attempt_id": aid, "step_id": step_id, "response_text": response_text, "state_version": state_version}

        def build(uow: LearnerUnitOfWork) -> dict:
            solve, step = self._guard(sid, aid, step_id, state_version)
            clock = _Clock()
            self._update_step(uow, step, clock.now(), {"state": "ATTEMPTED", "last_response_text": response_text,
                                                      "first_attempted_at": step.first_attempted_at or clock.now()},
                              increment={"attempt_count": 1})
            event_id = self._event(uow, clock, sid, aid, "STEP_RESPONSE_SUBMITTED", "STUDENT", step_id=step_id,
                                   payload={"response": response_text}, key=idempotency_key)
            self._update_solve(uow, solve, clock.now())
            return {"event_id": event_id, "state": "ATTEMPTED", "evaluation_status": "PENDING",
                    "state_version": solve.state_version + 1}

        response, replayed = self._run(sid, idempotency_key, "step_response", body, build)
        return {**response, "replayed": replayed}

    def request_hint(self, student_id, attempt_id, step_id: str, state_version: int, idempotency_key: str | None = None) -> dict:
        """Escalate help by one level (max 5); ``hint_requested_count`` replaces the event-count query. The hint text is attached by the caller."""
        sid, aid = str(student_id), str(attempt_id)
        body = {"attempt_id": aid, "step_id": step_id, "state_version": state_version}

        def build(uow: LearnerUnitOfWork) -> dict:
            solve, step = self._guard(sid, aid, step_id, state_version)
            clock = _Clock()
            level = min(step.help_level_used + 1, MAX_HELP_LEVEL)
            self._update_step(uow, step, clock.now(), {"help_level_used": level})
            self._event(uow, clock, sid, aid, "HINT_REQUESTED", "STUDENT", step_id=step_id,
                        payload={"help_level": level, "help_kind": HELP_LEVELS[level]}, key=idempotency_key)
            self._update_solve(uow, solve, clock.now(), increment={"hint_requested_count": 1})
            return {"help_level": level, "help_kind": HELP_LEVELS[level], "hint_text": None, "state_version": solve.state_version + 1}

        response, replayed = self._run(sid, idempotency_key, "hint", body, build)
        return {**response, "replayed": replayed}

    def record_hint_presented(self, student_id, attempt_id, step_id: str, level: int, hint_source: str | None) -> None:
        """HINT_PRESENTED: the hint text reached the learner (HINT_REQUESTED is the escalation)."""
        sid = str(student_id)
        uow = LearnerUnitOfWork(sid)
        self._event(uow, _Clock(), sid, str(attempt_id), "HINT_PRESENTED", "TUTOR", step_id=step_id,
                    payload={"help_level": level, "help_kind": HELP_LEVELS.get(level), "hint_source": hint_source})
        uow.commit()

    # ------------------------------------------------------------------------------------------ T12 outcome

    def record_step_outcome(self, attempt_id, step_id: str, result: str, state_version: int, *, actor: str = "TUTOR",
                            evaluation: dict | None = None, idempotency_key: str | None = None) -> dict:
        """Apply an evaluated outcome (evaluator/agent, never the learner) and advance; the owner is resolved through SOLVE#<id>/OWNER."""
        if actor not in INTERNAL_ACTORS:
            raise InvalidTransition("step outcomes are recorded by the tutor/evaluator, not the student")
        aid = str(attempt_id)
        sid = str(self._owner(aid).student_id)
        body = {"attempt_id": aid, "step_id": step_id, "result": result, "state_version": state_version,
                "evaluation": evaluation or {}}
        extras: dict[str, Any] = {}

        def attempt() -> tuple[dict, bool]:
            extras.clear()
            extras["post"] = []
            return self._run(sid, idempotency_key, "step_outcome", body,
                             lambda uow: self._outcome(uow, sid, aid, step_id, result, state_version, actor, evaluation,
                                                       idempotency_key, extras))

        response, replayed = with_retries(attempt)
        out = {**response, "replayed": replayed}
        if not replayed:
            self._after_commit(extras["post"])
            if extras.get("updated_mastery") is not None:
                out["updated_mastery"] = extras["updated_mastery"]
        return out

    @staticmethod
    def _after_commit(callbacks: list[Callable[[], None]]) -> None:
        """Work that did not fit in the transaction (deferred mastery): never allowed to lose the committed outcome."""
        for callback in callbacks:
            try:
                callback()
            except Exception:
                LOG.exception("post-commit step of a solve operation failed; the mastery-repair consumer converges it")

    def _outcome(self, uow: LearnerUnitOfWork, sid: str, aid: str, step_id: str, result: str, state_version: int, actor: str,
                 evaluation: dict | None, key: str | None, extras: dict) -> dict:
        solve, cur = self._guard(sid, aid, step_id, state_version)
        steps_state = self._load_steps(sid, aid)
        dag = self._content().get_solution_dag(problem_id=str(solve.problem_id))
        steps, prereqs = steps_from_dag(dag)
        by_id = {s["solution_step_id"]: s for s in dag["steps"]}
        clock = _Clock()
        now = clock.now()
        new_state, event_type, independent = outcome_transition(result, cur.help_level_used)
        states = {k: v.state for k, v in steps_state.items()} | {step_id: new_state}
        upcoming = next_step(steps, states, prereqs)
        completed = upcoming is None
        returned = new_state in DONE_STATES and returned_from_detour(cur.returned_to_step_count, cur.returned_to_problem_count)

        self._event(uow, clock, sid, aid, "STEP_EVALUATED", actor, step_id=step_id,
                    payload={"result": result, "evaluation": evaluation or {}}, key=key)
        self._event(uow, clock, sid, aid, event_type, actor, step_id=step_id, payload={"help_level_used": cur.help_level_used})
        if returned:
            self._event(uow, clock, sid, aid, "RETURNED_TO_ORIGINAL_PROBLEM", "SYSTEM", step_id=step_id,
                        payload={"next_step_id": upcoming.solution_step_id if upcoming else None})

        # the current step, merged with its own re-presentation when it fails and stays current (FAILED -> RETRY_PRESENTED)
        retry = upcoming is not None and upcoming.solution_step_id == step_id and new_state == "FAILED"
        changes: dict[str, Any] = {"state": "RETRY_PRESENTED" if retry else new_state, "independent_success": independent,
                                   "last_evaluation": {"result": result, **(evaluation or {})}}
        self._update_step(uow, cur, now, changes, increment={"returned_to_problem_count": 1} if returned else None)
        step_after = cur.model_copy(update={**changes, "returned_to_problem_count": cur.returned_to_problem_count + int(returned)})
        if upcoming is not None and upcoming.solution_step_id != step_id:
            nxt = steps_state.get(upcoming.solution_step_id)
            if nxt is None:
                uow.put_new(self._new_step(sid, aid, str(solve.problem_id), upcoming, by_id.get(upcoming.solution_step_id) or {}, now))
            else:
                self._update_step(uow, nxt, now, {"state": "RETRY_PRESENTED" if nxt.state == "FAILED" else nxt.state})
        if upcoming is not None:
            self._event(uow, clock, sid, aid, "STEP_PRESENTED", "SYSTEM", step_id=upcoming.solution_step_id)

        version = solve.state_version + 1
        outcome = None
        solve_changes: dict[str, Any] = {"current_solution_part_id": upcoming.solution_part_id if upcoming else None,
                                         "current_solution_step_id": upcoming.solution_step_id if upcoming else None}
        removes: tuple[str, ...] = ()
        if completed:
            is_correct = attempt_is_correct(states)
            hints = solve.hint_requested_count
            built = self._record_outcome_ops(uow, sid, solve, now, is_correct=is_correct, hint_count=hints,
                                             post_commit=extras["post"])
            outcome = {"attempt_id": built["attempt_id"], "is_correct": is_correct, "hint_count": hints}
            extras["updated_mastery"] = built.get("updated_mastery")
            self._event(uow, clock, sid, aid, "ATTEMPT_COMPLETED", "SYSTEM",
                        payload={"is_correct": is_correct, "hint_count": hints, "outcome_attempt_id": built["attempt_id"]})
            solve_changes |= {"status": "COMPLETED", "current_mode": "COMPLETED", "completed_at": now,
                              "submitted_at": solve.submitted_at or now, "outcome_attempt_id": built["attempt_id"]}
            removes = ("GSI1PK", "GSI1SK")
        self._update_solve(uow, solve, clock.now(), solve_changes, remove=removes, open_session=not completed)

        out: dict[str, Any] = {}
        hooks.run_auto_diagnose(uow, {"student_id": sid, "attempt_id": aid, "solution_step_id": step_id,
                                      "solve": solve.model_copy(update={**solve_changes, "version": version}),
                                      "step_state": step_after, "outcome": result, "actor": actor, "out": out})
        return {"state": new_state, "independent_success": independent,
                "current_step_id": upcoming.solution_step_id if upcoming else None, "attempt_completed": completed,
                "outcome_attempt": outcome, "state_version": version, "student_id": sid, "problem_id": str(solve.problem_id),
                "gap_status_changes": public(out.get("gap_status_changes") or []), "diagnosis": public(out.get("diagnosis"))}

    # ------------------------------------------------------------------------------------------ T14 early submit

    def submit_attempt(self, student_id, attempt_id, state_version: int, idempotency_key: str | None = None) -> dict:
        """The learner hands in the attempt early; remaining steps stay as they are. An outcome follows ``SUBMIT_OUTCOME_POLICY``."""
        sid, aid = str(student_id), str(attempt_id)
        body = {"attempt_id": aid, "state_version": state_version}

        def build(uow: LearnerUnitOfWork) -> dict:
            solve = self._load_solve(sid, aid)
            check_version(solve.state_version, state_version)
            if solve.status != "IN_PROGRESS":
                raise InvalidTransition(f"attempt is {solve.status}")
            if solve.current_mode == "RECOVERY":
                raise InvalidTransition("leave the recovery detour before handing in the attempt")
            clock = _Clock()
            now = clock.now()
            policy = _submit_outcome_policy()
            changes: dict[str, Any] = {"status": "SUBMITTED", "current_mode": "REVIEW", "submitted_at": now}
            if policy != "off":
                built = self._record_outcome_ops(uow, sid, solve, now, is_correct=False if policy == "false" else None,
                                                 hint_count=solve.hint_requested_count, post_commit=post)
                changes["outcome_attempt_id"] = built["attempt_id"]
            else:
                self._close_problem_cursor(uow, sid, solve, now, count_outcome=False)
            self._event(uow, clock, sid, aid, "ATTEMPT_SUBMITTED", "STUDENT", key=idempotency_key)
            self._update_solve(uow, solve, clock.now(), changes, remove=("GSI1PK", "GSI1SK"), open_session=False)
            return {"status": "SUBMITTED", "state_version": solve.state_version + 1}

        def attempt() -> tuple[dict, bool]:
            post.clear()
            return self._run(sid, idempotency_key, "submit_attempt", body, build)

        post: list[Callable[[], None]] = []
        response, replayed = with_retries(attempt)
        if not replayed:
            self._after_commit(post)
        return {**response, "replayed": replayed}

    # ------------------------------------------------------------------------------------------ T15 stale sessions

    def abandon_stale_attempts(self, idle_days: int = 30, limit: int = 500) -> list[str]:
        """Mark IN_PROGRESS attempts idle for ``idle_days`` ABANDONED: open-solve GSI1 shards below the cutoff, then a CAS per attempt."""
        cutoff = _iso(dt.datetime.now(dt.UTC) - dt.timedelta(days=idle_days))
        done: list[str] = []
        for shard in range(OPEN_SOLVE_SHARDS):
            token = None
            while len(done) < limit:
                page = typed.query(LearnerSolve, f"OPEN_SOLVE#{shard}", index="GSI1", sk_between=("0", cutoff),
                                   limit=min(200, limit - len(done)), next_token=token)
                for solve in page.items:
                    if len(done) < limit and self._abandon(solve, idle_days):
                        done.append(str(solve.solve_attempt_id))
                token = page.next_token
                if not token:
                    break
        return done

    def _abandon(self, solve: LearnerSolve, idle_days: int) -> bool:
        sid, aid = str(solve.student_id), str(solve.solve_attempt_id)
        uow = LearnerUnitOfWork(sid)
        clock = _Clock()
        uow.update(LearnerSolve, solve.PK, solve.SK, {"status": "ABANDONED", "current_mode": "ABANDONED"},
                   expected={"status": "IN_PROGRESS", "version": solve.version}, remove=("GSI1PK", "GSI1SK"),
                   conflict=ConditionFailed("the attempt moved"))
        self._close_problem_cursor(uow, sid, solve, clock.now(), count_outcome=False)
        aborter = getattr(self, "build_abort_plan_ops", None)
        if aborter is not None and solve.plan_ids:
            aborter(uow, student_id=sid, attempt_id=aid, plan_ids=[str(p) for p in solve.plan_ids], actor="SYSTEM",
                    reason="ATTEMPT_ABANDONED")
        self._event(uow, clock, sid, aid, "ATTEMPT_ABANDONED", "SYSTEM", payload={"idle_days": idle_days, "last_activity_at": _iso(solve.last_activity_at)})
        try:
            _assert_distinct(uow.ops())
            uow.commit()
        except ConditionFailed:  # the attempt moved (or another worker took it) between the query and the CAS: skip it
            return False
        return True

    # ------------------------------------------------------------------------------------------ reads

    def get_attempt_owner(self, attempt_id) -> dict | None:
        """A12: who owns an attempt, for admin routes that carry no learner token."""
        owner = typed.get(LearnerSolveOwner, owner_pk(attempt_id), "OWNER")
        return None if owner is None else {"student_id": owner.student_id, "problem_id": owner.problem_id}

    def get_attempt_runtime(self, attempt_id, student_id=None) -> dict:
        """A11: the learner-safe runtime view. ``student_id=None`` is the admin read (owner resolved through the OWNER pointer)."""
        aid = str(attempt_id)
        sid = str(student_id) if student_id is not None else str(self._owner(aid).student_id)
        solve = self._load_solve(sid, aid)
        content = self._content()
        dag = content.get_solution_dag(problem_id=str(solve.problem_id))
        code = dag.get("problem_code")
        problems = content.get_problems_by_codes([code]) if code else []
        attempt = {
            "solve_attempt_id": solve.solve_attempt_id, "student_id": solve.student_id, "problem_id": solve.problem_id,
            "attempt_number": solve.attempt_number, "status": solve.status, "started_at": solve.started_at,
            "submitted_at": solve.submitted_at, "completed_at": solve.completed_at,
            "current_solution_part_id": solve.current_solution_part_id, "current_solution_step_id": solve.current_solution_step_id,
            "recovery_plan_id": solve.recovery_plan_id, "current_recovery_plan_id": solve.current_recovery_plan_id,
            "state_version": solve.state_version, "current_mode": solve.current_mode, "problem_code": code,
            "statement_text": problems[0].get("statement_text") if problems else None}
        states = {step_id: {"state": s.state, "help_level_used": s.help_level_used, "attempt_count": s.attempt_count,
                            "last_response_text": s.resolve("last_response_text"), "last_evaluation": s.resolve("last_evaluation")}
                  for step_id, s in self._load_steps(sid, aid).items()}
        diagnosis = getattr(self, "get_step_diagnosis_view", None)
        return build_runtime_view(
            attempt, dag, states, step_lookup=lambda step_id: content.get_step_details([step_id]).get(step_id),
            diagnosis_for_step=lambda step_id: diagnosis(sid, aid, step_id) if diagnosis else None,
            recovery=self._recovery_summary(sid, solve))

    def _recovery_summary(self, sid: str, solve: LearnerSolve) -> dict | None:
        """The pointer of the runtime read model: the current recovery plan, if any."""
        if not solve.current_recovery_plan_id:
            return None
        plan = typed.get(base.model_for(CTX, "PLAN"), self._pk(sid), f"PLAN#{solve.current_recovery_plan_id}")
        return {"recovery_plan_id": str(solve.current_recovery_plan_id), "target_label": getattr(plan, "target_label", None),
                "status": getattr(plan, "status", None)}

    def get_step_tutor_state(self, attempt_id, step_id: str, *, student_id=None, conn=None) -> dict:
        """The learner's own state of a step for the evaluator and the hint writer: last response and help level."""
        aid = str(attempt_id)
        sid = str(student_id) if student_id is not None else str(self._owner(aid).student_id)
        step = typed.get(LearnerStepstate, self._pk(sid), step_sk(aid, step_id))
        if step is None:
            return {"last_response_text": None, "help": 0}
        return {"last_response_text": step.resolve("last_response_text"), "help": step.help_level_used}

    def list_solve_attempts(self, student_id, status: str | None = None, *, limit: int = 50, next_token: str | None = None) -> dict:
        """A13: the learner's solve sessions, newest first (GSI2 ``STUDENT#<sid>#SOLVES``), problem codes from the content store."""
        sid, limit = str(student_id), min(max(limit, 1), 200)
        items: list[LearnerSolve] = []
        token = next_token
        while len(items) < limit:
            # GSI2 projects only a subset of attributes (INCLUDE): read the keys there, then fetch the whole items by key
            page = ddb.query_page("learner", f"STUDENT#{sid}#SOLVES", index="GSI2", forward=False, limit=limit - len(items),
                                  next_token=token)
            keys = [(r["PK"], r["SK"]) for r in page["items"]]
            by_key = {(i.PK, i.SK): i for i in typed.batch_get(LearnerSolve, keys)}
            items += [s for k in keys if (s := by_key.get(k)) is not None and (status is None or s.status == status)]
            token = page["next_token"]
            if not token:
                break
        codes: dict[str, str | None] = {}
        for pid in {str(s.problem_id) for s in items}:
            problem = self._content().get_problem_by_id(pid)
            codes[pid] = problem["canonical_code"] if problem else None
        rows = [{"solve_attempt_id": s.solve_attempt_id, "problem_id": s.problem_id, "problem_code": codes[str(s.problem_id)],
                 "attempt_number": s.attempt_number, "status": s.status, "current_mode": s.current_mode,
                 "started_at": s.started_at, "submitted_at": s.submitted_at, "completed_at": s.completed_at,
                 "state_version": s.state_version} for s in items]
        return {"items": rows, "limit": limit, "next_token": token}

    # -- event feed (A16 learner, A17 admin)

    def _events(self, student_id, *, attempt_id, limit: int, forward: bool, after: str | None, next_token: str | None,
                student_view: bool) -> dict:
        sid, limit = str(student_id), min(max(limit, 1), MAX_EVENTS)
        pk = self._pk(sid)
        kw: dict[str, Any] = {"forward": forward}
        if attempt_id:
            kw["index"] = "GSI1"
        part = f"SOLVE#{attempt_id}" if attempt_id else pk
        if after is not None:
            kw["sk_between"] = (f"EVT#{_iso_param(after)}#~", "EVT#~")
        else:
            kw["sk_begins"] = "EVT#"
        rows: list[dict] = []
        token = next_token
        while len(rows) < limit:
            page = typed.query(LearnerEvent, part, limit=limit - len(rows), next_token=token, **kw)
            for ev in page.items:
                if ev.PK != pk:  # a foreign attempt id reads as an empty feed
                    continue
                payload = ev.resolve("payload") or {}
                rows.append({"event_id": ev.event_id, "solve_attempt_id": ev.solve_attempt_id, "event_type": ev.event_type,
                             "event_time": ev.event_time, "actor_type": ev.actor_type, "solution_step_id": ev.solution_step_id,
                             "payload": student_event_payload(ev.event_type, payload) if student_view else payload})
            token = page.next_token
            if not token:
                break
        return {"items": rows, "limit": limit, "next_token": token}

    def list_events(self, student_id, *, attempt_id=None, limit: int = 100, student_view: bool = False) -> list[dict]:
        """Newest first (legacy list shape). ``student_view`` projects the payload through the learner allow-list (LRN-F01)."""
        return self._events(student_id, attempt_id=attempt_id, limit=limit, forward=False, after=None, next_token=None,
                            student_view=student_view)["items"]

    def list_events_page(self, student_id, *, attempt_id=None, limit: int = 100, next_token: str | None = None,
                         student_view: bool = False) -> dict:
        """Newest first, ``{items, limit, next_token}`` with a signed, partition-bound token."""
        return self._events(student_id, attempt_id=attempt_id, limit=limit, forward=False, after=None, next_token=next_token,
                            student_view=student_view)

    def get_events_after(self, student_id, after: str, *, attempt_id=None, limit: int = 100, next_token: str | None = None,
                         student_view: bool = False) -> dict:
        """Oldest first, strictly after the ``after`` instant (a polling cursor)."""
        return self._events(student_id, attempt_id=attempt_id, limit=limit, forward=True, after=after, next_token=next_token,
                            student_view=student_view)
