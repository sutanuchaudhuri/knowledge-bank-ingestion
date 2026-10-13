"""Project imported textbook solution steps (migration 010) into the Neo4j graph.

Graph Projection v2 (requirements pack runtime_extension/06_GRAPH_PROJECTION_V2.md):

    (Solution)-[:HAS_PART]->(SolutionPart)-[:HAS_STEP]->(SolutionStep)
    (SolutionStep)-[:USES_SKILL|USES_CONCEPT|USES_SUBCONCEPT]->(Skill|Concept)
    (SolutionStep)-[:USES_TECHNIQUE {confidence, source_type}]->(Technique)   (NYI-3, migration 017)
    (SolutionStep)-[:NEXT|DEPENDS_ON]->(SolutionStep)
    (LearningItem)-[:DERIVED_FROM]->(Problem), -[:ANCHORED_AT]->(SolutionStep), -[:ASSESSES]->(Skill)
    (LearningItem)-[:TARGETS_CONCEPT]->(Concept), -[:TARGETS_SUBCONCEPT]->(Subconcept)   (NYI-ATB-7)

PostgreSQL stays canonical:
- Step text is not projected; the graph only holds metadata.
- Learning items are projected only when APPROVED and student_visible.

Everything written here has projection_kind='solution_steps'. The atomic pedagogy replacement in
project_from_postgres.py only deletes 'pedagogy' relationships, so this layer survives every paper batch.

Problem/Solution/Skill/Concept nodes must already exist. Run
`project_from_postgres.py --pedagogy` first, or use `make -C mathbank-db textbook-graph-remote`,
which runs both.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import psycopg
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_from_postgres import BATCH_SIZE, _load_env, chunks, graph_target, pg_conninfo  # noqa: E402

KIND = "solution_steps"
PROJECTION_VERSION = "v2"
READY_STATUSES = ("POSTGRES_COMPLETE", "EMBEDDING", "GRAPH_PROJECTING", "COMPLETED")
STEP_EDGE_TYPES = ("NEXT", "DEPENDS_ON", "DERIVES_FROM", "USES_RESULT_FROM", "ALTERNATIVE_TO", "JOINS_AT")
SOURCE_EDGE_ALIASES = {"USES_RESULT": "USES_RESULT_FROM"}

CONSTRAINTS = [
    "CREATE CONSTRAINT solution_part_id IF NOT EXISTS FOR (n:SolutionPart) REQUIRE n.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT solution_step_id IF NOT EXISTS FOR (n:SolutionStep) REQUIRE n.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT learning_item_id IF NOT EXISTS FOR (n:LearningItem) REQUIRE n.canonical_id IS UNIQUE",
]


def rows(cur, query: str, params=None) -> list[dict]:
    cur.execute(query, params)
    names = [d.name for d in cur.description]
    out = []
    for values in cur.fetchall():
        row = {}
        for name, value in zip(names, values):
            if value is not None and not isinstance(value, (str, int, float, bool, list)):
                value = float(value) if name in {"confidence"} else str(value)
            row[name] = value
        out.append(row)
    return out


def load(cur) -> dict[str, list[dict]]:
    packages = rows(cur, """
        SELECT content_package_id, package_name, package_version, book_code
          FROM ingest.content_package WHERE status = ANY(%s)""", (list(READY_STATUSES),))
    ids = [p["content_package_id"] for p in packages]
    data: dict[str, list[dict]] = {"packages": packages}
    data["parts"] = rows(cur, """
        SELECT sp.solution_part_id AS id, sp.source_part_id AS external_id, sp.occurrence, sp.book_code,
               sp.solution_id::text AS solution_id, sp.part_label, sp.part_ordinal, sp.step_count,
               sp.source_page, p.canonical_code AS problem_canonical_code,
               sp.content_package_id::text AS source_package_id, cp.package_version AS content_version
          FROM pedagogy.solution_part sp
          JOIN core.problem p ON p.problem_id = sp.problem_id
          JOIN ingest.content_package cp ON cp.content_package_id = sp.content_package_id
         WHERE sp.content_package_id = ANY(%s::uuid[])""", (ids,))
    data["steps"] = rows(cur, """
        SELECT st.solution_step_id AS id, st.source_step_id AS external_id, st.occurrence, st.book_code,
               st.solution_part_id AS part_id, st.global_step_index, st.step_index_in_part, st.step_type,
               st.tutor_role, st.hint_level, st.is_checkpoint, st.skill_name, st.source_page,
               st.publication_status, p.canonical_code AS problem_canonical_code,
               st.content_package_id::text AS source_package_id, cp.package_version AS content_version,
               sk.skill_id::text AS skill_id, co.concept_id::text AS concept_id,
               sc.concept_id::text AS subconcept_id
          FROM pedagogy.solution_step st
          JOIN core.problem p ON p.problem_id = st.problem_id
          JOIN ingest.content_package cp ON cp.content_package_id = st.content_package_id
          LEFT JOIN pedagogy.taxonomy_node sk ON sk.taxonomy_node_id = st.skill_node_id
          LEFT JOIN pedagogy.taxonomy_node co ON co.taxonomy_node_id = st.concept_node_id
          LEFT JOIN pedagogy.taxonomy_node sc ON sc.taxonomy_node_id = st.subconcept_node_id
         WHERE st.content_package_id = ANY(%s::uuid[])""", (ids,))
    data["dependencies"] = rows(cur, """
        SELECT from_step_id, to_step_id, relationship_type, logical_dependency, confidence, source_type,
               review_status, approval_method
          FROM pedagogy.solution_step_dependency WHERE content_package_id = ANY(%s::uuid[])
           AND review_status <> 'REJECTED'""", (ids,))  # 019: admin-rejected edges are pruned
    data["subconcepts"] = rows(cur, """
        SELECT DISTINCT concept_id::text AS id FROM pedagogy.taxonomy_node
         WHERE node_type = 'SUBCONCEPT' AND concept_id IS NOT NULL""")
    data["learning_items"] = rows(cur, """
        SELECT li.learning_item_id AS id, li.source_transformation_id AS external_id, li.book_code,
               li.transformation_type, li.transformed_form, li.difficulty_direction, li.review_status,
               li.source_problem_id::text AS problem_id, sk.skill_id::text AS skill_id,
               co.concept_id::text AS concept_id, sc.concept_id::text AS subconcept_id,
               li.content_package_id::text AS source_package_id, cp.package_version AS content_version
          FROM pedagogy.learning_item li
          JOIN ingest.content_package cp ON cp.content_package_id = li.content_package_id
          LEFT JOIN pedagogy.taxonomy_node sk ON sk.taxonomy_node_id = li.target_skill_node_id
          LEFT JOIN pedagogy.taxonomy_node co ON co.taxonomy_node_id = li.target_concept_node_id
                                             AND co.node_type = 'CONCEPT'
          LEFT JOIN pedagogy.taxonomy_node sc ON sc.taxonomy_node_id = li.target_subconcept_node_id
                                             AND sc.node_type = 'SUBCONCEPT'
         WHERE li.review_status = 'APPROVED' AND li.student_visible
           AND li.content_package_id = ANY(%s::uuid[])""", (ids,))
    item_ids = [i["id"] for i in data["learning_items"]]
    data["anchors"] = rows(cur, """
        SELECT learning_item_id, solution_step_id, anchor_ordinal AS ordinal FROM pedagogy.learning_item_step_anchor
         WHERE learning_item_id = ANY(%s)""", (item_ids,))
    # Derived step techniques (migration 017, NYI-3). Bridged via taxonomy_node.technique_id, the
    # core.technique uuid that is the graph Technique canonical_id. Approved rows only.
    data["step_techniques"] = rows(cur, """
        SELECT t.solution_step_id, tn.technique_id::text AS technique_id, t.confidence, t.source_type,
               t.review_status, t.approval_method, t.derivation_version
          FROM pedagogy.solution_step_technique t
          JOIN pedagogy.solution_step st ON st.solution_step_id = t.solution_step_id
          JOIN pedagogy.taxonomy_node tn ON tn.taxonomy_node_id = t.technique_node_id
                                        AND tn.node_type = 'TECHNIQUE' AND tn.technique_id IS NOT NULL
         WHERE t.review_status = 'APPROVED' AND st.content_package_id = ANY(%s::uuid[])""", (ids,))
    return data


def edge_key(kind: str, start: str, end: str) -> str:
    return f"{kind}|{start}|{end}"


def build_jobs(data: dict[str, list[dict]]) -> tuple[list[tuple[str, str, list[dict]]], Counter, list[str]]:
    """Return (label, cypher, rows) jobs, the expected count per node/edge type and all edge keys."""
    jobs: list[tuple[str, str, list[dict]]] = []
    expected: Counter = Counter()
    keys: list[str] = []
    common = (f"n.projection_kind = '{KIND}', n.projection_version = '{PROJECTION_VERSION}', "
              "n.postgres_id = row.id, n.external_id = row.external_id, n.book_code = row.book_code, "
              "n.source_package_id = row.source_package_id, n.content_version = row.content_version")

    def edge_job(kind: str, start_label: str, end_label: str, start: str, end: str,
                 selected: list[dict], props: list[str] = ()) -> None:
        for row in selected:
            row["projection_key"] = edge_key(kind, row[start], row[end])
            keys.append(row["projection_key"])
        assignments = "".join(f", r.{p} = row.{p}" for p in props)
        jobs.append((kind, f"""
            UNWIND $rows AS row
            MATCH (a:{start_label} {{canonical_id: row.{start}}})
            MATCH (b:{end_label} {{canonical_id: row.{end}}})
            MERGE (a)-[r:{kind}]->(b)
            SET r.projection_kind = '{KIND}', r.projection_key = row.projection_key{assignments}
            RETURN count(r) AS written""", selected))
        expected[kind] += len(selected)

    jobs.append(("Subconcept", """
        UNWIND $rows AS row MATCH (n:Concept {canonical_id: row.id}) SET n:Subconcept
        RETURN count(n) AS written""", data["subconcepts"]))
    jobs.append(("SolutionPart", f"""
        UNWIND $rows AS row
        MERGE (n:SolutionPart {{canonical_id: row.id}})
        SET {common}, n.occurrence = row.occurrence, n.part_label = row.part_label,
            n.part_ordinal = row.part_ordinal, n.step_count = row.step_count, n.source_page = row.source_page,
            n.problem_canonical_code = row.problem_canonical_code, n.publication_status = 'IMPORTED'
        RETURN count(n) AS written""", data["parts"]))
    expected["SolutionPart"] = len(data["parts"])
    jobs.append(("SolutionStep", f"""
        UNWIND $rows AS row
        MERGE (n:SolutionStep {{canonical_id: row.id}})
        SET {common}, n.occurrence = row.occurrence, n.global_step_index = row.global_step_index,
            n.step_index_in_part = row.step_index_in_part, n.step_type = row.step_type,
            n.tutor_role = row.tutor_role, n.hint_level = row.hint_level, n.is_checkpoint = row.is_checkpoint,
            n.skill_name = row.skill_name, n.source_page = row.source_page,
            n.problem_canonical_code = row.problem_canonical_code,
            n.publication_status = row.publication_status
        RETURN count(n) AS written""", data["steps"]))
    expected["SolutionStep"] = len(data["steps"])
    edge_job("HAS_PART", "Solution", "SolutionPart", "solution_id", "id",
             [dict(r) for r in data["parts"]], ["part_ordinal"])
    edge_job("HAS_STEP", "SolutionPart", "SolutionStep", "part_id", "id",
             [dict(r) for r in data["steps"]], ["step_index_in_part"])
    for kind, column, label in (("USES_SKILL", "skill_id", "Skill"), ("USES_CONCEPT", "concept_id", "Concept"),
                                ("USES_SUBCONCEPT", "subconcept_id", "Subconcept")):
        edge_job(kind, "SolutionStep", label, "id", column, [dict(r) for r in data["steps"] if r[column]])
    edge_job("USES_TECHNIQUE", "SolutionStep", "Technique", "solution_step_id", "technique_id",
             [dict(r) for r in data.get("step_techniques", [])],
             ["confidence", "source_type", "review_status", "approval_method", "derivation_version"])
    by_kind: dict[str, list[dict]] = {}
    for dep in data["dependencies"]:
        kind = SOURCE_EDGE_ALIASES.get(dep["relationship_type"], dep["relationship_type"])
        if kind in STEP_EDGE_TYPES:
            by_kind.setdefault(kind, []).append(dict(dep))
    for kind, selected in sorted(by_kind.items()):
        edge_job(kind, "SolutionStep", "SolutionStep", "from_step_id", "to_step_id", selected,
                 ["logical_dependency", "confidence", "source_type", "review_status", "approval_method"])

    jobs.append(("LearningItem", f"""
        UNWIND $rows AS row
        MERGE (n:LearningItem {{canonical_id: row.id}})
        SET {common}, n.transformation_type = row.transformation_type,
            n.transformed_form = row.transformed_form, n.difficulty_direction = row.difficulty_direction,
            n.publication_status = row.review_status
        RETURN count(n) AS written""", data["learning_items"]))
    expected["LearningItem"] = len(data["learning_items"])
    edge_job("DERIVED_FROM", "LearningItem", "Problem", "id", "problem_id", [dict(r) for r in data["learning_items"]])
    edge_job("ASSESSES", "LearningItem", "Skill", "id", "skill_id",
             [dict(r) for r in data["learning_items"] if r["skill_id"]])
    # Bridged like the step USES_* edges: taxonomy node -> core.concept uuid (the graph canonical_id).
    for kind, column, label in (("TARGETS_CONCEPT", "concept_id", "Concept"),
                                ("TARGETS_SUBCONCEPT", "subconcept_id", "Subconcept")):
        edge_job(kind, "LearningItem", label, "id", column,
                 [dict(r) for r in data["learning_items"] if r.get(column)])
    edge_job("ANCHORED_AT", "LearningItem", "SolutionStep", "learning_item_id", "solution_step_id",
             [dict(r) for r in data["anchors"]], ["ordinal"])
    return jobs, expected, keys


def write_with_retry(target, work, attempts: int = 6):
    for attempt in range(1, attempts + 1):
        try:
            with target.session() as session:
                return session.execute_write(work)
        except (TransientError, ServiceUnavailable, SessionExpired) as exc:
            if attempt == attempts:
                raise
            delay = min(60, 5 * attempt)
            print(f"  transient graph error ({type(exc).__name__}); retry {attempt}/{attempts - 1} in {delay}s")
            time.sleep(delay)


def project(target, data: dict[str, list[dict]]) -> Counter:
    jobs, expected, keys = build_jobs(data)
    with target.session() as session:
        for statement in CONSTRAINTS:
            session.run(statement).consume()
    for label, query, selected in jobs:
        for batch in chunks(selected, BATCH_SIZE):
            def work(tx, batch=batch, query=query):
                return tx.run(query, rows=batch).single()["written"]
            written = write_with_retry(target, work)
            if written != len(batch):
                raise RuntimeError(
                    f"{label}: wrote {written}/{len(batch)}; graph endpoints are missing. "
                    "Run project_from_postgres.py --pedagogy first (make -C mathbank-db textbook-graph-remote)."
                )
    node_ids = {"SolutionPart": [r["id"] for r in data["parts"]], "SolutionStep": [r["id"] for r in data["steps"]],
                "LearningItem": [r["id"] for r in data["learning_items"]]}

    def prune(tx):
        removed = 0
        for label, ids in node_ids.items():
            removed += tx.run(f"MATCH (n:{label}) WHERE n.projection_kind = $kind AND NOT n.canonical_id IN $ids "
                              "DETACH DELETE n RETURN count(*) AS c", kind=KIND, ids=ids).single()["c"]
        removed += tx.run("MATCH ()-[r]->() WHERE r.projection_kind = $kind AND NOT r.projection_key IN $keys "
                          "DELETE r RETURN count(*) AS c", kind=KIND, keys=keys).single()["c"]
        return removed

    print(f"  pruned {write_with_retry(target, prune)} stale node(s)/edge(s)")
    return expected


def graph_counts(target) -> Counter:
    counts: Counter = Counter()
    with target.session() as session:
        for record in session.run("MATCH (n) WHERE n.projection_kind = $kind "
                                  "RETURN labels(n)[0] AS label, count(*) AS c", kind=KIND):
            counts[record["label"]] = record["c"]
        for record in session.run("MATCH ()-[r]->() WHERE r.projection_kind = $kind "
                                  "RETURN type(r) AS label, count(*) AS c", kind=KIND):
            counts[record["label"]] = record["c"]
    return counts


def reconcile(expected: Counter, actual: Counter) -> bool:
    ok = True
    print(f"  {'type':<18}{'postgres':>10}{'graph':>10}  ok")
    for label in sorted(set(expected) | set(actual)):
        match = expected[label] == actual[label]
        ok &= match
        print(f"  {label:<18}{expected[label]:>10}{actual[label]:>10}  {'yes' if match else 'NO'}")
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Read PostgreSQL and print planned counts only")
    parser.add_argument("--status", action="store_true", help="Compare PostgreSQL with the graph without writing")
    args = parser.parse_args(argv)
    env = _load_env()
    with psycopg.connect(pg_conninfo(env)) as conn, conn.cursor() as cur:
        data = load(cur)
        conn.commit()
        _, expected, _ = build_jobs({k: [dict(r) for r in v] for k, v in data.items()})
        packages = ", ".join(p["package_name"] for p in data["packages"]) or "none"
        print(f"textbook step projection: packages = {packages}")
        if args.dry_run:
            for label, count in sorted(expected.items()):
                print(f"  {label:<18}{count:>10}")
            return 0
        target = graph_target(env)
        try:
            if args.status:
                return 0 if reconcile(expected, graph_counts(target)) else 1
            cur.execute("INSERT INTO pipeline.graph_projection (graph_name, status) "
                        "VALUES ('textbook_step_graph', 'IN_PROGRESS') RETURNING projection_run_id")
            run_id = cur.fetchone()[0]
            conn.commit()
            try:
                expected = project(target, data)
                actual = graph_counts(target)
                ok = reconcile(expected, actual)
                nodes = sum(actual[k] for k in ("SolutionPart", "SolutionStep", "LearningItem"))
                cur.execute("UPDATE pipeline.graph_projection SET completed_at = now(), status = %s, "
                            "nodes_upserted = %s, edges_upserted = %s, error = %s WHERE projection_run_id = %s",
                            ("COMPLETED" if ok else "FAILED", nodes, sum(actual.values()) - nodes,
                             None if ok else "graph/postgres count mismatch", run_id))
                summary = {"graph_projection": {"run_id": str(run_id), "reconciled": ok,
                                                "counts": dict(actual), "projection_version": PROJECTION_VERSION}}
                cur.execute("UPDATE ingest.content_package SET report = coalesce(report, '{}'::jsonb) || %s::jsonb "
                            "WHERE content_package_id = ANY(%s::uuid[])",
                            (json.dumps(summary), [p["content_package_id"] for p in data["packages"]]))
                conn.commit()
                return 0 if ok else 1
            except Exception as exc:
                conn.rollback()
                cur.execute("UPDATE pipeline.graph_projection SET completed_at = now(), status = 'FAILED', "
                            "error = %s WHERE projection_run_id = %s", (str(exc)[:2000], run_id))
                conn.commit()
                raise
        finally:
            target.close()


if __name__ == "__main__":
    raise SystemExit(main())
