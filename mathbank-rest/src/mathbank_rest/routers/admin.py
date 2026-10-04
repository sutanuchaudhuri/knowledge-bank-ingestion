"""Admin endpoints — register competitions/papers (auto-PENDING pipeline rows),
monitor pipeline stage progress, retry failed stages.

Per the user's ask: "tables automatically have rows PENDING once an admin
adds a new competition with page urls" + "every stage logged". The actual
download -> parse -> ingest -> embed -> graph-project work stays in the
existing scripts (etl/pdf_pipeline.py, etl/embed_corpus.py, etl/load_corpus.py,
mathbank-graph/etl/project_from_postgres.py) — this router is only the
"register work + check status" surface over pipeline.pdf_source / pipeline.run /
pipeline.graph_projection, all pre-existing tables.

Auth: single shared `X-Admin-Api-Key` header (security.require_admin_api_key).
No per-admin-user accounts/roles yet — tracked as a follow-up in
requirements/11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md once there's an actual
multi-admin need; a single shared key is sufficient for the current one-operator
usage and avoids building a role system against a guess at future requirements.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mathbank_rest.db import admin as admin_db
from mathbank_rest.security import require_admin_api_key

router = APIRouter(prefix="/v1/admin", tags=["admin"], dependencies=[Depends(require_admin_api_key)])

_PAPER_CODE_RE = re.compile(r"^[A-Z0-9_]+$")
SOURCE_KINDS = {"PDF", "HTML"}


class CompetitionRequest(BaseModel):
    external_code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    organization: str | None = None
    country: str | None = None
    level: str | None = None


class PaperRequest(BaseModel):
    paper_external_code: str = Field(min_length=1, max_length=100, description="e.g. PAPER_SMT_2027_TEAM")
    competition_external_code: str
    year: int = Field(ge=1900, le=2200)
    problem_url: str
    solution_url: str | None = None
    source_kind: str = Field(default="PDF", description="PDF | HTML")
    link_scope: str | None = None


class PapersBatchRequest(BaseModel):
    papers: list[PaperRequest]


@router.post("/competitions")
def create_competition(body: CompetitionRequest) -> dict:
    return admin_db.create_competition(
        external_code=body.external_code,
        name=body.name,
        organization=body.organization,
        country=body.country,
        level=body.level,
    )


def _register_one(body: PaperRequest) -> dict:
    if not _PAPER_CODE_RE.match(body.paper_external_code):
        raise HTTPException(
            status_code=422,
            detail="paper_external_code must be upper-case alphanumeric/underscore (e.g. PAPER_SMT_2027_TEAM)",
        )
    source_kind = body.source_kind.upper()
    if source_kind not in SOURCE_KINDS:
        raise HTTPException(status_code=422, detail=f"source_kind must be one of {sorted(SOURCE_KINDS)}")
    return admin_db.register_paper(
        paper_external_code=body.paper_external_code,
        competition_external_code=body.competition_external_code,
        crawl_dir=body.competition_external_code.lower(),
        problem_url=body.problem_url,
        solution_url=body.solution_url,
        source_kind=source_kind,
        link_scope=body.link_scope,
    )


@router.post("/papers", status_code=201)
def register_paper(body: PaperRequest) -> dict:
    return _register_one(body)


@router.post("/papers/batch", status_code=201)
def register_papers_batch(body: PapersBatchRequest) -> dict:
    return {"registered": [_register_one(p) for p in body.papers]}


@router.get("/papers")
def list_papers(
    competition: str | None = None,
    status: str | None = Query(default=None, description="PENDING | DOWNLOADED | PARSED | INGESTED | FAILED"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    return admin_db.list_papers(competition=competition, status=status, limit=limit, offset=offset)


@router.post("/papers/{paper_external_code}/retry")
def retry_paper(paper_external_code: str) -> dict:
    result = admin_db.retry_paper(paper_external_code)
    if result is None:
        raise HTTPException(status_code=404, detail="no such paper_external_code")
    return result


@router.get("/pipeline/runs")
def pipeline_runs(limit: int = Query(20, le=200)) -> dict:
    return {
        "runs": admin_db.list_pipeline_runs(limit=limit),
        "graph_projections": admin_db.list_graph_projections(limit=limit),
    }
