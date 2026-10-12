"""Calibrated success-probability model: logistic regression / gradient boosting
baseline (requirements/01 §5, requirements/55 §6)."""
from __future__ import annotations


class SuccessBaselineModel:
    """Calibrated (Platt scaling / isotonic) classifier for
    `problem_correct_without_reveal` (requirements/03 §3).

    TODO (requirements/55 §6): implement with scikit-learn `LogisticRegression` or
    `GradientBoostingClassifier` + `CalibratedClassifierCV`. Must report calibration
    curve + AUC/log-loss on held-out data (requirements/13 §9), not just accuracy.
    """

    def train(self, dataset: dict) -> None:
        raise NotImplementedError("requirements/55 §6 — success baseline training")

    def predict_proba(self, features: dict) -> float:
        raise NotImplementedError("requirements/55 §6 — success baseline inference")
