"""Step-level hybrid retrieval over solution steps and published learning items (v2 Phase 5).

runtime_extension/07_VECTOR_METADATA_AND_RAG.md: apply hard structured filters first, then rank the
remaining candidates with semantic + lexical reciprocal-rank fusion. Filters use canonical taxonomy
IDs only. Learning items are re-checked against the live row (APPROVED, student-visible, no-proof)
so a stale embedding can never surface unpublished content.

Semantic distance is computed exactly over the filtered candidate set rather than through the
global HNSW index, which would apply filters after the approximate top-N and silently lose rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import text

from mathbank_rest.db.postgres import engine

PROFILE_NAME = "pedagogy_step_v2"
Unit = Literal["step", "learning_item", "taxonomy"]
TAXONOMY_NODE_TYPES = ("DOMAIN", "CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE")


@dataclass(frozen=True)
class _UnitSpec:
    kinds: tuple[str, ...]
    eligible_join: str
    filters: dict[str, str]
    entity_expr: str


_UNITS: dict[str, _UnitSpec] = {
    "step": _UnitSpec(
        kinds=("SOLUTION_STEP",),
        eligible_join=(
            "JOIN pedagogy.solution_step s ON s.solution_step_id = c.solution_step_id "
            "AND s.publication_status = 'PUBLISHED'"
        ),
        filters={
            "skill_node_id": "c.skill_node_id = :skill_node_id",
            "subconcept_node_id": "c.subconcept_node_id = :subconcept_node_id",
            "concept_node_id": "c.concept_node_id = :concept_node_id",
            "step_type": "s.step_type = :step_type",
            "tutor_role": "s.tutor_role = :tutor_role",
            "is_checkpoint": "s.is_checkpoint = :is_checkpoint",
            "problem_id": "c.problem_id = CAST(:problem_id AS uuid)",
            "exclude_problem_id": "c.problem_id <> CAST(:exclude_problem_id AS uuid)",
            "max_hint_level": "s.hint_level <= :max_hint_level",
            "technique_node_id": (
                "EXISTS (SELECT 1 FROM pedagogy.solution_step_technique t "
                "WHERE t.solution_step_id = s.solution_step_id AND t.technique_node_id = :technique_node_id "
                "AND t.review_status = 'APPROVED')"
            ),
        },
        entity_expr="c.solution_step_id",
    ),
    "learning_item": _UnitSpec(
        kinds=("LEARNING_ITEM_QUESTION", "LEARNING_ITEM_SKILL_SIGNATURE"),
        eligible_join=(
            "JOIN pedagogy.learning_item li ON li.learning_item_id = c.learning_item_id "
            "AND li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof"
        ),
        filters={
            "target_skill_node_id": "c.skill_node_id = :target_skill_node_id",
            "target_subconcept_node_id": "c.subconcept_node_id = :target_subconcept_node_id",
            "learning_item_type": "li.transformed_form = :learning_item_type",
            "transformation_type": "li.transformation_type = :transformation_type",
            "difficulty": "li.difficulty_direction = :difficulty",
            "anchor_step_id": (
                "EXISTS (SELECT 1 FROM pedagogy.learning_item_step_anchor a "
                "WHERE a.learning_item_id = li.learning_item_id AND a.solution_step_id = :anchor_step_id)"
            ),
            "exclude_problem_id": "li.source_problem_id <> CAST(:exclude_problem_id AS uuid)",
        },
        entity_expr="c.learning_item_id",
    ),
    # Taxonomy chunks carry the node id only in metadata (source_entity_id is a uuid5 surrogate).
    "taxonomy": _UnitSpec(
        kinds=("TAXONOMY_NODE",),
        eligible_join=(
            "JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = c.metadata->>'taxonomy_node_id'"
        ),
        filters={
            "node_types": "n.node_type = ANY(:node_types)",
            "chapter_number": "n.chapter_number = :chapter_number",
        },
        entity_expr="n.taxonomy_node_id",
    ),
}


def build_search_sql(
    unit: Unit, filters: dict, *, semantic: bool, lexical: bool
) -> tuple[str, dict]:
    """Return (sql, params). Only allow-listed filter names are accepted; values are bound."""
    if not (semantic or lexical):
        raise ValueError("At least one of semantic or lexical ranking is required")
    spec = _UNITS[unit]
    unknown = set(filters) - set(spec.filters)
    if unknown:
        raise ValueError(f"Unsupported {unit} filter(s): {sorted(unknown)}")
    active = {k: v for k, v in filters.items() if v is not None}
    where = " ".join(f"AND {spec.filters[k]}" for k in sorted(active))
    eligible = f"""
        eligible AS (
            SELECT c.chunk_id, {spec.entity_expr} AS entity_id, c.textsearch
              FROM search.chunk c
              JOIN search.representation r ON r.representation_id = c.representation_id
              JOIN search.preprocessing_profile pp ON pp.preprocessing_profile_id = r.preprocessing_profile_id
              {spec.eligible_join}
             WHERE r.status = 'ACTIVE' AND pp.name = :profile_name
               AND r.representation_kind = ANY(:kinds) {where}
        )"""
    semantic_cte = (
        """
        semantic AS (
            SELECT el.entity_id,
                   min(e.embedding OPERATOR(public.<=>) CAST(:query_vector AS public.vector)) AS distance
              FROM eligible el
              JOIN search.embedding e ON e.chunk_id = el.chunk_id
             WHERE e.embedding_model_id = CAST(:model_id AS uuid) AND e.status = 'ACTIVE'
             GROUP BY el.entity_id
        ), semantic_ranked AS (
            SELECT entity_id, distance, row_number() OVER (ORDER BY distance) AS rnk
              FROM semantic ORDER BY distance LIMIT :candidate_limit
        )"""
        if semantic
        else """
        semantic_ranked AS (
            SELECT NULL::text AS entity_id, NULL::float8 AS distance, NULL::bigint AS rnk WHERE false
        )"""
    )
    lexical_cte = (
        """
        lexical AS (
            SELECT el.entity_id,
                   max(ts_rank_cd(el.textsearch, websearch_to_tsquery('english', :query_text))) AS score
              FROM eligible el
             WHERE el.textsearch @@ websearch_to_tsquery('english', :query_text)
             GROUP BY el.entity_id
        ), lexical_ranked AS (
            SELECT entity_id, row_number() OVER (ORDER BY score DESC) AS rnk
              FROM lexical ORDER BY score DESC LIMIT :candidate_limit
        )"""
        if lexical
        else """
        lexical_ranked AS (SELECT NULL::text AS entity_id, NULL::bigint AS rnk WHERE false)"""
    )
    sql = f"""
        WITH {eligible}, {semantic_cte}, {lexical_cte}
        SELECT coalesce(s.entity_id, l.entity_id) AS entity_id,
               coalesce(1.0 / (60 + s.rnk), 0) + coalesce(1.0 / (60 + l.rnk), 0) AS rrf_score,
               s.rnk AS semantic_rank, l.rnk AS lexical_rank, s.distance
          FROM semantic_ranked s
          FULL OUTER JOIN lexical_ranked l ON l.entity_id = s.entity_id
         ORDER BY rrf_score DESC, entity_id
         LIMIT :limit"""
    params = {"profile_name": PROFILE_NAME, "kinds": list(spec.kinds), **active}
    return sql, params


_STEP_DETAILS = """
SELECT s.solution_step_id, s.problem_id::text AS problem_id, s.solution_id::text AS solution_id,
       s.solution_part_id, s.global_step_index, s.step_type, s.tutor_role, s.hint_level,
       s.is_checkpoint, s.skill_node_id, s.skill_name, s.subconcept_node_id, s.concept_node_id,
       p.canonical_code AS problem_code, s.step_text
  FROM pedagogy.solution_step s JOIN core.problem p ON p.problem_id = s.problem_id
 WHERE s.solution_step_id = ANY(:ids)
