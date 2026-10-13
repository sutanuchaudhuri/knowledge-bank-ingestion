"""Student learning-profile state (requirements/14 §2 `GET /v1/ml/me/state`,
requirements/56 §2).
"""
from __future__ import annotations

from mathbank_ml_inference.contracts import StudentStateResponse


def get_student_state(student_id: str) -> StudentStateResponse:
    """TODO (requirements/56): read the student's latest feature snapshot
    (feature_store.get_student_features), classify mastery bands per concept/domain
    using mathbank_ml_training.features.mastery_features.classify_mastery_band's logic
    (once implemented), and assemble the misconception trend series. Must always
    populate `explanation` (requirements/01 §7) even in a degraded/NOT_READY state.
    """
    raise NotImplementedError("requirements/56 §2 — GET /v1/ml/me/state")


def get_misconception_trend(student_id: str) -> dict:
    """Backs `GET /v1/ml/me/misconception-trends` (requirements/56 §2). TODO: implement."""
    raise NotImplementedError("requirements/56 §2 — GET /v1/ml/me/misconception-trends")
