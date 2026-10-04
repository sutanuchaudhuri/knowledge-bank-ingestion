"""Project the mathbank Postgres system of record into the Neo4j corpus graph.

Per mathematics_tutor_db_plan/graph/03_postgres_to_graph_projection.md:
- idempotent (MERGE on canonical_id = the Postgres UUID)
- records a pipeline.graph_projection row in Postgres for each run

Run via `make project` in mathbank-graph/.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from neo4j import GraphDatabase

BATCH_SIZE = 500


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


def ensure_constraints(driver) -> None:
    with driver.session() as session:
        for stmt in CONSTRAINTS:
            session.run(stmt)


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


def project_problems(driver, pg_cur) -> int:
    pg_cur.execute(
        """
        SELECT problem_id, canonical_code, problem_number, official_answer,
               source_url, paper_id, difficulty_band, classification_status
        FROM core.problem
        """
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


def project_problem_concept(driver, pg_cur) -> int:
    pg_cur.execute(
        "SELECT problem_id, concept_id, role, confidence FROM knowledge.problem_concept"
    )
    rows = [
        {
            "problem_id": str(r[0]),
            "concept_id": str(r[1]),
            "role": r[2],
            "confidence": float(r[3]) if r[3] is not None else None,
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
                SET r.confidence = row.confidence
                """,
                rows=batch,
            )
    return len(rows)


def project_problem_technique(driver, pg_cur) -> int:
    pg_cur.execute(
        "SELECT problem_id, technique_id, role, confidence FROM knowledge.problem_technique"
    )
    rows = [
        {
            "problem_id": str(r[0]),
            "technique_id": str(r[1]),
            "role": r[2],
            "confidence": float(r[3]) if r[3] is not None else None,
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
                SET r.confidence = row.confidence
                """,
                rows=batch,
            )
    return len(rows)


def project_concept_relation(driver, pg_cur) -> int:
    pg_cur.execute(
        "SELECT from_concept_id, to_concept_id, relation_type, strength FROM knowledge.concept_relation"
    )
    rows = [
        {
            "from_id": str(r[0]),
            "to_id": str(r[1]),
            "relation_type": r[2],
            "strength": float(r[3]) if r[3] is not None else None,
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
                SET r.strength = row.strength
                """,
                rows=batch,
            )
    return len(rows)


def main() -> None:
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
    neo4j_user = env.get("NEO4J_USERNAME", "neo4j")
    neo4j_password = env.get("NEO4J_PASSWORD", "")
    neo4j_database = env.get("NEO4J_DATABASE")

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    with psycopg.connect(pg_conninfo) as pg_conn:
        with pg_conn.cursor() as pg_cur:
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
                ensure_constraints(driver)

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
