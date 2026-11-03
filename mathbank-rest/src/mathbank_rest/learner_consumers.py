"""Lambda-style DynamoDB Stream consumers and scheduled jobs of the learner table (requirement 70 C1 section 5, requirement 71 WP5).

Every entry point has the Lambda signature ``handler(event, context=None)`` (a keyword-only ``store`` is for tests) and, for stream
batches, answers ``{"batchItemFailures": [...]}``: a record that fails is reported with every later record of the same item, so
per-item order is preserved and the event-source mapping's bisect/retry/DLQ settings do the rest. Stream images are accepted in raw
attribute-value form (``{"S": ...}``) and already deserialised, like ``vector_sync``. No PostgreSQL anywhere in this module.

* ``integrity_handler``    ``learner-integrity``: an alarm (error log + CloudWatch EMF metric ``LearnerAppendOnlyViolation`` + in-process
                           counter) for any MODIFY/REMOVE of OUTCOME, MEVID, EVENT, MCEVENT, IXEVENT, MISCEVID or DIAG, except a TTL
                           expiry (principal ``dynamodb.amazonaws.com``), a REMOVE inside a partition whose erasure was requested
                           (the ``ERASED#<sid>`` job item exists), and the one legitimate edit: ``mastery-repair`` clearing
                           ``mastery_pending`` on an OUTCOME.
* ``mastery_repair_handler`` ``mastery-repair``: INSERT of an OUTCOME with ``mastery_pending`` -> missing MEVID, recompute, clear the flag.
* ``mastery_cohort_handler`` ``mastery-cohort``: INSERT/MODIFY/REMOVE of a concept MASTERY -> ``COHORT#CONCEPT`` counters
                           (``n_students``, ``sum_score``, ``sum_attempts``), exactly once per stream event.
* ``abandon_stale_handler`` ``learner-abandon-stale`` (daily schedule): abandons IN_PROGRESS solve attempts idle for ``ABANDON_IDLE_DAYS``.
* ``erasure_handler``      the erasure worker (Step Functions task, SQS message or a scheduled sweep of ``ERASURE#REQUESTED``).
* ``rebuild_handler``      mastery / daily-activity rebuild of one student or of the whole directory, resumable by ``next_token``.

Switch from ``outbox_worker --abandon-idle-days N`` (left untouched): schedule ``mathbank_rest.learner_consumers.abandon_stale_handler``
daily with LEARNER_STORE=dynamodb and stop running the CLI flag; the CLI keeps working for PostgreSQL deployments.
"""
from __future__ import annotations

import collections
import json
import logging
import time
from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import Any, Literal

from boto3.dynamodb.types import TypeDeserializer
from pydantic import BaseModel, ConfigDict, Field

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.stores.learner.uow import APPEND_ONLY

LOG = logging.getLogger(__name__)

METRIC_NAMESPACE = "MathBank/Learner"
VIOLATION_METRIC = "LearnerAppendOnlyViolation"
COUNTERS: collections.Counter[str] = collections.Counter()
TTL_PRINCIPAL = "dynamodb.amazonaws.com"
REPAIR_OK_CHANGES = frozenset({"mastery_pending", "updated_at"})
REBUILD_PAGE = 50
ABANDON_BATCH = 500
ABANDON_MAX_ROUNDS = 20

_DES = TypeDeserializer()
_ATTR_TYPES = {"S", "N", "B", "SS", "NS", "BS", "M", "L", "NULL", "BOOL"}


# ------------------------------------------------------------------ stream records

def _image(raw: dict | None) -> dict | None:
    """A stream image as a plain dict (numbers stay ``Decimal`` when raw), whether deserialised or in attribute-value form."""
    if not raw:
        return None
    pk = raw.get("PK")
    if isinstance(pk, dict) and len(pk) == 1 and next(iter(pk)) in _ATTR_TYPES:
        return {k: _DES.deserialize(v) for k, v in raw.items()}
    return raw


class StreamBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    Keys: dict | None = None
    OldImage: dict | None = None
    NewImage: dict | None = None
    SequenceNumber: str | None = None


class StreamRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    eventID: str = ""
    eventName: Literal["INSERT", "MODIFY", "REMOVE"]
    userIdentity: dict | None = None
    dynamodb: StreamBody = Field(default_factory=StreamBody)

    @property
    def old(self) -> dict | None:
        return _image(self.dynamodb.OldImage)

    @property
    def new(self) -> dict | None:
        return _image(self.dynamodb.NewImage)

    @property
    def keys(self) -> dict:
        return _image(self.dynamodb.Keys) or {}

    @property
    def sequence(self) -> str:
        return self.dynamodb.SequenceNumber or self.eventID

    @property
    def by_ttl(self) -> bool:
        ident = self.userIdentity or {}
        return ident.get("principalId") == TTL_PRINCIPAL and ident.get("type") == "Service"


def _records(event: dict) -> list[StreamRecord]:
    return [StreamRecord.model_validate(r) for r in event.get("Records", [])]