"""

_ITEM_DETAILS = """
SELECT li.learning_item_id, li.source_problem_id::text AS source_problem_id,
       li.transformed_form AS learning_item_type, li.transformation_type,
       li.target_skill_node_id, li.target_subconcept_node_id, li.difficulty_direction,
       li.question_text, li.choices, li.diagram_strategy
  FROM pedagogy.learning_item li
 WHERE li.learning_item_id = ANY(:ids)
   AND li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof
"""


# Each node maps 1:1 to a knowledge.{concept,skill,technique} row whose slug is what the corpus
# routes (/v1/concepts/{slug}/problems, /v1/techniques/{slug}/problems, /v1/tutor/prerequisites/{slug})
# accept. Problem counts come from published solution steps (techniques: approved step links).
_TAXONOMY_DETAILS = """
SELECT n.taxonomy_node_id, n.node_type, n.name, n.parent_node_id, parent.name AS parent_name,
       n.chapter_number, n.section_number,
       coalesce(kc.slug, ks.slug, kt.slug) AS slug,
       CASE WHEN kc.slug IS NOT NULL THEN 'concept' WHEN ks.slug IS NOT NULL THEN 'skill'
            WHEN kt.slug IS NOT NULL THEN 'technique' END AS slug_kind,
       ex.problem_count, ex.example_problem_codes
  FROM pedagogy.taxonomy_node n
  LEFT JOIN pedagogy.taxonomy_node parent ON parent.taxonomy_node_id = n.parent_node_id
  LEFT JOIN knowledge.concept kc ON kc.concept_id = n.concept_id
  LEFT JOIN knowledge.skill ks ON ks.skill_id = n.skill_id
  LEFT JOIN knowledge.technique kt ON kt.technique_id = n.technique_id
  LEFT JOIN LATERAL (
       SELECT count(*) AS problem_count,
              (array_agg(p.canonical_code ORDER BY p.canonical_code))[1:5] AS example_problem_codes
         FROM core.problem p
        WHERE p.problem_id IN (
              SELECT s.problem_id FROM pedagogy.solution_step s
               WHERE s.publication_status = 'PUBLISHED'
                 AND ((n.node_type = 'SKILL' AND s.skill_node_id = n.taxonomy_node_id)
                   OR (n.node_type = 'SUBCONCEPT' AND s.subconcept_node_id = n.taxonomy_node_id)
                   OR (n.node_type = 'CONCEPT' AND s.concept_node_id = n.taxonomy_node_id)
                   OR (n.node_type = 'TECHNIQUE' AND EXISTS (
                        SELECT 1 FROM pedagogy.solution_step_technique t
                         WHERE t.solution_step_id = s.solution_step_id
                           AND t.technique_node_id = n.taxonomy_node_id AND t.review_status = 'APPROVED')
                       AND NOT EXISTS (
                         SELECT 1 FROM knowledge.problem_technique rejected
                          WHERE rejected.problem_id=s.problem_id
                            AND rejected.technique_id=n.technique_id
                            AND rejected.review_status='REJECTED'))))
  ) ex ON true
 WHERE n.taxonomy_node_id = ANY(:ids)
