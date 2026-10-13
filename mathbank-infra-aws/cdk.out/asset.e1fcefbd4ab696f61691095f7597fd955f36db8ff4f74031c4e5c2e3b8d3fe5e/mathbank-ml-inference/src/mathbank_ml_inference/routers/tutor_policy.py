"""Tutor-policy status/scoring endpoints (requirements/56 §2, requirements/11,
requirements/14 §3/§8).
"""
from __future__ import annotations

from fastapi import APIRouter

from mathbank_ml_inference._stub_utils import call_stubbed
from mathbank_ml_inference.contracts import ScoreTutorActionsRequest
from mathbank_ml_inference.services import tutor_action

router = APIRouter(prefix="/v1/admin/ml/tutor-policy", tags=["admin-ml-tutor-policy"])


@router.get("")
def get_tutor_policy_status():
    return call_stubbed(
        tutor_action.get_policy_status,
        todo_ref="requirements/56 §2 GET /v1/admin/ml/tutor-policy",
        design_doc_ref="14_API_FASTMCP_ADMIN_STUDENT_UI.md §3",
    )


@router.post("/score-actions")
def post_score_actions(body: ScoreTutorActionsRequest):
    return call_stubbed(
        lambda: tutor_action.score_tutor_actions(body),
        todo_ref="requirements/56 §2 POST /v1/admin/ml/tutor-policy/score-actions",
        design_doc_ref="11_RL_BANDIT_AND_OFFLINE_POLICY.md §6",
    )