def _student_of(pk: str) -> str | None:
    return pk.split("#", 1)[1] if pk.startswith("STUDENT#") else None


def _dec(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(repr(value) if isinstance(value, float) else str(value))


def _run_batch(event: dict, apply: Callable[[StreamRecord], Any]) -> dict:
    """Apply one record at a time; a failing record and the later records of the same item go to ``batchItemFailures``."""
    failures: list[dict[str, str]] = []
    blocked: set[str] = set()
    for raw in event.get("Records", []):
        try:
            rec = StreamRecord.model_validate(raw)
        except ValueError:
            LOG.exception("unreadable stream record %s", raw.get("eventID"))
            failures.append({"itemIdentifier": (raw.get("dynamodb") or {}).get("SequenceNumber") or raw.get("eventID") or ""})
            continue
        item = rec.keys.get("PK", "")
        if item in blocked:
            failures.append({"itemIdentifier": rec.sequence})
            continue
        try:
            apply(rec)
        except Exception:
            LOG.exception("stream record %s failed", rec.sequence)
            failures.append({"itemIdentifier": rec.sequence})
            if item:
                blocked.add(item)
    return {"batchItemFailures": failures}


def _store(store: Any = None) -> Any:
    return store or stores.get_store("learner")


# ------------------------------------------------------------------ learner-integrity

def emit_metric(name: str, value: int = 1, **dimensions: str) -> None:
    """CloudWatch Embedded Metric Format line (no API call) plus the in-process counter."""
    COUNTERS[name] += value
    print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000),
                               "CloudWatchMetrics": [{"Namespace": METRIC_NAMESPACE, "Dimensions": [sorted(dimensions)] if dimensions else [[]],
                                                      "Metrics": [{"Name": name, "Unit": "Count"}]}]},
                      name: value, **dimensions}), flush=True)


def _repair_only(old: dict, new: dict) -> bool:
    """The edit ``mastery-repair`` makes to an OUTCOME: ``mastery_pending`` true -> absent/false, nothing else."""
    changed = {k for k in set(old) | set(new) if old.get(k) != new.get(k)}
    return old.get("mastery_pending") is True and not new.get("mastery_pending") and changed <= REPAIR_OK_CHANGES


def append_only_violation(rec: StreamRecord, erasing: Callable[[str], bool]) -> str | None:
    """Why this record breaks the append-only rule, or None when it is allowed (see the module docstring)."""
    if rec.eventName == "INSERT":
        return None
    old = rec.old or {}
    kind = old.get("type")
    if kind not in APPEND_ONLY or rec.by_ttl:
        return None
    if rec.eventName == "REMOVE":
        sid = _student_of(str(old.get("PK", "")))
        return None if sid and erasing(sid) else f"REMOVE of {kind}"
    if kind == "OUTCOME" and _repair_only(old, rec.new or {}):
        return None
    return f"MODIFY of {kind}"


def integrity_handler(event: dict, context: Any = None, *, store: Any = None) -> dict:
    learner = _store(store)
    cache: dict[str, bool] = {}

    def erasing(sid: str) -> bool:
        if sid not in cache:
            cache[sid] = learner.get_erasure_job(sid) is not None
        return cache[sid]

    violations = []
    for rec in _records(event):
        why = append_only_violation(rec, erasing)
        if why:
            old = rec.old or {}
            LOG.error("LearnerAppendOnlyViolation: %s PK=%s SK=%s event=%s", why, old.get("PK"), old.get("SK"), rec.eventID)
            emit_metric(VIOLATION_METRIC, Type=str(old.get("type")))
            violations.append({"event_id": rec.eventID, "reason": why, "PK": old.get("PK"), "SK": old.get("SK")})
    return {"batchItemFailures": [], "violations": violations}


# ------------------------------------------------------------------ mastery-repair

def mastery_repair_handler(event: dict, context: Any = None, *, store: Any = None) -> dict:
    learner = _store(store)

    def apply(rec: StreamRecord) -> None:
        new = rec.new or {}
        if rec.eventName != "INSERT" or new.get("type") != "OUTCOME" or new.get("mastery_pending") is not True:
            return
        sid = _student_of(str(new["PK"]))
        if sid:
            learner.repair_pending_outcome(sid, str(new["SK"]))

    return _run_batch(event, apply)


# ------------------------------------------------------------------ mastery-cohort

class CohortDelta(BaseModel):
    concept_id: str
    d_students: int
    d_score: Decimal
    d_attempts: int


