"""Read-only admin browser over imported textbook packages (Prasolov) — requirements/24.

Everything here is a SELECT: corpus coverage (source CSV rows vs Postgres vs pgvector vs Neo4j),
paginated problem / learning-item / taxonomy lists and a full problem detail including hidden
solution diagrams. Admin-key protected at the router; never exposed to students.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

log = logging.getLogger(__name__)

DEFAULT_BOOK = "PRASOLOV_PGV1"

# Source CSV (package_file.relative_path) -> the entity it feeds, for the coverage matrix.
SOURCE_FILES: dict[str, str] = {
    "csv/problems.csv": "problem",
    "csv/solutions.csv": "solution",
    "csv/chapters_sections.csv": "chapter_section",
    "csv/diagram_manifest.csv": "diagram",
    "pedagogy_v3/csv/taxonomy_nodes.csv": "taxonomy_node",
    "pedagogy_v3/csv/taxonomy_edges.csv": "taxonomy_edge",
    "pedagogy_v3/csv/problem_taxonomy_enriched.csv": "problem_enrichment",
    "pedagogy_v3/csv/solution_parts.csv": "solution_part",
    "pedagogy_v3/csv/solution_steps.csv": "solution_step",
    "pedagogy_v3/csv/solution_step_dependencies.csv": "step_dependency",
    "pedagogy_v3/csv/transformations_v3_no_proof.csv": "learning_item",
    "csv/transformations.csv": "legacy_transformation",
    "csv/problem_concepts.csv": "raw_problem_concept",
    "csv/problem_skills.csv": "raw_problem_skill",
    "csv/problem_techniques.csv": "raw_problem_technique",
}

# Entities that are deliberately kept as RAW provenance only (superseded by pedagogy_v3).
PROVENANCE_ONLY = {
    "legacy_transformation": "superseded by transformations_v3_no_proof.csv (learning items)",
    "raw_problem_concept": "superseded by problem_taxonomy_enriched.csv concept/subconcept columns",
    "raw_problem_skill": "superseded by problem_taxonomy_enriched.csv skill columns",
    "raw_problem_technique": "superseded by problem_taxonomy_enriched.csv technique_ids",
}


def _rows(conn: Connection, sql: str, **params: Any) -> list[dict]:
    return [dict(r) for r in conn.execute(text(sql), params).mappings()]


def _one(conn: Connection, sql: str, **params: Any) -> dict | None:
    row = conn.execute(text(sql), params).mappings().first()
    return dict(row) if row else None


# ------------------------------------------------------------------ coverage

_PG_COUNTS = """
WITH pr AS (SELECT problem_id FROM pedagogy.problem_source_ref WHERE book_code = :book)
SELECT
  (SELECT count(*) FROM pr)                                                         AS problem,
  (SELECT count(*) FROM pedagogy.solution_source_ref WHERE book_code = :book)       AS solution,
  (SELECT count(*) FROM pedagogy.chapter_section WHERE book_code = :book)           AS chapter_section,
  (SELECT count(*) FROM pedagogy.diagram WHERE book_code = :book)                   AS diagram,
  (SELECT count(*) FROM pedagogy.diagram WHERE book_code = :book AND visibility = 'STUDENT_PROBLEM') AS diagram_student,
  (SELECT count(*) FROM pedagogy.taxonomy_node n WHERE n.content_package_id IN
      (SELECT content_package_id FROM ingest.content_package WHERE book_code = :book)) AS taxonomy_node,
  (SELECT count(*) FROM pedagogy.taxonomy_edge e WHERE e.content_package_id IN
      (SELECT content_package_id FROM ingest.content_package WHERE book_code = :book)) AS taxonomy_edge,
  (SELECT count(*) FROM pedagogy.problem_enrichment WHERE problem_id IN (SELECT problem_id FROM pr)) AS problem_enrichment,
  (SELECT count(*) FROM pedagogy.solution_part WHERE book_code = :book)             AS solution_part,
  (SELECT count(*) FROM pedagogy.solution_step WHERE book_code = :book)             AS solution_step,
  (SELECT count(*) FROM pedagogy.solution_step_dependency d
     JOIN pedagogy.solution_step s ON s.solution_step_id = d.to_step_id WHERE s.book_code = :book) AS step_dependency,
  (SELECT count(*) FROM pedagogy.learning_item WHERE book_code = :book)             AS learning_item,
  (SELECT count(*) FROM pedagogy.learning_item WHERE book_code = :book AND review_status = 'APPROVED') AS learning_item_approved,
  (SELECT count(*) FROM pedagogy.learning_item_step_anchor a
     JOIN pedagogy.learning_item li USING (learning_item_id) WHERE li.book_code = :book) AS learning_item_anchor,
  (SELECT count(*) FROM pedagogy.learning_item WHERE book_code = :book AND target_concept_node_id IS NOT NULL
     AND review_status = 'APPROVED' AND student_visible) AS learning_item_concept,
  (SELECT count(*) FROM pedagogy.solution_step_technique t JOIN pedagogy.solution_step s USING (solution_step_id)
    WHERE s.book_code = :book AND t.review_status = 'APPROVED') AS step_technique