"""

_DETAILS = {"step": (_STEP_DETAILS, "solution_step_id"), "learning_item": (_ITEM_DETAILS, "learning_item_id"),
            "taxonomy": (_TAXONOMY_DETAILS, "taxonomy_node_id")}


def _search(unit: Unit, query_text: str, filters: dict, *, semantic: bool, lexical: bool,
            limit: int, query_vector: str | None = None) -> list[dict]:
    if not 1 <= limit <= 50:
        raise ValueError("limit must be between 1 and 50")
    sql, params = build_search_sql(unit, filters, semantic=semantic, lexical=lexical)
    params.update({"query_text": query_text, "limit": limit, "candidate_limit": max(limit * 4, 100)})
    if semantic:
        from mathbank_rest.db import vector_search  # imports the OpenAI client lazily

        params["model_id"] = vector_search._active_model_id()
        params["query_vector"] = query_vector or vector_search.embed_query(query_text)
    with engine.connect() as conn:
        ranked = [dict(r) for r in conn.execute(text(sql), params).mappings()]
        if not ranked:
            return []
        details_sql, key = _DETAILS[unit]
        details = {
            row[key]: dict(row)
            for row in conn.execute(text(details_sql), {"ids": [r["entity_id"] for r in ranked]}).mappings()
        }
    results = []
    for r in ranked:
        detail = details.get(r["entity_id"])
        if detail is None:  # became ineligible between ranking and detail fetch
            continue
        detail.update(rrf_score=float(r["rrf_score"]), semantic_rank=r["semantic_rank"],
                      lexical_rank=r["lexical_rank"])
        results.append(detail)
    return results


def search_solution_steps(
    query_text: str,
    *,
    skill_node_id: str | None = None,
    subconcept_node_id: str | None = None,
    concept_node_id: str | None = None,
    step_type: str | None = None,
    tutor_role: str | None = None,
    is_checkpoint: bool | None = None,
    problem_id: str | None = None,
    exclude_problem_id: str | None = None,
    max_hint_level: int | None = None,
    technique_node_id: str | None = None,
    include_step_text: bool = False,
    semantic: bool = True,
    lexical: bool = True,
    limit: int = 10,
    query_vector: str | None = None,
) -> list[dict]:
    """Similar reasoning steps (STEP_HELP). Step text is solution content: callers must opt in.

    ``query_vector`` (pgvector text form) skips the paid query embedding, e.g. when the query is
    an already-embedded step.
    """
    filters = {
        "skill_node_id": skill_node_id, "subconcept_node_id": subconcept_node_id,
        "concept_node_id": concept_node_id, "step_type": step_type, "tutor_role": tutor_role,
        "is_checkpoint": is_checkpoint, "problem_id": problem_id,
        "exclude_problem_id": exclude_problem_id, "max_hint_level": max_hint_level,
        "technique_node_id": technique_node_id,
    }
    results = _search("step", query_text, filters, semantic=semantic, lexical=lexical, limit=limit,
                      query_vector=query_vector)
    if not include_step_text:
        for row in results:
            row.pop("step_text", None)
    return results


def search_learning_items(
    query_text: str,
    *,
    target_skill_node_id: str | None = None,
    target_subconcept_node_id: str | None = None,
    learning_item_type: str | None = None,
    transformation_type: str | None = None,
    difficulty: str | None = None,
    anchor_step_id: str | None = None,
    exclude_problem_id: str | None = None,
    semantic: bool = True,
    lexical: bool = True,
    limit: int = 10,
) -> list[dict]:
    """RECOVERY_PRACTICE candidates: always published, approved, no-proof learning items."""
    filters = {
        "target_skill_node_id": target_skill_node_id,
        "target_subconcept_node_id": target_subconcept_node_id,
        "learning_item_type": learning_item_type, "transformation_type": transformation_type,
        "difficulty": difficulty, "anchor_step_id": anchor_step_id,
        "exclude_problem_id": exclude_problem_id,
    }
    return _search("learning_item", query_text, filters, semantic=semantic, lexical=lexical, limit=limit)


def search_taxonomy_nodes(
    query_text: str,
    *,
    node_types: list[str] | None = None,
    chapter_number: int | None = None,
    semantic: bool = True,
    lexical: bool = True,
    limit: int = 10,
    query_vector: str | None = None,
) -> list[dict]:
    """Concept-level retrieval over the embedded TAXONOMY_NODE representations.

    Maps a free-text topic ("power of a point") to canonical taxonomy nodes plus the corpus slug
    and the number of problems that exercise each node. Returns no solution content.
    """
    if node_types:
        unknown = set(node_types) - set(TAXONOMY_NODE_TYPES)
        if unknown:
            raise ValueError(f"Unsupported node type(s): {sorted(unknown)}")
    filters = {"node_types": list(node_types) if node_types else None, "chapter_number": chapter_number}
    results = _search("taxonomy", query_text, filters, semantic=semantic, lexical=lexical, limit=limit,
                      query_vector=query_vector)
    for row in results:
        row["problem_count"] = int(row["problem_count"] or 0)
        row["example_problem_codes"] = list(row["example_problem_codes"] or [])
    return results


def similar_steps_for_step(solution_step_id: str, *, limit: int = 5, same_skill: bool = True) -> dict:
    """Practice candidates for a step: other problems' steps exercising the same skill.

    Uses the step's own stored ACTIVE embedding as the query vector (no paid call) and its skill
    name as the lexical query. Excludes the step's own problem and never returns step text.
    """
    from mathbank_rest.db import vector_search

    with engine.connect() as conn:
        anchor = conn.execute(text(
            "SELECT s.solution_step_id, s.problem_id::text AS problem_id, s.skill_node_id, s.skill_name, "
            "       s.step_type, (SELECT e.embedding::text FROM search.chunk c "
            "          JOIN search.representation r ON r.representation_id = c.representation_id "
            "          JOIN search.embedding e ON e.chunk_id = c.chunk_id "
            "         WHERE c.solution_step_id = s.solution_step_id AND r.representation_kind = 'SOLUTION_STEP' "
            "           AND e.status = 'ACTIVE' AND e.embedding_model_id = CAST(:m AS uuid) LIMIT 1) AS vec "
            "  FROM pedagogy.solution_step s WHERE s.solution_step_id = :s AND s.publication_status = 'PUBLISHED'"),
            {"s": solution_step_id, "m": vector_search._active_model_id()}).mappings().first()
    if anchor is None:
        raise LookupError(solution_step_id)
    results = search_solution_steps(
        anchor["skill_name"] or anchor["step_type"] or "step",
        skill_node_id=anchor["skill_node_id"] if same_skill and anchor["skill_node_id"] else None,
        exclude_problem_id=anchor["problem_id"],
        semantic=anchor["vec"] is not None, lexical=True, limit=limit, query_vector=anchor["vec"],
    )
    return {"anchor": {k: anchor[k] for k in ("solution_step_id", "skill_node_id", "skill_name", "step_type")},
            "embedding_available": anchor["vec"] is not None, "results": results}
