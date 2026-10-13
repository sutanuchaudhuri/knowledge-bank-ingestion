"""Problem-level RRF combining pgvector/FTS and reviewed Neo4j evidence."""

from __future__ import annotations

import logging
import re

from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from sqlalchemy import text

from mathbank_rest.db import vector_search
from mathbank_rest.db.graph import driver
from mathbank_rest.db.postgres import engine

logger = logging.getLogger(__name__)


def graph_candidates(
    query: str, seeds: list[str], eligible: list[str] | None, limit: int
) -> list[dict]:
    terms = list(dict.fromkeys(re.findall(r"[a-z0-9]{3,}", query.lower())))
    terms = [
        t
        for t in terms
        if t
        not in {
            "the",
            "and",
            "with",
            "for",
            "find",
            "problems",
            "questions",
            "similar",
            "show",
            "recent",
            "latest",
            "about",
            "some",
            "give",
            "that",
            "this",
        }
    ]
    with driver.session() as session:
        return [
            dict(r)
            for r in session.run(
                """
            // Resolve the small set of candidate tags first; expanding every
            // reviewed Problem->tag link before filtering took 30s+ on Aura.
            CALL {
              MATCH (tag)
              WHERE (tag:Concept OR tag:Technique OR
                     (tag:Skill AND tag.review_status='REVIEWED'))
              WITH tag,
                size([term IN $terms WHERE toLower(coalesce(tag.name,'')+' '+
                     replace(coalesce(tag.slug,''),'-',' ')) CONTAINS term]) AS matches
              WHERE matches > 0
              RETURN tag, matches, [] AS seed_codes
              UNION ALL
              MATCH (seed:Problem)-[sr:TESTS|USES_TECHNIQUE|REQUIRES|PRACTICES]->(tag)
              WHERE seed.canonical_code IN $seeds AND sr.review_status='REVIEWED'
                AND (tag:Concept OR tag:Technique OR
                     (tag:Skill AND tag.review_status='REVIEWED'))
              RETURN tag, 0 AS matches, collect(DISTINCT seed.canonical_code) AS seed_codes
            }
            WITH tag, max(matches) AS matches, collect(seed_codes) AS nested
            WITH tag, matches,
              reduce(acc=[], s IN nested | acc + s) AS seed_codes
            MATCH (p:Problem)-[link:TESTS|USES_TECHNIQUE|REQUIRES|PRACTICES]->(tag)
            WHERE link.review_status='REVIEWED'
              AND ($eligible IS NULL OR p.canonical_code IN $eligible)
            WITH p,tag,link,matches,
              size([c IN seed_codes WHERE c <> p.canonical_code]) AS shared
            WHERE matches > 0 OR shared > 0
            WITH p,sum(matches*2+shared) AS score,
              collect({kind:type(link),slug:tag.slug,name:tag.name,
                       review_status:link.review_status,source:link.source}) AS evidence
            RETURN p.canonical_code AS canonical_code,score,evidence
            ORDER BY score DESC,canonical_code LIMIT $limit
        """,
                terms=terms,
                seeds=seeds,
                eligible=eligible,
                limit=limit,
            )
        ]


