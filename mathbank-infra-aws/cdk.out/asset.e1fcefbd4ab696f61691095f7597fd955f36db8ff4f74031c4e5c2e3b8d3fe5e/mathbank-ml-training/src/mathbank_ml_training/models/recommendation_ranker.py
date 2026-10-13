"""Next-best problem/course ranker: candidate generation + learning-to-rank
(requirements/01 §5, requirements/55 §6)."""
from __future__ import annotations


class RecommendationRanker:
    """Rule-based candidate generation (prerequisite-satisfied, not-recently-seen,
    within-difficulty-band) followed by a learned ranker over "future utility"
    (requirements/03 §3: learning_gain + exam_relevance - excessive_time_cost -
    redundancy - frustration/abandonment_penalty).

    TODO (requirements/55 §6): implement candidate generation first (pure rules, no ML),
    then a learning-to-rank model (e.g. LightGBM ranker) over the candidate set. Every
    output must populate contracts.Explanation — do not return a bare ranked list.
    """

    def generate_candidates(self, student_features: dict, content_features: list[dict]) -> list[dict]:
        raise NotImplementedError("requirements/55 §6 — candidate generation")

    def rank(self, candidates: list[dict], student_features: dict) -> list[dict]:
        raise NotImplementedError("requirements/55 §6 — learning-to-rank")
