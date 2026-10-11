"""Cohort clustering: validated KMeans/HDBSCAN (requirements/01 §5, requirements/08,
requirements/55 §6, requirements/58 §2)."""
from __future__ import annotations

from mathbank_ml_training.contracts import CohortAssignment


class CohortClusteringModel:
    """Clusters students on normalized behavior/mastery features (requirements/08 §2's
    explicit feature list — no PII, no protected/sensitive demographic attributes).

    TODO (requirements/55 §6): implement PCA-for-visualization-only +
    KMeans-with-stability-checks as the first baseline, HDBSCAN for irregular
    clusters/noise as a comparison. Must pass requirements/08 §4's validation gate
    (bootstrap stability, interpretable feature differences, minimum cluster size, time-
    window consistency) — see evaluation/cluster_validation.py — before any assignment is
    ever returned to a caller.
    """

    def fit_predict(self, student_features: list[dict]) -> list[CohortAssignment]:
        raise NotImplementedError("requirements/55 §6 — cohort clustering")
