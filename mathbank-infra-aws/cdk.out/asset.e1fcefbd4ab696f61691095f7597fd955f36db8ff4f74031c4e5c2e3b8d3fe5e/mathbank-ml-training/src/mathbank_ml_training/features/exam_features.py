"""Exam-session pacing/behavior feature group (requirements/03 §1 "exam behavior",
requirements/55 §4 item 3).

BLOCKED (requirements/55 §4): requires `learner.exam_session` /
`learner.exam_question_event` (requirements/02 §3) to have adequate per-question timing
coverage. Check requirements/58's data-readiness report for this use case before trusting
any output of this module — do not silently train a model on sparse timing data.
"""
from __future__ import annotations


def compute_exam_pacing_features(session: dict, question_events: list[dict]) -> dict:
    """early/mid/late_accuracy, skip_strategy, revisit_value, answer_change_value,
    time_spent_by_difficulty, time_spent_by_topic, end_of_exam_collapse,
    unanswered_count, careless_error_proxy, overinvestment_on_low_yield_questions
    (requirements/03 §1).

    TODO: do not implement until requirements/02 §3's exam-session/question-event tables
    are confirmed to exist with real per-question timestamps — this is the exact
    "without per-question timing, pacing recommendations will be weak" warning from
    requirements/02 §3's own text.
    """
    raise NotImplementedError(
        "requirements/55 §4 item 3 — exam pacing features (check data readiness first)"
    )
