"""Atomic metadata-only projection of published instructional route releases."""

from __future__ import annotations

import json

from neo4j.exceptions import Neo4jError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.config import settings
from mathbank_rest.db.graph import driver
from mathbank_rest.db.postgres import engine
from mathbank_rest.route_runtime import load_program

KIND = "tutoring_routes"
LABELS = {
    "CLAIM": "Claim",
    "MISCONCEPTION": "Misconception",
    "THEORY": "TheoryItem",
    "LEARNING_ITEM": "LearningItem",
}


def metadata(conn) -> dict:
    releases = [
        dict(row)
        for row in conn.execute(
            text("""
        SELECT r.route_release_id::text AS id,r.solution_id::text AS solution_id,
               r.problem_id::text AS problem_id,p.canonical_code,r.release_version,
               r.difficulty_level,r.conceptual_load,r.algebraic_load,r.insight_load,r.status
        FROM pedagogy.solution_route_release r JOIN core.problem p USING(problem_id)
        WHERE r.status='PUBLISHED' ORDER BY r.route_release_id
    """)
        ).mappings()
    ]
    nodes, edges = [], []
    taxonomy = {
        row["taxonomy_node_id"]: dict(row)
        for row in conn.execute(
            text("""
        SELECT taxonomy_node_id,node_type,coalesce(technique_id,skill_id,concept_id)::text AS id
        FROM pedagogy.taxonomy_node
    """)
        ).mappings()
    }
    for release in releases:
        rid = release["id"]
        nodes.append(
            {"label": "RouteRelease", "id": rid, "properties": {"canonical_id": rid, **release}}
        )
        edges.append(
            {
                "from": release["solution_id"],
                "from_label": "Solution",
                "to": rid,
                "to_label": "RouteRelease",
                "type": "HAS_ROUTE",
                "properties": {},
            }
        )
        step_ids = dict(
            conn.execute(
                text("""
            SELECT step_index,step_id::text FROM pedagogy.route_step WHERE route_release_id=:r
        """),
                {"r": rid},
            ).all()
        )
        asset_ids = dict(
            conn.execute(
                text("""
            SELECT asset_key,asset_id::text FROM pedagogy.route_asset WHERE route_release_id=:r
        """),
                {"r": rid},
            ).all()
        )
        program = load_program(conn, rid)
        assets = {asset.key: asset for asset in program.assets}
        for asset in program.assets:
            aid = asset_ids[asset.key]
            nodes.append(
                {
                    "id": aid,
                    "label": LABELS[asset.kind],
                    "properties": {
                        "canonical_id": aid,
                        "route_release_id": rid,
                        "asset_key": asset.key,
                        "purpose": asset.purpose,
                        "review_status": "REVIEWED",
                    },
                }
            )
            for key in asset.remediates:
                edges.append(
                    {
                        "from": asset_ids[key],
                        "from_label": "Misconception",
                        "to": aid,
                        "to_label": "TheoryItem",
                        "type": "REMEDIATED_BY",
                        "properties": {},
                    }
                )
            for key in asset.diagnoses:
                edges.append(
                    {
                        "from": asset_ids[key],
                        "from_label": "Misconception",
                        "to": aid,
                        "to_label": "LearningItem",
                        "type": "DIAGNOSED_BY",
                        "properties": {},
                    }
                )
                edges.append(
                    {
                        "from": aid,
                        "from_label": "LearningItem",
                        "to": asset_ids[key],
                        "to_label": "Misconception",
                        "type": "TESTS_MISCONCEPTION",
                        "properties": {},
                    }
                )
            for key in asset.taxonomy_node_ids:
                target = taxonomy[key]
                if (
                    target["id"]
                    and target["node_type"] == "TECHNIQUE"
                    and asset.kind in {"THEORY", "LEARNING_ITEM"}
                ):
                    edges.append(
                        {
                            "from": aid,
                            "from_label": LABELS[asset.kind],
                            "to": target["id"],
                            "to_label": "Technique",
                            "type": "EXPLAINS" if asset.kind == "THEORY" else "PRACTICES",
                            "properties": {},
                        }
                    )
        for index, step in enumerate(program.steps, 1):
            sid = step_ids[index]
            nodes.append(
                {
                    "id": sid,
                    "label": "RouteStep",
                    "properties": {
                        "canonical_id": sid,
                        "route_release_id": rid,
                        "step_index": index,
                        "review_status": "REVIEWED",
                    },
                }
            )
            edges.append(
                {
                    "from": rid,
                    "from_label": "RouteRelease",
                    "to": sid,
                    "to_label": "RouteStep",
                    "type": "HAS_STEP",
                    "properties": {},
                }
            )
            for prior in step.depends_on:
                edges.append(
                    {
                        "from": sid,
                        "from_label": "RouteStep",
                        "to": step_ids[prior],
                        "to_label": "RouteStep",
                        "type": "DEPENDS_ON",
                        "properties": {},
                    }
                )
            for relation, keys in (("PRODUCES", step.produces), ("USES_CLAIM", step.uses_claims)):
                edges.extend(
                    {
                        "from": sid,
                        "from_label": "RouteStep",
                        "to": asset_ids[key],
                        "to_label": "Claim",
                        "type": relation,
                        "properties": {},
                    }
                    for key in keys
                )
            for link in step.asset_links:
                edges.append(
                    {
                        "from": sid,
                        "from_label": "RouteStep",
                        "to": asset_ids[link.asset_key],
                        "to_label": LABELS[assets[link.asset_key].kind],
                        "type": link.role,
                        "properties": {},
                    }
                )
            for requirement in step.requirements:
                target = taxonomy[requirement.taxonomy_node_id]
                if not target["id"]:
                    raise ValueError("Canonical requirement has no graph identity.")
                label = {
                    "SKILL": "Skill",
                    "TECHNIQUE": "Technique",
                    "CONCEPT": "Concept",
                    "SUBCONCEPT": "Concept",
                }[target["node_type"]]
                edges.append(
                    {
                        "from": sid,
                        "from_label": "RouteStep",
                        "to": target["id"],
                        "to_label": label,
                        "type": {
                            "Skill": "USES_SKILL",
                            "Technique": "USES_TECHNIQUE",
                            "Concept": "USES_CONCEPT",
                        }[label]
                        if requirement.role == "USED"
                        else "REQUIRES",
                        "properties": requirement.model_dump(exclude={"taxonomy_node_id"}),
                    }
                )
                if label == "Technique" and requirement.role == "USED":
                    edges.append(
                        {
                            "from": release["solution_id"],
                            "from_label": "Solution",
                            "to": target["id"],
                            "to_label": "Technique",
                            "type": "USES_APPROACH",
                            "properties": {},
                        }
                    )
    return {"releases": releases, "nodes": nodes, "edges": edges}


