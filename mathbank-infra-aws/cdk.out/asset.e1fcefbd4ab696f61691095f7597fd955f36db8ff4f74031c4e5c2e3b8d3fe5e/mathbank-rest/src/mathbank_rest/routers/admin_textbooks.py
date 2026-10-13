"""Admin textbook corpus browser (requirements/24): read-only, X-Admin-Api-Key protected."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as Path_
from fastapi.responses import FileResponse

from mathbank_rest import security
from mathbank_rest.db import textbook_admin as db
from mathbank_rest.db.postgres import engine

router = APIRouter(prefix="/v1/admin/textbooks", tags=["admin-textbooks"],
                   dependencies=[Depends(security.require_admin_api_key)])

REPO_ROOT = Path(__file__).resolve().parents[4]
BOOK = Query(db.DEFAULT_BOOK, max_length=64, pattern=r"^[A-Z0-9_]+$")
NodeType = Literal["DOMAIN", "CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE"]


def _read(fn, *args, **kwargs):
    with engine.connect() as conn:
        return fn(conn, *args, **kwargs)


@router.get("/coverage")
def coverage(book: str = BOOK, graph: bool = Query(True, description="Also count Neo4j nodes/edges")) -> dict:
    """Source CSV rows vs Postgres vs pgvector vs Neo4j per entity, packages, conflicts and per-chapter totals."""
    return _read(db.coverage, book, include_graph=graph)


@router.get("/problems")
def problems(book: str = BOOK, chapter: int | None = Query(None, ge=1, le=99),
             q: str | None = Query(None, max_length=200), node: str | None = Query(None, max_length=200),
             has_diagram: bool | None = None, has_solution: bool | None = None,
             limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict:
    """Paginated problems with taxonomy, counts and embedding status."""
    return _read(db.list_problems, book=book, chapter=chapter, q=q, node=node, has_diagram=has_diagram,
                 has_solution=has_solution, limit=limit, offset=offset)


@router.get("/problems/{code}")
def problem(code: str, graph: bool = True) -> dict:
    """Everything about one problem: source, solution, parts/steps/dependencies, learning items (with answers),
    taxonomy, diagrams (including solution-hidden ones) and per-store status."""
    if len(code) > 100:
        raise HTTPException(status_code=422, detail="code too long")
    found = _read(db.problem_detail, code, include_graph=graph)
    if not found:
        raise HTTPException(status_code=404, detail="problem not found")
    return found


@router.get("/learning-items")
def learning_items(book: str = BOOK, transformation_type: str | None = Query(None, max_length=64),
                   chapter: int | None = Query(None, ge=1, le=99), q: str | None = Query(None, max_length=200),
                   limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict:
    """Paginated transformations (learning items) with per-type totals."""
    return _read(db.list_learning_items, book=book, transformation_type=transformation_type, chapter=chapter,
                 q=q, limit=limit, offset=offset)


@router.get("/taxonomy")
def taxonomy(book: str = BOOK, node_type: NodeType | None = None, q: str | None = Query(None, max_length=200),
             limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict:
    """Taxonomy nodes with usage counts (problems, steps, edges)."""
    return _read(db.list_taxonomy, book=book, node_type=node_type, q=q, limit=limit, offset=offset)


@router.get("/taxonomy/{node_id}")
def taxonomy_node(node_id: str) -> dict:
    """A taxonomy node with parent, children, edges and up to 50 problems tagged with it."""
    if len(node_id) > 200:
        raise HTTPException(status_code=422, detail="node_id too long")
    found = _read(db.taxonomy_detail, node_id)
    if not found:
        raise HTTPException(status_code=404, detail="taxonomy node not found")
    return found


@router.get("/diagrams/{source_diagram_id}/image", response_class=FileResponse)
def diagram_image(source_diagram_id: str = Path_(..., max_length=100, pattern=r"^[A-Za-z0-9_.-]+$"),
                  book: str = BOOK):
    """Any diagram file, including SOLUTION_HIDDEN ones students never see."""
    path = _read(db.diagram_path, book, source_diagram_id, REPO_ROOT)
    if path is None:
        raise HTTPException(status_code=404, detail="diagram not found")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=3600"})
