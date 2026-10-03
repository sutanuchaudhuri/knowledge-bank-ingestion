"""Tools that call mathbank-rest (hybrid RAG + corpus queries over Postgres).

Each function is a plain, type-hinted, docstring-documented Python callable —
ADK auto-generates the function-calling schema from this signature, so the
docstring IS the tool description the LLM sees. Keep it accurate.
"""
from __future__ import annotations

import os

import httpx

REST_BASE_URL = os.environ.get("MATHBANK_REST_BASE_URL", "http://127.0.0.1:8000")


def _client() -> httpx.Client:
    return httpx.Client(base_url=REST_BASE_URL, timeout=15.0)


def search_problems(
    query: str,
    competition: str = "",
    year_min: int = 0,
    year_max: int = 0,
    recent_first: bool = False,
    limit: int = 10,
) -> dict:
    """Hybrid semantic + lexical search over competition math problem statements.

    Use this for any open-ended question about what problems exist on a topic,
    e.g. "recent questions on combinatorics", "problems about cyclic
    quadrilaterals", "AIME problems on polynomial roots since 2015".

    Args:
        query: The natural-language topic or concept to search for (required).
        competition: Optional exact competition code to filter by, one of
            AMC10, AMC12, AIME, HMMT_FEB, HMMT_NOV, HMMT_INV, SMT, PUMAC,
            CHMMC, CMM, MPG_MAIN, MPG_OLY. Leave empty to search all.
        year_min: Optional earliest competition year to include (0 = no limit).
        year_max: Optional latest competition year to include (0 = no limit).
        recent_first: If true, sort matching problems by year descending
            instead of by relevance — use this whenever the user asks for
            "recent"/"latest"/"newest" problems.
        limit: Max number of results (default 10, max 100).

    Returns:
        {"query": str, "results": [{"canonical_code", "statement_text",
        "competition", "year", "paper_code", "rrf_score", "semantic_rank",
        "lexical_rank"}, ...]}
    """
    body: dict = {"query": query, "limit": min(limit, 100), "filters": {}}
    if competition:
        body["filters"]["competition"] = competition
    if year_min:
        body["filters"]["year_min"] = year_min
    if year_max:
        body["filters"]["year_max"] = year_max
    if recent_first:
        body["order_by"] = "year_desc"
    with _client() as client:
        response = client.post("/v1/search/problems", json=body)
        response.raise_for_status()
        return response.json()


def get_problem_by_code(canonical_code: str) -> dict:
    """Fetch full detail for one problem by its canonical code (e.g. 'AIME_2023_I_Q11'),
    including its statement, official answer, tagged concepts/techniques, and
    all known solutions. Use this after search_problems to show a full solution.
    """
    with _client() as client:
        response = client.get(f"/v1/problems/by-code/{canonical_code}")
        if response.status_code == 404:
            return {"error": f"no problem found with canonical_code={canonical_code!r}"}
        response.raise_for_status()
        return response.json()


def list_competitions() -> list[dict]:
    """List all competitions tracked in the corpus (AMC, AIME, HMMT, SMT, PUMaC, CHMMC, CMM, MPG)."""
    with _client() as client:
        response = client.get("/v1/competitions")
        response.raise_for_status()
        return response.json()


def get_corpus_coverage() -> list[dict]:
    """Per-competition ingestion statistics: how many papers/problems are in the
    database and how many have concept/technique tags assigned so far. Use this
    to answer questions like "how much of HMMT do you have" or "is the corpus
    complete".
    """
    with _client() as client:
        response = client.get("/v1/corpus/coverage")
        response.raise_for_status()
        return response.json()


def list_concepts(domain: str = "", limit: int = 50) -> list[dict]:
    """List taxonomy concepts (e.g. 'Vieta's formulas', 'Law of Sines'), optionally
    filtered by a domain substring like 'Algebra' or 'Geometry'.
    """
    with _client() as client:
        params = {"limit": min(limit, 200)}
        if domain:
            params["domain"] = domain
        response = client.get("/v1/concepts", params=params)
        response.raise_for_status()
        return response.json()


def get_problems_for_concept(concept_slug: str, limit: int = 25) -> list[dict]:
    """List problems tagged with a specific concept slug (see list_concepts for slugs)."""
    with _client() as client:
        response = client.get(f"/v1/concepts/{concept_slug}/problems", params={"limit": min(limit, 200)})
        response.raise_for_status()
        return response.json()
