"""Learner store, admin area (requirement 71 WP5; requirement 70 C1 access patterns A5, A17, A41, A43, write paths T4, T35, T36).

``AdminPostgres`` runs today's equivalent where it is trivial (profile read and list, account status, daily activity of one student,
the enrollment reset lookup, the audit row) and answers ``StoreNotImplemented`` (HTTP 501) for what only the DynamoDB design has
(token revocation, erasure, rebuilds, interaction-event listing, stream-consumer operations). ``AdminDynamoDB`` is the ``mb-learner``
implementation on ``LearnerUnitOfWork`` and the typed models. A method is a read exactly when its name starts with a
``stores.READ_PREFIXES`` entry.

* reads   ``list_admin_students`` (A5), ``get_admin_student`` (A3), ``list_admin_daily_activity`` (A41),
          ``list_admin_interaction_events``, ``get_enrollment_reset_info`` (A30), ``get_erasure_job``, ``list_pending_erasures``
* writes  ``set_account_status`` (T4), ``revoke_student_tokens``, ``request_erasure`` + ``erase_partition`` (T36), ``rebuild_mastery``
          (T35), ``rebuild_daily_activity`` (ANL-E03), ``purge_idempotency`` (LRN-E21), ``record_admin_audit``; for the stream
          consumers of ``learner_consumers.py``: ``apply_cohort_change``, ``repair_pending_outcome``

Erasure is two-step so a request path never bulk-deletes: ``request_erasure`` flips the profile to ``ERASING`` (every token is rejected
at once) and writes the durable job item ``ERASED#<sid>/TOMBSTONE`` (``REQUESTED``, listed in the sparse GSI1 partition
``ERASURE#REQUESTED``); ``erase_partition`` (run by ``learner_consumers.erasure_handler``) does the deletion, idempotently and
resumably, in this order: other contexts' hooks, then per page of the partition the owner pointers/sentinels derived from it BEFORE the
items themselves (so a crash never strands a pointer), the S3 offload prefix, and finally in ONE transaction the e-mail and Cognito
sentinels, the profile, the tombstone (``DONE``) and the audit record. Deletes use ``TransactWriteItems`` (no BatchWriteItem on this path).

GSI2 projects only a subset of the profile (no ``password_hash``, no ``email_lc``): the directory is read through the
``StudentDirectoryRow`` projection model, never the full profile model.

Differences from the design observable by callers (all listed in the WP5 report):

* the stream-consumer sentinel ``APPLIED`` lives in ``APPLIED#<consumer>#<shard>`` partitions, not under the student;
* the S3 prefix erased is the one ``stores.ddb.offload_key`` writes (``offload/learner/students/<sid>/``);
* a cross-student daily-activity read is one Query per student of one directory page (no global index exists): ``group_by=day``
  sums that page only.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import TypeAdapter

from mathbank_rest import stores
from mathbank_rest.models.base import UtcDateTime
from mathbank_rest.models.ddb.learner import LearnerEvent
from mathbank_rest.models.manual import learner_microcourse as mc
from mathbank_rest.models.manual.learner_admin import (
    DAILY_EVENT_COLUMNS,
    ERASURE_PENDING_PK,
    LearnerAdminAudit,
    LearnerApplied,
    LearnerTombstone,
    StudentDirectoryRow,
)
from mathbank_rest.models.manual.learner_idem import LearnerIdem
from mathbank_rest.models.manual.learner_identity import IdentityProfile
from mathbank_rest.models.manual.learner_outcomes import (
    DAILY_COUNTERS,
    DailyItem,
    MevidItem,
    OutcomeItem,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    NotFound,
    StoreNotImplemented,
    ValidationFailed,
)
from mathbank_rest.stores.learner.identity import TERMINAL_STATUSES, is_password_hash
from mathbank_rest.stores.learner.uow import CTX, LearnerUnitOfWork, with_retries

LOG = logging.getLogger(__name__)

DIRECTORY_PK = "STUDENT_DIR"
DIRECTORY_PAGE = 200
DIRECTORY_MAX_PAGES = 25                     # pages read per request while a q/status filter is thinning the directory
PROFILE_STATUSES = ("ACTIVE", "DISABLED", "DELETED", "ERASING")
AUDIT_RETENTION_DAYS = 400
OFFLOAD_PREFIX = "offload/learner/students/{sid}/"
TX_CHUNK = 100
APPLIED_TTL_DAYS = 2
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_TS = TypeAdapter(UtcDateTime)

# Other contexts' erase operations, called (and required to succeed) before the learner partition is deleted. Work packages that own
# per-student data register here; the notify store is built in because it already exists.
ERASURE_HOOKS: dict[str, Callable[[str], int | None]] = {}


def register_erasure_hook(name: str, fn: Callable[[str], int | None] | None) -> None:
    if fn is None:
        ERASURE_HOOKS.pop(name, None)
    else:
        ERASURE_HOOKS[name] = fn


def _adm_notify_hook(student_id: str) -> int | None:
    try:
        store = stores.get_store("notify")
    except StoreNotImplemented:
        return None
    erase = getattr(store, "erase_student", None)
    return erase(student_id) if erase is not None and getattr(store, "backend", "") == "dynamodb" else None


def _adm_audit_op(actor_id: str | None, action: str, entity_type: str, entity_id: str, before: dict | None,
                  after: dict | None) -> ddb.TxOp:
    """The ``mb-audit`` Put of one staff mutation, to be added to the mutation's own transaction."""
    actor = actor_id or "system"
    actor_type = "SYSTEM" if actor.startswith("system") else "ADMIN"
    audit_id, request_id = str(uuid.uuid4()), str(uuid.uuid4())
    at = f"AT#{int(time.time() * 1_000_000):017d}#{audit_id}"
    entry = LearnerAdminAudit(
        PK=f"ENTITY#{entity_type}#{entity_id}", SK=at, GSI1PK=f"ACTOR#{actor_type}#{actor}", GSI1SK=at,
        GSI2PK=f"REQ#{request_id}", GSI2SK=at, GSI3PK=f"AUDIT#{audit_id}", GSI3SK="AUDIT", audit_id=audit_id,
        actor_type=actor_type, actor_id=actor, action=action, entity_type=entity_type, entity_id=entity_id,
        before_state=before, after_state=after, request_id=request_id, created_at=ddb.now_iso(),
        ttl=ddb.epoch_after(AUDIT_RETENTION_DAYS))
    return typed.tx_put(entry, ddb.NOT_EXISTS, label="audit")