def cohort_delta(rec: StreamRecord) -> CohortDelta | None:
    """What one MASTERY change adds to its concept's cohort counters (concept scores only; techniques have no cohort)."""
    image = rec.new or rec.old or {}
    sk = str(image.get("SK", ""))
    if image.get("type") != "MASTERY" or not sk.startswith("MASTERY#C#"):
        return None
    concept = sk.split("#", 2)[2]

    def score_attempts(img: dict | None) -> tuple[Decimal, int]:
        return (Decimal(0), 0) if not img else (_dec(img.get("mastery_score", 0)), int(img.get("attempts_count", 0)))

    old_s, old_a = score_attempts(rec.old)
    new_s, new_a = score_attempts(rec.new)
    d_students = {"INSERT": 1, "REMOVE": -1, "MODIFY": 0}[rec.eventName]
    delta = CohortDelta(concept_id=concept, d_students=d_students, d_score=new_s - old_s, d_attempts=new_a - old_a)
    return None if not (delta.d_students or delta.d_score or delta.d_attempts) else delta


def mastery_cohort_handler(event: dict, context: Any = None, *, store: Any = None) -> dict:
    learner = _store(store)

    def apply(rec: StreamRecord) -> None:
        delta = cohort_delta(rec)
        if delta is not None:
            learner.apply_cohort_change(event_id=rec.eventID or rec.sequence, concept_id=delta.concept_id,
                                        d_students=delta.d_students, d_score=delta.d_score, d_attempts=delta.d_attempts)

    return _run_batch(event, apply)


# ------------------------------------------------------------------ learner-abandon-stale

def abandon_stale_handler(event: dict | None = None, context: Any = None, *, store: Any = None) -> dict:
    """Daily job: abandon IN_PROGRESS attempts idle for ``idle_days`` (event override, else ``ABANDON_IDLE_DAYS``), in batches of
    500 until a batch comes back short."""
    event = event or {}
    learner = _store(store)
    idle_days = int(event.get("idle_days") or settings.abandon_idle_days)
    batch = int(event.get("limit") or ABANDON_BATCH)
    total = 0
    for _ in range(ABANDON_MAX_ROUNDS):
        done = learner.abandon_stale_attempts(idle_days, batch)
        total += len(done)
        if len(done) < batch:
            break
    return {"abandoned": total, "idle_days": idle_days}


# ------------------------------------------------------------------ erasure

def _erasure_targets(event: dict, learner: Any) -> list[str]:
    if event.get("student_id"):
        return [str(event["student_id"])]
    if event.get("Records"):
        return [str(json.loads(r["body"])["student_id"]) for r in event["Records"] if r.get("body")]
    return learner.list_pending_erasures(int(event.get("limit") or 25))


def erasure_handler(event: dict | None = None, context: Any = None, *, store: Any = None) -> dict:
    """Run ``erase_partition`` for the named student, for the students of SQS messages, or (empty event, scheduled) for every pending
    request. Safe to run repeatedly. A direct invocation that fails re-raises so Step Functions retries it; a batch reports the
    failed messages."""
    event = event or {}
    learner = _store(store)
    max_seconds = event.get("max_seconds")
    results, failed = [], []
    for sid in _erasure_targets(event, learner):
        try:
            results.append(learner.erase_partition(sid, max_seconds=max_seconds))
        except Exception:
            LOG.exception("erasure of %s failed; it will be retried", sid)
            failed.append(sid)
            if not event.get("Records") and event.get("student_id"):
                raise
    return {"results": results, "failed": failed, "batchItemFailures": [
        {"itemIdentifier": r["messageId"]} for r in event.get("Records", [])
        if r.get("body") and json.loads(r["body"]).get("student_id") in failed]}


# ------------------------------------------------------------------ rebuilds

def rebuild_handler(event: dict, context: Any = None, *, store: Any = None) -> dict:
    """``{"kind": "mastery" | "daily", "student_id"?: ..., "next_token"?: ..., "max_seconds"?: ...}``. With a student id that student is
    rebuilt; without, the directory is walked page by page and the answer carries the ``next_token`` to continue (``None`` = done)."""
    learner = _store(store)
    kind = event.get("kind")
    if kind not in ("mastery", "daily"):
        raise ValueError("kind must be 'mastery' or 'daily'")
    run = learner.rebuild_mastery if kind == "mastery" else learner.rebuild_daily_activity
    actor = "system:learner-rebuild"
    if event.get("student_id"):
        return {"kind": kind, "processed": 1, "failed": [], "next_token": None, "result": run(event["student_id"], actor)}
    started, token, processed, failed = time.monotonic(), event.get("next_token"), 0, []
    max_seconds = event.get("max_seconds")
    while True:
        page = learner.list_admin_students(limit=REBUILD_PAGE, next_token=token)
        for row in page["items"]:
            try:
                run(row["student_id"], actor)
                processed += 1
            except Exception:
                LOG.exception("%s rebuild of %s failed", kind, row["student_id"])
                failed.append(row["student_id"])
        token = page["next_token"]
        if not token or (max_seconds is not None and time.monotonic() - started > max_seconds):
            return {"kind": kind, "processed": processed, "failed": failed, "next_token": token}


__all__: Iterable[str] = (
    "abandon_stale_handler", "erasure_handler", "integrity_handler", "mastery_cohort_handler", "mastery_repair_handler",
    "rebuild_handler",
)
