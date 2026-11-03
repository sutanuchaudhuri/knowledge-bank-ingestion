"""Hand-written item models for ``mb-media`` (attempt media: submissions, assets, transcripts, approvals,
assessments, events).

Source: ``mathbank-db/aws/dynamo/specs/media.py`` (``MEDIA`` mappings + ``OFFLOAD``) and requirement 70 §13 (C4).
They are hand-written because the context had no data when the generated models were built, so there was nothing
to infer them from. ``AUDIT`` is design-only: the migration never emits it, REST writes it (C4 §3).
"""
from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal
from uuid import UUID

from pydantic import Field, StrictFloat, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, JsonDoc, S3Ref, UtcDateTime

_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_STUDENT_PK = f"^STUDENT#{_UUID}$"
_SUBMISSION = f"^SUBMISSION#{_UUID}"
_SHA256 = "^[0-9a-f]{64}$"


class MediaTranscriptStep(JsonDoc):
    step_id: UUID
    ordinal: StrictInt
    plain_text: StrictStr
    latex_text: StrictStr
    step_type: StrictStr
    confidence: StrictFloat
    evidence_ids: list[UUID]


class MediaTranscriptRegion(JsonDoc):
    region_id: UUID
    media_asset_id: UUID
    page_number: StrictInt | None = None
    x_norm: StrictFloat | None = None
    y_norm: StrictFloat | None = None
    width_norm: StrictFloat | None = None
    height_norm: StrictFloat | None = None
    start_ms: StrictInt | None = None
    end_ms: StrictInt | None = None
    region_type: StrictStr
    reading_order: StrictInt
    confidence: StrictFloat
    first_version: StrictInt


class MediaAssessment(JsonDoc):
    assessment_id: UUID
    step_id: UUID
    assessment_version: StrictInt
    correctness: StrictStr  # CORRECT | PARTIALLY_CORRECT | INCORRECT | UNJUSTIFIED | UNCERTAIN
    alignment_type: StrictStr
    canonical_solution_step_id: StrictStr | None = None
    confidence: StrictFloat
    why: StrictStr
    failure_mode: StrictStr
    next_action: StrictStr
    evidence_ids: list[StrictStr]  # jsonb in the source, not constrained to uuid there
    model_profile: StrictStr
    created_at: UtcDateTime


class MediaEvent(JsonDoc):
    sequence: StrictInt
    event_type: StrictStr
    transcription_version: StrictInt
    approved_version: StrictInt
    payload: dict[str, Any]
    created_at: UtcDateTime


class MediaSubmission(DdbItem, ctx="media", item_type="SUBMISSION"):
    type: Literal["SUBMISSION"] = "SUBMISSION"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"{_SUBMISSION}$")
    active_original_count: StrictInt
    approved_version: StrictInt
    canonical_code: StrictStr | None = None  # LEFT JOIN core.problem: absent when the problem is gone
    created_at: UtcDateTime
    error_code: StrictStr | None = None
    last_sequence: StrictInt
    problem_id: UUID
    status: StrictStr  # RECEIVED | MEDIA_NORMALIZED | TRANSCRIBING | TRANSCRIPTION_READY | STUDENT_REVIEWING |
    #                    APPROVED | ALIGNING | CRITIQUING | VISUAL_GROUNDING | READY | FAILED
    student_id: UUID
    submission_id: UUID
    transcription_version: StrictInt


class MediaSubref(DdbItem, ctx="media", item_type="SUBREF"):
    type: Literal["SUBREF"] = "SUBREF"
    PK: str = Field(pattern=f"{_SUBMISSION}$")
    SK: str = Field(pattern="^REF$")
    owner_pk: str = Field(pattern=_STUDENT_PK)
    student_id: UUID


class MediaAsset(DdbItem, ctx="media", item_type="ASSET"):
    type: Literal["ASSET"] = "ASSET"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"{_SUBMISSION}#ASSET#{_UUID}$")
    asset_type: StrictStr  # IMAGE | PDF | AUDIO | VIDEO
    bucket: StrictStr
    created_at: UtcDateTime
    duration_ms: StrictInt | None = None
    media_asset_id: UUID
    mime_type: StrictStr
    object_key: StrictStr
    page_count: StrictInt | None = None
    parent_asset_id: UUID | None = None
    purged_at: UtcDateTime | None = None
    retention_class: StrictStr
    role: StrictStr  # ORIGINAL | PAGE | KEYFRAME | AUDIO
    sha256: str = Field(pattern=_SHA256)
    size_bytes: StrictInt
    submission_id: UUID
    timestamp_ms: StrictInt | None = None


