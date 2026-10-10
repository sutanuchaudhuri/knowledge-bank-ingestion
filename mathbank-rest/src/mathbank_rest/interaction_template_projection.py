"""Deterministic, idempotent Neo4j projection for the interaction template
library (requirements/41_INTERACTION_TEMPLATE_LIBRARY.md ITL-14/15/16).

Only PUBLISHED template versions, approved instances/scenes/feedback/evidence
structures are projected; learner evidence and answer-bearing content are
never written to the shared graph. Projector-owned nodes/edges are tagged
projection_kind='interaction_template' and pruning only ever touches that
tag — this function must never delete canonical knowledge nodes or another
projector's content.
"""

from __future__ import annotations

from neo4j.exceptions import Neo4jError
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.config import settings
from mathbank_rest.db.graph import driver
from mathbank_rest.db.postgres import engine

KIND = "interaction_template"
BATCH_SIZE = 500
ADVISORY_LOCK_KEY = 390028


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def metadata(conn) -> dict:
    nodes, edges = [], []

    for row in conn.execute(
        text("""
        SELECT interaction_template_id::text AS id, template_key, interaction_family, status
        FROM visual.interaction_template
    """)
    ).mappings():
        nodes.append(
            {
                "label": "InteractionTemplate",
                "id": row["id"],
                "properties": {
                    "canonical_id": row["id"],
                    "template_key": row["template_key"],
                    "interaction_family": row["interaction_family"],
                    "status": row["status"],
                },
            }
        )

    published_versions = [
        dict(row)
        for row in conn.execute(
            text("""
        SELECT v.interaction_template_version_id::text AS id, v.interaction_template_id::text AS template_id,
               v.version, v.status
        FROM visual.interaction_template_version v WHERE v.status='PUBLISHED'
    """)
        ).mappings()
    ]
    published_version_ids = {row["id"] for row in published_versions}
    for row in published_versions:
        nodes.append(
            {
                "label": "InteractionTemplateVersion",
                "id": row["id"],
                "properties": {
                    "canonical_id": row["id"],
                    "version": row["version"],
                    "status": row["status"],
                },
            }
        )
        edges.append(
            {
                "from": row["template_id"],
                "from_label": "InteractionTemplate",
                "to": row["id"],
                "to_label": "InteractionTemplateVersion",
                "type": "HAS_VERSION",
                "properties": {},
            }
        )

    for row in conn.execute(
        text("SELECT control_key::text AS id, control_type, status FROM visual.control_template")
    ).mappings():
        nodes.append(
            {
                "label": "ControlTemplate",
                "id": row["id"],
                "properties": {
                    "canonical_id": row["id"],
                    "control_type": row["control_type"],
                    "status": row["status"],
                },
            }
        )
    for row in conn.execute(
        text(
            "SELECT token_key::text AS id, icon_class, accessible_label, status FROM visual.icon_token"
        )
    ).mappings():
        nodes.append(
            {
                "label": "IconToken",
                "id": row["id"],
                "properties": {
                    "canonical_id": row["id"],
                    "icon_class": row["icon_class"],
                    "accessible_label": row["accessible_label"],
                    "status": row["status"],
                },
            }
        )
    for row in conn.execute(
        text("SELECT animation_key::text AS id, status FROM visual.animation_template")
    ).mappings():
        nodes.append(
            {
                "label": "AnimationTemplate",
                "id": row["id"],
                "properties": {"canonical_id": row["id"], "status": row["status"]},
            }
        )

    scenes = {
        row["id"]: dict(row)
        for row in conn.execute(
            text("""
        SELECT scene_spec_id::text AS id, canonical_code, version, status
        FROM visual.scene_spec WHERE status='APPROVED'
    """)
        ).mappings()
    }
    for scene in scenes.values():
        nodes.append(
            {
                "label": "SceneSpec",
                "id": scene["id"],
                "properties": {
                    "canonical_id": scene["id"],
                    "canonical_code": scene["canonical_code"],
                    "version": scene["version"],
                },
            }
        )

    feedback_templates = {
        row["id"]: dict(row)
        for row in conn.execute(
            text("""
        SELECT feedback_template_id::text AS id, feedback_key, feedback_type
        FROM pedagogy.feedback_template WHERE review_status='APPROVED'
    """)
        ).mappings()
    }
    for row in feedback_templates.values():
        nodes.append(
            {
                "label": "FeedbackTemplate",
                "id": row["id"],
                "properties": {
                    "canonical_id": row["id"],
                    "feedback_key": row["feedback_key"],
                    "feedback_type": row["feedback_type"],
                },
            }
        )

    feedback_policies = {
        row["id"]: dict(row)
        for row in conn.execute(
            text("""
        SELECT feedback_policy_id::text AS id, policy_key, version
        FROM pedagogy.feedback_policy WHERE review_status='APPROVED'
    """)
        ).mappings()
    }
    for row in feedback_policies.values():
        nodes.append(
            {
                "label": "FeedbackPolicy",
                "id": row["id"],
                "properties": {
                    "canonical_id": row["id"],
                    "policy_key": row["policy_key"],
                    "version": row["version"],
                },
            }
        )

    # Only instances bound to a PUBLISHED template version and themselves APPROVED.
    instances = [
        dict(row)
        for row in conn.execute(
            text("""
        SELECT i.interaction_instance_id::text AS id, i.canonical_code, i.title,
               i.interaction_template_version_id::text AS version_id,
               i.feedback_policy_id::text AS feedback_policy_id, i.scene_spec_id::text AS scene_spec_id
        FROM visual.interaction_instance i
        JOIN visual.interaction_template_version v USING (interaction_template_version_id)
        WHERE i.review_status='APPROVED' AND v.status='PUBLISHED'
    """)
        ).mappings()
    ]
    for row in instances:
        nodes.append(
            {
                "label": "InteractionInstance",
                "id": row["id"],
                "properties": {
                    "canonical_id": row["id"],
                    "canonical_code": row["canonical_code"],
                    "title": row["title"],
                },
            }
        )
        edges.append(
            {
                "from": row["id"],
                "from_label": "InteractionInstance",
                "to": row["version_id"],
                "to_label": "InteractionTemplateVersion",
                "type": "USES_TEMPLATE_VERSION",
                "properties": {},
            }
        )
        if row["feedback_policy_id"] and row["feedback_policy_id"] in feedback_policies:
            edges.append(
                {
                    "from": row["id"],
                    "from_label": "InteractionInstance",
                    "to": row["feedback_policy_id"],
                    "to_label": "FeedbackPolicy",
                    "type": "USES_FEEDBACK_POLICY",
                    "properties": {},
                }
            )
        if row["scene_spec_id"] and row["scene_spec_id"] in scenes:
            edges.append(
                {
                    "from": row["id"],
                    "from_label": "InteractionInstance",
                    "to": row["scene_spec_id"],
                    "to_label": "SceneSpec",
                    "type": "USES_SCENE",
                    "properties": {},
                }
            )

    instance_ids = {row["id"] for row in instances}
    role_edge = {
        "TEACHES": "TEACHES",
        "REQUIRES": "REQUIRES",
        "PRACTICES": "PRACTICES",
        "ASSESSES": "ASSESSES",
        "CAN_REVEAL": "CAN_REVEAL",
        "REMEDIATES": "REMEDIATES",
    }
    for target_label, table, target_col in (
        ("Concept", "interaction_instance_concept", "concept_id"),
        ("Technique", "interaction_instance_technique", "technique_id"),
        ("Skill", "interaction_instance_skill", "skill_id"),
        ("Misconception", "interaction_instance_misconception", "misconception_id"),
    ):
        for row in conn.execute(
            text(f"""
            SELECT interaction_instance_id::text AS iid, {target_col}::text AS tid, role
            FROM visual.{table}
        """)
        ).mappings():
            if row["iid"] not in instance_ids:
                continue
            edges.append(
                {
                    "from": row["iid"],
                    "from_label": "InteractionInstance",
                    "to": row["tid"],
                    "to_label": target_label,
                    "type": role_edge[row["role"]],
                    "properties": {},
                }
            )

    # SceneSpec-[:EXPLAINS]->Concept/Technique and -[:USES_ANIMATION]-> are authored
    # per-scene content not yet modeled by a join table; left as a documented gap
    # until SceneSpec authoring tooling exists (see requirements/41 open items).

    for row in conn.execute(
        text("""
        SELECT evidence_rule_id::text AS id, misconception_id::text AS misconception_id,
               interaction_template_version_id::text AS version_id, diagnostic_learning_item_id,
               feedback_template_id::text AS feedback_template_id
        FROM pedagogy.misconception_evidence_rule WHERE review_status='APPROVED'
    """)
    ).mappings():
        nodes.append(
            {"label": "EvidenceRule", "id": row["id"], "properties": {"canonical_id": row["id"]}}
        )
        if row["version_id"] in published_version_ids:
            edges.append(
                {
                    "from": row["id"],
                    "from_label": "EvidenceRule",
                    "to": row["version_id"],
                    "to_label": "InteractionTemplateVersion",
                    "type": "APPLIES_TO",
                    "properties": {},
                }
            )
        edges.append(
            {
                "from": row["id"],
                "from_label": "EvidenceRule",
                "to": row["misconception_id"],
                "to_label": "Misconception",
                "type": "EVIDENCE_FOR",
                "properties": {},
            }
        )
        if row["diagnostic_learning_item_id"]:
            edges.append(
                {
                    "from": row["id"],
                    "from_label": "EvidenceRule",
                    "to": row["diagnostic_learning_item_id"],
                    "to_label": "LearningItem",
                    "type": "USES_DIAGNOSTIC",
                    "properties": {},
                }
            )
        if row["feedback_template_id"] and row["feedback_template_id"] in feedback_templates:
            edges.append(
                {
                    "from": row["id"],
                    "from_label": "EvidenceRule",
                    "to": row["feedback_template_id"],
                    "to_label": "FeedbackTemplate",
                    "type": "USES_FEEDBACK",
                    "properties": {},
                }
            )

    return {"nodes": nodes, "edges": edges}