"""

_VECTOR_COUNTS = """
WITH pr AS (SELECT problem_id FROM pedagogy.problem_source_ref WHERE book_code = :book),
emb AS (SELECT DISTINCT chunk_id FROM search.embedding)
SELECT
  (SELECT count(DISTINCT c.problem_id) FROM search.chunk c JOIN search.representation r USING (representation_id)
     JOIN emb USING (chunk_id) WHERE r.source_entity_type = 'PROBLEM' AND c.problem_id IN (SELECT problem_id FROM pr)) AS problem,
  (SELECT count(DISTINCT c.solution_id) FROM search.chunk c JOIN search.representation r USING (representation_id)
     JOIN emb USING (chunk_id) JOIN pedagogy.solution_source_ref so ON so.solution_id = c.solution_id
     WHERE r.source_entity_type = 'SOLUTION' AND so.book_code = :book) AS solution,
  (SELECT count(DISTINCT c.solution_step_id) FROM search.chunk c JOIN emb USING (chunk_id)
     JOIN pedagogy.solution_step s ON s.solution_step_id = c.solution_step_id WHERE s.book_code = :book) AS solution_step,
  (SELECT count(DISTINCT c.learning_item_id) FROM search.chunk c JOIN emb USING (chunk_id)
     JOIN pedagogy.learning_item li ON li.learning_item_id = c.learning_item_id WHERE li.book_code = :book) AS learning_item,
  (SELECT count(DISTINCT n.taxonomy_node_id) FROM search.chunk c
     JOIN search.representation r USING (representation_id) JOIN emb USING (chunk_id)
     JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id = c.metadata->>'taxonomy_node_id'
     JOIN ingest.content_package cp ON cp.content_package_id = n.content_package_id
     WHERE r.source_entity_type = 'TAXONOMY_NODE' AND r.status = 'ACTIVE' AND cp.book_code = :book) AS taxonomy_node
