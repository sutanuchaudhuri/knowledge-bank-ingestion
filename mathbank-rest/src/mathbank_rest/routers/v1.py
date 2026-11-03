"""v1 read endpoints over the corpus schema — per rest/02 + rest/03 design docs."""
from __future__ import annotations

import logging
from contextlib import nullcontext
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mathbank_rest import rate_limit, stores
from mathbank_rest.config import settings
from mathbank_rest.db import hybrid_search, step_search
from mathbank_rest.db import queries as queries  # noqa: PLC0414

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


@router.get("/competitions", tags=["corpus"])
def get_competitions() -> list[dict]:
    return stores.get_store("content").list_competitions()


@router.get("/problems", tags=["corpus"])
def get_problems(
    competition: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    concept: str | None = None,
    technique: str | None = None,
    limit: int = Query(25, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    return stores.get_store("content").list_problems(
        competition=competition,
        year_min=year_min,
        year_max=year_max,
        concept=concept,
        technique=technique,
        limit=limit,
        offset=offset,
    )


@router.get("/problems/by-code/{canonical_code}", tags=["corpus"])
def get_problem(canonical_code: str) -> dict:
    problem = stores.get_store("content").get_problem_by_code(canonical_code)
    if problem is None:
        raise HTTPException(status_code=404, detail="problem not found")
    return problem


@router.get("/concepts", tags=["taxonomy"])
def get_concepts(
    domain: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    return stores.get_store("content").list_concepts(domain=domain, limit=limit, offset=offset)


@router.get("/concepts/{slug}/problems", tags=["taxonomy"])
def get_concept_problems(
    slug: str, limit: int = Query(25, le=200), offset: int = Query(0, ge=0)
) -> list[dict]:
    return stores.get_store("content").get_concept_problems(slug, limit=limit, offset=offset)


@router.get("/concepts/{slug}/neighbors", tags=["taxonomy"])
def get_concept_neighbors(slug: str) -> list[dict]:
    return stores.get_store("content").get_concept_neighbors(slug)


@router.get("/techniques", tags=["taxonomy"])
def get_techniques(
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    return stores.get_store("content").list_techniques(q=q, limit=limit, offset=offset)


@router.get("/techniques/{slug}/problems", tags=["taxonomy"])
def get_technique_problems(
    slug: str, limit: int = Query(25, le=200), offset: int = Query(0, ge=0)
) -> list[dict]:
    return stores.get_store("content").get_technique_problems(slug, limit=limit, offset=offset)


@router.get("/corpus/coverage", tags=["analytics"])
def get_corpus_coverage() -> list[dict]:
    return stores.get_store("content").get_corpus_coverage()


@router.get("/analytics/weak-concepts", tags=["analytics"])
def get_weak_concepts(
    min_students: int = Query(1, ge=1), limit: int = Query(20, le=100)
) -> dict:
    """Cohort-level (no PII — concept-level aggregates only), lowest average
    mastery first. Signals what to improve at the platform level: genuinely
    hard material, a thin bank of practice problems, or a retrieval gap —
    not any individual student's data. A concept is reported only when at
    least `cohort_min_students` learners contribute, whatever `min_students`
    asks for; otherwise the result is empty with `suppressed: true`."""
    floor = settings.cohort_min_students
    results = stores.get_store("learner").get_cohort_weak_concepts(min_students=max(min_students, floor), limit=limit)
    body: dict = {"results": results, "suppressed": not results, "cohort_min_students": floor}
    if not results:
        body["note"] = f"No concept has at least {floor} learners; aggregates below that size are withheld."
    return body


def _embedding_scope(caller: rate_limit.Caller | None):
    return rate_limit.embeddings_blocked() if caller is None else nullcontext()


def _gate_semantic(caller: rate_limit.Caller | None, body_retrieval, *, other_sources: bool) -> tuple[bool, list[str]]:
    """Semantic (paid embedding) retrieval needs a signed-in caller. An anonymous request that did not
    explicitly ask for it is served from the free sources and told so; an explicit request gets 401."""
    if not body_retrieval.semantic:
        return False, []
    if caller is not None:
        rate_limit.enforce(caller, "search")
        return True, []
    if "semantic" in body_retrieval.model_fields_set or not other_sources:
        raise HTTPException(
            status_code=401,
            detail="semantic search requires a learner token or admin credential",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return False, ["Semantic ranking requires sign-in; results use the free retrieval sources only."]


@router.post("/search/concepts", tags=["search"])
def search_concepts(
    body: ConceptSearchRequest, caller: Annotated[rate_limit.Caller | None, Depends(rate_limit.optional_paid_caller)]
) -> dict:
    """Concept-level hybrid search over the embedded taxonomy (TAXONOMY_NODE vectors).

    Maps a topic to taxonomy nodes with their corpus slug, problem count and example problem codes.
    Semantic ranking needs a learner token or admin credential and is rate limited per caller; anonymous
    callers get lexical ranking. If the query embedding is unavailable, falls back to lexical ranking.

    With S3 Vectors on (``VECTOR_STORE=s3vectors``) ranking is semantic only: lexical is reported as ``not_applied``
    (never a Postgres fallback), so anonymous callers need to sign in and an unavailable query embedding is a 503
    ``SEMANTIC_UNAVAILABLE``.
    """
    from mathbank_rest import vector_store
    from mathbank_rest.stores.errors import StoreError

    s3_vectors = vector_store.uses_s3_vectors()
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query must contain non-whitespace text")
    if not (body.retrieval.semantic or body.retrieval.lexical):
        raise HTTPException(status_code=400, detail="at least one retrieval source must be true")
    semantic, warnings = _gate_semantic(caller, body.retrieval, other_sources=body.retrieval.lexical and not s3_vectors)
    semantic_status = "queried" if semantic else "requires_sign_in" if warnings else "disabled"
    lexical_status = "queried" if body.retrieval.lexical else "disabled"
    if s3_vectors and body.retrieval.lexical:
        lexical_status = "not_applied"
        warnings.append("Lexical ranking is not applied with S3 Vectors search; results are semantic only.")
    kwargs = {"node_types": body.node_types or None, "chapter_number": body.chapter_number, "limit": body.limit}
    try:
        with _embedding_scope(caller):
            results = step_search.search_taxonomy_nodes(
                query, semantic=semantic, lexical=body.retrieval.lexical, **kwargs)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        if s3_vectors:
            if isinstance(exc, HTTPException | StoreError):
                raise
            logger.exception("Concept search semantic ranking unavailable")
            raise HTTPException(
                status_code=503,
                detail={"code": "SEMANTIC_UNAVAILABLE", "message": "semantic ranking is temporarily unavailable"},
            ) from exc
        if not (semantic and body.retrieval.lexical):
            raise
        logger.exception("Concept search semantic ranking unavailable; falling back to lexical")
        warnings.append("Semantic ranking unavailable; results are lexical only.")
        semantic_status = "unavailable"
        results = step_search.search_taxonomy_nodes(query, semantic=False, lexical=True, **kwargs)
    return {
        "query": query,
        "results": results,
        "retrieval": {"semantic": semantic_status, "lexical": lexical_status,
                      "unit": "TAXONOMY_NODE", "profile": step_search.PROFILE_NAME},
        "warnings": warnings,
    }


@router.post("/search/problems", tags=["search"])
def search_problems(
    body: ProblemSearchRequest, caller: Annotated[rate_limit.Caller | None, Depends(rate_limit.optional_paid_caller)]
) -> dict:
    """Hybrid problem search. Semantic ranking calls a paid embedding model, so it needs a learner token or
    admin credential and is rate limited per caller; anonymous callers get the lexical/graph sources."""
    if not body.query.strip():
        raise HTTPException(status_code=422, detail="query must contain non-whitespace text")
    if not any((body.retrieval.semantic, body.retrieval.lexical, body.retrieval.graph)):
        raise HTTPException(status_code=400, detail="at least one retrieval source must be true")
    semantic, gate_warnings = _gate_semantic(
        caller, body.retrieval, other_sources=body.retrieval.lexical or body.retrieval.graph)
    with _embedding_scope(caller):
        result = hybrid_search.search_problems(
            body.query.strip(),
            competition=body.filters.competition,
            year_min=body.filters.year_min,
            year_max=body.filters.year_max,
            semantic=semantic,
            lexical=body.retrieval.lexical,
            graph=body.retrieval.graph,
            order_by=body.order_by,
            limit=body.limit,
        )
    if gate_warnings:
        result["warnings"] = [*gate_warnings, *result.get("warnings", [])]
        result.setdefault("retrieval", {})["semantic_requires_sign_in"] = True
    return result
