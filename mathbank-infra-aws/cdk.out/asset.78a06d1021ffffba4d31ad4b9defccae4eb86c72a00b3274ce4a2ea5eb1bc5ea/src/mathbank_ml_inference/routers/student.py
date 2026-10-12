"""Student-facing ML endpoints (requirements/56 §2, requirements/14 §2).

Every route calls its service function inside `_not_implemented_yet()` (see
`mathbank_ml_inference.main`), which converts a `NotImplementedError` into a structured
`501` body (`contracts.MLUnavailable`) instead of a bare 500 — so a partial frontend
integration can already render a "coming soon" EmptyState.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from mathbank_ml_inference._stub_utils import call_stubbed
from mathbank_ml_inference.services import data_readiness, exam_strategy, recommendation, student_state
from mathbank_ml_inference.contracts import GeneratedExamRequest

router = APIRouter(prefix="/v1/ml/me", tags=["student-ml"])

# TODO (requirements/56): replace this placeholder with the real student-auth dependency
# once this service needs to verify a student JWT — reuse mathbank-rest's
# `get_current_student_id` pattern (same cookie/JWT scheme) rather than inventing a new
# auth mechanism for this service.


def get_current_student_id_stub() -> str:
    raise NotImplementedError("requirements/56 — student auth not wired yet")


@router.get("/state")
def get_state(student_id: str = Depends(get_current_student_id_stub)):
    return call_stubbed(
        lambda: student_state.get_student_state(student_id),
        todo_ref="requirements/56 §2 GET /v1/ml/me/state",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §2",
    )


@router.get("/recommendations")
def get_recommendations(student_id: str = Depends(get_current_student_id_stub)):
    return call_stubbed(
        lambda: recommendation.recommend_next(student_id),
        todo_ref="requirements/56 §2 GET /v1/ml/me/recommendations",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §2",
    )


@router.get("/exam-strategy")
def get_exam_strategy(exam_family: str = Query(...), student_id: str = Depends(get_current_student_id_stub)):
    return call_stubbed(
        lambda: exam_strategy.recommend_exam_strategy(student_id, exam_family=exam_family),
        todo_ref="requirements/56 §2 GET /v1/ml/me/exam-strategy",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §2",
    )


@router.post("/generated-exams")
def post_generated_exam(body: GeneratedExamRequest, student_id: str = Depends(get_current_student_id_stub)):
    return call_stubbed(
        lambda: exam_strategy.generate_exam_plan(
            student_id, exam_family=body.exam_family, target_length=body.target_length
        ),
        todo_ref="requirements/56 §2 POST /v1/ml/me/generated-exams",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §2",
    )


@router.get("/misconception-trends")
def get_misconception_trends(student_id: str = Depends(get_current_student_id_stub)):
    return call_stubbed(
        lambda: student_state.get_misconception_trend(student_id),
        todo_ref="requirements/56 §2 GET /v1/ml/me/misconception-trends",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §2",
    )


@router.get("/data-readiness")
def get_data_readiness_for_me(use_case: str = Query(...), student_id: str = Depends(get_current_student_id_stub)):
    return call_stubbed(
        lambda: data_readiness.get_data_readiness(student_id=student_id, use_case=use_case),
        todo_ref="requirements/56 §2 GET /v1/ml/me/data-readiness",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §2",
    )
