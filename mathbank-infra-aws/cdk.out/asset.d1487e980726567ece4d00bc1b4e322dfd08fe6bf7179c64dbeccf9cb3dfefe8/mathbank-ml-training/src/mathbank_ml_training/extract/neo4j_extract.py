"""Structural graph reads from Neo4j (requirements/55 §2 EXTRACT stage).

requirements/01 §1: "Do not write learner-specific mastery/misconception edges to shared
Neo4j" — this module is read-only by design; it has no write/MERGE/CREATE function and
should never grow one. Learner-specific state belongs in Postgres `ml.*` tables
(contracts.FeatureSnapshot), not graph edges.

requirements/13 §2: "Use Neo4j snapshots/exports only for structural graph features. Do
not train from live mutable graph state without a recorded projection watermark." —
every function below takes a `projection_watermark` parameter for exactly this reason,
even though none of them use it yet (TODO: wire once mathbank-graph exposes one — check
whether project_from_postgres.py already records a watermark anywhere before inventing a
new one).
"""
from __future__ import annotations

from neo4j import GraphDatabase, Driver

from mathbank_ml_training.config import Settings


def get_driver(settings: Settings) -> Driver:
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_username, settings.neo4j_password)
    )


def extract_prerequisite_depth(driver: Driver, *, technique_id: str, projection_watermark: str | None = None) -> dict:
    """Graph-prerequisite-depth feature (requirements/03 §1 "problem behavior").

    TODO: implement a variable-length REQUIRES traversal, reusing the pattern already
    proven in mathbank-rest's `prerequisite_path` tool (see requirements/52's hybrid-RAG
    audit, which already documented this exact traversal) rather than writing a new one.
    """
    raise NotImplementedError("requirements/55 §2 EXTRACT stage — prerequisite depth")


def extract_similar_content(driver: Driver, *, entity_id: str, entity_type: str, top_k: int = 10) -> list[dict]:
    """SIMILAR_TO / structural-neighbor candidates for recommendation candidate
    generation (requirements/05, requirements/01 §5 "recommendation: rule + learning-to-
    rank hybrid").

    TODO: confirm with requirements/52 (hybrid RAG audit) which existing Neo4j
    relationship types are already populated before assuming SIMILAR_TO coverage is
    sufficient for candidate generation — do not assume without checking.
    """
    raise NotImplementedError("requirements/55 §2 EXTRACT stage — similar content")
