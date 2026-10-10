"""Atomic metadata-only projection of published instructional route releases."""

from __future__ import annotations

import json

from neo4j.exceptions import Neo4jError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.config import settings
from mathbank_rest.db.graph import driver
from mathbank_rest.db.postgres import engine

KIND = "tutoring_routes"
LABELS = {
    "CLAIM": "Claim",
    "MISCONCEPTION": "Misconception",
    "THEORY": "TheoryItem",
    "LEARNING_ITEM": "LearningItem",
}
TAXONOMY_LABELS = {
    "SKILL": "Skill",
    "TECHNIQUE": "Technique",
    "CONCEPT": "Concept",
    "SUBCONCEPT": "Concept",
}
PROJECTION_BATCH_SIZE = 500


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


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
    # Curated nodes resolve to a pre-existing knowledge.concept/skill/technique row and
    # graph identity via the base corpus/taxonomy projector. AI-proposed nodes (added
    # mid-ingestion when no curated node genuinely applied) have no such row; project
    # them directly here, using taxonomy_node_id itself as the graph canonical_id, the
    # first time one is actually referenced by a published release.
    taxonomy = {
        row["taxonomy_node_id"]: dict(row)
        for row in conn.execute(
            text("""
        SELECT taxonomy_node_id,node_type,name,description,proposed_by,
               coalesce(technique_id,skill_id,concept_id)::text AS id
        FROM pedagogy.taxonomy_node
    """)
        ).mappings()
    }
    projected_taxonomy_ids: set[str] = set()

    def taxonomy_target(key: str) -> dict:
        target = taxonomy[key]
        label = TAXONOMY_LABELS[target["node_type"]]
        if not target["id"]:
            target = target | {"id": key}
            if key not in projected_taxonomy_ids:
                projected_taxonomy_ids.add(key)
                nodes.append(
                    {
                        "label": label,
                        "id": key,
                        "properties": {
                            "canonical_id": key,
                            "name": target["name"],
                            "description": target["description"],
                            "node_type": target["node_type"],
                            "proposed_by": target["proposed_by"],
                            # Only referenced by requirements on an already-PUBLISHED
                            # release (see the releases query above), so this is an
                            # approved teaching artifact, not an unreviewed estimate.
                            "review_status": "REVIEWED",
                        },
                    }
                )
        return target | {"label": label}

    if not releases:
        return {"releases": releases, "nodes": nodes, "edges": edges}

    # Per-release queries (as route_runtime.load_program() does) do not scale past a
    # few hundred published releases: each one issues several round trips, so a few
    # thousand releases means tens of thousands of sequential Postgres calls. Fetch
    # every table ONCE across all published releases and group in Python instead.
    # instruction/hints are never read below, so solution_step_instruction and
    # route_step_hint (which load_program() also joins) are deliberately skipped.
    steps_by_release: dict[str, list[dict]] = {}
    for row in conn.execute(
        text("""
        SELECT s.route_release_id::text AS route_release_id,s.step_index,s.step_id::text AS step_id,
               s.depends_on,s.produces,s.uses_claims
        FROM pedagogy.route_step s
        JOIN pedagogy.solution_route_release r USING(route_release_id)
        WHERE r.status='PUBLISHED' ORDER BY s.route_release_id,s.step_index
    """)
    ).mappings():
        steps_by_release.setdefault(row["route_release_id"], []).append(dict(row))

    requirements_by_step: dict[tuple[str, int], list[dict]] = {}
    for row in conn.execute(
        text("""
        SELECT req.route_release_id::text AS route_release_id,req.step_index,req.taxonomy_node_id,
               req.role,req.required_level,req.importance::float8 AS importance,req.blocking
        FROM pedagogy.solution_step_requirement req
        JOIN pedagogy.solution_route_release r USING(route_release_id)
        WHERE r.status='PUBLISHED'
        ORDER BY req.route_release_id,req.step_index,req.taxonomy_node_id,req.role
    """)
    ).mappings():
        key = (row["route_release_id"], row["step_index"])
        requirements_by_step.setdefault(key, []).append(dict(row))

    links_by_step: dict[tuple[str, int], list[dict]] = {}
    for row in conn.execute(
        text("""
        SELECT l.route_release_id::text AS route_release_id,l.step_index,l.asset_key,l.role
        FROM pedagogy.route_asset_link l
        JOIN pedagogy.solution_route_release r USING(route_release_id)
        WHERE r.status='PUBLISHED'
        ORDER BY l.route_release_id,l.step_index,l.asset_key,l.role
    """)
    ).mappings():
        key = (row["route_release_id"], row["step_index"])
        links_by_step.setdefault(key, []).append(dict(row))

    assets_by_release: dict[str, list[dict]] = {}
    for row in conn.execute(
        text("""
        SELECT a.route_release_id::text AS route_release_id,a.asset_id::text AS asset_id,a.content
        FROM pedagogy.route_asset a
        JOIN pedagogy.solution_route_release r USING(route_release_id)
        WHERE r.status='PUBLISHED' ORDER BY a.route_release_id,a.asset_key
    """)
    ).mappings():
        assets_by_release.setdefault(row["route_release_id"], []).append(dict(row))

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
        step_rows = steps_by_release.get(rid, [])
        step_ids = {row["step_index"]: row["step_id"] for row in step_rows}
        asset_rows = assets_by_release.get(rid, [])
        asset_ids = {row["content"]["key"]: row["asset_id"] for row in asset_rows}
        assets = {row["content"]["key"]: row["content"] for row in asset_rows}
        for asset in assets.values():
            aid = asset_ids[asset["key"]]
            nodes.append(
                {
                    "id": aid,
                    "label": LABELS[asset["kind"]],
                    "properties": {
                        "canonical_id": aid,
                        "route_release_id": rid,
                        "asset_key": asset["key"],
                        "purpose": asset["purpose"],
                        "review_status": "REVIEWED",
                    },
                }
            )
            for key in asset["remediates"]:
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
            for key in asset["diagnoses"]:
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
            for key in asset["taxonomy_node_ids"]:
                target = taxonomy_target(key)
                if target["node_type"] == "TECHNIQUE" and asset["kind"] in {
                    "THEORY",
                    "LEARNING_ITEM",
                }:
                    edges.append(
                        {
                            "from": aid,
                            "from_label": LABELS[asset["kind"]],
                            "to": target["id"],
                            "to_label": "Technique",
                            "type": "EXPLAINS" if asset["kind"] == "THEORY" else "PRACTICES",
                            "properties": {},
                        }
                    )
        for row in step_rows:
            index = row["step_index"]
            sid = row["step_id"]
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
            for prior in row["depends_on"]:
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
            for relation, keys in (
                ("PRODUCES", row["produces"]),
                ("USES_CLAIM", row["uses_claims"]),
            ):
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
            for link in links_by_step.get((rid, index), []):
                edges.append(
                    {
                        "from": sid,
                        "from_label": "RouteStep",
                        "to": asset_ids[link["asset_key"]],
                        "to_label": LABELS[assets[link["asset_key"]]["kind"]],
                        "type": link["role"],
                        "properties": {},
                    }
                )
            for requirement in requirements_by_step.get((rid, index), []):
                target = taxonomy_target(requirement["taxonomy_node_id"])
                label = target["label"]
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
                        if requirement["role"] == "USED"
                        else "REQUIRES",
                        "properties": {
                            key: value
                            for key, value in requirement.items()
                            if key not in ("route_release_id", "step_index", "taxonomy_node_id")
                        },
                    }
                )
                if label == "Technique" and requirement["role"] == "USED":
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

        # A single transaction wrapping the whole delete+recreate does not fit this
        # instance's per-transaction memory budget once there are tens of thousands
        # of nodes/edges; commit per batch instead. This trades full all-or-nothing
        # atomicity for actually being able to run at this scale — an interrupted
        # run can leave a partially-replaced graph, which a subsequent project()
        # call fully repairs (delete-then-recreate is idempotent per entity).
        session.execute_write(
            lambda tx: tx.run(
                "MATCH ()-[r]->() WHERE r.projection_kind=$kind DELETE r", kind=KIND
            ).consume()
        )
        session.execute_write(
            lambda tx: tx.run(
                "MATCH (n) WHERE n.projection_kind=$kind DETACH DELETE n", kind=KIND
            ).consume()
        )

        nodes_by_label: dict[str, list[dict]] = {}
        for node in data["nodes"]:
            nodes_by_label.setdefault(node["label"], []).append(node)
        for label, items in nodes_by_label.items():
            for batch in _chunks(items, PROJECTION_BATCH_SIZE):
                rows = [{"id": item["id"], "properties": item["properties"]} for item in batch]

                def write_nodes(tx, label=label, rows=rows):
                    tx.run(
                        f"UNWIND $rows AS row "
                        f"MERGE (n:{label} {{canonical_id: row.id}}) "
                        "SET n += row.properties, n.projection_kind=$kind",
                        rows=rows,
                        kind=KIND,
                    ).consume()

                session.execute_write(write_nodes)

        edges_by_shape: dict[tuple[str, str, str], list[dict]] = {}
        for edge in data["edges"]:
            key = (edge["from_label"], edge["to_label"], edge["type"])
            edges_by_shape.setdefault(key, []).append(edge)
        for (from_label, to_label, rel_type), items in edges_by_shape.items():
            for batch in _chunks(items, PROJECTION_BATCH_SIZE):
                rows = [
                    {
                        "from_id": edge["from"],
                        "to_id": edge["to"],
                        "role": edge["properties"].get("role", ""),
                        # metadata() only ever processes PUBLISHED releases, so
                        # every edge it emits is an approved teaching artifact;
                        # the "Approved only" UI filter (mathbank-web
                        # app/api/graph/relationship/[rel]/route.js) checks
                        # r.review_status, which this is the only place it's set.
                        "properties": edge["properties"] | {"review_status": "REVIEWED"},
                    }
                    for edge in batch
                ]

                def write_edges(
                    tx, from_label=from_label, to_label=to_label, rel_type=rel_type, rows=rows
                ):
                    return tx.run(
                        "UNWIND $rows AS row "
                        f"MATCH (a:{from_label} {{canonical_id: row.from_id}}),"
                        f"(b:{to_label} {{canonical_id: row.to_id}}) "
                        f"MERGE (a)-[r:{rel_type} {{projection_kind:$kind,role:row.role}}]->(b) "
                        "SET r += row.properties RETURN count(*) AS written",
                        rows=rows,
                        kind=KIND,
                    ).single()

                result = session.execute_write(write_edges)
                if not result or result["written"] != len(batch):
                    raise ValueError(
                        "Graph endpoint is missing; refresh the corpus/taxonomy projection first."
                    )

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
