"""Job queue backends for the Studio (requirement 71 WP3).

``postgres`` (default) is today's behaviour: rows in ``studio.*``, claimed by ``FOR UPDATE SKIP LOCKED`` polling (``jobs.py``).
``dynamodb`` keeps the jobs in ``mb-jobs`` and wakes workers through SQS, using ``mathbank_rest.stores.jobs`` (conditional
claims with a lease, heartbeats, retries, DLQ); nothing then touches Postgres, so Neon can suspend while the Studio is idle
and the EventBridge ``rate(1 minute)`` poll is not needed (an SQS trigger invokes ``lambda_handler.worker_handler``).

Both backends return job dicts in the column shape of the ``studio.*`` tables, so ``main.py`` renders them identically.
Select with ``STUDIO_JOBS_BACKEND=dynamodb``; it needs ``mathbank-rest`` importable and ``boto3`` (``.[dynamodb]``).
"""
from __future__ import annotations

import dataclasses
import logging
import os
import socket
from functools import lru_cache
from typing import Any

from mathbank_manim_studio import jobs
from mathbank_manim_studio.config import get_settings
from mathbank_manim_studio.db import connection

logger = logging.getLogger("mathbank_manim_studio.jobs_backend")


class JobConflict(Exception):
    """The requested transition is not allowed in the job's current state (HTTP 409)."""


class ClaimLost(Exception):
    """This worker no longer holds the job (lease expired and re-claimed, or cancelled): drop the result."""


@dataclasses.dataclass
class Claimed:
    job_id: str
    kind: str                       # research | render
    payload: dict[str, Any]         # research: topic, context_json; render: scene_spec_json
    claim_token: str | None = None
    receipt: str | None = None      # SQS receipt handle (dynamodb backend, polling workers only)


class PostgresJobsBackend:
    """Today's behaviour, unchanged: the SQL in ``jobs.py`` over a pooled Postgres connection."""

    name = "postgres"
    supports_heartbeat = False

    def create_research_job(self, topic: str, context: dict) -> dict:
        with connection() as conn:
            return jobs.get_research_job(conn, jobs.create_research_job(conn, topic, context))

    def get_research_job(self, job_id: str) -> dict | None:
        with connection() as conn:
            return jobs.get_research_job(conn, job_id)

    def create_render_job(self, scene_spec_json: dict, source_research_job_id: str | None) -> dict:
        with connection() as conn:
            return jobs.get_render_job(conn, jobs.create_render_job(
                conn, scene_spec_json=scene_spec_json, source_research_job_id=source_research_job_id))

    def get_render_job(self, job_id: str) -> dict | None:
        with connection() as conn:
            return jobs.get_render_job(conn, job_id)

    def list_render_jobs(self, *, status: str | None, unpromoted_only: bool) -> list[dict]:
        with connection() as conn:
            return jobs.list_render_jobs(conn, status=status, unpromoted_only=unpromoted_only)

    def mark_render_job_promoted(self, job_id: str, scene_spec_id: str) -> dict | None:
        with connection() as conn:
            if jobs.get_render_job(conn, job_id) is None:
                return None
            jobs.mark_render_job_promoted(conn, job_id, scene_spec_id)
            return jobs.get_render_job(conn, job_id)

    # worker side -------------------------------------------------------------------------------------------------

    def claim(self, kind: str, wait_seconds: int = 0) -> Claimed | None:
        with connection() as conn:
            if kind == "research":
                job = jobs.claim_pending_research_job(conn)
                return job and Claimed(str(job["scene_research_job_id"]), kind,
                                       {"topic": job["topic"], "context_json": job["context_json"]})
            job = jobs.claim_pending_render_job(conn)
            return job and Claimed(str(job["video_render_job_id"]), kind, {"scene_spec_json": job["scene_spec_json"]})

    def claim_message(self, kind: str, job_id: str) -> Claimed | None:
        raise NotImplementedError("SQS-triggered claims need STUDIO_JOBS_BACKEND=dynamodb")

    def heartbeat(self, claimed: Claimed) -> None:
        return None

    def complete_research(self, claimed: Claimed, scene_spec: dict, explanation: str) -> None:
        with connection() as conn:
            jobs.complete_research_job(conn, claimed.job_id, scene_spec, explanation)

    def complete_render(self, claimed: Claimed, video_object_key: str, video_duration_ms: int) -> None:
        with connection() as conn:
            jobs.complete_render_job(conn, claimed.job_id, video_object_key, video_duration_ms)

    def fail(self, claimed: Claimed, message: str) -> None:
        with connection() as conn:
            (jobs.fail_research_job if claimed.kind == "research" else jobs.fail_render_job)(conn, claimed.job_id, message)

    def ack(self, claimed: Claimed) -> None:
        return None

    def mark_exhausted(self, kind: str, job_id: str) -> None:
        raise NotImplementedError("dead-letter handling needs STUDIO_JOBS_BACKEND=dynamodb")


