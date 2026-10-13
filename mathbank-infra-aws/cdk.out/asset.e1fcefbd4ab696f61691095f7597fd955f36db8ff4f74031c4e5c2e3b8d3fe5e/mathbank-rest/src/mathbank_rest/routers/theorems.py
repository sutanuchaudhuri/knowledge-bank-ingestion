"""Admin authoring and student read APIs for the Theorem/Axiom/Lemma/Proposition/
Corollary/Identity/Definition catalog (requirements/61). Dedicated router, same
admin_router/student_router-in-one-file pattern as `micro_courses.py`, rather than
folding into `admin_taxonomy.py`'s generic concept/technique/skill/misconception CRUD
(see `theorem_service.py`'s module docstring for why)."""

from __future__ import annotations

import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from mathbank_rest import theorem_service as theorems
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import require_admin_api_key

logger = logging.getLogger(__name__)

_KIND = Literal["AXIOM", "THEOREM", "LEMMA", "PROPOSITION", "COROLLARY", "IDENTITY", "DEFINITION"]
_FIELD = Literal[
    "ALGEBRA", "GEOMETRY", "NUMBER_THEORY", "COMBINATORICS", "PROBABILITY",
    "ANALYSIS", "LOGIC_AND_SET_THEORY", "OTHER",
]
_RELATION_TYPE = Literal["DEPENDS_ON", "GENERALIZES", "SPECIAL_CASE_OF", "EQUIVALENT_TO", "COROLLARY_OF"]
_SOURCE_TYPE = Literal["REFERENCE", "FORMAL_PROOF", "VIDEO", "TEXTBOOK", "OTHER"]

admin_router = APIRouter(
    prefix="/v1/admin/theorems",
    tags=["admin-theorems"],
    dependencies=[Depends(require_admin_api_key)],
)
student_router = APIRouter(prefix="/v1/theorems", tags=["theorems"])


def _call(operation, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return operation(conn, *args, **kwargs)
    except theorems.TheoremCycle as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except theorems.TheoremConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except theorems.TheoremNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="The requested change conflicts with existing theorem data."
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Theorem database operation failed")
        raise HTTPException(status_code=503, detail="Theorem data is unavailable.") from exc


class CreateTheorem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=300)
    kind: _KIND
    field: _FIELD
    statement_text: str = Field(min_length=1)
    statement_latex: str | None = None
    description: str | None = None
    proof_sketch: str | None = None
    source: Literal["HUMAN", "LLM_DRAFT", "LLM_REVIEWED"] = "HUMAN"
    actor: str = Field(min_length=1, max_length=200)
    auto_approve: bool = False


class UpdateTheorem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=200)
    name: str | None = None
    field: _FIELD | None = None
    statement_text: str | None = None
    statement_latex: str | None = None
    description: str | None = None
    proof_sketch: str | None = None


class ActorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=200)
    reason: str | None = None


class CreateRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_slug: str = Field(min_length=1, max_length=120)
    relation_type: _RELATION_TYPE
    assertion_source: str = Field(min_length=1, max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)
    actor: str = Field(min_length=1, max_length=200)


class CreateTechniqueLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    technique_slug: str = Field(min_length=1, max_length=120)
    role: Literal["JUSTIFIES", "APPLIES"] = "JUSTIFIES"
    assertion_source: str = Field(min_length=1, max_length=200)
    confidence: float | None = Field(default=None, ge=0, le=1)
    actor: str = Field(min_length=1, max_length=200)


class CreateTaxonomyLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taxonomy_node_id: str = Field(min_length=1, max_length=120)
    role: Literal["PRIMARY", "RELATED"] = "PRIMARY"
    actor: str = Field(min_length=1, max_length=200)


class CreateSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(min_length=1, max_length=2000)
    label: str = Field(min_length=1, max_length=200)
    source_type: _SOURCE_TYPE = "REFERENCE"
    added_by: str = Field(min_length=1, max_length=200)
    review_status: Literal["PENDING_REVIEW", "APPROVED", "REJECTED"] = "PENDING_REVIEW"


class CreateAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: UUID
    caption: str | None = None


# ----------------------------------------------------------------------- admin CRUD ---

