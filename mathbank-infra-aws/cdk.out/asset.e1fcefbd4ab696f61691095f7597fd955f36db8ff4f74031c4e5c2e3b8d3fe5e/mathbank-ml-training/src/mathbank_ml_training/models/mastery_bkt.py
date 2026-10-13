"""Mastery baseline model: BKT/Bayesian/EWMA (requirements/01 §5, requirements/55 §6).

Start here before anything deeper (DKT/transformers) — requirements/16's own rule:
"Only adopt deeper models when they materially beat strong baselines under held-out
student/time splits."
"""
from __future__ import annotations


class MasteryBaselineModel:
    """EWMA/Bayesian-Knowledge-Tracing-style mastery estimator.

    TODO (requirements/55 §6): implement. Suggested starting point: a per-(student,
    concept) exponentially-weighted moving average of no-hint correctness, with a
    separate BKT-style guess/slip/learn-rate model as a comparison baseline — train both,
    keep whichever one calibrates better on held-out data (requirements/13 §9
    "calibration" is a monitored metric, not an afterthought).
    """

    def train(self, dataset: dict) -> None:
        raise NotImplementedError("requirements/55 §6 — mastery baseline training")

    def predict(self, features: dict) -> float:
        raise NotImplementedError("requirements/55 §6 — mastery baseline inference")
