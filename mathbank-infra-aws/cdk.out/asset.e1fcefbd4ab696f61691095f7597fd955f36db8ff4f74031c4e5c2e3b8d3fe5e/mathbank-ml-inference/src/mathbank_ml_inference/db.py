"""Read-only Postgres access for mathbank-ml-inference (requirements/01 §4, requirements/56 §1).

Deliberately does NOT expose a generic "run arbitrary query" helper — every function here
is a named, narrow read against a specific `ml.*` feature-snapshot table, so no endpoint
can accidentally fall back to a live OLTP join (requirements/01 §4's explicit anti-pattern:
"recommendation request -> 19 joins across raw event tables -> ...").
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from mathbank_ml_inference.config import Settings


def get_engine(settings: Settings) -> Engine:
    url = (
        f"postgresql+psycopg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )
    return create_engine(url, pool_pre_ping=True)


def get_latest_feature_snapshot(engine: Engine, *, student_id: str, feature_set_version: str) -> dict | None:
    """TODO (requirements/56 §1): SELECT the most recent `ml.feature_snapshot` row for
    this student/feature_set_version. Returns None (not a 404 itself — the caller decides
    how to represent "no snapshot yet", likely as data_sufficiency=NOT_READY) if nothing
    exists."""
    raise NotImplementedError("requirements/56 §1 — feature snapshot read")


def get_content_feature_snapshot(engine: Engine, *, entity_type: str, entity_id: str) -> dict | None:
    """TODO (requirements/56 §1): SELECT from `ml.content_feature_snapshot`."""
    raise NotImplementedError("requirements/56 §1 — content feature snapshot read")
