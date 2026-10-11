"""Admin taxonomy CRUD: list/update/alias/activate-deactivate for concept, technique, skill,
and misconception (requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md §5, APID-6..11).
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from mathbank_rest import taxonomy_service as taxonomy
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import require_admin_api_key

logger = logging.getLogger(__name__)

Kind = Literal["concepts", "techniques", "skills", "misconceptions"]

router = APIRouter(
    prefix="/v1/admin/taxonomy",
    tags=["admin-taxonomy"],
    dependencies=[Depends(require_admin_api_key)],
)


def _call(operation, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return operation(conn, *args, **kwargs)
    except taxonomy.TaxonomyConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except taxonomy.TaxonomyNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="The requested change conflicts with existing data.") from exc
    except SQLAlchemyError as exc:
        logger.exception("Taxonomy admin operation failed")
        raise HTTPException(status_code=503, detail="Taxonomy data is unavailable.") from exc


class UpdateEntityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, max_length=4000)
    level: int | None = Field(default=None, ge=1, le=10)
    actor: str = Field(min_length=1, max_length=200)


class ActorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=200)
    reason: str | None = Field(default=None, max_length=2000)


class AliasRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alias: str = Field(min_length=1, max_length=200)
    actor: str = Field(min_length=1, max_length=200)


@router.get("/{kind}")
def list_entities(
    kind: Kind,
    q: str = Query(default="", max_length=200),
    status: Literal["ACTIVE", "INACTIVE", "ALL"] = "ALL",
    review_status: str = Query(default="ALL", description="For skills/misconceptions only; "
                                "one of PENDING|REVIEWED|REJECTED (skills) or "
                                "PENDING_REVIEW|APPROVED|REJECTED (misconceptions), or ALL."),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List/search concepts, techniques, skills, or misconceptions (doc 45 APID-6) — the
    first-ever listing endpoint for skills/misconceptions. q= also matches aliases."""
    return _call(taxonomy.list_entities, kind, q=q, status=status, review_status=review_status,
                 limit=limit, offset=offset)


@router.get("/{kind}/{code}")
def get_entity(kind: Kind, code: str) -> dict:
    """Fetch one entity by its slug/canonical_code, including its aliases."""
    return _call(taxonomy.get_entity, kind, code)


@router.patch("/{kind}/{code}")
def update_entity(kind: Kind, code: str, body: UpdateEntityRequest) -> dict:
    """Lightweight name/description(-or-objective)/level update; no revision gate (doc 45 §5.2(b))."""
    return _call(
        taxonomy.update_entity, kind, code,
        name=body.name, description=body.description, level=body.level, actor=body.actor,
    )


@router.post("/{kind}/{code}/deactivate")
def deactivate_entity(kind: Kind, code: str, body: ActorRequest) -> dict:
    """Hide from public listings; blocked (409) while still the PRIMARY target of a published micro-course."""
    return _call(taxonomy.deactivate_entity, kind, code, body.actor, reason=body.reason)


@router.post("/{kind}/{code}/reactivate")
def reactivate_entity(kind: Kind, code: str, body: ActorRequest) -> dict:
    """Restore visibility in public listings."""
    return _call(taxonomy.reactivate_entity, kind, code, body.actor)


@router.get("/{kind}/{code}/aliases")
def list_aliases(kind: Kind, code: str) -> list[dict]:
    """List synonyms that also match this entity in q= search (doc 45 §5.3)."""
    return _call(taxonomy.list_aliases, kind, code)


@router.post("/{kind}/{code}/aliases", status_code=201)
def add_alias(kind: Kind, code: str, body: AliasRequest) -> dict:
    """Add a synonym (e.g. "AM-GM") so q= search finds the entity by that term too."""
    return _call(taxonomy.add_alias, kind, code, body.alias, body.actor)


@router.delete("/{kind}/{code}/aliases/{alias_id}", status_code=204)
def remove_alias(kind: Kind, code: str, alias_id: str, actor: str = Query(..., min_length=1, max_length=200)) -> None:
    """Remove a previously-added synonym."""
    _call(taxonomy.remove_alias, kind, code, alias_id, actor)
