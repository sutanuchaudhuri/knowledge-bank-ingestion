"""Admin import / reconciliation / semantic DAG review (runtime_extension/15). X-Admin-Api-Key protected.

Reads come from the import ledger (ingest.*), coverage (Postgres vs pgvector vs Neo4j) and the
projection-request queue. Writes record a decision + audit row + outbox event in one transaction; graph
and embedding refreshes are queued (``pipeline.projection_request``), never executed inline, and no raw
Cypher/SQL is accepted.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mathbank_rest import security
from mathbank_rest.db import import_admin as db
from mathbank_rest.db.postgres import engine
from mathbank_rest.db.textbook_admin import DEFAULT_BOOK

router = APIRouter(prefix="/v1/admin/imports", tags=["admin-imports"],
                   dependencies=[Depends(security.require_admin_api_key)])

BOOK = Query(DEFAULT_BOOK, max_length=64, pattern=r"^[A-Z0-9_]+$")
UUID_RE = r"^[0-9a-fA-F-]{36}$"
DependencyType = Literal["NEXT", "DEPENDS_ON", "DERIVES_FROM", "USES_RESULT_FROM", "ALTERNATIVE_TO", "BRANCHES_TO",
                         "JOINS_AT", "JUSTIFIES"]
Note = Field(None, max_length=2000)


def _call(fn, *args, write: bool = False, **kwargs):
    try:
        with (engine.begin() if write else engine.connect()) as conn:
            return fn(conn, *args, **kwargs)
    except db.NotFound as exc:
        raise HTTPException(status_code=404, detail=f"not found: {exc}") from exc
    except db.Invalid as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except db.Conflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# ---------------------------------------------------------------- packages

@router.get("/packages")
def packages(book: str | None = Query(None, max_length=64, pattern=r"^[A-Z0-9_]+$")) -> list[dict]:
    """Import dashboard: package, version, book, registered/postgres/reconciled status and open work."""
    return _call(db.list_packages, book)


@router.get("/packages/{package_id}")
def package_detail(package_id: str) -> dict:
    """Per-entity source/valid/imported/rejected/conflict counts, staging summary, files and status history."""
    _uuid(package_id)
    return _call(db.package_detail, package_id)


@router.get("/packages/{package_id}/issues")
def issues(package_id: str, entity_type: str | None = Query(None, max_length=40),
           kind: Literal["ALL", "REJECTED", "WARNINGS"] = "ALL",
           limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict:
    """Validation issues: rejected staging rows and rows imported with warnings."""
    _uuid(package_id)
    return _call(db.validation_issues, package_id, entity_type=entity_type, kind=kind, limit=limit, offset=offset)


@router.get("/packages/{package_id}/conflicts")
def conflicts(package_id: str, entity_type: str | None = Query(None, max_length=40),
              resolution_status: Literal["OPEN", "AUTO_RESOLVED", "RESOLVED", "IGNORED"] | None = None,
              limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict:
    _uuid(package_id)
    return _call(db.list_conflicts, package_id, entity_type=entity_type, resolution_status=resolution_status,
                 limit=limit, offset=offset)


class ConflictDecision(BaseModel):
    decision: Literal["KEEP_EXISTING", "ACCEPT_INCOMING", "MERGE_MANUALLY"]
    note: str | None = Note


@router.post("/conflicts/{conflict_id}/decision")
def decide_conflict(conflict_id: int, body: ConflictDecision) -> dict:
    """Record a conflict decision (audited). The decision is applied by re-import or a DAG edit."""
    return _call(db.decide_conflict, conflict_id, body.decision, body.note, write=True)


# ---------------------------------------------------------------- reconciliation

@router.get("/reconciliation")
def reconciliation(book: str = BOOK, graph: bool = Query(True, description="Also count Neo4j nodes/edges")) -> dict:
    """Graph expected/actual/missing/extra, embedding expected/completed, active model/profile and queue."""
    return _call(db.reconciliation, book, include_graph=graph)


@router.get("/projection-requests")
def projection_requests(status: Literal["PENDING", "DONE", "CANCELLED"] | None = None,
                        limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    return _call(db.list_projection_requests, status, limit)


class ProjectionRequest(BaseModel):
    target: Literal["GRAPH_TEXTBOOK_STEPS", "STEP_EMBEDDINGS", "LEARNING_ITEM_EMBEDDINGS", "GRAPH_LEARNING_ITEMS"]
    scope_type: Literal["BOOK", "PACKAGE", "PROBLEM", "STEP", "LEARNING_ITEM"] = "BOOK"
    scope_id: str = Field(..., min_length=1, max_length=200)
    note: str | None = Note


@router.post("/projection-requests", status_code=202)
def request_projection(body: ProjectionRequest) -> dict:
    """"Reproject missing": queue a projector run (coalesces with an open request for the same scope)."""
    return _call(db.request_projection, body.target, body.scope_type, body.scope_id, body.note, write=True)


# ---------------------------------------------------------------- learning items

class ItemReview(BaseModel):
    decision: Literal["APPROVE", "REJECT", "NEEDS_REVISION"]
    note: str | None = Note


@router.post("/learning-items/{learning_item_id}/review")
def review_learning_item(learning_item_id: str, body: ItemReview) -> dict:
    """Human approve/reject (approval_method=human, never overwritten by re-import)."""
    return _call(db.review_learning_item, learning_item_id, body.decision, body.note, write=True)


# ---------------------------------------------------------------- semantic DAG review

@router.get("/problems/{code}/dag")
def problem_dag(code: str) -> dict:
    """Steps (skill, checkpoint), dependency edges, DAG review status and recent admin actions."""
    return _call(db.problem_dag, code)


class StepEdit(BaseModel):
    skill_node_id: str | None = Field(None, max_length=200)
    is_checkpoint: bool | None = None
    note: str | None = Note


@router.patch("/steps/{step_id:path}")
def edit_step(step_id: str, body: StepEdit) -> dict:
    """Adjust skill / mark checkpoint. Emits SOLUTION_STEP_CHANGED (graph + embedding re-projection)."""
    return _call(db.edit_step, step_id, skill_node_id=body.skill_node_id, is_checkpoint=body.is_checkpoint,
                 note=body.note, write=True)


class DependencyEdit(BaseModel):
    from_step_id: str = Field(..., max_length=200)
    to_step_id: str = Field(..., max_length=200)
    relationship_type: DependencyType
    previous_type: DependencyType | None = Field(None, description="Set to change an existing edge's type")
    logical_dependency: str | None = Field(None, max_length=2000)
    note: str | None = Note


@router.put("/dependencies")
def upsert_dependency(body: DependencyEdit) -> dict:
    """Create an edge or change its type (e.g. mark an alternative branch). Rejects DEPENDS_ON cycles (409)."""
    return _call(db.upsert_dependency, body.from_step_id, body.to_step_id, body.relationship_type,
                 previous_type=body.previous_type, logical_dependency=body.logical_dependency, note=body.note,
                 write=True)


class DependencyReject(BaseModel):
    from_step_id: str = Field(..., max_length=200)
    to_step_id: str = Field(..., max_length=200)
    relationship_type: DependencyType
    note: str | None = Note


@router.post("/dependencies/reject")
def reject_dependency(body: DependencyReject) -> dict:
    """Mark an edge REJECTED: the runtime ignores it and the next graph projection prunes it."""
    return _call(db.reject_dependency, body.from_step_id, body.to_step_id, body.relationship_type, body.note,
                 write=True)


class DagReview(BaseModel):
    status: Literal["APPROVED", "NEEDS_REVISION"]
    note: str | None = Note


@router.post("/problems/{code}/dag/review")
def review_dag(code: str, body: DagReview) -> dict:
    return _call(db.review_dag, code, body.status, body.note, write=True)


@router.get("/actions")
def actions(target_type: Literal["IMPORT_CONFLICT", "SOLUTION_STEP", "STEP_DEPENDENCY", "SOLUTION_DAG",
                                 "LEARNING_ITEM", "PROJECTION_REQUEST"] | None = None,
            limit: int = Query(100, ge=1, le=500)) -> list[dict]:
    """Append-only admin decision audit trail."""
    return _call(db.list_actions, target_type, limit)


def _uuid(value: str) -> None:
    import re

    if not re.fullmatch(UUID_RE, value):
        raise HTTPException(status_code=422, detail="package_id must be a UUID")
