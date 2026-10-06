"""v1 read endpoints over the corpus schema — per rest/02 + rest/03 design docs."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mathbank_rest.db import hybrid_search, queries, step_search
from mathbank_rest.db import learner as learner_db

router = APIRouter(prefix="/v1")
logger = logging.getLogger(__name__)


class SearchFilters(BaseModel):
    competition: str | None = None
    year_min: int | None = None
    year_max: int | None = None


class SearchRetrieval(BaseModel):
    semantic: bool = True
    lexical: bool = True
    graph: bool = True


class ProblemSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    filters: SearchFilters = SearchFilters()
    retrieval: SearchRetrieval = SearchRetrieval()
    order_by: Literal["relevance", "year_desc", "year_asc"] = "relevance"
    limit: int = Field(default=25, ge=1, le=100)


class ConceptSearchRetrieval(BaseModel):
    semantic: bool = True
    lexical: bool = True


class ConceptSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    node_types: list[Literal["DOMAIN", "CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE"]] = Field(
        default_factory=list, max_length=5)
    chapter_number: int | None = Field(default=None, ge=1, le=100)
    retrieval: ConceptSearchRetrieval = ConceptSearchRetrieval()
    limit: int = Field(default=10, ge=1, le=50)


@router.get("/competitions")
def get_competitions() -> list[dict]:
    return queries.list_competitions()


@router.get("/problems")
def get_problems(
    competition: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    concept: str | None = None,
    technique: str | None = None,
    limit: int = Query(25, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    return queries.list_problems(
        competition=competition,
        year_min=year_min,
        year_max=year_max,
        concept=concept,
        technique=technique,
        limit=limit,
        offset=offset,
    )


@router.get("/problems/by-code/{canonical_code}")
def get_problem(canonical_code: str) -> dict:
    problem = queries.get_problem_by_code(canonical_code)
    if problem is None:
        raise HTTPException(status_code=404, detail="problem not found")
    return problem


@router.get("/concepts")
def get_concepts(
    domain: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    return queries.list_concepts(domain=domain, limit=limit, offset=offset)


@router.get("/concepts/{slug}/problems")
def get_concept_problems(
    slug: str, limit: int = Query(25, le=200), offset: int = Query(0, ge=0)
) -> list[dict]:
    return queries.get_concept_problems(slug, limit=limit, offset=offset)


@router.get("/concepts/{slug}/neighbors")
def get_concept_neighbors(slug: str) -> list[dict]:
    return queries.get_concept_neighbors(slug)


@router.get("/techniques")
def get_techniques(limit: int = Query(50, le=200), offset: int = Query(0, ge=0)) -> list[dict]:
    return queries.list_techniques(limit=limit, offset=offset)


@router.get("/techniques/{slug}/problems")
def get_technique_problems(
    slug: str, limit: int = Query(25, le=200), offset: int = Query(0, ge=0)
) -> list[dict]:
    return queries.get_technique_problems(slug, limit=limit, offset=offset)


@router.get("/corpus/coverage")
def get_corpus_coverage() -> list[dict]:
    return queries.corpus_coverage()


@router.get("/analytics/weak-concepts")
def get_weak_concepts(
    min_students: int = Query(1, ge=1), limit: int = Query(20, le=100)
) -> list[dict]:
    """Cohort-level (no PII — concept-level aggregates only), lowest average
    mastery first. Signals what to improve at the platform level: genuinely
    hard material, a thin bank of practice problems, or a retrieval gap —
    not any individual student's data."""
    return learner_db.get_cohort_weak_concepts(min_students=min_students, limit=limit)


@router.post("/search/concepts")
def search_concepts(body: ConceptSearchRequest) -> dict:
    """Concept-level hybrid search over the embedded taxonomy (TAXONOMY_NODE vectors).

    Maps a topic to taxonomy nodes with their corpus slug, problem count and example problem codes.
    If the query embedding is unavailable, falls back to lexical ranking and reports a warning.
    """
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must contain non-whitespace text")
    if not (body.retrieval.semantic or body.retrieval.lexical):
        raise HTTPException(status_code=400, detail="at least one retrieval source must be true")
    kwargs = {"node_types": body.node_types or None, "chapter_number": body.chapter_number, "limit": body.limit}
    warnings: list[str] = []
    semantic = body.retrieval.semantic
    try:
        results = step_search.search_taxonomy_nodes(
            query, semantic=semantic, lexical=body.retrieval.lexical, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        if not (semantic and body.retrieval.lexical):
            raise
        logger.exception("Concept search semantic ranking unavailable; falling back to lexical")
        warnings.append("Semantic ranking unavailable; results are lexical only.")
        semantic = False
        results = step_search.search_taxonomy_nodes(query, semantic=False, lexical=True, **kwargs)
    return {
        "query": query,
        "results": results,
        "retrieval": {"semantic": "queried" if semantic else "disabled" if not body.retrieval.semantic
                      else "unavailable", "lexical": "queried" if body.retrieval.lexical else "disabled",
                      "unit": "TAXONOMY_NODE", "profile": step_search.PROFILE_NAME},
        "warnings": warnings,
    }


@router.post("/search/problems")
def search_problems(body: ProblemSearchRequest) -> dict:
    if not body.query.strip():
        raise HTTPException(status_code=422, detail="query must contain non-whitespace text")
    if not any((body.retrieval.semantic, body.retrieval.lexical, body.retrieval.graph)):
        raise HTTPException(status_code=400, detail="at least one retrieval source must be true")
    return hybrid_search.search_problems(
        body.query.strip(),
        competition=body.filters.competition,
        year_min=body.filters.year_min,
        year_max=body.filters.year_max,
        semantic=body.retrieval.semantic,
        lexical=body.retrieval.lexical,
        graph=body.retrieval.graph,
        order_by=body.order_by,
        limit=body.limit,
    )