def project() -> dict:
    direct = create_engine(engine.url.set(host=(engine.url.host or "").replace("-pooler.", ".")))
    try:
        with direct.connect() as lease:
            acquired = lease.execute(text("SELECT pg_try_advisory_lock(390027)")).scalar_one()
            lease.commit()
            if not acquired:
                raise ValueError("A tutoring-route projection is already running.")
            with engine.begin() as conn:
                run = conn.execute(
                    text("""
                    INSERT INTO pipeline.graph_projection(graph_name,status)
                    VALUES ('tutoring_routes','IN_PROGRESS') RETURNING projection_run_id
                """)
                ).scalar_one()
            try:
                report = _project()
            except (SQLAlchemyError, Neo4jError, ValueError) as exc:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                        UPDATE pipeline.graph_projection SET status='FAILED',completed_at=now(),error=:e
                        WHERE projection_run_id=:id
                    """),
                        {"id": run, "e": type(exc).__name__},
                    )
                raise
            else:
                with engine.begin() as conn:
                    conn.execute(
                        text("""
                        UPDATE pipeline.graph_projection SET status='COMPLETED',completed_at=now(),
                            nodes_upserted=:n,edges_upserted=:e WHERE projection_run_id=:id
                    """),
                        {"id": run, "n": report["nodes"], "e": report["edges"]},
                    )
                return {**report, "projection_run_id": str(run)}
            finally:
                lease.execute(text("SELECT pg_advisory_unlock(390027)"))
                lease.commit()
    finally:
        direct.dispose()


def _project() -> dict:
    with engine.connect() as conn:
        data = metadata(conn)
    with driver.session(database=settings.neo4j_database) as session:
        for label in {"RouteRelease", "RouteStep", *LABELS.values()}:
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.canonical_id IS UNIQUE"
            ).consume()

        def replace(tx):
            tx.run("MATCH ()-[r]->() WHERE r.projection_kind=$kind DELETE r", kind=KIND).consume()
            tx.run("MATCH (n) WHERE n.projection_kind=$kind DETACH DELETE n", kind=KIND).consume()
            for node in data["nodes"]:
                tx.run(
                    f"MERGE (n:{node['label']} {{canonical_id:$id}}) "
                    "SET n += $properties,n.projection_kind=$kind",
                    id=node["id"],
                    properties=node["properties"],
                    kind=KIND,
                ).consume()
            for edge in data["edges"]:
                result = tx.run(
                    f"MATCH (a:{edge['from_label']} {{canonical_id:$from_id}}),"
                    f"(b:{edge['to_label']} {{canonical_id:$to_id}}) "
                    f"MERGE (a)-[r:{edge['type']} {{projection_kind:$kind,role:$role}}]->(b) "
                    "SET r += $properties RETURN count(r) AS written",
                    from_id=edge["from"],
                    to_id=edge["to"],
                    properties=edge["properties"],
                    role=edge["properties"].get("role", ""),
                    kind=KIND,
                ).single()
                if not result or result["written"] != 1:
                    raise ValueError(
                        "Graph endpoint is missing; refresh the corpus/taxonomy projection first."
                    )

        session.execute_write(replace)
        count = session.run(
            "MATCH (n) WHERE n.projection_kind=$kind RETURN count(n) AS nodes", kind=KIND
        ).single()["nodes"]
        edge_count = session.run(
            "MATCH ()-[r]->() WHERE r.projection_kind=$kind RETURN count(r) AS edges", kind=KIND
        ).single()["edges"]
        expected_edges = {
            (edge["from"], edge["to"], edge["type"], edge["properties"].get("role", ""))
            for edge in data["edges"]
        }
        if count != len(data["nodes"]) or edge_count != len(expected_edges):
            raise ValueError("Tutoring graph metadata counts do not reconcile.")
    return {
        "status": "COMPLETED",
        "published_releases": len(data["releases"]),
        "nodes": count,
        "edges": edge_count,
        "drafts_projected": 0,
    }


if __name__ == "__main__":
    print(json.dumps(project(), indent=2))
