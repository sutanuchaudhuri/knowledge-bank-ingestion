"""Leakage checks (requirements/03 §4, requirements/55 §7).

Every one of these must pass before a DatasetManifest is considered valid
(datasets/manifest.py currently has no implementation gate for this yet — TODO: wire
`run_all_leakage_checks()` into `build_manifest()` once both exist).
"""
from __future__ import annotations


def check_no_future_attempts(features: list[dict], as_of_time_key: str = "as_of_time") -> bool:
    """TODO: implement. Assert no feature row's underlying attempt data has a timestamp
    after that row's own as_of_time (requirements/03 §4 rule 1)."""
    raise NotImplementedError("requirements/55 §7 — leakage check: future attempts")


def check_no_future_course_completion(features: list[dict], labels: list[dict]) -> bool:
    """TODO: implement (requirements/03 §4 rule 2)."""
    raise NotImplementedError("requirements/55 §7 — leakage check: future course completion")


def check_no_post_prediction_reveal(features: list[dict]) -> bool:
    """TODO: implement — no hint/solution reveal after the prediction timestamp
    (requirements/03 §4 rule 3)."""
    raise NotImplementedError("requirements/55 §7 — leakage check: post-prediction reveal")


def check_no_final_exam_leakage_into_early_questions(exam_sessions: list[dict]) -> bool:
    """TODO: implement — final exam result must never predict earlier question success
    within the same session (requirements/03 §4 rule 4)."""
    raise NotImplementedError("requirements/55 §7 — leakage check: final exam result")


def run_all_leakage_checks(features: list[dict], labels: list[dict]) -> dict[str, bool]:
    """TODO: implement once the four checks above exist. Returns a dict suitable for
    DatasetManifest.leakage_checks — {"check_name": passed_bool, ...}."""
    raise NotImplementedError("requirements/55 §7 — leakage check aggregation")
