"""Read queries against the mathbank corpus schema (core.*, knowledge.*).

Raw SQL via SQLAlchemy Core — the schema is managed by mathbank-db/sql/001_schema.sql,
not by this service, so there are no ORM models here on purpose.
"""
from __future__ import annotations

from sqlalchemy import text

from mathbank_rest.db.postgres import engine
from mathbank_rest.db.problem_images import list_images


def list_competitions() -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT competition_id, external_code, name, level "
                "FROM core.competition ORDER BY name"
            )
        ).mappings()
        return [dict(r) for r in rows]


def list_problems(
    *,
    competition: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    concept: str | None = None,
    technique: str | None = None,
    limit: int = 25,
    offset: int = 0,
) -> list[dict]:
    clauses = []
    params: dict = {"limit": limit, "offset": offset}

    if competition:
        clauses.append("comp.external_code = :competition")
        params["competition"] = competition
    if year_min is not None:
        clauses.append("ed.year >= :year_min")
        params["year_min"] = year_min
    if year_max is not None:
        clauses.append("ed.year <= :year_max")
        params["year_max"] = year_max
    if concept:
        clauses.append(
            "EXISTS (SELECT 1 FROM knowledge.problem_concept pc "
            "JOIN knowledge.concept c ON c.concept_id = pc.concept_id "
            "WHERE pc.problem_id = p.problem_id AND c.slug = :concept)"
        )
        params["concept"] = concept
    if technique:
        clauses.append(
            "EXISTS (SELECT 1 FROM knowledge.problem_technique pt "
            "JOIN knowledge.technique t ON t.technique_id = pt.technique_id "
            "WHERE pt.problem_id = p.problem_id AND t.slug = :technique)"
        )
        params["technique"] = technique

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    query = text(
        f"""
        SELECT p.canonical_code, p.problem_number, p.official_answer, p.source_url,
               pa.paper_code, ed.year, comp.name AS competition
        FROM core.problem p
        JOIN core.paper pa ON pa.paper_id = p.paper_id
        JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
        JOIN core.competition comp ON comp.competition_id = ed.competition_id
        {where}
        ORDER BY comp.name, ed.year, pa.paper_code, p.problem_number
        LIMIT :limit OFFSET :offset
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings()
        return [dict(r) for r in rows]


def get_problem_by_code(canonical_code: str) -> dict | None:
    with engine.connect() as conn:
        problem = conn.execute(
            text(
                """
                SELECT p.problem_id, p.canonical_code, p.problem_number, p.statement_text,
                       p.official_answer, p.source_url, p.difficulty_band, p.classification_status,
                       pa.paper_code, ed.year, comp.name AS competition
                FROM core.problem p
                JOIN core.paper pa ON pa.paper_id = p.paper_id
                JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
                JOIN core.competition comp ON comp.competition_id = ed.competition_id
                WHERE p.canonical_code = :code
                """
            ),
            {"code": canonical_code},
        ).mappings().first()
        if problem is None:
            return None
        result = dict(problem)

        concepts = conn.execute(
            text(
                """
                SELECT c.slug, c.name, pc.role, pc.confidence
                FROM knowledge.problem_concept pc
                JOIN knowledge.concept c ON c.concept_id = pc.concept_id
                WHERE pc.problem_id = :pid
                """
            ),
            {"pid": result["problem_id"]},
        ).mappings()
        techniques = conn.execute(
            text(
                """
                SELECT t.slug, t.name, pt.role, pt.confidence
                FROM knowledge.problem_technique pt
                JOIN knowledge.technique t ON t.technique_id = pt.technique_id
                WHERE pt.problem_id = :pid
                """
            ),
            {"pid": result["problem_id"]},
        ).mappings()
        solutions = conn.execute(
            text(
                """
                SELECT solution_kind, revision, body_markdown, verification_status
                FROM core.solution
                WHERE problem_id = :pid
                ORDER BY solution_kind, revision
                """
            ),
            {"pid": result["problem_id"]},
        ).mappings()

        result["concepts"] = [dict(r) for r in concepts]
        result["techniques"] = [dict(r) for r in techniques]
        result["solutions"] = [dict(r) for r in solutions]
        result["diagrams"] = list_images(conn, canonical_code)
        del result["problem_id"]
        return result


def list_concepts(*, domain: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    clause = "WHERE c.name ILIKE :domain" if domain else ""
    query = text(
        f"""
        SELECT c.slug, c.name, c.level, c.description
        FROM knowledge.concept c
        {clause}
        ORDER BY c.level NULLS LAST, c.name
        LIMIT :limit OFFSET :offset
        """
    )
    params: dict = {"limit": limit, "offset": offset}
    if domain:
        params["domain"] = f"%{domain}%"
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings()
        return [dict(r) for r in rows]


def get_concept_problems(slug: str, *, limit: int = 25, offset: int = 0) -> list[dict]:
    # Concepts form a hierarchy (knowledge.concept_relation, HAS_SUBCONCEPT —
    # e.g. 'count' -> 'count-subset'/'count-pie'/...). Classification always
    # tags the most specific leaf concept, never the broad parent, so a plain
    # `WHERE c.slug = :slug` match against a parent slug like 'count' returns
    # ~0 rows even though hundreds of problems are tagged with its children.
    # See GOTCHAS.md #16 for the regression this caused in retrieval eval.
    query = text(
        """
        WITH RECURSIVE concept_closure AS (
            SELECT concept_id, ARRAY[concept_id] AS path
            FROM knowledge.concept WHERE slug = :slug
            UNION ALL
            SELECT cr.to_concept_id, cc.path || cr.to_concept_id
            FROM knowledge.concept_relation cr
            JOIN concept_closure cc ON cc.concept_id = cr.from_concept_id
            WHERE cr.relation_type = 'HAS_SUBCONCEPT'
              AND NOT cr.to_concept_id = ANY(cc.path)
        ),
        matched AS (
            SELECT DISTINCT ON (pc.problem_id)
                   pc.problem_id, pc.role, pc.confidence, c.slug AS matched_concept_slug
            FROM knowledge.problem_concept pc
            JOIN concept_closure cc ON cc.concept_id = pc.concept_id
            JOIN knowledge.concept c ON c.concept_id = pc.concept_id
            ORDER BY pc.problem_id, (pc.role = 'PRIMARY') DESC, pc.confidence DESC NULLS LAST
        )
        SELECT p.canonical_code, p.problem_number, comp.name AS competition, ed.year,
               matched.role, matched.confidence, matched.matched_concept_slug
        FROM matched
        JOIN core.problem p ON p.problem_id = matched.problem_id
        JOIN core.paper pa ON pa.paper_id = p.paper_id
        JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
        JOIN core.competition comp ON comp.competition_id = ed.competition_id
        ORDER BY ed.year, p.problem_number
        LIMIT :limit OFFSET :offset
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"slug": slug, "limit": limit, "offset": offset}).mappings()
        return [dict(r) for r in rows]


