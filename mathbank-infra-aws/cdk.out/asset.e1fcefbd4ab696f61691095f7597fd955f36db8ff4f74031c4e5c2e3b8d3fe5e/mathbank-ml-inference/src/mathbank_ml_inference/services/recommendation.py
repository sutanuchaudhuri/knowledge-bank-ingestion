"""Next-best recommendation serving (requirements/14 §2 `GET /v1/ml/me/recommendations`,
requirements/56 §2).
"""
from __future__ import annotations

from mathbank_ml_inference.contracts import RecommendationsResponse


def recommend_next(student_id: str, *, admin_detail: bool = False) -> RecommendationsResponse:
    """TODO (requirements/56): load the approved recommendation_ranker model
    (registry.model_loader.load_approved_model("recommendation_ranker")), score
    candidates from the student's feature snapshot, and return ranked items. When
    `admin_detail=True` (admin caller, requirements/14 §7), the explanation should
    include the fuller "top reasons" breakdown shown in requirements/14 §7's worked
    example rather than the shorter student-facing wording from requirements/14's §4
    wireframe — same underlying data, different verbosity, not two different models.
    """
    raise NotImplementedError("requirements/56 §2 — GET /v1/ml/me/recommendations")
