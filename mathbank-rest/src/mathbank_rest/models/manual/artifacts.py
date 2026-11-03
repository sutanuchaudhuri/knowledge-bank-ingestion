"""Hand-written item models for ``mb-artifacts`` (artifact requests, bundles, tags, validation results).

Source: ``mathbank-db/aws/dynamo/specs/media.py`` (``ARTIFACTS`` mappings + ``OFFLOAD``) and requirement 70 §13 (C4).
They are hand-written because the context had no data when the generated models were built, so there was nothing
to infer them from. ``AUDIT`` and ``RATE`` are design-only: the migration never emits them, REST writes them.
"""
from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, JsonDoc, S3Ref, UtcDateTime

_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_BUNDLE_PK = f"^BUNDLE#{_UUID}$"
_SHA256 = "^[0-9a-f]{64}$"


class ArtifactsBundleAsset(JsonDoc):
    artifact_asset_id: UUID
    asset_type: StrictStr  # SVG_DIAGRAM | LATEX_CARD | FRAME_SEQUENCE | MANIM_EXPORT_SPEC
    bucket: StrictStr
    created_at: UtcDateTime
    element_ids: list[Any]
    height: StrictInt | None = None
    mime_type: StrictStr
    object_key: StrictStr
    render_format: StrictStr
    sha256: StrictStr
    size_bytes: StrictInt
    width: StrictInt | None = None


class ArtifactsBundleTags(JsonDoc):
    concept: list[StrictStr]
    skill: list[StrictStr]
    theorem: list[StrictStr]


class ArtifactsBundleEmbedding(JsonDoc):
    """Vector itself lives in S3 Vectors; only its coordinates are kept on the item."""

    dimensions: StrictInt
    index_name: StrictStr
    indexed_at: UtcDateTime
    model: StrictStr
    search_text_sha256: StrictStr


