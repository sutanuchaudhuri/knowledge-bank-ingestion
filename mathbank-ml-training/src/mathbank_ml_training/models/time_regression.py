"""Response-time model: robust/survival-style regression (requirements/01 §5,
requirements/55 §6)."""
from __future__ import annotations


class TimeBaselineModel:
    """Predicts active response time, respecting censored (abandoned) observations
    (requirements/03 §3 "Time model").

    TODO (requirements/55 §6): a plain regression on uncensored data will be biased —
    use a survival-analysis-style approach (e.g. accelerated failure time model) or at
    minimum explicitly exclude/flag censored rows rather than treating an abandonment as
    "a very long completion time."
    """

    def train(self, dataset: dict) -> None:
        raise NotImplementedError("requirements/55 §6 — time baseline training")

    def predict(self, features: dict) -> float:
        raise NotImplementedError("requirements/55 §6 — time baseline inference")
