"""Hybrid (semantic + lexical) retrieval over search.chunk / search.embedding.

Per mathematics_tutor_db_plan_v2/vector/10_reference_sql_and_query_examples.md
(RRF fusion) and vector/11_rest_vector_search_contracts.md (task-oriented API
— callers pass a query string and filters, never raw vectors/model UUIDs).
"""
from __future__ import annotations

from functools import lru_cache

from openai import OpenAI
from sqlalchemy import text

from mathbank_rest.db.postgres import engine
from mathbank_rest.project_credentials import configure_openai

EMBEDDING_MODEL_NAME = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

_client = OpenAI(api_key=configure_openai())


@lru_cache(maxsize=1)
def _active_model_id() -> str:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT embedding_model_id FROM search.embedding_model "
                "WHERE model_name = :name AND status = 'ACTIVE' LIMIT 1"
            ),
            {"name": EMBEDDING_MODEL_NAME},
        ).first()
    if row is None:
        raise RuntimeError(f"no ACTIVE embedding model named {EMBEDDING_MODEL_NAME!r}")
    return str(row[0])


def embed_query(query_text: str) -> str:
    """Returns a pgvector literal string, e.g. '[0.1,0.2,...]'."""
    response = _client.embeddings.create(model=EMBEDDING_MODEL_NAME, input=[query_text])
    values = response.data[0].embedding
    return "[" + ",".join(repr(v) for v in values) + "]"


def search_problems(
    query_text: str,
    *,
    competition: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    semantic: bool = True,
    lexical: bool = True,
    order_by: str = "relevance",
    limit: int = 25,
) -> list[dict]:
    """Hybrid RRF search over PROBLEM_STATEMENT chunks, returning ranked problems.

    order_by: 'relevance' (default, RRF score) | 'year_desc' | 'year_asc' —
    use 'year_desc' for "recent problems on X" style queries.
    """
    model_id = _active_model_id() if semantic else None
    query_vector = embed_query(query_text) if semantic else None

    clauses = []
    params: dict = {
        "model_id": model_id,
        "query_vector": query_vector,
        "query_text": query_text,
        "limit": limit,
        "candidate_limit": max(limit * 4, 100),
    }
    if competition:
        clauses.append("comp.external_code = :competition")
        params["competition"] = competition
    if year_min is not None:
        clauses.append("ed.year >= :year_min")
        params["year_min"] = year_min
    if year_max is not None:
        clauses.append("ed.year <= :year_max")
        params["year_max"] = year_max
    filter_sql = f"AND {' AND '.join(clauses)}" if clauses else ""

    order_sql = {
        "year_desc": "ed.year DESC NULLS LAST, combined.rrf_score DESC",
        "year_asc": "ed.year ASC NULLS LAST, combined.rrf_score DESC",
    }.get(order_by, "combined.rrf_score DESC")

    # Filters are applied here, BEFORE the top-N ANN/lexical ranking, not after.
    # Ranking first and filtering the resulting top-`candidate_limit` rows would
    # silently return zero results for any competition whose chunks don't happen
    # to fall in the global top-N nearest neighbors for a given query (e.g. a
    # competition filter narrowing to a small/underrepresented subset).
    eligible_cte = f"""
        eligible_problem AS (
            SELECT p.problem_id,
                   regexp_replace('[Problem] ' || p.statement_text,'[[:space:]]+$','') AS rendered
            FROM core.problem p
            JOIN core.paper pa ON pa.paper_id = p.paper_id
            JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
            JOIN core.competition comp ON comp.competition_id = ed.competition_id
            WHERE TRUE {filter_sql}
        )
    """

    semantic_cte = (
        """
        semantic AS (
            SELECT e.chunk_id,
                   row_number() OVER (ORDER BY e.embedding::public.vector(1536) OPERATOR(public.<=>) CAST(:query_vector AS public.vector(1536))) AS rnk
            FROM search.embedding e
            JOIN search.chunk c ON c.chunk_id = e.chunk_id
            JOIN search.representation r ON r.representation_id=c.representation_id
            JOIN eligible_problem ep ON ep.problem_id = c.problem_id
            WHERE e.embedding_model_id = :model_id AND e.status = 'ACTIVE'
              AND r.status='ACTIVE' AND r.representation_kind='PROBLEM_STATEMENT'
              AND r.rendered_text=ep.rendered
            ORDER BY e.embedding::public.vector(1536) OPERATOR(public.<=>) CAST(:query_vector AS public.vector(1536))
            LIMIT :candidate_limit
        )
        """
        if semantic
        else "semantic AS (SELECT NULL::uuid AS chunk_id, NULL::bigint AS rnk WHERE false)"
    )
    lexical_cte = (
        """
        lexical AS (
            SELECT c.chunk_id,
                   row_number() OVER (ORDER BY ts_rank_cd(c.textsearch, websearch_to_tsquery('english', :query_text)) DESC) AS rnk
            FROM search.chunk c
            JOIN search.representation r ON r.representation_id=c.representation_id
            JOIN eligible_problem ep ON ep.problem_id = c.problem_id
            WHERE c.textsearch @@ websearch_to_tsquery('english', :query_text)
              AND r.status='ACTIVE' AND r.representation_kind='PROBLEM_STATEMENT'
              AND r.rendered_text=ep.rendered
            ORDER BY ts_rank_cd(c.textsearch, websearch_to_tsquery('english', :query_text)) DESC
            LIMIT :candidate_limit
        )
        """
        if lexical
        else "lexical AS (SELECT NULL::uuid AS chunk_id, NULL::bigint AS rnk WHERE false)"
    )

    query = text(
        f"""
        WITH {eligible_cte},
        {semantic_cte},
        {lexical_cte},
        combined AS (
            SELECT coalesce(s.chunk_id, l.chunk_id) AS chunk_id,
                   coalesce(1.0 / (60 + s.rnk), 0) + coalesce(1.0 / (60 + l.rnk), 0) AS rrf_score,
                   s.rnk AS semantic_rank, l.rnk AS lexical_rank
            FROM semantic s
            FULL OUTER JOIN lexical l ON l.chunk_id = s.chunk_id
        )
        SELECT p.canonical_code, p.problem_number, p.statement_text, p.source_url,
               comp.name AS competition, ed.year, pa.paper_code,
               combined.rrf_score, combined.semantic_rank, combined.lexical_rank
        FROM combined
        JOIN search.chunk c ON c.chunk_id = combined.chunk_id
        JOIN core.problem p ON p.problem_id = c.problem_id
        JOIN core.paper pa ON pa.paper_id = p.paper_id
        JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
        JOIN core.competition comp ON comp.competition_id = ed.competition_id
        WHERE c.problem_id IS NOT NULL
        ORDER BY {order_sql}
        LIMIT :limit
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings()
        return [dict(r) for r in rows]