def _adm_expected(profile: IdentityProfile) -> dict | None:
    return {"version": profile.version} if profile.version is not None else None


def _adm_job_view(t: LearnerTombstone) -> dict:
    return {"job_id": t.job_id, "student_id": t.student_id, "status": t.status, "requested_at": t.requested_at,
            "requested_by": t.requested_by, "erased_at": t.erased_at, "report": t.report}


def _adm_directory_row(r: StudentDirectoryRow) -> dict:
    return {"student_id": r.student_id, "email": r.email, "first_name": r.first_name, "last_name": r.last_name,
            "display_name": r.display_name, "status": r.status, "created_at": r.created_at, "is_anonymous": r.is_anonymous}


def _adm_student_dict(p: IdentityProfile) -> dict:
    """The admin profile view: never ``password_hash`` or ``search_blob``."""
    return {"student_id": p.student_id, "email": p.email, "first_name": p.first_name, "last_name": p.last_name,
            "display_name": p.display_name, "status": p.status, "grade": p.grade, "phone": p.phone,
            "is_anonymous": p.is_anonymous, "auth": "password" if is_password_hash(p.password_hash) else "cognito",
            "cognito_sub": None if p.cognito_sub is None else str(p.cognito_sub), "token_version": p.token_version,
            "version": p.version, "created_at": p.created_at, "last_login_at": p.last_login_at, "disabled_at": p.disabled_at}


def _adm_pages(model: Any, pk: str, **kwargs: Any):
    token = None
    while True:
        page = typed.query(model, pk, limit=200, next_token=token, **kwargs)
        yield from page.items
        token = page.next_token
        if not token:
            return


def _adm_base_token(pk: str, sk: str) -> str:
    """Signed 'continue after this item' token of a base-table partition query (same bindings as ``ddb.query_page``)."""
    return ddb.sign_token({"t": ddb.table_name(CTX), "i": "", "p": pk, "f": True, "k": {"PK": pk, "SK": sk}})


def _adm_daily_view(rows: list[dict], *, group_by: str | None, limit: int, next_token: str | None, scope: str) -> dict:
    if group_by == "day":
        days: dict[Any, dict] = {}
        for row in rows:
            day = days.setdefault(row["activity_date"], {"activity_date": row["activity_date"], "students": 0,
                                                         **dict.fromkeys(DAILY_COUNTERS, 0)})
            day["students"] += 1
            for c in DAILY_COUNTERS:
                day[c] += row[c]
        items = [days[d] for d in sorted(days)]
    else:
        items = rows[:limit] if scope == "student" else rows
    return {"items": items, "limit": limit, "next_token": next_token, "scope": scope, "group_by": group_by}


