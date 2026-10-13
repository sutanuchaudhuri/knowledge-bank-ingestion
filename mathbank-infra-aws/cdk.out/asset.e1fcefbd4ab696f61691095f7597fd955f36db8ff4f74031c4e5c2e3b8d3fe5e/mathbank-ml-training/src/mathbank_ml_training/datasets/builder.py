"""Dataset assembly and time/student splits (requirements/03 §4, requirements/55 §2 SPLIT
stage).

requirements/03 §4: "Training split should be by time and preferably by student: train
earlier periods, validation later, test latest held-out, additional cold-student/
cold-problem tests." This is the single most important leakage-avoidance rule in the
whole platform — every model-training notebook must go through this function, not
`sklearn.model_selection.train_test_split` with a random shuffle.
"""
from __future__ import annotations

from datetime import datetime


def time_and_student_split(rows: list[dict], *, train_end: datetime, validation_end: datetime,
                             test_end: datetime, timestamp_key: str = "as_of_time",
                             student_key: str = "student_id") -> dict[str, list[dict]]:
    """Splits `rows` into train/validation/test by time boundary, and additionally
    carves out a cold-student and cold-problem held-out set (requirements/03 §4's
    "additional cold-student/cold-problem tests").

    TODO: implement. Return shape should be
    `{"train": [...], "validation": [...], "test": [...], "cold_student_test": [...],
    "cold_problem_test": [...]}` — do not return a bare tuple, the named dict keeps every
    call site self-documenting.
    """
    raise NotImplementedError("requirements/55 §2 SPLIT stage")


def build_training_dataset(features: list[dict], labels: list[dict]) -> list[dict]:
    """Joins feature rows to label rows by (student_id, entity_id, as_of_time) — a plain
    inner join, but written here as its own function so leakage audits have one place to
    check the join key logic.

    TODO: implement. Must assert zero rows where the label's outcome timestamp precedes
    the feature's as_of_time (that would be look-ahead, not leakage in the other
    direction — assert this explicitly, don't just trust the join).
    """
    raise NotImplementedError("requirements/55 §2 — dataset build / feature-label join")
