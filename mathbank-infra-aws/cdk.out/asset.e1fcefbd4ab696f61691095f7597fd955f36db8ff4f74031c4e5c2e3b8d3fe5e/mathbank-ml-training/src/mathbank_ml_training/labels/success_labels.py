"""Success/time labels (requirements/03 §3 "Success model"/"Time model",
requirements/55 §5).
"""
from __future__ import annotations


def label_success_without_reveal(attempt: dict) -> bool:
    """`problem_correct_without_reveal` (requirements/03 §3) — true only if the student
    got the right answer without ever triggering a hint/solution reveal first.

    TODO: implement against the attempt row's hint_count/hint_levels and whatever
    "revealed" flag the source table uses (check `learner.attempt`, `quiz.response`,
    `learner.micro_course_state_event` — all three may have a slightly different
    "revealed" representation; normalize here, don't assume one shape).
    """
    raise NotImplementedError("requirements/55 §5 — success label")


def label_active_time_censored(attempt: dict) -> float | None:
    """`active_time_ms`, censored for abandonment (requirements/03 §3). Returns None
    (censored) rather than a misleadingly large number when the student abandoned the
    item without finishing.

    TODO: define "abandonment" precisely (e.g. no further event for N minutes, or an
    explicit navigate-away event) before implementing — an ad hoc threshold here would
    bias every downstream time-model training run.
    """
    raise NotImplementedError("requirements/55 §5 — time label")