def _project() -> dict:
    with engine.connect() as conn:
        data = metadata(conn)
    with driver.session(database=settings.neo4j_database) as session:
        for label in (
            "InteractionTemplate",
            "InteractionTemplateVersion",
            "ControlTemplate",
            "IconToken",
            "AnimationTemplate",
            "SceneSpec",
            "FeedbackTemplate",
            "FeedbackPolicy",
            "EvidenceRule",
            "InteractionInstance",
        ):
            session.run(
                f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS FOR (n:{label}) REQUIRE n.canonical_id IS UNIQUE"
            ).consume()

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
            for batch in _chunks(items, BATCH_SIZE):
                rows = [{"id": item["id"], "properties": item["properties"]} for item in batch]

                def write_nodes(tx, label=label, rows=rows):
                    tx.run(
                        f"UNWIND $rows AS row MERGE (n:{label} {{canonical_id: row.id}}) "
                        "SET n += row.properties, n.projection_kind=$kind",
                        rows=rows,
                        kind=KIND,
                    ).consume()

                session.execute_write(write_nodes)

        edges_by_shape: dict[tuple[str, str, str], list[dict]] = {}
        for edge in data["edges"]:
            key = (edge["from_label"], edge["to_label"], edge["type"])
            edges_by_shape.setdefault(key, []).append(edge)
        missing_targets = []
        for (from_label, to_label, rel_type), items in edges_by_shape.items():
            for batch in _chunks(items, BATCH_SIZE):
                rows = [
                    {"from_id": e["from"], "to_id": e["to"], "properties": e["properties"]}
                    for e in batch
                ]

                def write_edges(
                    tx, from_label=from_label, to_label=to_label, rel_type=rel_type, rows=rows
                ):
                    return tx.run(
                        "UNWIND $rows AS row "
                        f"MATCH (a:{from_label} {{canonical_id: row.from_id}}),(b:{to_label} {{canonical_id: row.to_id}}) "
                        f"MERGE (a)-[r:{rel_type} {{projection_kind:$kind}}]->(b) SET r += row.properties "
                        "RETURN count(*) AS written",
                        rows=rows,
                        kind=KIND,
                    ).single()

                result = session.execute_write(write_edges)
                if not result or result["written"] != len(batch):
                    missing_targets.append(
                        (
                            from_label,
                            to_label,
                            rel_type,
                            len(batch) - (result["written"] if result else 0),
                        )
                    )
        if missing_targets:
            raise ValueError(f"Graph endpoints missing for edges: {missing_targets}")

        count = session.run(
            "MATCH (n) WHERE n.projection_kind=$kind RETURN count(n) AS c", kind=KIND
        ).single()["c"]
        edge_count = session.run(
            "MATCH ()-[r]->() WHERE r.projection_kind=$kind RETURN count(r) AS c", kind=KIND
        ).single()["c"]
    return {"status": "COMPLETED", "nodes": count, "edges": edge_count}


