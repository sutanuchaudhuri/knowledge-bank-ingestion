"""Scaffolded problem-solving endpoints — the agent-callable surface for Turn 3's
decompose/check flow (requirements/10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md
AGT-11). Both call a paid model, so they need a learner token or admin
credential and are rate limited per caller; they don't touch student state —
recording a hint/weakness still goes through the existing, authenticated
POST /v1/learner/attempts.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mathbank_rest import rate_limit, tutor

router = APIRouter(prefix="/v1/tutor", tags=["tutor"])


class DecomposeRequest(BaseModel):
    problem_code: str
    max_steps: int = Field(default=3, ge=1, le=5)


class CheckSubproblemRequest(BaseModel):
    subproblem_prompt: str
    student_answer: str


@router.post("/decompose")
def decompose(body: DecomposeRequest, caller: Annotated[rate_limit.Caller, Depends(rate_limit.require_paid_caller)]) -> dict:
    rate_limit.enforce(caller, "tutor")
    try:
        return tutor.decompose_problem(body.problem_code, body.max_steps)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/check-subproblem")
def check_subproblem(
    body: CheckSubproblemRequest, caller: Annotated[rate_limit.Caller, Depends(rate_limit.require_paid_caller)]
) -> dict:
    rate_limit.enforce(caller, "tutor")
    return tutor.check_subproblem_answer(body.subproblem_prompt, body.student_answer)
