"""Problem/course/route content feature group (requirements/03 §1 "problem behavior",
"course/route"; requirements/55 §4 item 2).
"""
from __future__ import annotations


def compute_problem_features(problem_row: dict, *, historical_attempts: list[dict]) -> dict:
    """difficulty, contest_family, expected_time, topic/subtopic/technique,
    graph_prerequisite_depth, representation_embedding, historical_success_rate,
    discrimination_estimate, common_misconception_distribution (requirements/03 §1).

    TODO: `representation_embedding` should reuse the existing pgvector embeddings
    already computed by mathbank-rest/scripts/generate_similarity_embeddings.py — do not
    recompute embeddings in this package; read the existing vector column.
    """
    raise NotImplementedError("requirements/55 §4 item 2 — problem features")


def compute_course_features(course_row: dict, *, enrollment_history: list[dict]) -> dict:
    """target_nodes, prerequisite_nodes, estimated_duration, historic_completion,
    historic_post_course_lift, route_quality, interaction_density, assessment_density
    (requirements/03 §1).

    TODO: "historic_post_course_lift" needs a pre/post comparison — reuse the
    associative-language convention from requirements/08 §8 / contracts.InterventionEffect
    once this function actually computes it.
    """
    raise NotImplementedError("requirements/55 §4 item 2 — course features")
