"""Hand-written models for the pedagogy part of ``mb-content`` (requirement 71 WP4, requirement 70 C6 A26/A27).

* ``ContentHint`` refines the generated model: the generator only saw levels 1-2 and step ids without ``#`` in the dev data,
  but the tutor caches levels 1-5 and a step id may carry an ``#<occurrence>`` suffix. It also carries ``invalidated_at``
  (a cached hint is ignored once invalidated).
* ``ContentRouteptr`` adds the publisher's ``route_quality``.
* ``ContentVideo`` / ``ContentVtranscript`` / ``VideoTranscriptDoc``: the video tables were empty when the models were
  generated, so the items and the transcript snapshot are written from the design.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictFloat, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, JsonDoc, UtcDateTime
from mathbank_rest.models.ddb.content import ContentHint as _GeneratedHint
from mathbank_rest.models.ddb.content import ContentRouteptr as _GeneratedRouteptr


class ContentHint(_GeneratedHint, ctx="content", item_type="HINT"):
    PK: str = Field(pattern=r"^HINT#.+$")
    SK: str = Field(pattern=r"^L[1-5]#[^#]+$")
    invalidated_at: UtcDateTime | None = None


class ContentRouteptr(_GeneratedRouteptr, ctx="content", item_type="ROUTEPTR"):
    """``route_quality`` is written by the publisher (null for unscored routes, so the dev data never showed it)."""

    route_quality: StrictFloat | None = None


class ContentVideo(DdbItem, ctx="content", item_type="VIDEO"):
    type: Literal["VIDEO"] = "VIDEO"
    PK: str = Field(pattern=r"^VIDEO#[^#]+$")
    SK: str = Field(pattern=r"^META$")
    video_asset_id: StrictStr
    provider: StrictStr | None = None
    url: StrictStr | None = None
    title: StrictStr | None = None
    visual_asset_id: StrictStr | None = None
    duration_ms: StrictInt | None = None
    review_status: StrictStr | None = None
    transcript_status: StrictStr | None = None


class ContentVtranscript(DdbItem, ctx="content", item_type="VTRANSCRIPT"):
    type: Literal["VTRANSCRIPT"] = "VTRANSCRIPT"
    PK: str = Field(pattern=r"^VIDEO#[^#]+$")
    SK: str = Field(pattern=r"^TRANSCRIPT#[^#]+$")
    language_code: StrictStr
    transcript_version: StrictInt
    s3_key: StrictStr
    sha256: StrictStr
    segment_count: StrictInt


class VideoSegmentDoc(JsonDoc):
    segment_id: StrictStr
    segment_index: StrictInt
    start_ms: StrictInt
    end_ms: StrictInt
    transcript_text: StrictStr
    speaker: StrictStr | None = None


class VideoTranscriptDoc(JsonDoc):
    """``video/<video_asset_id>/<lang>/v<n>/<sha256>.json`` (immutable, content-addressed)."""

    schema_: StrictStr = Field(alias="schema")
    video_asset_id: StrictStr
    language_code: StrictStr
    version: StrictInt
    segments: list[VideoSegmentDoc]


class RouteLearnerStep(JsonDoc):
    step_index: StrictInt
    step_id: StrictStr | None = None
    instruction: dict | None = None
    hints: list[dict] = Field(default_factory=list)
    requirements: list[dict] = Field(default_factory=list)
    asset_links: list[dict] = Field(default_factory=list)


class RouteLearnerDoc(JsonDoc):
    """``releases/route/<release_id>/<sha>/learner.json``: what the route views serve; never carries ``expected_response``."""

    route_release_id: StrictStr
    approach_name: StrictStr
    approach_summary: StrictStr | None = None
    difficulty_level: StrictInt | None = None
    conceptual_load: StrictInt | None = None
    algebraic_load: StrictInt | None = None
    insight_load: StrictInt | None = None
    steps: list[RouteLearnerStep] = Field(default_factory=list)


class RouteServerStep(JsonDoc):
    step_index: StrictInt
    expected_response: StrictStr | None = None
    mathematical_result: StrictStr | None = None
    source_quote: StrictStr | None = None
    depends_on: list = Field(default_factory=list)
    produces: list = Field(default_factory=list)
    uses_claims: list = Field(default_factory=list)


class RouteServerAsset(JsonDoc):
    asset_key: StrictStr
    content: dict | list | str | None = None


class RouteServerDoc(JsonDoc):
    """``.../server.json``: expected responses and the route assets; server-side use only, never in a learner payload."""

    route_release_id: StrictStr
    steps: list[RouteServerStep] = Field(default_factory=list)
    assets: list[RouteServerAsset] = Field(default_factory=list)
