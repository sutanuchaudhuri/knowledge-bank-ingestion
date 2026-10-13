"""Per-student mastery/transfer/hint/recency feature group (requirements/03 §1 "student
mastery", requirements/55 §4 item 1 — highest priority, blocks the "recognition path"
half of the platform's stated purpose).

Every function returns a plain dict matching one `features_json` namespace inside
contracts.FeatureSnapshot — not yet a typed sub-model (TODO: promote to a typed
MasteryFeatureSet once the exact key set stabilizes against real data).
"""
from __future__ import annotations

from datetime import datetime


def compute_mastery_features(attempts: list[dict], *, as_of_time: datetime) -> dict:
    """Per Concept/Technique/Skill (requirements/03 §1):
    attempts_7/30/90d, weighted_accuracy, no_hint_accuracy, first_attempt_accuracy,
    transfer_accuracy, difficulty_adjusted_accuracy, recency, spacing, hint_dependence,
    response_time_percentile, misconception_confidence, misconception_slope,
    mastery_slope.

    TODO: start from the EWMA/Bayesian baseline (requirements/01 §5), not a deep model.
    Reuse mathbank-rest's existing `mastery.compute_mastery_score()` scoring logic as a
    reference implementation — it already solves a closely related problem (this
    session's own work confirmed it operates generically over `list[dict]` attempt rows
    regardless of source table), but this function's job is the full *feature* vector for
    training, not just a single mastery score for serving.
    """
    raise NotImplementedError("requirements/55 §4 item 1 — mastery features")


def classify_mastery_band(mastery_probability: float, *, transfer_accuracy: float,
                            hint_dependence: float, sample_size: int) -> str:
    """EXCELLENT / STRONG / DEVELOPING / SCRATCHY / WEAK / UNKNOWN per the explicit,
    non-subjective thresholds in requirements/03 §2 — copy those thresholds verbatim here
    once implemented, do not invent new ones.

    TODO: implement the exact threshold table from requirements/03 §2. Pay special
    attention to SCRATCHY's definition (high ordinary-practice accuracy BUT high
    transfer-accuracy drop / hint dependence / time instability) — it is intentionally
    different from WEAK and must not be collapsed into it.
    """
    raise NotImplementedError("requirements/55 §4 item 1 — mastery band classification")