class ArtifactsArtreq(DdbItem, ctx="artifacts", item_type="ARTREQ"):
    type: Literal["ARTREQ"] = "ARTREQ"
    PK: str = Field(pattern=f"^(STUDENT#{_UUID}|STAFF#ARTIFACTS)$")
    SK: str = Field(pattern=f"^ARTREQ#[^#]*#{_UUID}$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"spec"})
    artifact_request_id: UUID
    bundle_id: UUID | None = None
    created_at: UtcDateTime
    created_by: StrictStr
    goal_type: StrictStr
    linked_problem_id: UUID | None = None
    linked_solution_step_id: StrictStr | None = None
    owner_student_id: UUID | None = None
    request_source: StrictStr
    spec: dict[str, Any] | None = None
    spec_sha256: str = Field(pattern=_SHA256)
    status: StrictStr  # REQUESTED | GENERATED (design adds REJECTED | FAILED)
    subject: StrictStr  # GEOMETRY | ALGEBRA | COMBINATORICS | NUMBER_THEORY
    subtopic: StrictStr | None = None
    topic: StrictStr
    spec_ref: S3Ref | None = None
    # design-only (C4 §3), written by the staff decision path
    decided_at: UtcDateTime | None = None
    decided_by: StrictStr | None = None
    status_reason: StrictStr | None = None


class ArtifactsBundle(DdbItem, ctx="artifacts", item_type="BUNDLE"):
    type: Literal["BUNDLE"] = "BUNDLE"
    PK: str = Field(pattern=_BUNDLE_PK)
    SK: str = Field(pattern="^META$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"source_spec", "search_text", "metadata", "assets"})
    OFFLOAD_DOCS: ClassVar[dict[str, Any]] = {"assets": list[ArtifactsBundleAsset]}
    annotation_profile_id: StrictStr
    artifact_bundle_id: UUID
    artifact_request_id: UUID
    asset_types: list[StrictStr]
    assets: list[ArtifactsBundleAsset] | None = None
    bundle_version: StrictInt
    child_count: StrictInt
    created_at: UtcDateTime
    difficulty_band: StrictStr
    embedding: ArtifactsBundleEmbedding | None = None
    generated_by: StrictStr
    generator_version: StrictStr | None = None  # LEFT JOIN artifact_lineage
    grade_band: StrictStr
    manifest_asset_id: UUID | None = None
    metadata: dict[str, Any] | None = None
    ordered_overlay_ids: list[UUID] | None = None
    owner_student_id: UUID | None = None
    parent_bundle_id: UUID | None = None
    published_at: UtcDateTime | None = None
    root_bundle_id: UUID
    rule_profile_id: StrictStr
    search_text: StrictStr | None = None
    search_text_sha256: str = Field(pattern=_SHA256)
    source_spec: dict[str, Any] | None = None  # frozen copy of the request plan
    source_spec_sha256: StrictStr | None = None
    status: StrictStr  # DRAFT | PUBLISHED (design adds RETIRED)
    subject: StrictStr
    subtopic: StrictStr | None = None
    summary: StrictStr
    tags: ArtifactsBundleTags
    title: StrictStr
    topic: StrictStr
    assets_ref: S3Ref | None = None
    metadata_ref: S3Ref | None = None
    search_text_ref: S3Ref | None = None
    source_spec_ref: S3Ref | None = None
    # design-only (C4 §3), written by publish / retire
    published_by: StrictStr | None = None
    retired_at: UtcDateTime | None = None
    retired_by: StrictStr | None = None
    retired_reason: StrictStr | None = None


class ArtifactsBundletag(DdbItem, ctx="artifacts", item_type="BUNDLETAG"):
    type: Literal["BUNDLETAG"] = "BUNDLETAG"
    PK: str = Field(pattern=_BUNDLE_PK)
    SK: str = Field(pattern=r"^TAG#(concept|skill|theorem)#[\s\S]+$")
    artifact_bundle_id: UUID
    asset_types: list[StrictStr]
    difficulty_band: StrictStr
    status: StrictStr
    subject: StrictStr
    tag: StrictStr
    tag_type: StrictStr  # concept | skill | theorem


class ArtifactsUnique(DdbItem, ctx="artifacts", item_type="UNIQUE"):
    """Uniqueness sentinels: one bundle per request, one bundle per (root, version)."""

    type: Literal["UNIQUE"] = "UNIQUE"
    PK: str = Field(pattern=f"^UNIQUE#(bundle_request#{_UUID}|bundle_root_version#{_UUID}#[0-9]+)$")
    SK: str = Field(pattern="^UNIQUE$")
    bundle_id: UUID


class ArtifactsValidation(DdbItem, ctx="artifacts", item_type="VALIDATION"):
    type: Literal["VALIDATION"] = "VALIDATION"
    PK: str = Field(pattern=_BUNDLE_PK)
    SK: str = Field(pattern=f"^VALIDATION#[^#]*#{_UUID}$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"report"})
    artifact_bundle_id: UUID
    created_at: UtcDateTime
    report: Any | None = None
    valid: StrictBool
    validation_result_id: UUID
    validator_version: StrictStr
    report_ref: S3Ref | None = None
    actor: StrictStr | None = None  # design-only (C4 §3)


class ArtifactsAudit(DdbItem, ctx="artifacts", item_type="AUDIT"):
    """Design-only (C4 §3): staff mutation audit written in the same transaction; never emitted by the migration."""

    type: Literal["AUDIT"] = "AUDIT"
    PK: str = Field(pattern="^AUDIT#ARTIFACTS#[0-9]{6}$")
    SK: str = Field(pattern="^[^#]*#[^#]*$")
    action: StrictStr
    actor: StrictStr
    after_sha256: str | None = Field(default=None, pattern=_SHA256)
    before_sha256: str | None = Field(default=None, pattern=_SHA256)
    target: StrictStr | None = None


class ArtifactsRate(DdbItem, ctx="artifacts", item_type="RATE"):
    """Design-only (C4 §2 A8): per-student hourly embedding-request counter, ttl = +2 h."""

    type: Literal["RATE"] = "RATE"
    PK: str = Field(pattern=f"^RATE#STUDENT#{_UUID}$")
    SK: str = Field(pattern="^EMBED#[0-9]{10}$")
    count: StrictInt


ITEM_MODELS = [ArtifactsArtreq, ArtifactsAudit, ArtifactsBundle, ArtifactsBundletag, ArtifactsRate,
               ArtifactsUnique, ArtifactsValidation]
ArtifactsItem = Annotated[
    ArtifactsArtreq | ArtifactsAudit | ArtifactsBundle | ArtifactsBundletag | ArtifactsRate
    | ArtifactsUnique | ArtifactsValidation,
    Field(discriminator="type")]
