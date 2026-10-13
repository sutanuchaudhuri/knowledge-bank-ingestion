"""Admin-facing ML endpoints (requirements/56 §2, requirements/14 §3/§5/§6/§7)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from mathbank_ml_inference._stub_utils import call_stubbed
from mathbank_ml_inference.registry import model_loader
from mathbank_ml_inference.services import cohort, data_readiness, recommendation, student_state

router = APIRouter(prefix="/v1/admin/ml", tags=["admin-ml"])

# TODO (requirements/56): reuse mathbank-rest's `require_admin_api_key` auth pattern
# (same header scheme) once this service needs real admin auth — not wired yet.


@router.get("/students/{student_id}/profile")
def get_student_profile(student_id: str):
    return call_stubbed(
        lambda: student_state.get_student_state(student_id),
        todo_ref="requirements/56 §2 GET /v1/admin/ml/students/{id}/profile",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3/§5",
    )


@router.get("/students/{student_id}/recommendations")
def get_student_recommendations(student_id: str):
    return call_stubbed(
        lambda: recommendation.recommend_next(student_id, admin_detail=True),
        todo_ref="requirements/56 §2 GET /v1/admin/ml/students/{id}/recommendations",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3/§7",
    )


@router.get("/cohorts/clusters")
def get_cohort_clusters():
    return call_stubbed(
        cohort.get_cohort_clusters,
        todo_ref="requirements/56 §2 GET /v1/admin/ml/cohorts/clusters",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3/§6",
    )


@router.get("/course-effectiveness")
def get_course_effectiveness(course_release_id: str = Query(...)):
    return call_stubbed(
        lambda: cohort.get_course_effectiveness(course_release_id),
        todo_ref="requirements/56 §2 GET /v1/admin/ml/course-effectiveness",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3",
    )


@router.get("/data-readiness")
def get_data_readiness_admin(use_case: str = Query(...)):
    return call_stubbed(
        lambda: data_readiness.get_data_readiness(student_id=None, use_case=use_case),
        todo_ref="requirements/56 §2 GET /v1/admin/ml/data-readiness",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3, 09_DATA_READINESS_METADATA_GAPS.md §8",
    )


@router.get("/model-registry")
def get_model_registry():
    return call_stubbed(
        model_loader.list_registry,
        todo_ref="requirements/56 §2 GET /v1/admin/ml/model-registry",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3",
    )


@router.get("/training-runs")
def get_training_runs():
    return call_stubbed(
        model_loader.list_training_runs,
        todo_ref="requirements/56 §2 GET /v1/admin/ml/training-runs",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3",
    )
