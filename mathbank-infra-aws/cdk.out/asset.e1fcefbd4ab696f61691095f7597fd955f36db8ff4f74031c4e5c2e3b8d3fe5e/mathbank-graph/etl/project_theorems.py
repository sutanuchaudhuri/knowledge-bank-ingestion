"""Project the Theorem/Axiom/Lemma/Proposition/Corollary/Identity/Definition catalog
(requirements/61) into the Neo4j corpus graph — a focused, additive script, not a change
to the large `project_from_postgres.py`, mirroring `project_misconception_relations.py`'s
shape (doc 61 §6.4).

Only `review_status='APPROVED'` theorems and `review_status='REVIEWED'` relations/links
are ever projected — a PENDING_REVIEW row in Postgres never reaches the graph, the same
discipline every other reviewed-assertion projector in this codebase already follows.

Idempotent (MERGE on canonical_id = the Postgres UUID), additive only (never deletes a
pre-existing relationship), batched via UNWIND. Run via:
    GRAPH_ENV_FILE=remote.env .venv/bin/python etl/project_theorems.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_from_postgres import BATCH_SIZE, _load_env, chunks, graph_target, pg_conninfo  # noqa: E402

CONSTRAINT = "CREATE CONSTRAINT theorem_id IF NOT EXISTS FOR (n:Theorem) REQUIRE n.canonical_id IS UNIQUE"

# knowledge.theorem_relation.relation_type values map 1:1 onto Neo4j relationship types,
# except DEPENDS_ON gets a Theorem-specific name (THEOREM_DEPENDS_ON) because the plain
# DEPENDS_ON type already means something different for RouteStep/SolutionStep lineage
# (doc 61 §6.2) — reusing it here would make "trace dependencies" Cypher ambiguous.
_RELATION_TYPE_MAP = {
    "DEPENDS_ON": "THEOREM_DEPENDS_ON",
    "GENERALIZES": "GENERALIZES",
    "SPECIAL_CASE_OF": "SPECIAL_CASE_OF",
    "EQUIVALENT_TO": "EQUIVALENT_TO",
    "COROLLARY_OF": "COROLLARY_OF",
}


def ensure_theorem_constraints(driver) -> None:
    with driver.session() as session:
        session.run(CONSTRAINT)


def project_theorems(driver, pg_cur) -> int:
    pg_cur.execute(
        "SELECT theorem_id, slug, name, kind, field, statement_text, statement_latex "
        "FROM knowledge.theorem WHERE review_status = 'APPROVED'"
    )
    rows = [
        {
            "id": str(r[0]), "slug": r[1], "name": r[2], "kind": r[3], "field": r[4],
            "statement_text": r[5], "statement_latex": r[6],
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (t:Theorem {canonical_id: row.id})
                SET t.slug = row.slug, t.name = row.name, t.kind = row.kind, t.field = row.field,
                    t.statement_text = row.statement_text, t.statement_latex = row.statement_latex
                """,
                rows=batch,
            )
    return len(rows)


def project_theorem_relations(driver, pg_cur) -> int:
    pg_cur.execute(
        "SELECT from_theorem_id, to_theorem_id, relation_type, confidence, assertion_source, review_status "
        "FROM knowledge.theorem_relation WHERE review_status = 'REVIEWED'"
    )
    total = 0
    rows_by_type: dict[str, list[dict]] = {}
    for from_id, to_id, relation_type, confidence, source, review_status in pg_cur.fetchall():
        neo_type = _RELATION_TYPE_MAP[relation_type]
        rows_by_type.setdefault(neo_type, []).append({
            "from_id": str(from_id), "to_id": str(to_id),
            "confidence": float(confidence) if confidence is not None else None,
            "source": source, "review_status": review_status,
        })
    with driver.session() as session:
        for neo_type, rows in rows_by_type.items():
            for batch in chunks(rows, BATCH_SIZE):
                session.run(
                    f"""
                    UNWIND $rows AS row
                    MATCH (a:Theorem {{canonical_id: row.from_id}})
                    MATCH (b:Theorem {{canonical_id: row.to_id}})
                    MERGE (a)-[r:{neo_type}]->(b)
                    SET r.confidence = row.confidence, r.source = row.source,
                        r.review_status = row.review_status
                    """,
                    rows=batch,
                )
            total += len(rows)
    return total