class MediaTranscript(DdbItem, ctx="media", item_type="TRANSCRIPT"):
    """Immutable per-version item; ``version`` (base field) is the transcription version, not a CAS counter."""

    type: Literal["TRANSCRIPT"] = "TRANSCRIPT"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"{_SUBMISSION}#TX#[0-9]{{8}}$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"steps", "regions", "machine_output"})
    OFFLOAD_DOCS: ClassVar[dict[str, Any]] = {
        "steps": list[MediaTranscriptStep], "regions": list[MediaTranscriptRegion]}
    body_sha256: str = Field(pattern=_SHA256)
    created_at: UtcDateTime
    machine_output: Any | None = None  # MACHINE source only
    model_profile: StrictStr | None = None
    regions: list[MediaTranscriptRegion] | None = None
    source: StrictStr  # MACHINE | STUDENT
    steps: list[MediaTranscriptStep] | None = None
    submission_id: UUID
    machine_output_ref: S3Ref | None = None
    regions_ref: S3Ref | None = None
    steps_ref: S3Ref | None = None
    # design (C4 §3) names one ``body_ref`` for steps+regions; the migration offloads steps/regions separately
    body_ref: S3Ref | None = None


class MediaApproval(DdbItem, ctx="media", item_type="APPROVAL"):
    type: Literal["APPROVAL"] = "APPROVAL"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"{_SUBMISSION}#APPROVAL#[0-9]{{8}}$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"student_edit_summary"})
    approved_at: UtcDateTime
    approved_version: StrictInt
    learner_attempt_id: UUID
    student_edit_summary: StrictStr | None = None
    submission_id: UUID
    transcription_version: StrictInt
    student_edit_summary_ref: S3Ref | None = None


class MediaTxapproved(DdbItem, ctx="media", item_type="TXAPPROVED"):
    """UNIQUE(submission, transcription_version) sentinel."""

    type: Literal["TXAPPROVED"] = "TXAPPROVED"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"{_SUBMISSION}#UNIQUE#approved_tv#[0-9]{{8}}$")
    approved_version: StrictInt
    submission_id: UUID


class MediaLattemptref(DdbItem, ctx="media", item_type="LATTEMPTREF"):
    """learner_attempt_id → owner pointer (= UNIQUE(learner_attempt_id))."""

    type: Literal["LATTEMPTREF"] = "LATTEMPTREF"
    PK: str = Field(pattern=f"^LATTEMPT#{_UUID}$")
    SK: str = Field(pattern="^REF$")
    approved_version: StrictInt
    owner_pk: str = Field(pattern=_STUDENT_PK)
    submission_id: UUID
    transcription_version: StrictInt


class MediaAsmtrun(DdbItem, ctx="media", item_type="ASMTRUN"):
    type: Literal["ASMTRUN"] = "ASMTRUN"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"{_SUBMISSION}#ASMT#[0-9]{{8}}#[0-9]{{8}}$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"assessments"})
    OFFLOAD_DOCS: ClassVar[dict[str, Any]] = {"assessments": list[MediaAssessment]}
    actor_id: StrictStr
    actor_type: StrictStr  # STAFF (source INSTRUCTOR) | SYSTEM (source AI)
    approved_version: StrictInt
    assessments: list[MediaAssessment] | None = None
    created_at: UtcDateTime
    run: StrictInt
    source: StrictStr  # AI | INSTRUCTOR
    submission_id: UUID
    transcription_version: StrictInt
    assessments_ref: S3Ref | None = None
    # design (C4 §3) names ``body_ref``; the migration offloads ``assessments`` itself
    body_ref: S3Ref | None = None


class MediaEvtblock(DdbItem, ctx="media", item_type="EVTBLOCK"):
    type: Literal["EVTBLOCK"] = "EVTBLOCK"
    PK: str = Field(pattern=_STUDENT_PK)
    SK: str = Field(pattern=f"{_SUBMISSION}#EVT#[0-9]{{12}}$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"events"})
    OFFLOAD_DOCS: ClassVar[dict[str, Any]] = {"events": list[MediaEvent]}
    events: list[MediaEvent] | None = None
    first_seq: StrictInt
    last_seq: StrictInt
    submission_id: UUID
    events_ref: S3Ref | None = None


class MediaAudit(DdbItem, ctx="media", item_type="AUDIT"):
    """Design-only (C4 §3): staff mutation audit written in the same transaction; never emitted by the migration."""

    type: Literal["AUDIT"] = "AUDIT"
    PK: str = Field(pattern="^AUDIT#MEDIA#[0-9]{6}$")
    SK: str = Field(pattern="^[^#]*#[^#]*$")
    action: StrictStr
    actor: StrictStr
    after_sha256: str | None = Field(default=None, pattern=_SHA256)
    before_sha256: str | None = Field(default=None, pattern=_SHA256)
    target: StrictStr | None = None


ITEM_MODELS = [MediaApproval, MediaAsmtrun, MediaAsset, MediaAudit, MediaEvtblock, MediaLattemptref,
               MediaSubmission, MediaSubref, MediaTranscript, MediaTxapproved]
MediaItem = Annotated[
    MediaApproval | MediaAsmtrun | MediaAsset | MediaAudit | MediaEvtblock | MediaLattemptref
    | MediaSubmission | MediaSubref | MediaTranscript | MediaTxapproved,
    Field(discriminator="type")]
