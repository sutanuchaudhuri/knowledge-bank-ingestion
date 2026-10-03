"""v1 read endpoints over the corpus schema — per rest/02 + rest/03 design docs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from mathbank_rest.db import queries, vector_search

router = APIRouter(prefix="/v1")


class SearchFilters(BaseModel):
    competition: str | None = None
    year_min: int | None = None
    year_max: int | None = None


class SearchRetrieval(BaseModel):
    semantic: bool = True
    lexical: bool = True


class ProblemSearchRequest(BaseModel):
    query: str
    filters: SearchFilters = SearchFilters()
    retrieval: SearchRetrieval = SearchRetrieval()
    order_by: str = "relevance"  # relevance | year_desc | year_asc
    limit: int = 25


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


@router.post("/search/problems")
def search_problems(body: ProblemSearchRequest) -> dict:
    if not body.retrieval.semantic and not body.retrieval.lexical:
        raise HTTPException(status_code=400, detail="at least one of semantic/lexical must be true")
    results = vector_search.search_problems(
        body.query,
        competition=body.filters.competition,
        year_min=body.filters.year_min,
        year_max=body.filters.year_max,
        semantic=body.retrieval.semantic,
        lexical=body.retrieval.lexical,
        order_by=body.order_by,
        limit=body.limit,
    )
    return {"query": body.query, "results": results}
