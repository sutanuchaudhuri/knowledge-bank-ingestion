"""Dataset manifest assembly (requirements/13 §3, requirements/55 §7)."""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from mathbank_ml_training.contracts import DatasetManifest


def build_manifest(*, feature_set_version: str, label_version: str,
                     source_watermarks: dict[str, str], student_cohort_query_hash: str,
                     content_release_filters: dict, time_window: tuple[datetime, datetime],
                     row_counts: dict[str, int], exclusion_counts: dict[str, int]) -> DatasetManifest:
    """Assembles a DatasetManifest. Does not yet compute `leakage_checks` or
    `schema_hash` (both TODO — see evaluation/leakage_checks.py for the former; the
    latter should hash the feature/label column schema, e.g. via a stable JSON-schema
    digest, once that schema stops changing on every commit).
    """
    raise NotImplementedError(
        "requirements/55 §7 — dataset manifest assembly; "
        "needs leakage_checks (evaluation/leakage_checks.py) and schema_hash first"
    )


def new_dataset_id() -> str:
    """Convenience — not itself a TODO, trivial enough to implement now."""
    return str(uuid4())
