"""Project the mathbank Postgres system of record into the Neo4j corpus graph.

Per mathematics_tutor_db_plan/graph/03_postgres_to_graph_projection.md:
- idempotent (MERGE on canonical_id = the Postgres UUID)
- records a pipeline.graph_projection row in Postgres for each run

Run via `make project` in mathbank-graph/.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from neo4j import GraphDatabase

BATCH_SIZE = 500


class GraphTarget:
    """Apply the configured database consistently to every projection session."""

    def __init__(self, driver, database: str | None):
        self.driver = driver
        self.database = database

    def session(self):
        return self.driver.session(database=self.database)

    def close(self) -> None:
        self.driver.close()


def _load_env() -> dict[str, str]:
    # GRAPH_ENV_FILE lets `make project ENV_FILE=remote.env` point this at the
    # Neon/AuraDB remote credentials instead of the local .env (see remote.env).
    env_path = Path(os.environ.get("GRAPH_ENV_FILE") or Path(__file__).resolve().parents[1] / ".env")
    env: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip()
    return env


def chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


CONSTRAINTS = [
    "CREATE CONSTRAINT competition_id IF NOT EXISTS FOR (n:Competition) REQUIRE n.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT paper_id IF NOT EXISTS FOR (n:Paper) REQUIRE n.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT problem_id IF NOT EXISTS FOR (n:Problem) REQUIRE n.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (n:Concept) REQUIRE n.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT technique_id IF NOT EXISTS FOR (n:Technique) REQUIRE n.canonical_id IS UNIQUE",
    "CREATE CONSTRAINT solution_id IF NOT EXISTS FOR (n:Solution) REQUIRE n.canonical_id IS UNIQUE",
]


def ensure_constraints(driver, pedagogy: bool = False) -> None:
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)
        if pedagogy:
            session.run("CREATE CONSTRAINT skill_id IF NOT EXISTS FOR (n:Skill) REQUIRE n.canonical_id IS UNIQUE")


def project_competitions(driver, pg_cur) -> int:
    pg_cur.execute("SELECT competition_id, external_code, name, level FROM core.competition")
    rows = [
        {"id": str(r[0]), "external_code": r[1], "name": r[2], "level": r[3]}
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (c:Competition {canonical_id: row.id})
                SET c.external_code = row.external_code,
                    c.name = row.name,
                    c.level = row.level
                """,
                rows=batch,
            )
    return len(rows)


