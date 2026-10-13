"""Data-readiness reporting (requirements/09, requirements/58 §3, requirements/56 §2)."""
from __future__ import annotations

from mathbank_ml_inference.contracts import DataReadinessResponse


def get_data_readiness(*, student_id: str | None, use_case: str) -> DataReadinessResponse:
    """TODO (requirements/56 §2): read the latest `ml.data_quality_issue` rows (written
    by mathbank-ml-training's jobs.data_readiness_scan, requirements/57 §2) for this
    student/use_case and assemble a DataReadinessResponse. Never auto-mutate canonical
    metadata from this read path (requirements/09 §6) — this function is read-only by
    construction, it has no write-capable DB handle."""
    raise NotImplementedError("requirements/56 §2 — GET /v1/ml/me/data-readiness and /v1/admin/ml/data-readiness")


def rank_missing_data_by_expected_value(*, scope: str) -> list[dict]:
    """requirements/09 §8's ranked admin "what data should improve?" page — arguably the
    single most directly-requested feature from this platform's original purpose ("guide
    admin to recalibrate... based on collected feedback"). Worked example from
    requirements/09 §8 (reproduce this shape once implemented):

        1. Add expected-time calibration to 312 AMC problems.
           Unlocks: pacing model, dynamic mock quality.
        2. Add transfer labels to 5 micro-courses.
           Unlocks: course-effectiveness ranking.
        3. Collect 3 more full mocks for this student.
           Unlocks: stable exam pacing/time-of-day recommendation.

    TODO: implement — rank open `ml.data_quality_issue` rows by estimated downstream
    model-quality impact, not just by count.
    """
    raise NotImplementedError("requirements/58 §3 — ranked data-readiness admin report")
