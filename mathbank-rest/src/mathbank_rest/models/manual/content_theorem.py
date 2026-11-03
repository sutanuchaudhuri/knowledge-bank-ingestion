"""Hand-written models for the theorem catalogue in ``mb-content`` (requirement 70 C6: ``THEOREM``, ``THEOREM_REL``,
``THEOREM_LINK``; written by ``mathbank-db/aws/dynamo/specs/content.py``).

The generated models are built from items observed in ``dev``; the theorem items were not migrated there yet, so their
models are written from the migration spec. Attributes the spec drops when null (``statement_latex``, ``proof_sketch`` ...)
are optional.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, JsonDoc, UtcDateTime

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


class ContentTheoremSource(JsonDoc):
    theorem_source_id: StrictStr
    url: StrictStr
    label: StrictStr
    source_type: StrictStr
    ordinal: StrictInt


class ContentTheoremAsset(JsonDoc):
    asset_id: StrictStr
    mime: StrictStr | None = None
    sha256: StrictStr | None = None
    asset_kind: StrictStr | None = None
    ordinal: StrictInt
    caption: StrictStr | None = None


class ContentTheorem(DdbItem, ctx="content", item_type="THEOREM"):
    type: Literal["THEOREM"] = "THEOREM"
    PK: str = Field(pattern=f"^THEOREM#{_UUID}$")
    SK: str = Field(pattern="^META$")
    theorem_id: StrictStr
    slug: StrictStr
    name: StrictStr
    kind: StrictStr
    field: StrictStr
    statement_text: StrictStr
    statement_latex: StrictStr | None = None
    description: StrictStr | None = None
    proof_sketch: StrictStr | None = None
    source: StrictStr
    review_status: StrictStr
    approval_method: StrictStr | None = None
    approved_at: UtcDateTime | None = None
    created_at: UtcDateTime
    sources: list[ContentTheoremSource] = Field(default_factory=list)
    assets: list[ContentTheoremAsset] = Field(default_factory=list)
    vector_state: dict[str, Any] | None = None


class ContentTheoremRel(DdbItem, ctx="content", item_type="THEOREM_REL"):
    type: Literal["THEOREM_REL"] = "THEOREM_REL"
    PK: str = Field(pattern=f"^THEOREM#{_UUID}$")
    SK: str = Field(pattern=f"^REL#[A-Z_]+#{_UUID}$")
    relation_id: StrictStr | None = None
    relation_type: StrictStr
    to_theorem_id: StrictStr
    to_slug: StrictStr
    to_name: StrictStr
    confidence: float | None = None
    review_status: StrictStr | None = None


class ContentTheoremLink(DdbItem, ctx="content", item_type="THEOREM_LINK"):
    type: Literal["THEOREM_LINK"] = "THEOREM_LINK"
    PK: str = Field(pattern=f"^THEOREM#{_UUID}$")
    SK: str = Field(pattern=r"^LINK#(?:TECHNIQUE#[^#]+#[^#]+|TAXNODE#[^#]+)$")
    link_kind: Literal["TECHNIQUE", "TAXNODE"]
    theorem_id: StrictStr
    technique_id: StrictStr | None = None
    technique_slug: StrictStr | None = None
    taxonomy_node_id: StrictStr | None = None
    slug: StrictStr
    name: StrictStr
    role: StrictStr
    confidence: float | None = None
    derived_via: StrictStr | None = None