@admin_router.get("")
def list_admin_theorems(
    q: str = Query(default="", max_length=200),
    kind: str = Query(default=""),
    field: str = Query(default=""),
    review_status: str = Query(default="ALL"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return _call(
        theorems.list_theorems, q=q, kind=kind, field=field,
        review_status=review_status, limit=limit, offset=offset,
    )


@admin_router.post("", status_code=201)
def create_admin_theorem(body: CreateTheorem) -> dict:
    return _call(theorems.create_theorem, **body.model_dump(exclude={"actor"}), actor=body.actor)


@admin_router.get("/search")
def search_admin_theorems(
    q: str = Query(min_length=1, max_length=200),
    field: str = Query(default=""),
    kind: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """The mandatory dedup gate (doc 61 §8.3/§9) — includes PENDING_REVIEW candidates so
    the admin also sees near-duplicate drafts awaiting review, not just published ones."""
    return _call(theorems.search_theorems, q, field=field, kind=kind, limit=limit, include_unapproved=True)


@admin_router.get("/{slug}")
def get_admin_theorem(slug: str) -> dict:
    return _call(theorems.get_theorem, slug, include_unapproved=True)


@admin_router.patch("/{slug}")
def update_admin_theorem(slug: str, body: UpdateTheorem) -> dict:
    return _call(theorems.update_theorem, slug, **body.model_dump(exclude={"actor"}), actor=body.actor)


@admin_router.post("/{slug}/approve")
def approve_admin_theorem(slug: str, body: ActorRequest) -> dict:
    return _call(theorems.approve_theorem, slug, actor=body.actor)


@admin_router.post("/{slug}/reject")
def reject_admin_theorem(slug: str, body: ActorRequest) -> dict:
    return _call(theorems.reject_theorem, slug, actor=body.actor, reason=body.reason)


# ------------------------------------------------------------------ relations / DAG ---

@admin_router.post("/{slug}/relations", status_code=201)
def create_theorem_relation(slug: str, body: CreateRelation) -> dict:
    return _call(
        theorems.add_theorem_relation, from_slug=slug, to_slug=body.to_slug,
        relation_type=body.relation_type, assertion_source=body.assertion_source,
        confidence=body.confidence, actor=body.actor,
    )


@admin_router.get("/{slug}/relations")
def get_theorem_relations(slug: str) -> dict:
    return _call(theorems.list_theorem_relations, slug)


@admin_router.get("/{slug}/prerequisites")
def get_theorem_prerequisites_admin(slug: str, max_depth: int = Query(default=4, ge=1, le=10)) -> dict:
    return _call(theorems.get_theorem_prerequisites, slug, max_depth=max_depth)


# -------------------------------------------------------------------- linking / HAS-A ---

@admin_router.post("/{slug}/techniques", status_code=201)
def link_theorem_technique(slug: str, body: CreateTechniqueLink) -> dict:
    return _call(
        theorems.add_technique_theorem, technique_slug=body.technique_slug, theorem_slug=slug,
        role=body.role, assertion_source=body.assertion_source, confidence=body.confidence, actor=body.actor,
    )


@admin_router.post("/{slug}/taxonomy-links", status_code=201)
def link_theorem_taxonomy(slug: str, body: CreateTaxonomyLink) -> dict:
    return _call(
        theorems.add_theorem_taxonomy_link, theorem_slug=slug,
        taxonomy_node_id=body.taxonomy_node_id, role=body.role, actor=body.actor,
    )


@admin_router.post("/{slug}/sources", status_code=201)
def create_theorem_source(slug: str, body: CreateSource) -> dict:
    return _call(
        theorems.add_theorem_source, theorem_slug=slug, url=body.url, label=body.label,
        source_type=body.source_type, added_by=body.added_by, review_status=body.review_status,
    )


@admin_router.post("/sources/{theorem_source_id}/approve")
def approve_theorem_source(theorem_source_id: str, body: ActorRequest) -> dict:
    return _call(theorems.approve_theorem_source, theorem_source_id, actor=body.actor)


@admin_router.post("/{slug}/assets", status_code=201)
def create_theorem_asset(slug: str, body: CreateAsset) -> dict:
    return _call(theorems.add_theorem_asset, theorem_slug=slug, asset_id=str(body.asset_id), caption=body.caption)


# --------------------------------------------------------------------- student reads ---

@student_router.get("/search")
def search_student_theorems(
    q: str = Query(min_length=1, max_length=200),
    field: str = Query(default=""),
    kind: str = Query(default=""),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict:
    """APPROVED-only hybrid search (doc 61 §12.1) — no drafts, student or agent alike."""
    return _call(theorems.search_theorems, q, field=field, kind=kind, limit=limit, include_unapproved=False)


@student_router.get("/{slug}")
def get_student_theorem(slug: str) -> dict:
    return _call(theorems.get_theorem, slug, include_unapproved=False)


@student_router.get("/{slug}/prerequisites")
def get_student_theorem_prerequisites(slug: str, max_depth: int = Query(default=4, ge=1, le=10)) -> dict:
    return _call(theorems.get_theorem_prerequisites, slug, max_depth=max_depth, include_unapproved=False)


@student_router.get("/by-taxonomy/{taxonomy_node_id}")
def list_student_theorems_for_taxonomy(taxonomy_node_id: str) -> dict:
    return _call(theorems.list_theorems_for_taxonomy_node, taxonomy_node_id)


@student_router.get("/by-technique/{technique_slug}")
def list_student_theorems_for_technique(technique_slug: str) -> dict:
    return _call(theorems.get_theorems_for_technique, technique_slug)