def get_concept_neighbors(slug: str) -> list[dict]:
    query = text(
        """
        SELECT b.slug, b.name, cr.relation_type, cr.strength, 'outgoing' AS direction
        FROM knowledge.concept_relation cr
        JOIN knowledge.concept a ON a.concept_id = cr.from_concept_id
        JOIN knowledge.concept b ON b.concept_id = cr.to_concept_id
        WHERE a.slug = :slug
        UNION ALL
        SELECT a.slug, a.name, cr.relation_type, cr.strength, 'incoming' AS direction
        FROM knowledge.concept_relation cr
        JOIN knowledge.concept a ON a.concept_id = cr.from_concept_id
        JOIN knowledge.concept b ON b.concept_id = cr.to_concept_id
        WHERE b.slug = :slug
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"slug": slug}).mappings()
        return [dict(r) for r in rows]


def list_techniques(*, limit: int = 50, offset: int = 0) -> list[dict]:
    query = text(
        """
        SELECT slug, name, description
        FROM knowledge.technique
        ORDER BY name
        LIMIT :limit OFFSET :offset
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"limit": limit, "offset": offset}).mappings()
        return [dict(r) for r in rows]


def get_technique_problems(slug: str, *, limit: int = 25, offset: int = 0) -> list[dict]:
    query = text(
        """
        SELECT p.canonical_code, p.problem_number, comp.name AS competition, ed.year,
               pt.role, pt.confidence
        FROM knowledge.problem_technique pt
        JOIN knowledge.technique t ON t.technique_id = pt.technique_id
        JOIN core.problem p ON p.problem_id = pt.problem_id
        JOIN core.paper pa ON pa.paper_id = p.paper_id
        JOIN core.competition_edition ed ON ed.edition_id = pa.edition_id
        JOIN core.competition comp ON comp.competition_id = ed.competition_id
        WHERE t.slug = :slug
        ORDER BY ed.year, p.problem_number
        LIMIT :limit OFFSET :offset
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"slug": slug, "limit": limit, "offset": offset}).mappings()
        return [dict(r) for r in rows]


def corpus_coverage() -> list[dict]:
    query = text(
        """
        SELECT comp.name AS competition,
               count(DISTINCT pa.paper_id) AS papers,
               count(DISTINCT p.problem_id) AS problems,
               count(DISTINCT pc.problem_id) AS problems_with_concept,
               count(DISTINCT pt.problem_id) AS problems_with_technique
        FROM core.competition comp
        JOIN core.competition_edition ed ON ed.competition_id = comp.competition_id
        JOIN core.paper pa ON pa.edition_id = ed.edition_id
        JOIN core.problem p ON p.paper_id = pa.paper_id
        LEFT JOIN knowledge.problem_concept pc ON pc.problem_id = p.problem_id
        LEFT JOIN knowledge.problem_technique pt ON pt.problem_id = p.problem_id
        GROUP BY comp.name
        ORDER BY comp.name
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query).mappings()
        return [dict(r) for r in rows]