def project_papers(driver, pg_cur) -> int:
    pg_cur.execute(
        """
        SELECT p.paper_id, p.external_code, p.paper_code, p.question_count,
               e.year, e.competition_id
        FROM core.paper p
        JOIN core.competition_edition e ON e.edition_id = p.edition_id
        """
    )
    rows = [
        {
            "id": str(r[0]),
            "external_code": r[1],
            "paper_code": r[2],
            "question_count": r[3],
            "year": r[4],
            "competition_id": str(r[5]),
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (p:Paper {canonical_id: row.id})
                SET p.external_code = row.external_code,
                    p.paper_code = row.paper_code,
                    p.question_count = row.question_count,
                    p.year = row.year
                WITH p, row
                MATCH (c:Competition {canonical_id: row.competition_id})
                MERGE (c)-[:HAS_PAPER]->(p)
                """,
                rows=batch,
            )
    return len(rows)


def project_problems(driver, pg_cur, problem_codes: list[str] | None = None) -> int:
    pg_cur.execute(
        """
        SELECT problem_id, canonical_code, problem_number, official_answer,
               source_url, paper_id, difficulty_band, classification_status
        FROM core.problem
        """ + (" WHERE canonical_code=ANY(%s)" if problem_codes is not None else ""),
        (problem_codes,) if problem_codes is not None else None,
    )
    rows = [
        {
            "id": str(r[0]),
            "canonical_code": r[1],
            "problem_number": r[2],
            "official_answer": r[3],
            "source_url": r[4],
            "paper_id": str(r[5]),
            "difficulty_band": r[6],
            "classification_status": r[7],
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (p:Problem {canonical_id: row.id})
                SET p.canonical_code = row.canonical_code,
                    p.problem_number = row.problem_number,
                    p.official_answer = row.official_answer,
                    p.source_url = row.source_url,
                    p.difficulty_band = row.difficulty_band,
                    p.classification_status = row.classification_status
                WITH p, row
                MATCH (pa:Paper {canonical_id: row.paper_id})
                MERGE (pa)-[:HAS_PROBLEM]->(p)
                """,
                rows=batch,
            )
    return len(rows)


def project_solutions(driver, pg_cur) -> int:
    """Lightweight Solution nodes — full body_markdown stays in Postgres and is
    fetched by canonical_id, per graph/02_nodes_edges_and_constraints.md."""
    pg_cur.execute(
        """
        SELECT solution_id, problem_id, solution_kind, revision, verification_status
        FROM core.solution
        """
    )
    rows = [
        {
            "id": str(r[0]),
            "problem_id": str(r[1]),
            "solution_kind": r[2],
            "revision": r[3],
            "verification_status": r[4],
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (s:Solution {canonical_id: row.id})
                SET s.solution_kind = row.solution_kind,
                    s.revision = row.revision,
                    s.verification_status = row.verification_status
                WITH s, row
                MATCH (p:Problem {canonical_id: row.problem_id})
                MERGE (p)-[:HAS_SOLUTION]->(s)
                """,
                rows=batch,
            )
    return len(rows)


def project_concepts(driver, pg_cur) -> int:
    pg_cur.execute("SELECT concept_id, slug, name, level FROM knowledge.concept")
    rows = [
        {"id": str(r[0]), "slug": r[1], "name": r[2], "level": r[3]} for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (c:Concept {canonical_id: row.id})
                SET c.slug = row.slug, c.name = row.name, c.level = row.level
                """,
                rows=batch,
            )
    return len(rows)


def project_techniques(driver, pg_cur) -> int:
    pg_cur.execute("SELECT technique_id, slug, name FROM knowledge.technique")
    rows = [{"id": str(r[0]), "slug": r[1], "name": r[2]} for r in pg_cur.fetchall()]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MERGE (t:Technique {canonical_id: row.id})
                SET t.slug = row.slug, t.name = row.name
                """,
                rows=batch,
            )
    return len(rows)


def project_problem_concept(driver, pg_cur, problem_codes: list[str] | None = None) -> int:
    pg_cur.execute(
        "SELECT problem_id, concept_id, role, confidence, assertion_source, review_status FROM knowledge.problem_concept"
        + (" WHERE problem_id IN (SELECT problem_id FROM core.problem WHERE canonical_code=ANY(%s))"
           if problem_codes is not None else ""),
        (problem_codes,) if problem_codes is not None else None,
    )
    rows = [
        {
            "problem_id": str(r[0]),
            "concept_id": str(r[1]),
            "role": r[2],
            "confidence": float(r[3]) if r[3] is not None else None,
            "source": r[4],
            "review_status": r[5],
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Problem {canonical_id: row.problem_id})
                MATCH (c:Concept {canonical_id: row.concept_id})
                MERGE (p)-[r:TESTS {role: row.role}]->(c)
                SET r.confidence = row.confidence, r.source = row.source,
                    r.review_status = row.review_status
                """,
                rows=batch,
            )
    return len(rows)


def project_problem_technique(driver, pg_cur, problem_codes: list[str] | None = None) -> int:
    pg_cur.execute(
        "SELECT problem_id, technique_id, role, confidence, assertion_source, review_status FROM knowledge.problem_technique"
        + (" WHERE problem_id IN (SELECT problem_id FROM core.problem WHERE canonical_code=ANY(%s))"
           if problem_codes is not None else ""),
        (problem_codes,) if problem_codes is not None else None,
    )
    rows = [
        {
            "problem_id": str(r[0]),
            "technique_id": str(r[1]),
            "role": r[2],
            "confidence": float(r[3]) if r[3] is not None else None,
            "source": r[4],
            "review_status": r[5],
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Problem {canonical_id: row.problem_id})
                MATCH (t:Technique {canonical_id: row.technique_id})
                MERGE (p)-[r:USES_TECHNIQUE {role: row.role}]->(t)
                SET r.confidence = row.confidence, r.source = row.source,
                    r.review_status = row.review_status
                """,
                rows=batch,
            )
    return len(rows)


def project_concept_relation(driver, pg_cur) -> int:
    pg_cur.execute(
        "SELECT from_concept_id, to_concept_id, relation_type, strength, assertion_source, review_status FROM knowledge.concept_relation"
    )
    rows = [
        {
            "from_id": str(r[0]),
            "to_id": str(r[1]),
            "relation_type": r[2],
            "strength": float(r[3]) if r[3] is not None else None,
            "confidence": float(r[3]) if r[3] is not None else None,
            "source": r[4],
            "review_status": r[5],
        }
        for r in pg_cur.fetchall()
    ]
    with driver.session() as session:
        for batch in chunks(rows, BATCH_SIZE):
            session.run(
                """
                UNWIND $rows AS row
                MATCH (a:Concept {canonical_id: row.from_id})
                MATCH (b:Concept {canonical_id: row.to_id})
                MERGE (a)-[r:CONCEPT_RELATION {relation_type: row.relation_type}]->(b)
                SET r.strength = row.strength, r.confidence = row.confidence,
                    r.source = row.source, r.review_status = row.review_status
                """,
                rows=batch,
            )
    return len(rows)


PEDAGOGY_TABLES = ("skill", "skill_concept", "skill_relation", "problem_skill", "problem_pedagogy")
SEMANTIC_RELATIONS = frozenset({"PREREQUISITE_OF", "PART_OF", "BUILDS_ON"})


def require_pedagogy_schema(pg_cur) -> None:
    for table in PEDAGOGY_TABLES:
        pg_cur.execute("SELECT to_regclass(%s)", (f"knowledge.{table}",))
        if pg_cur.fetchone()[0] is None:
            raise RuntimeError("--pedagogy requires mathbank-db/sql/006_pedagogy.sql; "
                               "apply it explicitly with make -C mathbank-db migrate-pedagogy")


def semantic_relation(kind: str, from_id: str, to_id: str):
    """Only explicit, case-sensitive semantics; never infer unknown vocabulary."""
    if kind == "HAS_SUBCONCEPT":
        return "PART_OF", to_id, from_id
    if kind in SEMANTIC_RELATIONS:
        return kind, from_id, to_id
    return None


def _dict_rows(pg_cur, query: str, columns: list[str]) -> list[dict]:
    pg_cur.execute(query)
    rows = []
    for values in pg_cur.fetchall():
        row = dict(zip(columns, values))
        for key, value in row.items():
            if key.endswith("_id"):
                row[key] = str(value)
            elif key in {"confidence", "importance"} and value is not None:
                row[key] = float(value)
        rows.append(row)
    return rows


def project_pedagogy(driver, pg_cur, problem_codes: list[str] | None = None) -> tuple[int, int]:
    require_pedagogy_schema(pg_cur)
    jobs: list[tuple[str, list[dict]]] = []

    def queue(query: str, rows: list[dict]) -> int:
        jobs.append((query, rows))
        return len(rows)

    skill_columns = ["skill_id", "slug", "name", "objective", "level", "source", "confidence", "review_status", "approval_method"]
    skill_rows = _dict_rows(pg_cur, "SELECT " + ", ".join(skill_columns) + " FROM knowledge.skill", skill_columns)
    nodes = queue("""
        UNWIND $rows AS row
        MERGE (s:Skill {canonical_id: row.skill_id})
        SET s.slug = row.slug, s.name = row.name, s.objective = row.objective,
            s.level = row.level, s.source = row.source,
            s.confidence = row.confidence, s.review_status = row.review_status,
            s.approval_method = row.approval_method,
            s.projection_kind = 'pedagogy'
        RETURN count(s) AS written
    """, skill_rows)
    edges = 0
    specs = [
        ("skill_concept", "Skill", "Concept", "skill_id", "concept_id", ["source", "confidence", "review_status", "approval_method"]),
        ("skill_relation", "Skill", "Skill", "from_skill_id", "to_skill_id", ["relation_type", "source", "confidence", "review_status", "approval_method"]),
        ("problem_skill", "Problem", "Skill", "problem_id", "skill_id",
         ["relation_type", "role", "required_level", "importance", "source", "confidence", "review_status", "approval_method"]),
    ]
    for table, start_label, end_label, start, end, properties in specs:
        columns = [start, end] + properties
        rows = _dict_rows(pg_cur, "SELECT " + ", ".join(columns) +
                          f" FROM knowledge.{table}", columns)
        types = {"PART_OF"} if table == "skill_concept" else (
            {"REQUIRES", "PRACTICES", "TESTS"} if table == "problem_skill" else SEMANTIC_RELATIONS
        )
        for kind in sorted(types):
            selected = [row for row in rows if row.get("relation_type", "PART_OF") == kind]
            role_key = " {role: row.role}" if table == "problem_skill" else ""
            assignments = ", ".join(f"r.{prop} = row.{prop}" for prop in properties if prop != "relation_type")
            edges += queue(f"""
                UNWIND $rows AS row
                MATCH (a:{start_label} {{canonical_id: row.{start}}})
                MATCH (b:{end_label} {{canonical_id: row.{end}}})
                MERGE (a)-[r:{kind}{role_key}]->(b)
                SET {assignments}, r.projection_kind = 'pedagogy'
                RETURN count(r) AS written
            """, selected)
    columns = ["from_id", "to_id", "relation_type", "confidence", "source", "review_status", "approval_method"]
    rows = _dict_rows(pg_cur, """
        SELECT from_concept_id, to_concept_id, relation_type, strength, assertion_source, review_status, approval_method
        FROM knowledge.concept_relation
    """, columns)
    for kind in sorted(SEMANTIC_RELATIONS):
        selected = []
        for row in rows:
            semantic = semantic_relation(row["relation_type"], row["from_id"], row["to_id"])
            if semantic and semantic[0] == kind:
                selected.append({**row, "from_id": semantic[1], "to_id": semantic[2]})
        edges += queue(f"""
            UNWIND $rows AS row
            MATCH (a:Concept {{canonical_id: row.from_id}})
            MATCH (b:Concept {{canonical_id: row.to_id}})
            MERGE (a)-[r:{kind}]->(b)
            SET r.source = row.source, r.confidence = row.confidence,
                r.review_status = row.review_status, r.approval_method = row.approval_method,
                r.projection_kind = 'pedagogy'
            RETURN count(r) AS written
        """, selected)
    columns = ["problem_id", "conceptual_depth", "technical_load", "algebraic_load", "insight_required",
               "number_of_steps", "prerequisite_depth", "estimated_contest_level",
               "source", "confidence", "review_status", "approval_method"]
    # Keep assertion provenance names scoped to pedagogy on the shared Problem node.
    assignments = ", ".join(f"p.pedagogy_{c} = row.{c}" if c in {"source", "confidence", "review_status", "approval_method"}
                            else f"p.{c} = row.{c}" for c in columns[1:])
    names = ["pedagogy_" + c if c in {"source", "confidence", "review_status", "approval_method"} else c for c in columns[1:]]
    queue(f"UNWIND $rows AS row MATCH (p:Problem {{canonical_id: row.problem_id}}) SET {assignments} RETURN count(p) AS written",
          _dict_rows(pg_cur, "SELECT " + ", ".join(columns) + " FROM knowledge.problem_pedagogy", columns))

    def write(tx) -> None:
        # Atomic replacement: a failed import cannot erase the previous live layer.
        tx.run("MATCH ()-[r]->() WHERE r.projection_kind = 'pedagogy' DELETE r").consume()
        tx.run("MATCH (p:Problem) REMOVE " + ", ".join("p." + c for c in names)).consume()
        tx.run("""
            MATCH (s:Skill) WHERE s.projection_kind = 'pedagogy'
              AND NOT s.canonical_id IN $ids
            SET s.review_status = 'REJECTED'
        """, ids=[row["skill_id"] for row in skill_rows]).consume()
        for query, rows in jobs:
            for batch in chunks(rows, BATCH_SIZE):
                result = tx.run(query, rows=batch).single()
                if result is None or result["written"] != len(batch):
                    raise RuntimeError(
                        "Pedagogy projection has missing or duplicate canonical graph targets; "
                        "project the corpus first. The replacement was rolled back."
                    )

    with driver.session() as session:
        session.execute_write(write)
    project_approval_methods(driver, pg_cur, problem_codes)
    return nodes, edges


def project_approval_methods(driver, pg_cur, problem_codes: list[str] | None = None) -> None:
    """Carry automatic/human provenance without changing compatible review statuses."""
    queries = [
        ("skill", "skill_id", "Skill", "approval_method"),
        ("problem_pedagogy", "problem_id", "Problem", "pedagogy_approval_method"),
    ]
    with driver.session() as session:
        for table, key, label, prop in queries:
            pg_cur.execute(f"SELECT {key},approval_method FROM knowledge.{table}")
            rows = [{"id": str(row[0]), "method": row[1]} for row in pg_cur.fetchall()]
            for batch in chunks(rows, BATCH_SIZE):
                session.run(f"UNWIND $rows AS row MATCH (n:{label} {{canonical_id:row.id}}) "
                            f"SET n.{prop}=row.method", rows=batch).consume()
        for table, start, end, start_label, end_label, relation, role in [
            ("problem_skill", "problem_id", "skill_id", "Problem", "Skill", None, True),
            ("skill_concept", "skill_id", "concept_id", "Skill", "Concept", "PART_OF", False),
            ("skill_relation", "from_skill_id", "to_skill_id", "Skill", "Skill", None, False),
            ("problem_concept", "problem_id", "concept_id", "Problem", "Concept", "TESTS", True),
            ("problem_technique", "problem_id", "technique_id", "Problem", "Technique", "USES_TECHNIQUE", True),
        ]:
            columns = [start, end, "approval_method"]
            if relation is None:
                columns.append("relation_type")
            if role:
                columns.append("role")
            query = "SELECT " + ",".join(columns) + f" FROM knowledge.{table}"
            if start == "problem_id" and problem_codes is not None:
                pg_cur.execute(query + " WHERE problem_id IN "
                               "(SELECT problem_id FROM core.problem WHERE canonical_code=ANY(%s))",
                               (problem_codes,))
                rows = [dict(zip(columns, values)) for values in pg_cur.fetchall()]
                for row in rows:
                    row[start], row[end] = str(row[start]), str(row[end])
            else:
                rows = _dict_rows(pg_cur, query, columns)
            for batch in chunks(rows, BATCH_SIZE):
                role_filter = " AND r.role=row.role" if role else ""
                type_filter = f"type(r)='{relation}'" if relation else "type(r)=row.relation_type"
                session.run(f"""
                    UNWIND $rows AS row
                    MATCH (a:{start_label} {{canonical_id:row.{start}}})-[r]->(b:{end_label} {{canonical_id:row.{end}}})
                    WHERE {type_filter}{role_filter}
                    SET r.approval_method=row.approval_method
                """, rows=batch).consume()
        pg_cur.execute(
            "SELECT from_concept_id,to_concept_id,relation_type,approval_method "
            "FROM knowledge.concept_relation"
        )
        semantic_rows = []
        relation_rows = []
        for start, end, kind, method in pg_cur.fetchall():
            relation_rows.append({"start": str(start), "end": str(end),
                                  "kind": kind, "method": method})
            semantic = semantic_relation(kind, str(start), str(end))
            if semantic:
                semantic_rows.append({"start": semantic[1], "end": semantic[2],
                                      "kind": semantic[0], "method": method})
        for batch in chunks(relation_rows, BATCH_SIZE):
            session.run("""
                UNWIND $rows AS row
                MATCH (a:Concept {canonical_id:row.start})-[r:CONCEPT_RELATION]->
                      (b:Concept {canonical_id:row.end})
                WHERE r.relation_type=row.kind SET r.approval_method=row.method
            """, rows=batch).consume()
        for batch in chunks(semantic_rows, BATCH_SIZE):
            session.run("""
                UNWIND $rows AS row
                MATCH (a:Concept {canonical_id:row.start})-[r]->
                      (b:Concept {canonical_id:row.end})
                WHERE type(r)=row.kind SET r.approval_method=row.method
            """, rows=batch).consume()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pedagogy", action="store_true", help="Opt in to migration-006 skills and provenance-bearing semantic inventory")
    args = parser.parse_args()
    env = _load_env()
    pg_conninfo = (
        f"host={env.get('NEON_PG_HOST', '127.0.0.1')} port={env.get('NEON_PG_PORT') or env.get('PG_PORT', '5433')} "
        f"dbname={env.get('NEON_PG_DATABASE') or env.get('APP_DB', 'mathbank')} "
        f"user={env.get('NEON_PG_USER') or env.get('APP_USER', 'mathbank_app')} "
        f"password={env.get('NEON_PG_PASSWORD') or env.get('APP_DB_PASSWORD', '')}"
        + (f" sslmode={env['NEON_PG_SSLMODE']}" if env.get("NEON_PG_SSLMODE") else "")
    )
    # Remote (AuraDB) creds use the NEO4J_URI/NEO4J_USERNAME/NEO4J_DATABASE names
    # Aura's console download uses verbatim; local dev uses bolt://localhost + NEO4J_PASSWORD only.
    neo4j_uri = env.get("NEO4J_URI") or f"bolt://localhost:{env.get('NEO4J_BOLT_PORT', '7687')}"
    neo4j_user = env.get("NEO4J_USERNAME") or env.get("NEO4J_USER", "neo4j")
    neo4j_password = env.get("NEO4J_PASSWORD", "")
    driver = GraphTarget(
        GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password)),
        env.get("NEO4J_DATABASE") or None,
    )
    with psycopg.connect(pg_conninfo) as pg_conn:
        with pg_conn.cursor() as pg_cur:
            if args.pedagogy:
                require_pedagogy_schema(pg_cur)
            pg_cur.execute(
                """
                INSERT INTO pipeline.graph_projection (graph_name, status)
                VALUES ('corpus_graph', 'IN_PROGRESS')
                RETURNING projection_run_id
                """
            )
            run_id = pg_cur.fetchone()[0]
            pg_conn.commit()

            try:
                pg_cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                ensure_constraints(driver, args.pedagogy)

                node_counts = {
                    "Competition": project_competitions(driver, pg_cur),
                    "Paper": project_papers(driver, pg_cur),
                    "Problem": project_problems(driver, pg_cur),
                    "Concept": project_concepts(driver, pg_cur),
                    "Technique": project_techniques(driver, pg_cur),
                    "Solution": project_solutions(driver, pg_cur),
                }
                for label, count in node_counts.items():
                    print(f"{label}: {count} nodes upserted")

                edge_counts = {
                    "TESTS": project_problem_concept(driver, pg_cur),
                    "USES_TECHNIQUE": project_problem_technique(driver, pg_cur),
                    "CONCEPT_RELATION": project_concept_relation(driver, pg_cur),
                }
                if args.pedagogy:
                    skill_count, pedagogy_edges = project_pedagogy(driver, pg_cur)
                    node_counts["Skill"] = skill_count
                    edge_counts["PEDAGOGY"] = pedagogy_edges
                for label, count in edge_counts.items():
                    print(f"{label}: {count} edges upserted")

                pg_cur.execute(
                    """
                    UPDATE pipeline.graph_projection
                    SET completed_at = now(), status = 'COMPLETED',
                        nodes_upserted = %s, edges_upserted = %s
                    WHERE projection_run_id = %s
                    """,
                    (sum(node_counts.values()), sum(edge_counts.values()), run_id),
                )
                pg_conn.commit()
            except Exception as exc:
                pg_conn.rollback()
                pg_cur.execute(
                    """
                    UPDATE pipeline.graph_projection
                    SET completed_at = now(), status = 'FAILED', error = %s
                    WHERE projection_run_id = %s
                    """,
                    (str(exc), run_id),
                )
                pg_conn.commit()
                raise
    driver.close()


if __name__ == "__main__":
    main()
