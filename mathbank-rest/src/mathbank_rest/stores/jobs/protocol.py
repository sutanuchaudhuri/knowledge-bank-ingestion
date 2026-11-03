"""Contract of the ``jobs`` store (requirement 71 WP3): Studio research and render jobs.

Two backends implement it:

* ``PostgresJobsStore``  today's behaviour. The queue itself (``FOR UPDATE SKIP LOCKED``) lives in
  mathbank-manim-studio; REST only ever talked to the Studio over HTTP, so this backend is that HTTP client and the
  worker operations are not available on it.
* ``DynamoDBJobsStore``  ``mb-jobs`` items claimed by conditional updates, woken by SQS messages.

Job views are dicts in the column shape of ``studio.scene_research_job`` / ``studio.video_render_job`` (timestamps are
``datetime``), which is what the Studio already consumes.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, Protocol

from mathbank_rest.jobs_queue import JobKind
from mathbank_rest.stores.errors import ConditionFailed


class LeaseLost(ConditionFailed):
    """The caller no longer holds the job (lease expired and re-claimed, cancelled, or never claimed). A worker that
    gets this must drop its result and delete any output it produced for this run."""

    code = "lease_lost"


@dataclasses.dataclass(frozen=True)
class JobClaim:
    job_id: str
    kind: JobKind
    claim_token: str
    worker_id: str
    attempts: int
    lease_until: dt.datetime
    version: int
    payload: dict[str, Any]  # research: topic, context_json; render: scene_spec_json


class JobsStore(Protocol):
    backend: str

    def create_research_job(self, topic: str, context: dict | None = None, *, requested_by: str | None = None) -> dict: ...

    def create_render_job(self, scene_spec_json: dict | None = None, source_research_job_id: str | None = None, *,
                          requested_by: str | None = None) -> dict: ...

    def get_job(self, kind: JobKind, job_id: str) -> dict | None: ...

    def get_research_job(self, job_id: str) -> dict | None: ...

    def get_render_job(self, job_id: str) -> dict | None: ...

    def list_jobs(self, kind: JobKind, *, status: str | None = None, unpromoted_only: bool = False,
                  requested_by: str | None = None, limit: int = 50, next_token: str | None = None) -> dict: ...

    def list_render_jobs(self, *, status: str | None = None, unpromoted_only: bool = False, limit: int = 50) -> list[dict]: ...

    def mark_render_job_promoted(self, job_id: str, scene_spec_id: str) -> dict: ...
