"""Exam readiness/pacing/dynamic-exam-plan serving (requirements/14 §2, requirements/56 §2)."""
from __future__ import annotations

from mathbank_ml_inference.contracts import ExamStrategyResponse, GeneratedExamResponse


def recommend_exam_strategy(student_id: str, *, exam_family: str) -> ExamStrategyResponse:
    """TODO (requirements/56): load the approved exam_pacing model, score the student's
    exam features. BLOCKED on requirements/55 §4 item 3's data-readiness gate for exam
    timing data — check data_sufficiency before returning a confident prediction."""
    raise NotImplementedError("requirements/56 §2 — GET /v1/ml/me/exam-strategy")


def generate_exam_plan(student_id: str, *, exam_family: str, target_length: int) -> GeneratedExamResponse:
    """TODO (requirements/56, requirements/57): calls the nightly dynamic-exam-assembly
    CP-SAT/ILP optimizer's *output* (a pre-computed candidate set), does not run the
    optimizer inline in a request (requirements/13 §7 latency budget for "dynamic exam
    assembly" allows seconds, not request-blocking optimization from scratch every time —
    TODO: confirm whether the optimizer really needs to be precomputed nightly vs.
    acceptable to run synchronously; doc 07 was not read in full detail in this pass,
    revisit before finalizing)."""
    raise NotImplementedError("requirements/56 §2 — POST /v1/ml/me/generated-exams")
