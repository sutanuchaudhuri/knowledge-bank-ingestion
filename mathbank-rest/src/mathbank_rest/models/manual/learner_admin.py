"""Items and constants of the learner admin plane (requirement 71 WP5, requirement 70 C1 sections 5 and 6).

* ``StudentDirectoryRow`` the GSI2 ``STUDENT_DIR`` projection of a PROFILE (never ``password_hash``). It is a read model: the real
  profile model (``learner_identity.LearnerProfile``) requires the hash, which the index does not project.
* ``LearnerTombstone`` ``ERASED#<sid>`` / ``TOMBSTONE``: the durable erasure job and, once done, the proof of erasure (no PII). While
  the job is ``REQUESTED`` it is listed in the sparse GSI1 partition ``ERASURE#REQUESTED``, which is how the worker finds work without
  a scan.
* ``LearnerApplied`` stream-consumer idempotency sentinel. The design keeps it under ``STUDENT#<sid>``; it lives in its own
  ``APPLIED#<consumer>#<shard>`` partitions so that a consumer reacting to the erasure's own REMOVE records cannot re-create an item
  in the erased partition.
* ``LearnerAdminAudit`` the ``mb-audit`` record of a staff mutation of a student (same keys as every other learner audit entry).
"""
from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field, StrictBool, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, UtcDateTime
from mathbank_rest.models.manual.learner_routes import FeedbackAudit

_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

ERASURE_STATUSES = ("REQUESTED", "DONE")
ERASURE_PENDING_PK = "ERASURE#REQUESTED"

# learner-analytics column of an EVENT type (requirement 70 C1 section 5); STEP_EVALUATED also counts steps_succeeded when
# payload.result is SUCCESS. Shared by the stream consumer and the rebuild (ANL-E03).
DAILY_EVENT_COLUMNS: dict[str, str] = {
    "ATTEMPT_STARTED": "attempts_started",
    "ATTEMPT_COMPLETED": "attempts_completed",
    "ATTEMPT_ABANDONED": "attempts_abandoned",
    "STEP_EVALUATED": "steps_evaluated",
    "GAP_DIAGNOSED": "gaps_diagnosed",
    "GAP_HYPOTHESIS_CREATED": "knowledge_gaps_created",
    "KNOWLEDGE_GAP_CREATED": "knowledge_gaps_created",
    "RECOVERY_PLAN_CREATED": "recovery_plans_created",
    "RECOVERY_PLAN_COMPLETED": "recovery_plans_completed",
}


class StudentDirectoryRow(DdbItem):
    """An item of GSI2 ``STUDENT_DIR`` as projected (INCLUDE): identity columns and ``search_blob``, no secrets. ``email_lc``, ``cognito_sub`` and ``password_hash`` are NOT projected."""

    CTX: ClassVar[str] = "learner"           # unregistered model: typed.query needs the context
    type: Literal["PROFILE"] = "PROFILE"
    PK: str = Field(pattern=f"^STUDENT#{_UUID}$")
    SK: str = Field(pattern="^PROFILE$")
    student_id: StrictStr
    email: StrictStr
    first_name: StrictStr
    last_name: StrictStr
    display_name: StrictStr
    status: StrictStr
    created_at: UtcDateTime
    is_anonymous: StrictBool = False
    search_blob: StrictStr = ""


class LearnerTombstone(DdbItem, ctx="learner", item_type="TOMBSTONE"):
    type: Literal["TOMBSTONE"] = "TOMBSTONE"
    PK: str = Field(pattern=f"^ERASED#{_UUID}$")
    SK: str = Field(pattern="^TOMBSTONE$")
    student_id: StrictStr
    job_id: StrictStr = Field(min_length=8, max_length=64)
    status: Literal["REQUESTED", "DONE"]
    requested_at: UtcDateTime
    requested_by: StrictStr = Field(max_length=200)
    reason: StrictStr | None = Field(default=None, max_length=500)
    erased_at: UtcDateTime | None = None
    report: dict[str, Any] | None = None             # counts only, never content


class LearnerApplied(DdbItem, ctx="learner", item_type="APPLIED"):
    type: Literal["APPLIED"] = "APPLIED"
    PK: str = Field(pattern=r"^APPLIED#[a-z][a-z-]*#[0-9a-f]{2}$")
    SK: str = Field(min_length=1, max_length=256)
    consumer: StrictStr
    ttl: StrictInt = Field(ge=0)


class LearnerAdminAudit(FeedbackAudit):
    """Audit record of a staff mutation of a student or one of its items (``ENTITY#STUDENT#<sid>``)."""