def fuse(vector_rows: list[dict], graph_rows: list[dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for field in ("semantic_rank", "lexical_rank"):
        ranked = sorted(
            (r for r in vector_rows if r.get(field) is not None), key=lambda r: r[field]
        )
        codes = list(dict.fromkeys(r["canonical_code"] for r in ranked))
        for rank, code in enumerate(codes, 1):
            merged.setdefault(
                code,
                {
                    "rrf_score": 0.0,
                    "semantic_rank": None,
                    "lexical_rank": None,
                    "graph_rank": None,
                    "graph_evidence": [],
                },
            )
            merged[code][field] = rank
            merged[code]["rrf_score"] += 1 / (60 + rank)
    for rank, row in enumerate(graph_rows, 1):
        code = row["canonical_code"]
        merged.setdefault(
            code,
            {
                "rrf_score": 0.0,
                "semantic_rank": None,
                "lexical_rank": None,
                "graph_rank": None,
                "graph_evidence": [],
            },
        )
        if merged[code]["graph_rank"] is None:
            merged[code]["graph_rank"] = rank
            merged[code]["rrf_score"] += 1 / (60 + rank)
            merged[code]["graph_evidence"] = row["evidence"]
    return merged


def search_problems(
    query: str,
    *,
    competition: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    semantic: bool = True,
    lexical: bool = True,
    graph: bool = True,
    order_by: str = "relevance",
    limit: int = 25,
) -> dict:
    filters = {"competition": competition, "year_min": year_min, "year_max": year_max}
    candidates = min(max(limit * 4, 100), 400)
    rows = (
        vector_search.search_problems(
            query,
            competition=competition,
            year_min=year_min,
            year_max=year_max,
            semantic=semantic,
            lexical=lexical,
            limit=candidates,
        )
        if semantic or lexical
        else []
    )
    warnings, graph_rows = [], []
    if graph:
        eligible = None
        if any(v is not None for v in filters.values()):
            with engine.connect() as conn:
                eligible = list(
                    conn.execute(
                        text("""
                    SELECT p.canonical_code FROM core.problem p JOIN core.paper pa USING(paper_id)
                    JOIN core.competition_edition ed USING(edition_id)
                    JOIN core.competition comp USING(competition_id)
                    WHERE (CAST(:competition AS text) IS NULL OR comp.external_code=:competition)
                      AND (CAST(:year_min AS integer) IS NULL OR ed.year>=:year_min)
                      AND (CAST(:year_max AS integer) IS NULL OR ed.year<=:year_max)
                """),
                        filters,
                    ).scalars()
                )
        try:
            semantic_rows = sorted(
                (r for r in rows if r.get("semantic_rank") is not None),
                key=lambda r: r["semantic_rank"],
            )
            seeds = list(dict.fromkeys(r["canonical_code"] for r in semantic_rows))[:25]
            graph_rows = graph_candidates(query, seeds, eligible, candidates)
        except (Neo4jError, ServiceUnavailable, SessionExpired) as exc:
            logger.exception("Graph retrieval unavailable")
            warnings.append(
                f"Graph retrieval unavailable ({type(exc).__name__}); "
                "results use the remaining requested sources."
            )
    merged = fuse(rows, graph_rows)
    results = []
    if merged:
        with engine.connect() as conn:
            canonical = conn.execute(
                text("""
                SELECT p.canonical_code,p.problem_number,p.statement_text,p.source_url,
                       comp.name AS competition,comp.external_code AS competition_code,
                       ed.year,pa.paper_code
                FROM core.problem p JOIN core.paper pa USING(paper_id)
                JOIN core.competition_edition ed USING(edition_id)
                JOIN core.competition comp USING(competition_id)
                WHERE p.canonical_code=ANY(:codes)
                  AND (CAST(:competition AS text) IS NULL OR comp.external_code=:competition)
                  AND (CAST(:year_min AS integer) IS NULL OR ed.year>=:year_min)
                  AND (CAST(:year_max AS integer) IS NULL OR ed.year<=:year_max)
            """),
                {"codes": list(merged), **filters},
            ).mappings()
            results = [dict(r) | merged[r["canonical_code"]] for r in canonical]
        results.sort(key=lambda r: (-r["rrf_score"], r["canonical_code"]))
        if order_by == "year_desc":
            results.sort(key=lambda r: -(r["year"] or 0))
        elif order_by == "year_asc":
            results.sort(key=lambda r: r["year"] if r["year"] is not None else 9999)
    return {
        "query": query,
        "results": results[:limit],
        "warnings": warnings,
        "retrieval": {
            "semantic": semantic,
            "lexical": lexical,
            "graph": "unavailable" if warnings else "queried" if graph else "disabled",
            "graph_candidates": len(graph_rows),
            "vector_lexical_candidates": len(rows),
        },
    }