class DynamoJobsBackend:
    """``mb-jobs`` + SQS through ``mathbank_rest.stores.jobs.DynamoDBJobsStore``. Never opens a Postgres connection."""

    name = "dynamodb"
    supports_heartbeat = True

    def __init__(self, store: Any = None, worker_id: str | None = None):
        if store is None:
            try:
                from mathbank_rest.stores.jobs import DynamoDBJobsStore
            except ImportError as exc:  # pragma: no cover - environment problem, reported clearly
                raise RuntimeError("STUDIO_JOBS_BACKEND=dynamodb needs mathbank-rest importable and boto3 "
                                   "(pip install -e ../mathbank-rest && pip install -e '.[dynamodb]')") from exc
            store = DynamoDBJobsStore()
        from mathbank_rest.stores.errors import ConditionFailed, NotFound
        from mathbank_rest.stores.jobs.protocol import LeaseLost

        self.store, self._lost, self._conflict, self._missing = store, LeaseLost, ConditionFailed, NotFound
        self.worker_id = worker_id or f"studio-{socket.gethostname()}-{os.getpid()}"

    @property
    def heartbeat_interval(self) -> float:
        from mathbank_rest.stores.jobs.dynamodb import LEASE_SECONDS

        return LEASE_SECONDS / 3

    def create_research_job(self, topic: str, context: dict) -> dict:
        return self.store.create_research_job(topic, context)

    def get_research_job(self, job_id: str) -> dict | None:
        return self.store.get_research_job(job_id)

    def create_render_job(self, scene_spec_json: dict, source_research_job_id: str | None) -> dict:
        return self.store.create_render_job(scene_spec_json, source_research_job_id)

    def get_render_job(self, job_id: str) -> dict | None:
        return self.store.get_render_job(job_id)

    def list_render_jobs(self, *, status: str | None, unpromoted_only: bool) -> list[dict]:
        return self.store.list_render_jobs(status=status, unpromoted_only=unpromoted_only)

    def mark_render_job_promoted(self, job_id: str, scene_spec_id: str) -> dict | None:
        try:
            return self.store.mark_render_job_promoted(job_id, scene_spec_id)
        except self._missing:
            return None
        except self._conflict as exc:
            raise JobConflict(exc.message) from None

    # worker side -------------------------------------------------------------------------------------------------

    def _claimed(self, kind: str, job_id: str, receipt: str | None) -> Claimed | None:
        c = self.store.claim(kind, job_id, self.worker_id)
        return None if c is None else Claimed(c.job_id, kind, c.payload, c.claim_token, receipt)

    def claim(self, kind: str, wait_seconds: int = 0) -> Claimed | None:
        """Receive wake-ups and claim the first job that is really claimable; duplicates and stale messages are deleted."""
        for r in self.store.queue.receive(kind, max_messages=1, wait_seconds=wait_seconds):
            if r.message is None:
                continue  # poison message: left in flight so SQS moves it to the DLQ
            claimed = self._claimed(kind, str(r.message.job_id), r.receipt_handle)
            if claimed is not None:
                return claimed
            self.store.queue.delete(kind, r.receipt_handle)
        return None

    def claim_message(self, kind: str, job_id: str) -> Claimed | None:
        """SQS-triggered Lambda path: the runtime owns the message, so there is no receipt to delete."""
        return self._claimed(kind, job_id, None)

    def heartbeat(self, claimed: Claimed) -> None:
        try:
            lease = self.store.heartbeat(claimed.kind, claimed.job_id, claimed.claim_token)
        except self._lost:
            raise ClaimLost(claimed.job_id) from None
        if claimed.receipt:
            self.store.queue.extend_visibility(claimed.kind, claimed.receipt, int((lease - _now()).total_seconds()) + 30)

    def complete_research(self, claimed: Claimed, scene_spec: dict, explanation: str) -> None:
        try:
            self.store.complete_research_job(claimed.job_id, claimed.claim_token, scene_spec, explanation)
        except self._lost:
            raise ClaimLost(claimed.job_id) from None

    def complete_render(self, claimed: Claimed, video_object_key: str, video_duration_ms: int) -> None:
        try:
            self.store.complete_render_job(claimed.job_id, claimed.claim_token, video_object_key, video_duration_ms)
        except self._lost:
            raise ClaimLost(claimed.job_id) from None

    def fail(self, claimed: Claimed, message: str) -> None:
        try:
            self.store.fail(claimed.kind, claimed.job_id, claimed.claim_token, message)
        except self._lost:
            raise ClaimLost(claimed.job_id) from None

    def ack(self, claimed: Claimed) -> None:
        """Delete the SQS message once the job is settled (done, failed, or no longer ours)."""
        if claimed.receipt:
            try:
                self.store.queue.delete(claimed.kind, claimed.receipt)
            except Exception:  # noqa: BLE001 - an already-expired receipt only means the message was redelivered
                logger.warning("could not delete SQS message for %s %s", claimed.kind, claimed.job_id, exc_info=True)

    def mark_exhausted(self, kind: str, job_id: str) -> None:
        self.store.fail_exhausted(kind, job_id)


def _now():
    import datetime as dt

    return dt.datetime.now(dt.UTC)


@lru_cache
def get_backend() -> PostgresJobsBackend | DynamoJobsBackend:
    name = get_settings().studio_jobs_backend.strip().lower()
    if name == "dynamodb":
        return DynamoJobsBackend()
    if name != "postgres":
        raise RuntimeError(f"STUDIO_JOBS_BACKEND must be 'postgres' or 'dynamodb', got {name!r}")
    return PostgresJobsBackend()