def project_technique_theorem(driver, pg_cur) -> int:
    pg_cur.execute(
        "SELECT technique_id, theorem_id, role, confidence, assertion_source, review_status "
        "FROM knowledge.technique_theorem WHERE review_status = 'REVIEWED'"
    )
    rows = [
        {
            "technique_id": str(r[0]), "theorem_id": str(r[1]), "role": r[2],
            "confidence": float(r[3]) if r[3] is not None else None,
            "source": r[4], "review_status": r[5],
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (tc:Technique {canonical_id: row.technique_id})
                MATCH (th:Theorem {canonical_id: row.theorem_id})
                MERGE (tc)-[r:USES_THEOREM {role: row.role}]->(th)
                SET r.confidence = row.confidence, r.source = row.source,
                    r.review_status = row.review_status
                """,
                rows=batch,
            )
    return len(rows)


def project_theorem_taxonomy_link(driver, pg_cur) -> int:
    """Projects Theorem-[:FORMALIZES]->Concept|Skill|Technique, resolved through
    pedagogy.taxonomy_node's wrapper (doc 61 §3.1/§4.4). DOMAIN/SUBCONCEPT-only taxonomy
    nodes with no backing knowledge.* row are skipped — there is no corresponding Neo4j
    node to link to yet (an honest scope limit, not a silent gap: see doc 61 §12's note
    on the ITL catalog's own similar graph-projection gap)."""
    pg_cur.execute("""
        SELECT tl.theorem_id, tl.role, tn.concept_id, tn.skill_id, tn.technique_id
        FROM knowledge.theorem_taxonomy_link tl
        JOIN pedagogy.taxonomy_node tn ON tn.taxonomy_node_id = tl.taxonomy_node_id
        WHERE tn.concept_id IS NOT NULL OR tn.skill_id IS NOT NULL OR tn.technique_id IS NOT NULL
    """)
    by_label: dict[str, list[dict]] = {"Concept": [], "Skill": [], "Technique": []}
    for theorem_id, role, concept_id, skill_id, technique_id in pg_cur.fetchall():
        if concept_id is not None:
            by_label["Concept"].append({"theorem_id": str(theorem_id), "target_id": str(concept_id), "role": role})
        elif skill_id is not None:
            by_label["Skill"].append({"theorem_id": str(theorem_id), "target_id": str(skill_id), "role": role})
        elif technique_id is not None:
            by_label["Technique"].append({"theorem_id": str(theorem_id), "target_id": str(technique_id), "role": role})
    total = 0
    with driver.session() as session:
        for label, rows in by_label.items():
            for batch in chunks(rows, BATCH_SIZE):
                session.run(
                    f"""
                    UNWIND $rows AS row
                    MATCH (th:Theorem {{canonical_id: row.theorem_id}})
                    MATCH (target:{label} {{canonical_id: row.target_id}})
                    MERGE (th)-[r:FORMALIZES {{role: row.role}}]->(target)
                    """,
                    rows=batch,
                )
            total += len(rows)
    return total


def main() -> None:
    env = _load_env()
    driver = graph_target(env)
    with psycopg.connect(pg_conninfo(env)) as pg_conn:
        with pg_conn.cursor() as pg_cur:
            ensure_theorem_constraints(driver)
            theorem_count = project_theorems(driver, pg_cur)
            print(f"Theorem: {theorem_count} nodes upserted")
            relation_count = project_theorem_relations(driver, pg_cur)
            print(f"THEOREM_DEPENDS_ON/GENERALIZES/SPECIAL_CASE_OF/EQUIVALENT_TO/COROLLARY_OF: {relation_count} edges upserted")
            uses_count = project_technique_theorem(driver, pg_cur)
            print(f"USES_THEOREM: {uses_count} edges upserted")
            formalizes_count = project_theorem_taxonomy_link(driver, pg_cur)
            print(f"FORMALIZES: {formalizes_count} edges upserted")
    driver.close()


if __name__ == "__main__":
    main()