"""

_GRAPH_COUNTS: dict[str, str] = {
    "problem": "MATCH (p:Problem) WHERE p.canonical_code STARTS WITH $prefix RETURN count(p) AS n",
    "solution": "MATCH (p:Problem)-[:HAS_SOLUTION]->(s:Solution) WHERE p.canonical_code STARTS WITH $prefix RETURN count(DISTINCT s) AS n",
    "solution_part": "MATCH (n:SolutionPart) RETURN count(n) AS n",
    "solution_step": "MATCH (n:SolutionStep) RETURN count(n) AS n",
    "step_dependency": "MATCH (:SolutionStep)-[r:NEXT|DEPENDS_ON]->(:SolutionStep) RETURN count(r) AS n",
    "learning_item": "MATCH (n:LearningItem) RETURN count(n) AS n",
    "learning_item_anchor": "MATCH (:LearningItem)-[r:ANCHORED_AT]->(:SolutionStep) RETURN count(r) AS n",
    "learning_item_concept": "MATCH (n:LearningItem)-[:TARGETS_CONCEPT]->(:Concept) RETURN count(DISTINCT n) AS n",
    "step_technique": "MATCH (:SolutionStep)-[r:USES_TECHNIQUE]->(:Technique) RETURN count(r) AS n",
    "taxonomy_node": ("MATCH (n) WHERE (n:Concept OR n:Skill OR n:Technique) AND n.canonical_id IN $taxonomy_ids "
                      "RETURN count(DISTINCT n.canonical_id) AS n"),
    "problem_enrichment": "MATCH (p:Problem)-[:TESTS]->(:Concept) WHERE p.canonical_code STARTS WITH $prefix RETURN count(DISTINCT p) AS n",
}


def graph_counts(book: str, driver=None, taxonomy_ids: list[str] | None = None) -> dict[str, Any]:
    """Neo4j node/edge counts for the book. Never raises — returns {ok: False, error} when unavailable."""
    try:
        if driver is None:
            from mathbank_rest.db.graph import driver as default_driver
            driver = default_driver
        out: dict[str, Any] = {"ok": True}
        with driver.session() as session:
            for key, cypher in _GRAPH_COUNTS.items():
                out[key] = session.run(cypher, prefix=f"{book}_", book=book,
                                       taxonomy_ids=taxonomy_ids or []).single()["n"]
        return out
    except Exception as exc:  # noqa: BLE001 - surfaced as a coverage gap, not a 500
        log.warning("textbook graph coverage unavailable: %s", exc)
        return {"ok": False, "error": type(exc).__name__}


def coverage(conn: Connection, book: str = DEFAULT_BOOK, include_graph: bool = True, driver=None) -> dict:
    packages = _rows(conn, """
        SELECT p.content_package_id::text AS content_package_id, p.package_name, p.package_version, p.status,
               p.last_scope, p.imported_at, p.updated_at,
               (SELECT count(*) FROM ingest.import_conflict c WHERE c.content_package_id = p.content_package_id) AS conflicts
        FROM ingest.content_package p WHERE p.book_code = :book ORDER BY p.package_name""", book=book)
    files = _rows(conn, """
        SELECT f.relative_path, f.file_role, sum(f.row_count)::int AS row_count, count(*)::int AS packages
        FROM ingest.package_file f JOIN ingest.content_package p USING (content_package_id)
        WHERE p.book_code = :book GROUP BY 1, 2 ORDER BY 1""", book=book)
    source: dict[str, int] = {}
    for f in files:
        entity = SOURCE_FILES.get(f["relative_path"])
        if entity:
            source[entity] = source.get(entity, 0) + (f["row_count"] or 0)
    pg = _one(conn, _PG_COUNTS, book=book) or {}
    vec = _one(conn, _VECTOR_COUNTS, book=book) or {}
    # Graph taxonomy nodes are keyed by the linked core concept/skill/technique uuid, not the taxonomy id.
    taxonomy_ids = [r["id"] for r in _rows(conn, """
        SELECT DISTINCT coalesce(concept_id, skill_id, technique_id)::text AS id FROM pedagogy.taxonomy_node
        WHERE coalesce(concept_id, skill_id, technique_id) IS NOT NULL AND content_package_id IN
              (SELECT content_package_id FROM ingest.content_package WHERE book_code = :book)""", book=book)]
    pg["taxonomy_node_linked"] = len(taxonomy_ids)
    graph = (graph_counts(book, driver, taxonomy_ids) if include_graph
             else {"ok": False, "error": "skipped"})
    conflicts = _rows(conn, """
        SELECT c.entity_type, c.conflict_type, c.severity, count(*)::int AS count
        FROM ingest.import_conflict c JOIN ingest.content_package p USING (content_package_id)
        WHERE p.book_code = :book GROUP BY 1, 2, 3 ORDER BY 1, 2""", book=book)
    return {
        "book_code": book,
        "packages": packages,
        "files": files,
        "matrix": build_matrix(source, pg, vec, graph),
        "conflicts": conflicts,
        "graph_ok": bool(graph.get("ok")),
        "graph_error": graph.get("error"),
        "chapters": chapter_rows(conn, book),
    }


# Which stores each entity is expected in. None = not applicable by design.
EXPECTED = {
    "problem": ("pg", "vector", "graph"),
    "solution": ("pg", "vector", "graph"),
    "chapter_section": ("pg",),
    "diagram": ("pg",),
    "taxonomy_node": ("pg", "vector", "graph"),
    "taxonomy_edge": ("pg",),
    "problem_enrichment": ("pg", "graph"),
    "solution_part": ("pg", "graph"),
    "solution_step": ("pg", "vector", "graph"),
    "step_dependency": ("pg", "graph"),
    "learning_item": ("pg", "vector", "graph"),
    "learning_item_anchor": ("pg", "graph"),
    "learning_item_concept": ("pg", "graph"),
    "step_technique": ("pg", "graph"),
}


def build_matrix(source: dict, pg: dict, vec: dict, graph: dict) -> list[dict]:
    """One row per entity: source rows vs each store, with a status the UI can colour.

    ``status``: OK (every expected store covers every Postgres row), GAP (an expected store is short),
    PROVENANCE (raw file kept for provenance only), UNKNOWN (graph not observed)."""
    rows: list[dict] = []
    graph_ok = bool(graph.get("ok"))
    for entity, stores in EXPECTED.items():
        pg_n = pg.get(entity)
        row = {"entity": entity, "source_rows": source.get(entity), "postgres": pg_n,
               "vector": vec.get(entity) if "vector" in stores else None,
               "graph": graph.get(entity) if ("graph" in stores and graph_ok) else None,
               "expected": list(stores), "gaps": []}
        if "vector" in stores and (row["vector"] or 0) < (pg_n or 0):
            row["gaps"].append("vector")
        if "graph" in stores:
            if not graph_ok:
                row["gaps"].append("graph-unobserved")
            elif (row["graph"] or 0) < (pg.get(f"{entity}_linked", pg_n) or 0):
                row["gaps"].append("graph")
        if f"{entity}_linked" in pg:
            row["graph_expected"] = pg[f"{entity}_linked"]
            linked = pg[f"{entity}_linked"]
            row["note"] = (f"{linked} of {pg_n} nodes link to a core concept/skill/technique (the graph identity)"
                           + ("; the rest are hierarchy-only nodes" if linked < (pg_n or 0) else ""))
        row["status"] = "OK" if not row["gaps"] else ("UNKNOWN" if row["gaps"] == ["graph-unobserved"] else "GAP")
        rows.append(row)
    for entity, why in PROVENANCE_ONLY.items():
        rows.append({"entity": entity, "source_rows": source.get(entity), "postgres": None, "vector": None,
                     "graph": None, "expected": [], "gaps": [], "status": "PROVENANCE", "note": why})
    return rows


def chapter_rows(conn: Connection, book: str = DEFAULT_BOOK) -> list[dict]:
    return _rows(conn, """
        WITH pr AS (SELECT r.problem_id, r.chapter_number FROM pedagogy.problem_source_ref r WHERE r.book_code = :book),
        emb AS (SELECT DISTINCT c.problem_id FROM search.chunk c JOIN search.representation rp USING (representation_id)
                JOIN search.embedding e USING (chunk_id) WHERE rp.source_entity_type = 'PROBLEM'),
        titles AS (SELECT chapter_number, min(chapter_title) AS chapter_title, count(*) AS sections
                   FROM pedagogy.chapter_section WHERE book_code = :book GROUP BY 1)
        SELECT pr.chapter_number, t.chapter_title, coalesce(t.sections, 0)::int AS sections,
               count(*)::int AS problems,
               count(DISTINCT so.solution_id)::int AS solutions,
               (SELECT count(*) FROM pedagogy.solution_step s WHERE s.book_code = :book
                  AND s.problem_id IN (SELECT problem_id FROM pr p2 WHERE p2.chapter_number = pr.chapter_number))::int AS steps,
               (SELECT count(*) FROM pedagogy.learning_item li WHERE li.book_code = :book
                  AND li.source_problem_id IN (SELECT problem_id FROM pr p2 WHERE p2.chapter_number = pr.chapter_number))::int AS learning_items,
               (SELECT count(*) FROM pedagogy.diagram d WHERE d.book_code = :book
                  AND d.problem_id IN (SELECT problem_id FROM pr p2 WHERE p2.chapter_number = pr.chapter_number))::int AS diagrams,
               count(emb.problem_id)::int AS problems_embedded
        FROM pr
        LEFT JOIN titles t USING (chapter_number)
        LEFT JOIN pedagogy.solution_source_ref so ON so.problem_id = pr.problem_id
        LEFT JOIN emb ON emb.problem_id = pr.problem_id
        GROUP BY pr.chapter_number, t.chapter_title, t.sections
        ORDER BY pr.chapter_number""", book=book)


# ------------------------------------------------------------------ problems

def list_problems(conn: Connection, *, book: str = DEFAULT_BOOK, chapter: int | None = None,
                  q: str | None = None, node: str | None = None, has_diagram: bool | None = None,
                  has_solution: bool | None = None, limit: int = 50, offset: int = 0) -> dict:
    where = ["r.book_code = :book"]
    params: dict[str, Any] = {"book": book, "limit": limit, "offset": offset}
    if chapter is not None:
        where.append("r.chapter_number = :chapter")
        params["chapter"] = chapter
    if q:
        where.append("(p.statement_text ILIKE :q OR p.canonical_code ILIKE :q OR r.source_problem_id ILIKE :q)")
        params["q"] = f"%{q}%"
    if node:
        where.append("""(e.concept_node_id = :node OR e.subconcept_node_id = :node OR e.primary_skill_node_id = :node
                         OR :node = ANY(e.technique_ids) OR :node = ANY(e.solution_step_skill_ids))""")
        params["node"] = node
    if has_diagram is not None:
        where.append(("" if has_diagram else "NOT ") + "EXISTS (SELECT 1 FROM pedagogy.diagram d WHERE d.problem_id = p.problem_id)")
    if has_solution is not None:
        where.append(("" if has_solution else "NOT ") + "EXISTS (SELECT 1 FROM pedagogy.solution_source_ref s WHERE s.problem_id = p.problem_id)")
    clause = " AND ".join(where)
    base = f"""FROM pedagogy.problem_source_ref r JOIN core.problem p USING (problem_id)
               LEFT JOIN pedagogy.problem_enrichment e USING (problem_id)
               LEFT JOIN pedagogy.taxonomy_node cn ON cn.taxonomy_node_id = e.concept_node_id
               LEFT JOIN pedagogy.taxonomy_node sn ON sn.taxonomy_node_id = e.subconcept_node_id
               WHERE {clause}"""
    total = conn.execute(text(f"SELECT count(*) {base}"), params).scalar() or 0
    rows = _rows(conn, f"""
        SELECT p.canonical_code, r.source_problem_id, r.chapter_number, r.section_number, r.section_title,
               left(p.statement_text, 240) AS statement_preview,
               e.concept_node_id, cn.name AS concept_name, e.subconcept_node_id, sn.name AS subconcept_name,
               e.problem_form, e.solution_step_count,
               (SELECT count(*) FROM pedagogy.solution_source_ref s WHERE s.problem_id = p.problem_id)::int AS solutions,
               (SELECT count(*) FROM pedagogy.solution_step st WHERE st.problem_id = p.problem_id)::int AS steps,
               (SELECT count(*) FROM pedagogy.learning_item li WHERE li.source_problem_id = p.problem_id)::int AS learning_items,
               (SELECT count(*) FROM pedagogy.diagram d WHERE d.problem_id = p.problem_id)::int AS diagrams,
               EXISTS (SELECT 1 FROM search.chunk c JOIN search.representation rp USING (representation_id)
                       JOIN search.embedding em USING (chunk_id)
                       WHERE c.problem_id = p.problem_id AND rp.source_entity_type = 'PROBLEM') AS embedded
        {base}
        ORDER BY r.chapter_number, r.section_number, p.problem_number NULLS LAST, p.canonical_code
        LIMIT :limit OFFSET :offset""", **params)
    return {"total": int(total), "limit": limit, "offset": offset, "items": rows}


def _graph_problem_status(code: str, driver=None) -> dict:
    try:
        if driver is None:
            from mathbank_rest.db.graph import driver as default_driver
            driver = default_driver
        with driver.session() as session:
            found = session.run("MATCH (p:Problem {canonical_code: $code}) RETURN count(p) AS n", code=code).single()["n"]
            edges = [dict(r) for r in session.run(
                """MATCH (p:Problem {canonical_code: $code})-[r]-(t)
                   RETURN type(r) AS type, head(labels(t)) AS label,
                          CASE WHEN startNode(r) = p THEN 'out' ELSE 'in' END AS direction, count(r) AS count
                   ORDER BY type, label""", code=code)]
            steps = session.run(
                """MATCH (p:Problem {canonical_code: $code})-[:HAS_SOLUTION]->(:Solution)-[:HAS_PART]->(:SolutionPart)
                         -[:HAS_STEP]->(s:SolutionStep) RETURN count(DISTINCT s) AS n""", code=code).single()["n"]
        return {"ok": True, "present": bool(found), "edges": edges, "steps": steps}
    except Exception as exc:  # noqa: BLE001
        log.warning("graph status for %s unavailable: %s", code, exc)
        return {"ok": False, "error": type(exc).__name__}


def problem_detail(conn: Connection, code: str, include_graph: bool = True, driver=None) -> dict | None:
    head = _one(conn, """
        SELECT p.problem_id::text AS problem_id, p.canonical_code, p.problem_number, p.statement_text, p.statement_latex,
               p.official_answer, p.difficulty_band, p.status,
               r.book_code, r.source_problem_id, r.chapter_number, r.section_number, r.section_title,
               r.source_printed_problem_id, r.source_editorial_marker, r.source_numbering_note, r.source_pdf,
               r.source_page_start, r.source_page_end, r.problem_requires_diagram, r.solution_requires_diagram,
               r.difficulty_rank_in_section, r.section_problem_count, cs.chapter_title,
               pk.package_name
        FROM core.problem p JOIN pedagogy.problem_source_ref r USING (problem_id)
        LEFT JOIN pedagogy.chapter_section cs ON cs.book_code = r.book_code AND cs.chapter_number = r.chapter_number
             AND cs.section_number = r.section_number
        LEFT JOIN ingest.content_package pk ON pk.content_package_id = r.content_package_id
        WHERE p.canonical_code = :code""", code=code)
    if not head:
        return None
    pid = head["problem_id"]
    enrichment = _one(conn, """
        SELECT e.concept_node_id, cn.name AS concept_name, e.subconcept_node_id, sn.name AS subconcept_name,
               e.primary_skill_node_id, kn.name AS primary_skill_name, e.solution_step_skill_ids, e.technique_ids,
               e.problem_form, e.difficulty_band_source_order, e.solution_step_count, e.taxonomy_mapping_basis,
               e.taxonomy_confidence
        FROM pedagogy.problem_enrichment e
        LEFT JOIN pedagogy.taxonomy_node cn ON cn.taxonomy_node_id = e.concept_node_id
        LEFT JOIN pedagogy.taxonomy_node sn ON sn.taxonomy_node_id = e.subconcept_node_id
        LEFT JOIN pedagogy.taxonomy_node kn ON kn.taxonomy_node_id = e.primary_skill_node_id
        WHERE e.problem_id = CAST(:pid AS uuid)""", pid=pid)
    taxonomy_ids = []
    if enrichment:
        taxonomy_ids = list(dict.fromkeys([*(enrichment.get("solution_step_skill_ids") or []),
                                           *(enrichment.get("technique_ids") or [])]))
    taxonomy_names = {r["taxonomy_node_id"]: r for r in _rows(conn, """
        SELECT taxonomy_node_id, node_type, name FROM pedagogy.taxonomy_node WHERE taxonomy_node_id = ANY(:ids)""",
        ids=taxonomy_ids)} if taxonomy_ids else {}
    solutions = _rows(conn, """
        SELECT s.solution_id::text AS solution_id, s.solution_kind, s.revision, s.body_markdown, s.verification_status,
               sr.source_solution_id, sr.source_page,
               EXISTS (SELECT 1 FROM search.chunk c JOIN search.representation rp USING (representation_id)
                       JOIN search.embedding em USING (chunk_id)
                       WHERE c.solution_id = s.solution_id AND rp.source_entity_type = 'SOLUTION') AS embedded
        FROM core.solution s LEFT JOIN pedagogy.solution_source_ref sr USING (solution_id)
        WHERE s.problem_id = CAST(:pid AS uuid) ORDER BY s.revision""", pid=pid)
    parts = _rows(conn, """
        SELECT solution_part_id, solution_id::text AS solution_id, part_label, part_ordinal, step_count,
               source_step_count, source_page
        FROM pedagogy.solution_part WHERE problem_id = CAST(:pid AS uuid) ORDER BY part_ordinal""", pid=pid)
    steps = _rows(conn, """
        SELECT st.solution_step_id, st.solution_part_id, st.global_step_index, st.step_index_in_part, st.step_text,
               st.step_type, st.tutor_role, st.concept_node_id, st.subconcept_node_id, st.skill_node_id, st.skill_name,
               st.hint_level, st.is_checkpoint, st.source_page, st.publication_status,
               EXISTS (SELECT 1 FROM search.chunk c JOIN search.embedding em USING (chunk_id)
                       WHERE c.solution_step_id = st.solution_step_id) AS embedded
        FROM pedagogy.solution_step st WHERE st.problem_id = CAST(:pid AS uuid)
        ORDER BY st.global_step_index, st.solution_step_id""", pid=pid)
    deps = _rows(conn, """
        SELECT d.from_step_id, d.to_step_id, d.relationship_type, d.logical_dependency, d.confidence,
               d.source_type, d.review_status
        FROM pedagogy.solution_step_dependency d JOIN pedagogy.solution_step s ON s.solution_step_id = d.to_step_id
        WHERE s.problem_id = CAST(:pid AS uuid) ORDER BY d.relationship_type, d.from_step_id""", pid=pid)
    by_part: dict[str, list[dict]] = {}
    for st in steps:
        by_part.setdefault(st["solution_part_id"], []).append(st)
    for part in parts:
        part["steps"] = by_part.pop(part["solution_part_id"], [])
    items = _rows(conn, """
        SELECT li.learning_item_id, li.source_transformation_id, li.transformation_type, li.transformed_form,
               li.difficulty_direction, li.question_text, li.choices, li.correct_answer, li.answer_or_solution_seed,
               li.generation_mode, li.solution_part_label, li.requires_source_problem, li.diagram_strategy,
               li.review_status, li.student_visible, li.approval_method,
               li.target_skill_node_id, tn.name AS target_skill_name,
               coalesce((SELECT array_agg(a.solution_step_id ORDER BY a.anchor_ordinal)
                         FROM pedagogy.learning_item_step_anchor a WHERE a.learning_item_id = li.learning_item_id), '{}') AS anchor_step_ids,
               EXISTS (SELECT 1 FROM search.chunk c JOIN search.embedding em USING (chunk_id)
                       WHERE c.learning_item_id = li.learning_item_id) AS embedded
        FROM pedagogy.learning_item li LEFT JOIN pedagogy.taxonomy_node tn ON tn.taxonomy_node_id = li.target_skill_node_id
        WHERE li.source_problem_id = CAST(:pid AS uuid) ORDER BY li.transformation_type, li.learning_item_id""", pid=pid)
    diagrams = _rows(conn, """
        SELECT diagram_id::text AS diagram_id, source_diagram_id, usage, visibility, source_pdf_page,
               source_figure_number, source_caption, asset_path, validation_status,
               problem_image_id::text AS problem_image_id
        FROM pedagogy.diagram WHERE problem_id = CAST(:pid AS uuid) ORDER BY usage DESC, source_diagram_id""", pid=pid)
    return {
        **head,
        "enrichment": enrichment,
        "taxonomy_names": taxonomy_names,
        "solutions": solutions,
        "parts": parts,
        "unassigned_steps": [s for rest in by_part.values() for s in rest],
        "dependencies": deps,
        "learning_items": items,
        "diagrams": diagrams,
        "vector": {"problem": _problem_embedded(conn, pid),
                   "solutions_embedded": sum(1 for s in solutions if s["embedded"]),
                   "steps_embedded": sum(1 for s in steps if s["embedded"]), "steps": len(steps),
                   "items_embedded": sum(1 for i in items if i["embedded"]), "items": len(items)},
        "graph": _graph_problem_status(code, driver) if include_graph else {"ok": False, "error": "skipped"},
    }


def _problem_embedded(conn: Connection, pid: str) -> bool:
    return bool(conn.execute(text("""
        SELECT EXISTS (SELECT 1 FROM search.chunk c JOIN search.representation rp USING (representation_id)
                       JOIN search.embedding em USING (chunk_id)
                       WHERE c.problem_id = CAST(:pid AS uuid) AND rp.source_entity_type = 'PROBLEM')"""),
        {"pid": pid}).scalar())


# ------------------------------------------------------------------ learning items

def list_learning_items(conn: Connection, *, book: str = DEFAULT_BOOK, transformation_type: str | None = None,
                        chapter: int | None = None, q: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    where = ["li.book_code = :book"]
    params: dict[str, Any] = {"book": book, "limit": limit, "offset": offset}
    if transformation_type:
        where.append("li.transformation_type = :tt")
        params["tt"] = transformation_type
    if chapter is not None:
        where.append("r.chapter_number = :chapter")
        params["chapter"] = chapter
    if q:
        where.append("(li.question_text ILIKE :q OR p.canonical_code ILIKE :q OR li.learning_item_id ILIKE :q)")
        params["q"] = f"%{q}%"
    base = f"""FROM pedagogy.learning_item li JOIN core.problem p ON p.problem_id = li.source_problem_id
               JOIN pedagogy.problem_source_ref r ON r.problem_id = li.source_problem_id
               WHERE {' AND '.join(where)}"""
    total = conn.execute(text(f"SELECT count(*) {base}"), params).scalar() or 0
    types = _rows(conn, """SELECT transformation_type, count(*)::int AS count FROM pedagogy.learning_item
                           WHERE book_code = :book GROUP BY 1 ORDER BY 2 DESC""", book=book)
    rows = _rows(conn, f"""
        SELECT li.learning_item_id, li.transformation_type, li.transformed_form, li.difficulty_direction,
               left(li.question_text, 240) AS question_preview, li.review_status, li.student_visible,
               p.canonical_code, r.chapter_number, r.source_problem_id
        {base} ORDER BY r.chapter_number, p.canonical_code, li.transformation_type, li.learning_item_id
        LIMIT :limit OFFSET :offset""", **params)
    return {"total": int(total), "limit": limit, "offset": offset, "types": types, "items": rows}


# ------------------------------------------------------------------ taxonomy

def list_taxonomy(conn: Connection, *, book: str = DEFAULT_BOOK, node_type: str | None = None,
                  q: str | None = None, limit: int = 100, offset: int = 0) -> dict:
    where = ["n.content_package_id IN (SELECT content_package_id FROM ingest.content_package WHERE book_code = :book)"]
    params: dict[str, Any] = {"book": book, "limit": limit, "offset": offset}
    if node_type:
        where.append("n.node_type = :nt")
        params["nt"] = node_type
    if q:
        where.append("(n.name ILIKE :q OR n.taxonomy_node_id ILIKE :q)")
        params["q"] = f"%{q}%"
    clause = " AND ".join(where)
    total = conn.execute(text(f"SELECT count(*) FROM pedagogy.taxonomy_node n WHERE {clause}"), params).scalar() or 0
    types = _rows(conn, """SELECT node_type, count(*)::int AS count FROM pedagogy.taxonomy_node
                           WHERE content_package_id IN (SELECT content_package_id FROM ingest.content_package WHERE book_code = :book)
                           GROUP BY 1 ORDER BY 1""", book=book)
    rows = _rows(conn, f"""
        SELECT n.taxonomy_node_id, n.node_type, n.name, n.parent_node_id, n.chapter_number, n.section_number,
               (SELECT count(*) FROM pedagogy.problem_enrichment e
                 WHERE n.taxonomy_node_id IN (e.concept_node_id, e.subconcept_node_id, e.primary_skill_node_id)
                    OR n.taxonomy_node_id = ANY(e.technique_ids))::int AS problems,
               (SELECT count(*) FROM pedagogy.solution_step s
                 WHERE n.taxonomy_node_id IN (s.skill_node_id, s.subconcept_node_id, s.concept_node_id))::int AS steps,
               (SELECT count(*) FROM pedagogy.taxonomy_edge t
                 WHERE n.taxonomy_node_id IN (t.from_node_id, t.to_node_id))::int AS edges
        FROM pedagogy.taxonomy_node n WHERE {clause}
        ORDER BY n.node_type, n.taxonomy_node_id LIMIT :limit OFFSET :offset""", **params)
    return {"total": int(total), "limit": limit, "offset": offset, "types": types, "items": rows}


def taxonomy_detail(conn: Connection, node_id: str) -> dict | None:
    node = _one(conn, """
        SELECT n.taxonomy_node_id, n.node_type, n.name, n.parent_node_id, pn.name AS parent_name, n.chapter_number,
               n.section_number, n.source_basis, n.description
        FROM pedagogy.taxonomy_node n LEFT JOIN pedagogy.taxonomy_node pn ON pn.taxonomy_node_id = n.parent_node_id
        WHERE n.taxonomy_node_id = :id""", id=node_id)
    if not node:
        return None
    node["children"] = _rows(conn, """SELECT taxonomy_node_id, node_type, name FROM pedagogy.taxonomy_node
                                      WHERE parent_node_id = :id ORDER BY taxonomy_node_id""", id=node_id)
    node["edges"] = _rows(conn, """
        SELECT e.from_node_id, f.name AS from_name, e.relationship_type, e.to_node_id, t.name AS to_name,
               e.source_basis, e.confidence,
               CASE WHEN e.from_node_id = :id THEN 'out' ELSE 'in' END AS direction
        FROM pedagogy.taxonomy_edge e
        LEFT JOIN pedagogy.taxonomy_node f ON f.taxonomy_node_id = e.from_node_id
        LEFT JOIN pedagogy.taxonomy_node t ON t.taxonomy_node_id = e.to_node_id
        WHERE :id IN (e.from_node_id, e.to_node_id)
        ORDER BY direction, e.relationship_type, e.to_node_id LIMIT 500""", id=node_id)
    node["problems"] = _rows(conn, """
        SELECT p.canonical_code, r.source_problem_id, left(p.statement_text, 160) AS statement_preview
        FROM pedagogy.problem_enrichment e JOIN core.problem p USING (problem_id)
        JOIN pedagogy.problem_source_ref r USING (problem_id)
        WHERE :id IN (e.concept_node_id, e.subconcept_node_id, e.primary_skill_node_id) OR :id = ANY(e.technique_ids)
        ORDER BY r.chapter_number, p.canonical_code LIMIT 50""", id=node_id)
    return node


# ------------------------------------------------------------------ diagrams

def diagram_path(conn: Connection, book: str, source_diagram_id: str, root: Path) -> Path | None:
    """Resolve a diagram's file, refusing anything outside the repository root."""
    path = conn.execute(text("""SELECT local_path FROM pedagogy.diagram
                                WHERE book_code = :b AND source_diagram_id = :s"""),
                        {"b": book, "s": source_diagram_id}).scalar()
    if not path:
        return None
    resolved = Path(path).resolve()
    if not resolved.is_file() or root not in resolved.parents:
        return None
    return resolved
