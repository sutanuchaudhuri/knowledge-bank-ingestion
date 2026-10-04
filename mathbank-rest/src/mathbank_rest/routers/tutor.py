"""Scaffolded problem-solving endpoints — the agent-callable surface for Turn 3's
decompose/check flow (requirements/10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md
AGT-11). No auth required (same as /v1/search/problems) — these don't touch
student state; recording a hint/weakness still goes through the existing,
authenticated POST /v1/learner/attempts.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mathbank_rest import tutor

router = APIRouter(prefix="/v1/tutor", tags=["tutor"])


class DecomposeRequest(BaseModel):
    problem_code: str
    max_steps: int = Field(default=3, ge=1, le=5)


class CheckSubproblemRequest(BaseModel):
    subproblem_prompt: str
    student_answer: str


@router.post("/decompose")
def decompose(body: DecomposeRequest) -> dict:
    try:
        return tutor.decompose_problem(body.problem_code, body.max_steps)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/check-subproblem")
def check_subproblem(body: CheckSubproblemRequest) -> dict:
    return tutor.check_subproblem_answer(body.subproblem_prompt, body.student_answer)