def project() -> dict:
    direct = create_engine(engine.url.set(host=(engine.url.host or "").replace("-pooler.", ".")))
    try:
        with direct.connect() as lease:
            acquired = lease.execute(
                text("SELECT pg_try_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY}
            ).scalar_one()
            lease.commit()
            if not acquired:
                raise ValueError("An interaction-template projection is already running.")
            with engine.begin() as conn:
                run = conn.execute(
                    text("""
                    INSERT INTO pipeline.graph_projection(graph_name,status)
                    VALUES ('interaction_templates','IN_PROGRESS') RETURNING projection_run_id
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
                lease.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})
                lease.commit()
    finally:
        direct.dispose()


def verify() -> dict:
    """Compares Postgres-expected structure vs. Neo4j-actual (ITL-16)."""
    with engine.connect() as conn:
        expected = metadata(conn)
    expected_nodes = {(n["label"], n["id"]) for n in expected["nodes"]}
    expected_edges = {
        (e["from_label"], e["from"], e["type"], e["to_label"], e["to"]) for e in expected["edges"]
    }
    with driver.session(database=settings.neo4j_database) as session:
        actual_nodes = {
            (row["label"], row["id"])
            for row in session.run(
                "MATCH (n) WHERE n.projection_kind=$kind RETURN labels(n)[0] AS label, n.canonical_id AS id",
                kind=KIND,
            )
        }
        actual_edges = set()
        for row in session.run(
            """
            MATCH (a)-[r]->(b) WHERE r.projection_kind=$kind
            RETURN labels(a)[0] AS from_label, a.canonical_id AS from_id, type(r) AS type,
                   labels(b)[0] AS to_label, b.canonical_id AS to_id
            """,
            kind=KIND,
        ):
            actual_edges.add(
                (row["from_label"], row["from_id"], row["type"], row["to_label"], row["to_id"])
            )
    return {
        "missing_nodes": sorted(str(n) for n in expected_nodes - actual_nodes),
        "stale_nodes": sorted(str(n) for n in actual_nodes - expected_nodes),
        "missing_edges": sorted(str(e) for e in expected_edges - actual_edges),
        "stale_edges": sorted(str(e) for e in actual_edges - expected_edges),
    }
