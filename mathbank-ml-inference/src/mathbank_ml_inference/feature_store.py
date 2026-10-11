"""Thin feature-store read layer on top of db.py — the single place `services/*.py`
should go to fetch a student's current feature snapshot, never `db.py` directly, so the
cache-then-db fallback (requirements/56 §5) lives in exactly one place.
"""
from __future__ import annotations

from sqlalchemy.engine import Engine

from mathbank_ml_inference import cache, db


def get_student_features(engine: Engine, *, student_id: str, feature_set_version: str) -> dict | None:
    """TODO (requirements/56 §5): check cache first (cache.get), fall back to
    db.get_latest_feature_snapshot, then cache.set the result. Not implemented — both
    halves of this it depends on (db.py, cache.py) are themselves stubs."""
    raise NotImplementedError("requirements/56 — feature store read")
