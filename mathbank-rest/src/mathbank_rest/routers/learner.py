"""Student login + student state — register/login, attempts, mastery summary.

Per mathematics_tutor_db_plan/agent/18_future_student_profile_and_mastery.md and
requirements/10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md (MST-01..MST-08).
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from mathbank_rest import mastery, security
from mathbank_rest.db import learner as learner_db

router = APIRouter(prefix="/v1/learner", tags=["learner"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student_id: UUID
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None


class AttemptRequest(BaseModel):
    problem_code: str = Field(description="core.problem.canonical_code, e.g. AIME_1983_Q01")
    is_correct: bool
    submitted_answer: str | None = None
    time_spent_seconds: int | None = Field(default=None, ge=0)
    hint_count: int = Field(default=0, ge=0)
    source: str = "web"


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest) -> AuthResponse:
    if learner_db.get_student_by_email(body.email) is not None:
        raise HTTPException(status_code=409, detail="an account with this email already exists")
    password_hash = security.hash_password(body.password)
    student = learner_db.create_student(
        email=body.email, password_hash=password_hash,
        first_name=body.first_name, last_name=body.last_name,
    )
    token = security.create_access_token(student["student_id"])
    return AuthResponse(
        access_token=token, student_id=student["student_id"],
        first_name=student["first_name"], last_name=student["last_name"], display_name=student["display_name"],
    )


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest) -> AuthResponse:
    student = learner_db.get_student_by_email(body.email)
    # Same error for "no such user" and "wrong password" — do not leak which one it was.
    if student is None or not security.verify_password(body.password, student["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")
    if student["status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail="account is not active")
    learner_db.touch_last_login(student["student_id"])
    token = security.create_access_token(student["student_id"])
    return AuthResponse(
        access_token=token, student_id=student["student_id"],
        first_name=student["first_name"], last_name=student["last_name"], display_name=student["display_name"],
    )


@router.get("/me")
def get_me(student_id: UUID = Depends(security.get_current_student_id)) -> dict:
    profile = learner_db.get_student_profile(student_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="student not found")
    return profile


@router.post("/attempts", status_code=201)
def submit_attempt(
    body: AttemptRequest, student_id: UUID = Depends(security.get_current_student_id)
) -> dict:
    problem_id = learner_db.get_problem_id_by_code(body.problem_code)
    if problem_id is None:
        raise HTTPException(status_code=404, detail=f"no problem with code {body.problem_code!r}")
    attempt = learner_db.insert_attempt(
        student_id=student_id,
        problem_id=problem_id,
        is_correct=body.is_correct,
        submitted_answer=body.submitted_answer,
        time_spent_seconds=body.time_spent_seconds,
        hint_count=body.hint_count,
        source=body.source,
    )
    # Recompute mastery synchronously and inline — attempt volume per student is
    # low (human solving math problems, not a firehose), so there is no need for
    # an async queue yet. Revisit if/when bulk "import past attempts" lands.
    updated_mastery = mastery.recompute_mastery_for_problem(student_id, problem_id)
    return {"attempt": attempt, "updated_mastery": updated_mastery}


@router.get("/attempts")
def get_attempts(
    limit: int = 50, offset: int = 0, student_id: UUID = Depends(security.get_current_student_id)
) -> list[dict]:
    return learner_db.list_attempts(student_id, limit=min(limit, 200), offset=max(offset, 0))


@router.get("/mastery")
def get_mastery_summary(student_id: UUID = Depends(security.get_current_student_id)) -> dict:
    return learner_db.get_mastery_summary(student_id)


@router.get("/mastery/improvement-plan")
def get_improvement_plan(
    max_focus_areas: int = 5, student_id: UUID = Depends(security.get_current_student_id)
) -> dict:
    """Actionable 'what to improve next' view: weakest concepts/techniques
    (not yet 'solid'), each with a few recommended practice problems."""
    return mastery.build_improvement_plan(student_id, max_focus_areas=max_focus_areas)
