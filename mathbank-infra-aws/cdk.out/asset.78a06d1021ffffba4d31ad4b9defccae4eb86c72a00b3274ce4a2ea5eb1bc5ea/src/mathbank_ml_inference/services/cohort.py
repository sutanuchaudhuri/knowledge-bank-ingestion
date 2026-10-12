"""Cohort clustering + course-effectiveness serving (requirements/08, requirements/58 §2,
requirements/56 §2).
"""
from __future__ import annotations

from mathbank_ml_inference.contracts import CohortClusterResponse, CourseEffectivenessResponse


def get_cohort_clusters() -> CohortClusterResponse:
    """TODO (requirements/58 §2): must refuse to serve a cluster set that hasn't passed
    every check in mathbank_ml_training.evaluation.cluster_validation (bootstrap
    stability, interpretability, minimum size, time-window consistency) — once those
    checks and this refusal logic both exist. Until then, this function should not
    return any real cluster data even once model loading is implemented.
    """
    raise NotImplementedError("requirements/56 §2 — GET /v1/admin/ml/cohorts/clusters")


def get_course_effectiveness(course_release_id: str) -> CourseEffectivenessResponse:
    """TODO (requirements/58 §2, requirements/08 §8): summary_text must use associative
    ("associated with"), never causal ("caused"), language unless the underlying design
    is a true randomized experiment."""
    raise NotImplementedError("requirements/56 §2 — GET /v1/admin/ml/course-effectiveness")
