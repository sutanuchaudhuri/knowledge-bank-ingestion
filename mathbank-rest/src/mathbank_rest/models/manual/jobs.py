"""Hand-written item models for ``mb-jobs`` (Manim Studio research and render jobs).

Source: ``mathbank-db/aws/dynamo/specs/media.py`` (``JOBS`` mappings + ``OFFLOAD``) and requirement 70 §13 (C4).
They are hand-written because the context had no data when the generated models were built, so there was nothing
to infer them from.
"""
from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal
from uuid import UUID

from pydantic import Field, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, S3Ref, UtcDateTime

_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class JobsResearchjob(DdbItem, ctx="jobs", item_type="RESEARCHJOB"):
    type: Literal["RESEARCHJOB"] = "RESEARCHJOB"
    PK: str = Field(pattern=f"^RESEARCH#{_UUID}$")
    SK: str = Field(pattern="^META$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset(
        {"context_json", "result_scene_spec", "result_explanation", "error_message"})
    attempts: StrictInt
    context_json: dict[str, Any] | None = None
    created_at: UtcDateTime
    error_message: StrictStr | None = None
    expires_at: UtcDateTime
    result_explanation: StrictStr | None = None
    result_scene_spec: dict[str, Any] | None = None
    scene_research_job_id: UUID
    status: StrictStr  # PENDING | RUNNING | DONE | FAILED (design adds CANCELLED)
    topic: StrictStr
    context_json_ref: S3Ref | None = None
    error_message_ref: S3Ref | None = None
    result_explanation_ref: S3Ref | None = None
    result_scene_spec_ref: S3Ref | None = None
    # design-only (C4 §3): worker lease / claim written by JobStore.claim
    claim_token: StrictStr | None = None
    lease_until: UtcDateTime | None = None
    requested_by: StrictStr | None = None


class JobsRenderjob(DdbItem, ctx="jobs", item_type="RENDERJOB"):
    type: Literal["RENDERJOB"] = "RENDERJOB"
    PK: str = Field(pattern=f"^RENDER#{_UUID}$")
    SK: str = Field(pattern="^META$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"scene_spec_json", "error_message"})
    attempts: StrictInt
    created_at: UtcDateTime
    error_message: StrictStr | None = None
    expires_at: UtcDateTime
    promoted_scene_spec_id: UUID | None = None
    scene_spec_json: dict[str, Any] | None = None
    source_research_job_id: UUID | None = None
    status: StrictStr  # PENDING | RUNNING | DONE | FAILED (design adds CANCELLED)
    video_bucket: StrictStr | None = None
    video_duration_ms: StrictInt | None = None
    video_object_key: StrictStr | None = None
    video_render_job_id: UUID
    error_message_ref: S3Ref | None = None
    scene_spec_json_ref: S3Ref | None = None
    # design-only (C4 §3): same worker lease / claim attributes as RESEARCHJOB
    claim_token: StrictStr | None = None
    lease_until: UtcDateTime | None = None
    requested_by: StrictStr | None = None


ITEM_MODELS = [JobsRenderjob, JobsResearchjob]
JobsItem = Annotated[JobsRenderjob | JobsResearchjob, Field(discriminator="type")]