def _adm_daily_range(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise ValidationFailed("`from` must not be after `to`")
    if (date_to - date_from).days >= 366:
        raise ValidationFailed("the range is limited to 366 days")


# ------------------------------------------------------------------------------------------------ postgres

def _pg():
    from mathbank_rest.db import learner

    return learner


def _pg_engine():
    from mathbank_rest.db.postgres import engine

    return engine


def _only_dynamodb(what: str) -> StoreNotImplemented:
    return StoreNotImplemented(f"{what} needs LEARNER_STORE=dynamodb", feature=what)


class AdminPostgres:
    """Postgres backend: today's equivalent where trivial, else 501."""

    def list_admin_students(self, *, q: str | None = None, status: str | None = None, limit: int = 50,
                            next_token: str | None = None) -> dict:
        from sqlalchemy import text

        limit = min(max(int(limit), 1), 200)
        needle = (q or "").strip() or None
        offset = ddb.verify_token(next_token, q=needle or "", st=status or "")["o"] if next_token else 0
        with _pg_engine().connect() as conn:
            rows = [dict(r) for r in conn.execute(text(
                "SELECT student_id::text AS student_id, email, first_name, last_name, display_name, status, created_at, is_anonymous "
                "FROM learner.student_profile "
                "WHERE (CAST(:st AS text) IS NULL OR status = :st) AND (CAST(:q AS text) IS NULL "
                "  OR email ILIKE '%' || :q || '%' OR first_name ILIKE '%' || :q || '%' OR last_name ILIKE '%' || :q || '%' "
                "  OR display_name ILIKE '%' || :q || '%' OR student_id::text = :q) "
                "ORDER BY lower(email), student_id LIMIT :n OFFSET :o"),
                {"st": status, "q": needle, "n": limit + 1, "o": offset}).mappings()]
        token = ddb.sign_token({"q": needle or "", "st": status or "", "o": offset + limit}) if len(rows) > limit else None
        return {"items": rows[:limit], "limit": limit, "next_token": token}

    def get_admin_student(self, student_id: UUID | str) -> dict | None:
        from sqlalchemy import text

        with _pg_engine().connect() as conn:
            row = conn.execute(text(
                "SELECT student_id::text AS student_id, email, first_name, last_name, display_name, status, grade, phone, is_anonymous, "
                "created_at, last_login_at, disabled_at FROM learner.student_profile WHERE student_id = :id"),
                {"id": str(student_id)}).mappings().first()
        return None if row is None else {**row, "token_version": 0, "auth": None, "cognito_sub": None, "version": None}

    def set_account_status(self, student_id: UUID | str, new_status: str, actor_id: str, reason: str | None = None) -> dict | None:
        return _pg().set_student_status(UUID(str(student_id)), new_status, actor_id)

    def revoke_student_tokens(self, student_id: UUID | str, actor_id: str) -> dict | None:
        raise _only_dynamodb("token revocation (the PostgreSQL profile has no token_version)")

    def request_erasure(self, student_id: UUID | str, actor_id: str, reason: str | None = None) -> dict:
        raise _only_dynamodb("erasure")

    def get_erasure_job(self, student_id: UUID | str) -> dict | None:
        raise _only_dynamodb("erasure")

    def list_pending_erasures(self, limit: int = 25) -> list[str]:
        raise _only_dynamodb("erasure")

    def erase_partition(self, student_id: UUID | str, *, max_seconds: float | None = None) -> dict:
        raise _only_dynamodb("erasure")

    def rebuild_mastery(self, student_id: UUID | str, actor_id: str | None = None) -> dict:
        raise _only_dynamodb("the mastery rebuild")

    def rebuild_daily_activity(self, student_id: UUID | str, actor_id: str | None = None) -> dict:
        raise _only_dynamodb("the daily-activity rebuild")

    def list_admin_daily_activity(self, *, date_from: date, date_to: date, student_id: UUID | str | None = None, limit: int = 50,
                                  next_token: str | None = None, group_by: str | None = None) -> dict:
        _adm_daily_range(date_from, date_to)
        if student_id is None:
            raise _only_dynamodb("the cross-student daily activity")
        rows = [{"student_id": str(student_id), **r} for r in _pg().list_daily_activity(UUID(str(student_id)), date_from, date_to)]
        return _adm_daily_view(rows, group_by=group_by, limit=limit, next_token=None, scope="student")

    def list_admin_interaction_events(self, *, student_id: UUID | str, enrollment_id: str | None = None, after: str | None = None,
                                      limit: int = 50, next_token: str | None = None, include_payload: bool = False) -> dict:
        raise _only_dynamodb("the interaction-event listing")

    def purge_idempotency(self, student_id: UUID | str, actor_id: str | None = None) -> dict:
        raise _only_dynamodb("the idempotency purge (PostgreSQL has no receipt store)")

    def get_enrollment_reset_info(self, enrollment_id: str, *, with_entry: bool = False) -> dict | None:
        from sqlalchemy import text

        with _pg_engine().connect() as conn:
            row = conn.execute(text(
                "SELECT e.enrollment_id::text AS enrollment_id, e.student_id::text AS student_id, e.status, e.release_id::text AS release_id, "
                "rt.current_state_id::text AS current_state_id, rt.state_version FROM learner.micro_course_enrollment e "
                "JOIN tutor.micro_course_runtime rt USING (enrollment_id) WHERE e.enrollment_id = :e"),
                {"e": str(enrollment_id)}).mappings().first()
            if row is None:
                return None
            info = dict(row)
            if with_entry:
                info["entry_state_id"] = conn.execute(text(
                    "SELECT state_id::text FROM pedagogy.micro_course_state WHERE release_id = :r ORDER BY ordinal, state_id LIMIT 1"),
                    {"r": info["release_id"]}).scalar_one_or_none()
        return info

    def record_admin_audit(self, actor_id: str, action: str, entity_type: str, entity_id: str, before_state: dict | None = None,
                           after_state: dict | None = None) -> None:
        from mathbank_rest.micro_course_service import record_audit_event

        with _pg_engine().begin() as conn:
            record_audit_event(conn, "ADMIN", actor_id, action, entity_type, str(entity_id), before_state=before_state,
                               after_state=after_state)

    def apply_cohort_change(self, *, event_id: str, concept_id: str, d_students: int, d_score: Decimal, d_attempts: int) -> bool:
        raise _only_dynamodb("the cohort consumer")

    def repair_pending_outcome(self, student_id: UUID | str, outcome_sk: str) -> dict:
        raise _only_dynamodb("the mastery-repair consumer")


# ------------------------------------------------------------------------------------------------ dynamodb

def _outcomes():
    from mathbank_rest.stores.learner.outcomes import OutcomesDynamoDB

    return OutcomesDynamoDB()


class AdminDynamoDB:
    """DynamoDB backend over mb-learner."""

    # -- A5 / A3 -----------------------------------------------------------------------------------------------------

    @staticmethod
    def _adm_dir_token(row: StudentDirectoryRow) -> str:
        """The toolkit's signed token for 'continue after this directory row' (the page may stop mid-way through a filtered page)."""
        return ddb.sign_token({"t": ddb.table_name(CTX), "i": "GSI2", "p": DIRECTORY_PK, "f": True,
                               "k": {"PK": row.PK, "SK": row.SK, "GSI2PK": row.GSI2PK, "GSI2SK": row.GSI2SK}})

    def list_admin_students(self, *, q: str | None = None, status: str | None = None, limit: int = 50,
                            next_token: str | None = None) -> dict:
        """Staff directory: GSI2 ``STUDENT_DIR`` in e-mail order, filtered by ``status`` and by ``q`` (substring of the lower-cased
        e-mail/name blob, or an exact student id). The index projects no secrets and no full profile; a page read is bounded
        (``DIRECTORY_MAX_PAGES``), so a rare ``q`` may return fewer rows than ``limit`` with a ``next_token`` to continue."""
        limit = min(max(int(limit), 1), 200)
        needle = (q or "").strip().lower()
        if status is not None and status not in PROFILE_STATUSES:
            raise ValidationFailed(f"status must be one of {PROFILE_STATUSES}")
        if needle and _UUID_RE.match(needle):
            profile = typed.get(IdentityProfile, ddb.student_pk(needle), "PROFILE", consistent=False)
            hit = profile is not None and (status is None or profile.status == status)
            items = [{"student_id": str(profile.student_id), "email": profile.email, "first_name": profile.first_name,
                      "last_name": profile.last_name, "display_name": profile.display_name, "status": profile.status,
                      "created_at": profile.created_at, "is_anonymous": profile.is_anonymous}] if hit else []
            return {"items": items, "limit": limit, "next_token": None}
        filtered = bool(needle or status)
        rows: list[dict] = []
        token = next_token
        for _ in range(DIRECTORY_MAX_PAGES):
            page = typed.query(StudentDirectoryRow, DIRECTORY_PK, index="GSI2", limit=DIRECTORY_PAGE if filtered else limit,
                               next_token=token)
            for row in page.items:
                if (status is None or row.status == status) and (not needle or needle in row.search_blob):
                    rows.append(_adm_directory_row(row))
                    if len(rows) == limit:
                        return {"items": rows, "limit": limit, "next_token": self._adm_dir_token(row)}
            token = page.next_token
            if not token:
                break
        return {"items": rows, "limit": limit, "next_token": token}

    def get_admin_student(self, student_id: UUID | str) -> dict | None:
        profile = typed.get(IdentityProfile, ddb.student_pk(student_id), "PROFILE")
        return None if profile is None else _adm_student_dict(profile)

    # -- T4 / token version --------------------------------------------------------------------------------------------

    def set_account_status(self, student_id: UUID | str, new_status: str, actor_id: str, reason: str | None = None) -> dict | None:
        """Disable or re-enable an account (T4): status, ``disabled_at``, ``token_version + 1`` on disable (every earlier token stops
        working, also after a re-enable) and the ``mb-audit`` record in ONE transaction. None = no such student; ``ValueError`` for a
        deleted or erasing one."""
        if new_status not in ("ACTIVE", "DISABLED"):
            raise ValueError(f"unsupported status {new_status!r}")
        sid = str(student_id)

        def attempt() -> dict | None:
            profile = typed.get(IdentityProfile, ddb.student_pk(sid), "PROFILE")
            if profile is None:
                return None
            if profile.status in TERMINAL_STATUSES:
                raise ValueError("account is deleted")
            if profile.status == new_status:
                return {"student_id": profile.student_id, "status": profile.status, "disabled_at": profile.disabled_at}
            disabling = new_status == "DISABLED"
            disabled_at = datetime.now(UTC) if disabling else None
            changes: dict[str, Any] = {"status": new_status}
            if disabling:
                changes["disabled_at"] = disabled_at
            uow = LearnerUnitOfWork(sid)
            uow.update(IdentityProfile, profile.PK, "PROFILE", changes, expected=_adm_expected(profile),
                       cond=ddb.Cond("#st = :from", {"#st": "status"}, {":from": profile.status}),
                       increment={"token_version": 1} if disabling else None, remove=() if disabling else ("disabled_at",))
            uow.add(_adm_audit_op(actor_id, "STUDENT_DISABLED" if disabling else "STUDENT_ENABLED", "STUDENT", sid,
                                  {"status": profile.status}, {"status": new_status, **({"reason": reason} if reason else {})}))
            uow.commit()
            return {"student_id": profile.student_id, "status": new_status, "disabled_at": disabled_at}

        return with_retries(attempt)

    def revoke_student_tokens(self, student_id: UUID | str, actor_id: str) -> dict | None:
        """Sign the student out everywhere: ``token_version + 1`` (+ audit), status unchanged. None = no such student."""
        sid = str(student_id)

        def attempt() -> dict | None:
            profile = typed.get(IdentityProfile, ddb.student_pk(sid), "PROFILE")
            if profile is None:
                return None
            if profile.status in TERMINAL_STATUSES:
                raise ValueError("account is deleted")
            uow = LearnerUnitOfWork(sid)
            uow.update(IdentityProfile, profile.PK, "PROFILE", {}, expected=_adm_expected(profile), increment={"token_version": 1})
            uow.add(_adm_audit_op(actor_id, "STUDENT_TOKENS_REVOKED", "STUDENT", sid, {"token_version": profile.token_version},
                                  {"token_version": profile.token_version + 1}))
            uow.commit()
            return {"student_id": profile.student_id, "token_version": profile.token_version + 1}

        return with_retries(attempt)

    # -- T36 erasure ---------------------------------------------------------------------------------------------------

    @staticmethod
    def _adm_tomb_pk(student_id: str) -> str:
        return f"ERASED#{student_id}"

    def get_erasure_job(self, student_id: UUID | str) -> dict | None:
        t = typed.get(LearnerTombstone, self._adm_tomb_pk(str(student_id)), "TOMBSTONE")
        return None if t is None else _adm_job_view(t)

    def list_pending_erasures(self, limit: int = 25) -> list[str]:
        """Students whose erasure was requested and is not done, oldest request first (sparse GSI1 partition, no scan)."""
        page = typed.query(LearnerTombstone, ERASURE_PENDING_PK, index="GSI1", limit=min(max(limit, 1), 200))
        return [t.student_id for t in page.items]

    def request_erasure(self, student_id: UUID | str, actor_id: str, reason: str | None = None) -> dict:
        """Step 1 of the erasure (the only part on the request path): status ``ERASING`` and ``token_version + 1`` (every token is
        rejected from now on), the durable job item and the audit record in ONE transaction. Idempotent: a repeat returns the job."""
        sid = str(student_id)

        def attempt() -> dict:
            profile = typed.get(IdentityProfile, ddb.student_pk(sid), "PROFILE")
            tomb = typed.get(LearnerTombstone, self._adm_tomb_pk(sid), "TOMBSTONE")
            if tomb is not None and (profile is None or tomb.status == "DONE" or profile.status == "ERASING"):
                return {**_adm_job_view(tomb), "already_requested": True}
            if profile is None:
                raise NotFound("student")
            requested = datetime.now(UTC)
            job = LearnerTombstone(
                PK=self._adm_tomb_pk(sid), SK="TOMBSTONE", student_id=sid, job_id=ddb.uuid7(), status="REQUESTED",
                requested_at=requested, requested_by=actor_id, reason=reason, version=1,
                GSI1PK=ERASURE_PENDING_PK, GSI1SK=f"{ddb.encode(requested)}#{sid}")
            uow = LearnerUnitOfWork(sid)
            if profile.status != "ERASING":
                uow.update(IdentityProfile, profile.PK, "PROFILE", {"status": "ERASING"}, expected=_adm_expected(profile),
                           cond=ddb.Cond("#st = :from", {"#st": "status"}, {":from": profile.status}),
                           increment={"token_version": 1})
            uow.put(job, cond=ddb.NOT_EXISTS)
            uow.add(_adm_audit_op(actor_id, "STUDENT_ERASURE_REQUESTED", "STUDENT", sid, {"status": profile.status},
                                  {"status": "ERASING", "job_id": job.job_id}))
            uow.commit()
            return {**_adm_job_view(job), "already_requested": False}

        return with_retries(attempt)

    @staticmethod
    def _adm_pointer_keys(raw: dict) -> list[tuple[str, str]]:
        """Global owner pointers / sentinels that hang off one item of the student's partition."""
        kind, sk = raw.get("type"), raw["SK"]
        if kind in ("SOLVE", "PLAN", "ENROLL", "FEEDBACK"):
            return [(f"{kind}#{sk.split('#', 1)[1]}", "OWNER")]
        if kind == "AGENTLINK":
            _, app, session = sk.split("#", 2)
            return [ddb.unique_key("agent_session", f"{app}#{session}")]
        return []

    @staticmethod
    def _adm_delete_owned(keys: list[tuple[str, str]], sid: str) -> int:
        """Delete pointers/sentinels in transactions of 100, each only while it still belongs to this student (a resumed erasure
        must not remove an e-mail sentinel somebody else registered since)."""
        own = ddb.Cond("attribute_not_exists(PK) OR #sid = :sid", {"#sid": "student_id"}, {":sid": sid})
        for n in range(0, len(keys), TX_CHUNK):
            chunk = keys[n:n + TX_CHUNK]
            try:
                ddb.transact([ddb.Delete(CTX, pk, sk, own, label="erase pointer") for pk, sk in chunk])
            except ConditionFailed:                     # one of them is somebody else's now: delete the others one by one
                for pk, sk in chunk:
                    try:
                        ddb.transact([ddb.Delete(CTX, pk, sk, own, label="erase pointer")])
                    except ConditionFailed:
                        LOG.warning("pointer %s %s belongs to another student; left in place", pk, sk)
        return len(keys)

    @staticmethod
    def _adm_delete_prefix(sid: str) -> int:
        s3, bucket, prefix, count = ddb.client("s3"), ddb.data_bucket(), OFFLOAD_PREFIX.format(sid=sid), 0
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
            keys = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if keys:
                s3.delete_objects(Bucket=bucket, Delete={"Objects": keys, "Quiet": True})
                count += len(keys)
        return count

    def erase_partition(self, student_id: UUID | str, *, max_seconds: float | None = None) -> dict:
        """Step 2 of the erasure (worker): remove everything of one student. Requires ``ERASING`` (an active student cannot be erased
        by mistake). Idempotent and resumable: run it again after any failure. ``max_seconds`` stops between batches with
        ``done: False`` so a time-boxed worker can come back. Returns counts only."""
        sid, pk, started = str(student_id), ddb.student_pk(student_id), time.monotonic()
        tomb = typed.get(LearnerTombstone, self._adm_tomb_pk(sid), "TOMBSTONE")
        profile = typed.get(IdentityProfile, pk, "PROFILE")
        report: dict[str, Any] = {"items": 0, "pointers": 0, "s3_objects": 0, "hooks": {}}
        if tomb is not None and tomb.status == "DONE":
            return {"student_id": sid, "status": "DONE", "done": True, **report}
        if profile is None and tomb is None:
            raise NotFound("student")
        if profile is not None and profile.status != "ERASING":
            raise ConditionFailed("student is not being erased: request the erasure first", student_id=sid)

        for name, hook in {"notify": _adm_notify_hook, **ERASURE_HOOKS}.items():
            result = hook(sid)
            report["hooks"][name] = "skipped" if result is None else result
        while True:
            page = ddb.query_page(CTX, pk, limit=200)         # restarted each time: what is deleted no longer shows up
            batch = [r for r in page["items"] if r["SK"] != "PROFILE"]
            if not batch:
                break
            pointers = list(dict.fromkeys(k for r in batch for k in self._adm_pointer_keys(r)))
            report["pointers"] += self._adm_delete_owned(pointers, sid)
            for n in range(0, len(batch), TX_CHUNK):
                ddb.transact([ddb.Delete(CTX, r["PK"], r["SK"], label="erase item") for r in batch[n:n + TX_CHUNK]])
            report["items"] += len(batch)
            if max_seconds is not None and time.monotonic() - started > max_seconds:
                return {"student_id": sid, "status": "ERASING", "done": False, **report}
        report["s3_objects"] = self._adm_delete_prefix(sid)
        own = ddb.Cond("attribute_not_exists(PK) OR #sid = :sid", {"#sid": "student_id"}, {":sid": sid})
        ops: list[ddb.TxOp] = []
        if profile is not None:
            ops.append(ddb.Delete(CTX, *ddb.unique_key("email", profile.email_lc), own, label="erase email sentinel"))
            if profile.cognito_sub is not None:
                ops.append(ddb.Delete(CTX, *ddb.unique_key("cognito_sub", str(profile.cognito_sub)), own,
                                      label="erase cognito sentinel"))
            report["pointers"] += len(ops)
            ops.append(ddb.Delete(CTX, pk, "PROFILE", label="erase profile"))
        now = datetime.now(UTC)
        done = LearnerTombstone(
            PK=self._adm_tomb_pk(sid), SK="TOMBSTONE", student_id=sid, job_id=tomb.job_id if tomb else ddb.uuid7(), status="DONE",
            requested_at=tomb.requested_at if tomb else now, requested_by=tomb.requested_by if tomb else "system",
            reason=tomb.reason if tomb else None, erased_at=now, report=dict(report), version=1)
        ops.append(typed.tx_put(done, label="tombstone"))
        ops.append(_adm_audit_op(done.requested_by, "STUDENT_ERASED", "STUDENT", sid, {"status": "ERASING"},
                                 {"status": "ERASED", "items": report["items"], "pointers": report["pointers"]}))
        ddb.transact(ops)
        return {"student_id": sid, "status": "DONE", "done": True, **report}

    # -- T35 / ANL-E03 rebuilds ----------------------------------------------------------------------------------------

    def rebuild_mastery(self, student_id: UUID | str, actor_id: str | None = None) -> dict:
        """Recompute every concept and technique score of one student from its evidence (T35) with the outcomes store's
        recompute primitives; each write is version-guarded. ``actor_id`` set: an audit record is written."""
        sid, out = str(student_id), _outcomes()
        if typed.get(IdentityProfile, ddb.student_pk(sid), "PROFILE", consistent=False) is None:
            raise NotFound("student")
        tags = dict.fromkeys((e.tag_kind, str(e.tag_id)) for e in _adm_pages(MevidItem, ddb.student_pk(sid), sk_begins="MEVID#"))
        scores = []
        for kind, tag in tags:
            recompute = out.recompute_concept_mastery if kind == "C" else out.recompute_technique_mastery
            scores.append({"kind": kind, "tag_id": tag, "mastery_score": recompute(UUID(sid), UUID(tag))})
        if actor_id:
            ddb.transact([_adm_audit_op(actor_id, "STUDENT_MASTERY_REBUILT", "STUDENT", sid, None, {"tags": len(scores)})])
        return {"student_id": sid, "concepts": sum(1 for s in scores if s["kind"] == "C"),
                "techniques": sum(1 for s in scores if s["kind"] == "T"), "tags": scores}

    def rebuild_daily_activity(self, student_id: UUID | str, actor_id: str | None = None) -> dict:
        """Recompute the DAILY counters of one student from its EVENT items (what ``learner-analytics`` would have counted):
        days that now count are rewritten, days without any counted event are deleted."""
        sid, pk = str(student_id), ddb.student_pk(student_id)
        if typed.get(IdentityProfile, pk, "PROFILE", consistent=False) is None:
            raise NotFound("student")
        counts: dict[date, dict[str, int]] = {}
        for ev in _adm_pages(LearnerEvent, pk, sk_begins="EVT#"):
            column = DAILY_EVENT_COLUMNS.get(ev.event_type)
            if column is None:
                continue
            day = counts.setdefault(ev.event_time.astimezone(UTC).date(), dict.fromkeys(DAILY_COUNTERS, 0))
            day[column] += 1
            if ev.event_type == "STEP_EVALUATED" and (ev.resolve("payload") or {}).get("result") == "SUCCESS":
                day["steps_succeeded"] += 1
        existing = {d.activity_date for d in _adm_pages(DailyItem, pk, sk_begins="DAILY#")}
        stale = sorted(existing - set(counts))
        now = datetime.now(UTC)
        ops: list[ddb.TxOp] = [typed.tx_put(DailyItem(PK=pk, SK=f"DAILY#{d.isoformat()}", student_id=UUID(sid), activity_date=d,
                                                       updated_at=now, **c), label="daily") for d, c in sorted(counts.items())]
        ops += [ddb.Delete(CTX, pk, f"DAILY#{d.isoformat()}", label="stale daily") for d in stale]
        for n in range(0, len(ops), TX_CHUNK):
            ddb.transact(ops[n:n + TX_CHUNK])
        if actor_id:
            ddb.transact([_adm_audit_op(actor_id, "STUDENT_DAILY_REBUILT", "STUDENT", sid, None,
                                        {"days": len(counts), "removed": len(stale)})])
        return {"student_id": sid, "days": len(counts), "removed": len(stale)}

    # -- A41 / interaction events -------------------------------------------------------------------------------------

    def list_admin_daily_activity(self, *, date_from: date, date_to: date, student_id: UUID | str | None = None, limit: int = 50,
                                  next_token: str | None = None, group_by: str | None = None) -> dict:
        """Daily counters. One student: its days (A41). No student: one Query per student of one directory page of ``limit``
        students (``next_token`` continues the directory); ``group_by='day'`` sums that page only."""
        _adm_daily_range(date_from, date_to)
        limit = min(max(int(limit), 1), 200)
        if student_id is not None:
            rows = [{"student_id": str(student_id), **r} for r in self.list_daily_activity(UUID(str(student_id)), date_from, date_to)]
            return _adm_daily_view(rows, group_by=group_by, limit=limit, next_token=None, scope="student")
        directory = self.list_admin_students(limit=limit, next_token=next_token)
        with ThreadPoolExecutor(max_workers=8) as pool:
            per_student = list(pool.map(lambda s: [{"student_id": s["student_id"], **r}
                                                   for r in self.list_daily_activity(UUID(s["student_id"]), date_from, date_to)],
                                        directory["items"]))
        rows = [r for part in per_student for r in part]
        return _adm_daily_view(rows, group_by=group_by, limit=limit, next_token=directory["next_token"], scope="page")

    def list_admin_interaction_events(self, *, student_id: UUID | str, enrollment_id: str | None = None, after: str | None = None,
                                      limit: int = 50, next_token: str | None = None, include_payload: bool = False) -> dict:
        """Interaction telemetry of one student, optionally of one enrollment, in key order (instance, then time), strictly after the
        ``after`` instant when given. The payload only on request."""
        limit = min(max(int(limit), 1), 200)
        floor = None
        if after:
            try:
                floor = _TS.validate_python(after)
            except ValueError:
                raise ValidationFailed("after must be an ISO-8601 timestamp") from None
        pk = ddb.student_pk(student_id)
        rows: list[dict] = []
        token = next_token
        while True:
            if enrollment_id:
                page = typed.query(mc.LearnerIxevent, pk, sk_begins=f"ENROLL#{enrollment_id}#IX#", limit=200, next_token=token)
            else:
                page = typed.query("learner", pk, models=[mc.LearnerEnroll, mc.LearnerMcevent, mc.LearnerIxevent],
                                   sk_begins="ENROLL#", limit=200, next_token=token)
            for ev in page.items:
                if not isinstance(ev, mc.LearnerIxevent) or (floor is not None and ev.created_at <= floor):
                    continue
                row = {"interaction_event_id": str(ev.interaction_event_id), "enrollment_id": str(ev.enrollment_id),
                       "interaction_instance_id": str(ev.interaction_instance_id), "course_state_id": str(ev.course_state_id),
                       "event_type": ev.event_type, "semantic_action": ev.semantic_action, "control_key": ev.control_key,
                       "object_id": ev.object_id, "evaluation_outcome": ev.evaluation_outcome, "error_signature": ev.error_signature,
                       "created_at": ev.created_at}
                if include_payload:
                    row["action_payload"] = ev.resolve("action_payload")
                rows.append(row)
                if len(rows) == limit:
                    return {"items": rows, "limit": limit, "next_token": _adm_base_token(ev.PK, ev.SK)}
            token = page.next_token
            if not token:
                return {"items": rows, "limit": limit, "next_token": None}

    # -- LRN-E21 / A30 / audit ---------------------------------------------------------------------------------------

    def purge_idempotency(self, student_id: UUID | str, actor_id: str | None = None) -> dict:
        """Delete this student's expired ``IDEM#`` receipts (DynamoDB TTL does it for everybody, lagging up to 48 h)."""
        pk, now, expired, seen = ddb.student_pk(student_id), int(time.time()), [], 0
        for item in _adm_pages(LearnerIdem, pk, sk_begins="IDEM#"):
            seen += 1
            if item.ttl is not None and item.ttl < now:
                expired.append(item.SK)
        for n in range(0, len(expired), TX_CHUNK):
            ddb.transact([ddb.Delete(CTX, pk, sk, label="expired idem") for sk in expired[n:n + TX_CHUNK]])
        if actor_id and expired:
            ddb.transact([_adm_audit_op(actor_id, "STUDENT_IDEMPOTENCY_PURGED", "STUDENT", str(student_id), None,
                                        {"deleted": len(expired)})])
        return {"student_id": str(student_id), "scanned": seen, "deleted": len(expired)}

    def get_enrollment_reset_info(self, enrollment_id: str, *, with_entry: bool = False) -> dict | None:
        """A30: owner, status, version and (on request) the entry state of an enrollment's pinned release."""
        owner = typed.get(mc.LearnerEnrollOwner, mc.enroll_owner_pk(enrollment_id), "OWNER")
        if owner is None:
            return None
        e = typed.get(mc.LearnerEnroll, ddb.student_pk(owner.student_id), mc.enroll_sk(enrollment_id))
        if e is None:
            return None
        info = {"enrollment_id": str(e.enrollment_id), "student_id": str(e.student_id), "status": e.status,
                "release_id": str(e.release_id), "current_state_id": str(e.current_state_id), "state_version": e.state_version}
        if with_entry:
            reader = stores.get_store("content").get_pinned_micro_course_reader(None, str(e.release_id))
            entry = min(reader["states"], key=lambda s: (s["ordinal"], str(s["state_id"])), default=None)
            info["entry_state_id"] = None if entry is None else str(entry["state_id"])
        return info

    def record_admin_audit(self, actor_id: str, action: str, entity_type: str, entity_id: str, before_state: dict | None = None,
                           after_state: dict | None = None) -> None:
        ddb.transact([_adm_audit_op(actor_id, action, entity_type, str(entity_id), before_state, after_state)])

    # -- stream-consumer operations ----------------------------------------------------------------------------------

    def apply_cohort_change(self, *, event_id: str, concept_id: str, d_students: int, d_score: Decimal, d_attempts: int) -> bool:
        """``mastery-cohort``: add one MASTERY change to ``COHORT#CONCEPT/<concept>`` exactly once per stream event (the ``APPLIED``
        sentinel is in the same transaction). The score delta is a Decimal, so the stored sum is the exact sum of the stored scores.
        Returns False when the event was applied before."""
        shard = hashlib.sha256(event_id.encode()).hexdigest()[:2]
        applied = LearnerApplied(PK=f"APPLIED#mastery-cohort#{shard}", SK=event_id, consumer="mastery-cohort",
                                 ttl=ddb.epoch_after(APPLIED_TTL_DAYS))
        update = ddb.Update(
            CTX, "COHORT#CONCEPT", str(concept_id),
            "SET #t = :t, #c = :c, #u = :now ADD #n :dn, #s :ds, #a :da",
            names={"#t": "type", "#c": "concept_id", "#u": "updated_at", "#n": "n_students", "#s": "sum_score", "#a": "sum_attempts"},
            values={":t": "COHORT", ":c": str(concept_id), ":now": ddb.now_iso(), ":dn": d_students, ":ds": d_score, ":da": d_attempts},
            label="cohort")
        try:
            ddb.transact([typed.tx_put(applied, ddb.NOT_EXISTS, ConditionFailed("already applied"), "applied"), update])
        except ConditionFailed:
            return False
        return True

    def repair_pending_outcome(self, student_id: UUID | str, outcome_sk: str) -> dict:
        """``mastery-repair`` (T35): an OUTCOME flagged ``mastery_pending`` gets its missing MEVID rows, every tag of its problem is
        recomputed from the evidence, and only then the flag is cleared (the one permitted change of an append-only item; the
        ``learner-integrity`` consumer recognises exactly this transition)."""
        sid, pk, out = str(student_id), ddb.student_pk(student_id), _outcomes()
        item = typed.get(OutcomeItem, pk, outcome_sk)
        if item is None:
            return {"status": "missing"}
        if not item.mastery_pending:
            return {"status": "clear"}
        content = stores.get_store("content")
        problem = content.get_problem_by_id(item.problem_id)
        if problem is None:
            raise NotFound(f"problem {item.problem_id}")
        tags = content.get_problem_tags(problem_id=item.problem_id)
        kinds = [("C", UUID(str(t))) for t in dict.fromkeys(map(str, tags.get("concept_ids", ())))]
        kinds += [("T", UUID(str(t))) for t in dict.fromkeys(map(str, tags.get("technique_ids", ())))]
        ev = {"is_correct": item.is_correct, "attempted_at": item.attempted_at, "hint_count": item.hint_count,
              "difficulty_band": problem.get("difficulty_band"), "src_id": item.attempt_id, "problem_id": item.problem_id}
        for kind, tag in kinds:
            if item.is_correct is not None:
                try:
                    LearnerUnitOfWork(sid).put_new(out._mevid(sid, kind, tag, ev)).commit()
                except ConditionFailed:
                    pass                                               # written by the original follow-up
            (out.recompute_concept_mastery if kind == "C" else out.recompute_technique_mastery)(UUID(sid), tag)
        ddb.transact([ddb.Update(CTX, pk, outcome_sk, "REMOVE #mp", names={"#mp": "mastery_pending"},
                                 cond=ddb.Cond("attribute_exists(PK)"), label="clear mastery_pending")])
        return {"status": "repaired", "tags": len(kinds)}
