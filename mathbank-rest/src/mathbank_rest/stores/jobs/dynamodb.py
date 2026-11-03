"""``jobs`` store on DynamoDB (``mb-jobs``) with SQS wake-ups (requirement 70 C4 §4, requirement 71 WP3).

State machine of one job item (``RESEARCH#<id>`` / ``RENDER#<id>``, ``SK=META``)::

    PENDING --claim--> RUNNING --complete--> DONE
       |  ^               |  \\--fail(retryable, attempts left)--> PENDING
       |  |               |  \\--fail / attempts exhausted / DLQ--> FAILED
       |  +--retry--------+--(lease expired: reclaimable by the next claim, attempts + 1)
       \\--cancel--> CANCELLED                      FAILED --retry--> PENDING

* **Claim** is an optimistic-concurrency update on the item ``version``: the claimant reads the item (strongly consistent),
  checks it is claimable (PENDING, or RUNNING with an expired lease; attempts left; not expired) and writes
  ``status=RUNNING, claim_token, lease_until, attempts+1`` only if ``version`` did not move. Of any number of concurrent
  claimants exactly one write succeeds; the others re-read, see a live lease and get ``None``. A ``None`` claim means
  "duplicate or stale delivery": the caller deletes the SQS message.
* **Complete / fail / heartbeat** require ``status=RUNNING`` and the caller's ``claim_token``. Anything else raises
  :class:`LeaseLost` (the worker must drop its output). Repeating a finished call with the same token is a no-op.
* **Enqueue ordering (outbox-safe).** The item is written first (conditional put), the SQS message second. A message
  therefore never refers to a missing item, and a failed ``SendMessage`` leaves a PENDING item with no message, which
  ``republish_pending`` (idle worker loop or a schedule) re-sends: nothing is lost, and the reverse order could not make
  that guarantee. Duplicate messages are harmless because of the conditional claim. The table's stream consumer
  described in the design remains an equivalent producer and needs no change to this class.
* Every write goes through ``stores.typed`` so the item always satisfies ``JobsResearchjob`` / ``JobsRenderjob``.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import logging
import uuid
from typing import Any

from mathbank_rest.jobs_queue import JobKind, JobMessage, JobsQueue
from mathbank_rest.models.manual.jobs import JobsRenderjob, JobsResearchjob
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    NotFound,
    RevisionConflict,
    ValidationFailed,
)
from mathbank_rest.stores.jobs.protocol import JobClaim, LeaseLost

LOG = logging.getLogger("mathbank_rest.stores.jobs")

LEASE_SECONDS = 330
MAX_ATTEMPTS = 3
JOB_TTL_DAYS = 1
ERROR_MAX = 4000
STATUSES = ("PENDING", "RUNNING", "DONE", "FAILED", "CANCELLED")
_RETRIES = 3  # re-reads after losing an optimistic-concurrency race


@dataclasses.dataclass(frozen=True)
class _Spec:
    kind: JobKind
    prefix: str
    model: type
    id_attr: str


_SPECS = {
    "research": _Spec("research", "RESEARCH", JobsResearchjob, "scene_research_job_id"),
    "render": _Spec("render", "RENDER", JobsRenderjob, "video_render_job_id"),
}
_RESULT_KEYS = {"research": {"result_scene_spec", "result_explanation"},
                "render": {"video_object_key", "video_duration_ms", "video_bucket"}}


def _spec(kind: str) -> _Spec:
    try:
        return _SPECS[kind]
    except KeyError:
        raise ValidationFailed(f"unknown job kind {kind!r}", kind=kind) from None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _epoch(when: dt.datetime) -> int:
    return int(when.timestamp())


def _job_id(job_id: Any) -> str | None:
    try:
        return str(uuid.UUID(str(job_id)))
    except ValueError:
        return None


def _gsi1pk(spec: _Spec, status: str) -> str:
    return f"{spec.prefix}#STATUS#{status}"


def _present(item, *attrs: str) -> tuple[str, ...]:
    """The attributes of ``item`` that are currently stored (so REMOVE only names what exists)."""
    return tuple(a for a in attrs if getattr(item, a, None) is not None)


def _capped(text: str) -> str:
    return (text or "error")[:ERROR_MAX]


class DynamoDBJobsStore:
    backend = "dynamodb"

    def __init__(self, queue: JobsQueue | None = None):
        self._queue = queue

    @property
    def queue(self) -> JobsQueue:
        if self._queue is None:
            self._queue = JobsQueue()
        return self._queue

    # ------------------------------------------------------------------ internals

    def _load(self, spec: _Spec, job_id: str, *, include_expired: bool = False):
        jid = _job_id(job_id)
        if jid is None:
            return None
        item = typed.get(spec.model, f"{spec.prefix}#{jid}", "META")
        if item is not None and not include_expired and item.expires_at <= _now():
            return None
        return item

    def _row(self, spec: _Spec, item) -> dict:
        common = {"status": item.status, "error_message": item.resolve("error_message"), "created_at": item.created_at,
                  "updated_at": item.updated_at or item.created_at, "expires_at": item.expires_at,
                  "attempts": item.attempts, "lease_until": item.lease_until, "requested_by": item.requested_by}
        if spec.kind == "research":
            return {"scene_research_job_id": str(item.scene_research_job_id), "topic": item.topic,
                    "context_json": item.resolve("context_json") or {},
                    "result_scene_spec": item.resolve("result_scene_spec"),
                    "result_explanation": item.resolve("result_explanation"), **common}
        return {"video_render_job_id": str(item.video_render_job_id),
                "source_research_job_id": str(item.source_research_job_id) if item.source_research_job_id else None,
                "scene_spec_json": item.resolve("scene_spec_json"), "video_object_key": item.video_object_key,
                "video_bucket": item.video_bucket, "video_duration_ms": item.video_duration_ms,
                "promoted_scene_spec_id": str(item.promoted_scene_spec_id) if item.promoted_scene_spec_id else None, **common}

    def _offloaded(self, spec: _Spec, item, changes: dict) -> tuple[dict, list[str]]:
        """Apply the one S3 offload rule to an update: large values become ``<attr>_ref`` and the stale inline/ref twin is removed."""
        tmp = {"PK": item.PK, "SK": item.SK, "type": item.type, **changes}
        ddb.offload(spec.model.CTX, tmp, spec.model.OFFLOADED)
        out = {k: v for k, v in tmp.items() if k not in ("PK", "SK", "type")}
        remove: list[str] = []
        for attr in spec.model.OFFLOADED:
            if attr in changes and attr not in out and getattr(item, attr, None) is not None:
                remove.append(attr)
            if attr in out and item.ref(attr) is not None:
                remove.append(f"{attr}_ref")
        return out, remove

    def _update(self, spec: _Spec, item, changes: dict, *, remove: tuple[str, ...] = ()):
        changes, extra = self._offloaded(spec, item, changes)
        return typed.update(spec.model, item.PK, item.SK, item.version, changes, remove=[*remove, *extra])

    def _status_changes(self, spec: _Spec, status: str, **more: Any) -> dict:
        return {"status": status, "GSI1PK": _gsi1pk(spec, status), **more}

    def _publish(self, spec: _Spec, job_id: str, version: int, *, delay_seconds: int = 0) -> bool:
        try:
            self.queue.send(JobMessage(job_id=job_id, kind=spec.kind, version=max(1, version)), delay_seconds=delay_seconds)
            return True
        except Exception:
            LOG.exception("could not enqueue %s job %s; it stays PENDING for republish_pending", spec.kind, job_id)
            return False

    # ------------------------------------------------------------------ create / enqueue

    def _create(self, spec: _Spec, requested_by: str | None, **fields: Any) -> dict:
        job_id, now = str(uuid.uuid4()), _now()
        expires = now + dt.timedelta(days=JOB_TTL_DAYS)
        item = spec.model(PK=f"{spec.prefix}#{job_id}", SK="META", GSI1PK=_gsi1pk(spec, "PENDING"),
                          GSI1SK=f"{ddb.encode(now)}#{job_id}", version=1, attempts=0, status="PENDING", created_at=now,
                          updated_at=now, expires_at=expires, ttl=_epoch(expires), requested_by=requested_by,
                          **{spec.id_attr: job_id}, **fields)
        typed.put_new(item)
        self._publish(spec, job_id, 1)
        return self._row(spec, typed.require(spec.model, item.PK, "META"))

    def create_research_job(self, topic: str, context: dict | None = None, *, requested_by: str | None = None) -> dict:
        return self._create(_SPECS["research"], requested_by, topic=topic, context_json=context or {})

    def create_render_job(self, scene_spec_json: dict | None = None, source_research_job_id: str | None = None, *,
                          requested_by: str | None = None) -> dict:
        source = None
        if source_research_job_id:
            research = self._load(_SPECS["research"], source_research_job_id)
            if research is None:
                raise NotFound("research job not found")
            if research.status != "DONE":
                raise ConditionFailed(f"research job is {research.status}, not DONE yet")
            source = str(research.scene_research_job_id)
            scene_spec_json = scene_spec_json or research.resolve("result_scene_spec")
        if not scene_spec_json:
            raise ValidationFailed("one of source_research_job_id or scene_spec_json is required")
        fields: dict[str, Any] = {"scene_spec_json": scene_spec_json}
        if source:
            fields["source_research_job_id"] = source
        return self._create(_SPECS["render"], requested_by, **fields)

    def enqueue(self, kind: JobKind, job_id: str, *, delay_seconds: int = 0) -> bool:
        """(Re)send the wake-up message for a PENDING job. False when the job is not PENDING or SQS refused it."""
        spec = _spec(kind)
        item = self._load(spec, job_id)
        return bool(item and item.status == "PENDING" and self._publish(spec, str(_job_id(job_id)), item.version or 1,
                                                                        delay_seconds=delay_seconds))

    def republish_pending(self, kind: JobKind, *, older_than_seconds: int = 120, limit: int = 100) -> int:
        """Re-send messages for jobs that are PENDING (or RUNNING with an expired lease) and older than the cutoff: the
        recovery path for a lost ``SendMessage``, a purged queue or a DLQ'd-then-retried job. Returns messages sent."""
        spec, now = _spec(kind), _now()
        cutoff = ddb.encode(now - dt.timedelta(seconds=older_than_seconds))
        sent = 0
        for status in ("PENDING", "RUNNING"):
            page = typed.query(spec.model, _gsi1pk(spec, status), index="GSI1", sk_between=("0", cutoff + "~"), limit=limit)
            for item in page.items:
                if item.expires_at <= now or (status == "RUNNING" and not (item.lease_until and item.lease_until < now)):
                    continue
                sent += self._publish(spec, str(getattr(item, spec.id_attr)), item.version or 1)
        return sent

    # ------------------------------------------------------------------ worker protocol

    def claim(self, kind: JobKind, job_id: str, worker_id: str, lease_seconds: int = LEASE_SECONDS) -> JobClaim | None:
        spec = _spec(kind)
        for _ in range(_RETRIES):
            item = self._load(spec, job_id)
            now = _now()
            if item is None:
                return None
            reclaim = item.status == "RUNNING" and (item.lease_until is None or item.lease_until < now)
            if item.status != "PENDING" and not reclaim:
                return None
            if item.attempts >= MAX_ATTEMPTS:
                self._finish_failed(spec, item, f"DELIVERY_EXHAUSTED: {item.attempts} attempts used")
                return None
            token, lease = uuid.uuid4().hex, now + dt.timedelta(seconds=lease_seconds)
            keep = lease + dt.timedelta(days=JOB_TTL_DAYS)
            try:
                new = self._update(spec, item, self._status_changes(
                    spec, "RUNNING", attempts=item.attempts + 1, claim_token=token, lease_until=lease, claimed_by=worker_id,
                    expires_at=keep, ttl=_epoch(keep)))
            except (RevisionConflict, ConditionFailed):
                continue  # someone else moved the item: re-read; a live lease now means we lost the race
            payload = ({"topic": new.topic, "context_json": new.resolve("context_json") or {}} if spec.kind == "research"
                       else {"scene_spec_json": new.resolve("scene_spec_json")})
            return JobClaim(str(getattr(new, spec.id_attr)), spec.kind, token, worker_id, new.attempts, lease, new.version or 0, payload)
        return None

    def _owned(self, spec: _Spec, job_id: str, claim_token: str):
        item = self._load(spec, job_id, include_expired=True)
        if item is None or item.claim_token != claim_token:
            raise LeaseLost(f"{spec.kind} job {job_id}: claim not held")
        return item

    def heartbeat(self, kind: JobKind, job_id: str, claim_token: str, lease_seconds: int = LEASE_SECONDS) -> dt.datetime:
        """Extend the lease (and the item's expiry, so a RUNNING job is never reaped under its worker). Returns the new lease end."""
        spec = _spec(kind)
        for _ in range(_RETRIES):
            item = self._owned(spec, job_id, claim_token)
            if item.status != "RUNNING":
                raise LeaseLost(f"{spec.kind} job {job_id} is {item.status}")
            lease = _now() + dt.timedelta(seconds=lease_seconds)
            keep = lease + dt.timedelta(days=JOB_TTL_DAYS)
            try:
                self._update(spec, item, {"lease_until": lease, "expires_at": keep, "ttl": _epoch(keep)})
                return lease
            except (RevisionConflict, ConditionFailed):
                continue
        raise LeaseLost(f"{spec.kind} job {job_id}: lease changed while extending")

    def complete(self, kind: JobKind, job_id: str, claim_token: str, result: dict) -> dict:
        spec = _spec(kind)
        unknown = set(result) - _RESULT_KEYS[kind]
        if unknown:
            raise ValidationFailed(f"unknown result attributes {sorted(unknown)}", attrs=sorted(unknown))
        for _ in range(_RETRIES):
            item = self._owned(spec, job_id, claim_token)
            if item.status == "DONE":
                return self._row(spec, item)  # idempotent redelivery of the same completion
            if item.status != "RUNNING":
                raise LeaseLost(f"{spec.kind} job {job_id} is {item.status}")
            keep = _now() + dt.timedelta(days=JOB_TTL_DAYS)
            drop = _present(item, "lease_until", "error_message", "error_message_ref")
            try:
                done = self._update(spec, item, self._status_changes(spec, "DONE", expires_at=keep, ttl=_epoch(keep), **result),
                                    remove=drop)
                return self._row(spec, done)
            except (RevisionConflict, ConditionFailed):
                continue
        raise LeaseLost(f"{spec.kind} job {job_id}: changed while completing")

    def complete_research_job(self, job_id: str, claim_token: str, scene_spec: dict, explanation: str) -> dict:
        return self.complete("research", job_id, claim_token, {"result_scene_spec": scene_spec, "result_explanation": explanation})

    def complete_render_job(self, job_id: str, claim_token: str, video_object_key: str, video_duration_ms: int,
                            video_bucket: str | None = None) -> dict:
        result: dict[str, Any] = {"video_object_key": video_object_key, "video_duration_ms": int(video_duration_ms)}
        if video_bucket:
            result["video_bucket"] = video_bucket
        return self.complete("render", job_id, claim_token, result)

    def _finish_failed(self, spec: _Spec, item, error: str):
        keep = _now() + dt.timedelta(days=JOB_TTL_DAYS)
        return self._update(spec, item, self._status_changes(spec, "FAILED", error_message=_capped(error), expires_at=keep,
                                                             ttl=_epoch(keep)),
                            remove=_present(item, "lease_until", "error_message_ref"))

    def fail(self, kind: JobKind, job_id: str, claim_token: str, error: str, *, retryable: bool = False) -> dict:
        """Record a failed run. ``retryable`` with attempts left puts the job back to PENDING (new message, backoff)."""
        spec = _spec(kind)
        for _ in range(_RETRIES):
            item = self._owned(spec, job_id, claim_token)
            if item.status in ("FAILED", "PENDING"):
                return self._row(spec, item)  # idempotent
            if item.status != "RUNNING":
                raise LeaseLost(f"{spec.kind} job {job_id} is {item.status}")
            try:
                if retryable and item.attempts < MAX_ATTEMPTS:
                    new = self._update(spec, item, self._status_changes(spec, "PENDING", error_message=_capped(error)),
                                       remove=_present(item, "lease_until", "claimed_by", "error_message_ref"))
                    self._publish(spec, str(_job_id(job_id)), new.version or 1, delay_seconds=min(30 * item.attempts, 900))
                else:
                    new = self._finish_failed(spec, item, error)
                return self._row(spec, new)
            except (RevisionConflict, ConditionFailed):
                continue
        raise LeaseLost(f"{spec.kind} job {job_id}: changed while failing")

    def fail_exhausted(self, kind: JobKind, job_id: str, reason: str = "DELIVERY_EXHAUSTED") -> dict | None:
        """DLQ handler: SQS gave up on the message. PENDING/RUNNING -> FAILED; a job that already finished is left alone."""
        spec = _spec(kind)
        for _ in range(_RETRIES):
            item = self._load(spec, job_id, include_expired=True)
            if item is None or item.status not in ("PENDING", "RUNNING"):
                return None
            try:
                return self._row(spec, self._finish_failed(spec, item, reason))
            except (RevisionConflict, ConditionFailed):
                continue
        return None

    # ------------------------------------------------------------------ cancel / retry / promote

    def cancel(self, kind: JobKind, job_id: str) -> dict:
        spec = _spec(kind)
        for _ in range(_RETRIES):
            item = self._load(spec, job_id)
            if item is None:
                raise NotFound(f"{spec.kind} job not found")
            if item.status == "CANCELLED":
                return self._row(spec, item)
            if item.status != "PENDING":
                raise ConditionFailed(f"job is {item.status}; only a PENDING job can be cancelled")
            try:
                return self._row(spec, self._update(spec, item, self._status_changes(spec, "CANCELLED")))
            except (RevisionConflict, ConditionFailed):
                continue
        raise ConditionFailed("job changed while cancelling")

    def retry(self, kind: JobKind, job_id: str) -> dict:
        """FAILED (or RUNNING with an expired lease) -> PENDING with attempts reset and a fresh expiry; re-enqueued."""
        spec = _spec(kind)
        for _ in range(_RETRIES):
            item = self._load(spec, job_id, include_expired=True)
            if item is None:
                raise NotFound(f"{spec.kind} job not found")
            now = _now()
            if item.status == "PENDING":
                return self._row(spec, item)
            stale = item.status == "RUNNING" and item.lease_until is not None and item.lease_until < now
            if item.status != "FAILED" and not stale:
                raise ConditionFailed(f"job is {item.status}; only a FAILED or stale RUNNING job can be retried")
            keep = now + dt.timedelta(days=JOB_TTL_DAYS)
            gone = _present(item, "error_message", "error_message_ref", "claim_token", "lease_until", "claimed_by")
            try:
                new = self._update(spec, item, self._status_changes(spec, "PENDING", attempts=0, expires_at=keep, ttl=_epoch(keep)),
                                   remove=gone)
            except (RevisionConflict, ConditionFailed):
                continue
            self._publish(spec, str(_job_id(job_id)), new.version or 1)
            return self._row(spec, new)
        raise ConditionFailed("job changed while retrying")

    def mark_render_job_promoted(self, job_id: str, scene_spec_id: str) -> dict:
        """Write-once and idempotent: DONE, and either unpromoted or already promoted to the same scene spec."""
        spec = _SPECS["render"]
        try:
            sid = str(uuid.UUID(str(scene_spec_id)))
        except ValueError:
            raise ValidationFailed("scene_spec_id must be a UUID") from None
        for _ in range(_RETRIES):
            item = self._load(spec, job_id)
            if item is None:
                raise NotFound("render job not found")
            if item.promoted_scene_spec_id is not None:
                if str(item.promoted_scene_spec_id) == sid:
                    return self._row(spec, item)
                raise ConditionFailed(f"render job already promoted as {item.promoted_scene_spec_id}")
            if item.status != "DONE":
                raise ConditionFailed(f"render job is {item.status}, not DONE")
            try:
                return self._row(spec, self._update(spec, item, {"promoted_scene_spec_id": sid}))
            except (RevisionConflict, ConditionFailed):
                continue
        raise ConditionFailed("render job changed while marking promoted")

    # ------------------------------------------------------------------ reads

    def get_job(self, kind: JobKind, job_id: str) -> dict | None:
        spec = _spec(kind)
        item = self._load(spec, job_id)
        return None if item is None else self._row(spec, item)

    def get_research_job(self, job_id: str) -> dict | None:
        return self.get_job("research", job_id)

    def get_render_job(self, job_id: str) -> dict | None:
        return self.get_job("render", job_id)

    def list_jobs(self, kind: JobKind, *, status: str | None = None, unpromoted_only: bool = False,
                  requested_by: str | None = None, limit: int = 50, next_token: str | None = None) -> dict:
        """Newest first via GSI1 (``<KIND>#STATUS#<status>``). Without ``status`` the five status partitions are merged and
        only a first page is returned (``next_token`` is None); with a status the listing is fully paginated."""
        spec, now, limit = _spec(kind), _now(), max(1, min(int(limit), 200))
        if status is not None and status not in STATUSES:
            raise ValidationFailed(f"unknown status {status!r}", status=status)

        def keep(item) -> bool:
            return (item.expires_at > now and (not unpromoted_only or getattr(item, "promoted_scene_spec_id", None) is None)
                    and (requested_by is None or item.requested_by == requested_by))

        if status is None:
            if next_token:
                raise ValidationFailed("next_token needs a status filter")
            merged = [i for s in STATUSES for i in typed.query(spec.model, _gsi1pk(spec, s), index="GSI1", forward=False, limit=limit).items
                      if keep(i)]
            merged.sort(key=lambda i: i.GSI1SK or "", reverse=True)
            return {"items": [self._row(spec, i) for i in merged[:limit]], "next_token": None}
        items: list = []
        token = next_token
        for _ in range(20):
            page = typed.query(spec.model, _gsi1pk(spec, status), index="GSI1", forward=False, limit=limit - len(items), next_token=token)
            items += [i for i in page.items if keep(i)]
            token = page.next_token
            if token is None or len(items) >= limit:
                break
        return {"items": [self._row(spec, i) for i in items], "next_token": token}

    def list_research_jobs(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        return self.list_jobs("research", status=status, limit=limit)["items"]

    def list_render_jobs(self, *, status: str | None = None, unpromoted_only: bool = False, limit: int = 50) -> list[dict]:
        return self.list_jobs("render", status=status, unpromoted_only=unpromoted_only, limit=limit)["items"]

    def list_stale_jobs(self, kind: JobKind, *, limit: int = 100) -> list[dict]:
        """RUNNING jobs whose lease expired (sweep for the DLQ handler / operators)."""
        spec, now = _spec(kind), _now()
        page = typed.query(spec.model, _gsi1pk(spec, "RUNNING"), index="GSI1", forward=False, limit=limit)
        return [self._row(spec, i) for i in page.items if i.lease_until is not None and i.lease_until < now]
