"""requirements/53: student-authenticated AI-generated quiz endpoints.

All routes require a valid student bearer token (get_current_student_id) — a generated
quiz, its solutions, and a student's own responses are private to that student, same as
every other learner.* resource in this service.

WP6: every handler goes through ``stores.get_store("exam")`` (PostgreSQL or DynamoDB behind ``EXAM_STORE``). The student id is always
the verified token's, never a path or body value, so a foreign quiz id is simply a 404.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from mathbank_rest import stores
from mathbank_rest.quiz_logic import QuizError
from mathbank_rest.security import get_current_student_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/quiz", tags=["quiz"])
StudentId = Annotated[UUID, Depends(get_current_student_id)]


def _exam() -> Any:
    return stores.get_store("exam")


def _call(operation, *args: Any, **kwargs: Any) -> dict:
    try:
        return operation(*args, **kwargs)
    except QuizError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


class GenerateQuizRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: str = Field(min_length=1, max_length=20)
    question_count: int = Field(default=5, ge=1, le=20)
    question_types: list[str] = Field(default_factory=lambda: ["MCQ", "FREE_TEXT"])
    target_skill_slugs: list[str] = Field(default_factory=list, max_length=10)
    target_concept_slugs: list[str] = Field(default_factory=list, max_length=10)
    difficulty_band: str | None = Field(default=None, max_length=50)

    @field_validator("style")
    @classmethod
    def style_upper(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("question_types")
    @classmethod
    def types_upper(cls, value: list[str]) -> list[str]:
        return [v.strip().upper() for v in value]


@router.post("/generate")
def generate(body: GenerateQuizRequest, student_id: StudentId) -> dict:
    return _call(
        _exam().generate_quiz,
        student_id,
        style=body.style,
        question_count=body.question_count,
        question_types=body.question_types,
        target_skill_slugs=body.target_skill_slugs,
        target_concept_slugs=body.target_concept_slugs,
        difficulty_band=body.difficulty_band,
    )


@router.get("/mine")
def mine(student_id: StudentId) -> list[dict]:
    return _exam().list_my_quizzes(student_id)


@router.get("/{quiz_id}")
def get_quiz(quiz_id: UUID, student_id: StudentId) -> dict:
    return _call(_exam().get_quiz, quiz_id, student_id)


class SaveProgressRequest(BaseModel):
    """``SaveExamProgressRequest`` of the exam-agent router without ``student_id`` (it comes from the token)."""

    model_config = ConfigDict(extra="forbid")
    current_question_ordinal: int = Field(ge=1, le=20)
    question_id: UUID | None = None
    selected_key: str | None = Field(default=None, max_length=10)
    response_text: str | None = Field(default=None, max_length=10000)


@router.put("/{quiz_id}/progress")
def save_progress(quiz_id: UUID, body: SaveProgressRequest, student_id: StudentId) -> dict:
    """The learner's own save-progress (QUZ-E09): current position and an optional unsubmitted draft."""
    raw_response = {k: v for k, v in (
        ("selected_key", body.selected_key), ("response_text", body.response_text),
    ) if v is not None}
    return _call(
        _exam().save_exam_progress, quiz_id, student_id,
        current_question_ordinal=body.current_question_ordinal, question_id=body.question_id,
        raw_response=raw_response or None,
    )


class RespondRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_key: str | None = Field(default=None, max_length=10)
    response_text: str | None = Field(default=None, max_length=10000)
    time_spent_seconds: int | None = Field(default=None, ge=0, le=36000)


@router.post("/{quiz_id}/questions/{question_id}/respond")
def respond(quiz_id: UUID, question_id: UUID, body: RespondRequest, student_id: StudentId) -> dict:
    raw_response = {k: v for k, v in (
        ("selected_key", body.selected_key), ("response_text", body.response_text),
    ) if v is not None}
    if not raw_response:
        raise HTTPException(422, "supply selected_key (MCQ) or response_text (FREE_TEXT/PROOF)")
    return _call(
        _exam().submit_response, quiz_id, question_id, student_id,
        raw_response=raw_response, time_spent_seconds=body.time_spent_seconds,
    )


@router.get("/{quiz_id}/review")
def review(quiz_id: UUID, student_id: StudentId) -> dict:
    return _call(_exam().get_review, quiz_id, student_id)


@router.get("/{quiz_id}/diagnosis")
def diagnosis(quiz_id: UUID, student_id: StudentId) -> dict:
    """The learner's own read of the post-exam diagnosis (QUZ-E08): the latest version; 404 until one is written."""
    return _call(_exam().get_diagnosis, quiz_id, student_id)
