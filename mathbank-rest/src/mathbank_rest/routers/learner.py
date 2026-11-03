"""Student login + student state — register/login, attempts, mastery summary.

Per documentation/copilot-instructions/mathematics-tutor-db-plan/agent/18_future_student_profile_and_mastery.md and
requirements/10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md (MST-01..MST-08).
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from mathbank_rest import mastery, security, stores
from mathbank_rest.db import (
    learner as learner_db,  # noqa: F401  (tests patch the SQL layer through this module object)
)
from mathbank_rest.stores.errors import StoreFrozen, UniqueViolation

router = APIRouter(prefix="/v1/learner", tags=["learner"])

ACTIVITY_MAX_DAYS = 366
ACTIVITY_DEFAULT_DAYS = 30


def _store():
    return stores.get_store("learner")


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


class UpdateProfileRequest(BaseModel):
    """PATCH /v1/learner/me: only the fields that are sent change; e-mail and identity fields are not editable here."""

    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    grade: str | None = Field(default=None, max_length=50)
    phone: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def _only_optional_fields_clear(self) -> UpdateProfileRequest:
        for name in ("first_name", "last_name", "display_name"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be cleared")
        return self


class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)


class PracticeThemeProgress(BaseModel):
    kind: Literal["concept", "technique"]
    slug: str
    name: str
    available: int = Field(ge=0)
    attempted: int = Field(ge=0)
    remaining: int = Field(ge=0)


class PracticeProgressResponse(BaseModel):
    items: list[PracticeThemeProgress]


@router.get("/practice-progress", response_model=PracticeProgressResponse)
def get_practice_progress(
    student_id: Annotated[UUID, Depends(security.get_current_student_id)],
) -> dict:
    """Distinct available/attempted/unattempted problems per exact corpus theme.

    All recorded learner attempts count, including ungraded work. Coverage is
    not correctness or mastery. Technique eligibility matches the corpus filter.
    """
    return _store().get_practice_progress(student_id)


@router.post("/register", response_model=AuthResponse, status_code=201)
def register(body: RegisterRequest) -> AuthResponse:
    store = _store()
    taken = HTTPException(status_code=409, detail="an account with this email already exists")
    if store.get_student_by_email(body.email) is not None:
        raise taken
    password_hash = security.hash_password(body.password)
    try:
        student = store.create_student(
            email=body.email, password_hash=password_hash,
            first_name=body.first_name, last_name=body.last_name,
        )
    except UniqueViolation:
        raise taken from None
    token = security.create_access_token(student["student_id"])
    return AuthResponse(
        access_token=token, student_id=student["student_id"],
        first_name=student["first_name"], last_name=student["last_name"], display_name=student["display_name"],
    )


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest) -> AuthResponse:
    store = _store()
    student = store.get_student_by_email(body.email)
    # Same error for "no such user" and "wrong password" — do not leak which one it was.
    if student is None or not security.verify_password(body.password, student["password_hash"]):
        raise HTTPException(status_code=401, detail="invalid email or password")
    if student["status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail="account is not active")
    try:
        store.touch_last_login(student["student_id"])
    except StoreFrozen:
        pass                                    # a cutover freeze must not stop sign-in; only the last-login stamp is skipped
    token = security.create_access_token(student["student_id"], token_version=student.get("token_version"))
    return AuthResponse(
        access_token=token, student_id=student["student_id"],
        first_name=student["first_name"], last_name=student["last_name"], display_name=student["display_name"],
    )


@router.get("/me")
def get_me(student_id: UUID = Depends(security.get_current_student_id)) -> dict:
    profile = _store().get_student_profile(student_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="student not found")
    return profile


@router.patch("/me")
def update_me(body: UpdateProfileRequest, student_id: UUID = Depends(security.get_current_student_id)) -> dict:
    """Edit names, grade and phone (LRN-E06); the display name follows the names unless it is sent. Returns the profile."""
    changes = {k: v.strip() if isinstance(v, str) else v for k, v in body.model_dump(exclude_unset=True).items()}
    if any(v == "" for k, v in changes.items() if k in ("first_name", "last_name", "display_name")):
        raise HTTPException(status_code=422, detail="names cannot be blank")
    profile = _store().update_profile(student_id, changes)
    if profile is None:
        raise HTTPException(status_code=404, detail="student not found")
    return profile


@router.post("/me/password")
def change_my_password(body: ChangePasswordRequest, student_id: UUID = Depends(security.get_current_student_id)) -> dict:
    """Change the password of a password account (LRN-E07): needs the current password (403 when wrong), 409 for an account
    that signs in through its identity provider, 429 after 5 attempts in 15 minutes. Every older token stops working; the
    response carries a fresh one."""
    result = _store().change_password(student_id, current_password=body.current_password, new_password=body.new_password)
    security.invalidate_student_status(student_id)
    token = security.create_access_token(student_id, token_version=result["token_version"])
    return {"changed": True, "access_token": token, "token_type": "bearer"}


@router.post("/attempts", status_code=201)
def submit_attempt(
    body: AttemptRequest, student_id: UUID = Depends(security.get_current_student_id),
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=200)] = None,
) -> dict:
    store = _store()
    problem_id = store.get_problem_id_by_code(body.problem_code)
    if problem_id is None:
        raise HTTPException(status_code=404, detail=f"no problem with code {body.problem_code!r}")
    # The outcome and the mastery of every tag of the problem are recomputed synchronously and inline — attempt volume per
    # student is low (human solving math problems, not a firehose). DynamoDB commits both in one transaction.
    return store.record_outcome(
        student_id=student_id,
        problem_id=problem_id,
        is_correct=body.is_correct,
        submitted_answer=body.submitted_answer,
        time_spent_seconds=body.time_spent_seconds,
        hint_count=body.hint_count,
        source=body.source,
        idempotency_key=idempotency_key,
    )


@router.get("/attempts")
def get_attempts(
    limit: int = 50, offset: int = 0, student_id: UUID = Depends(security.get_current_student_id)
) -> list[dict]:
    return _store().list_attempts(student_id, limit=min(limit, 200), offset=max(offset, 0))


@router.get("/activity")
def get_activity(
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=ACTIVITY_MAX_DAYS)] = ACTIVITY_MAX_DAYS,
    offset: Annotated[int, Query(ge=0)] = 0,
    student_id: UUID = Depends(security.get_current_student_id),
) -> dict:
    """The caller's own daily engagement counters (ANL-E01): UTC days from `from` to `to` (default the last 30 days, at most
    366 days), oldest first, as `{items, total, limit, offset}`. Days without activity are absent."""
    end = date_to or datetime.now(UTC).date()
    start = date_from or end - timedelta(days=ACTIVITY_DEFAULT_DAYS - 1)
    if start > end:
        raise HTTPException(status_code=422, detail="`from` must not be after `to`")
    if (end - start).days >= ACTIVITY_MAX_DAYS:
        raise HTTPException(status_code=422, detail=f"the range is limited to {ACTIVITY_MAX_DAYS} days")
    rows = _store().list_daily_activity(student_id, start, end)
    return {"items": rows[offset:offset + limit], "total": len(rows), "limit": limit, "offset": offset}


@router.get("/mastery")
def get_mastery_summary(student_id: UUID = Depends(security.get_current_student_id)) -> dict:
    return _store().get_mastery_summary(student_id)


@router.get("/mastery/improvement-plan")
def get_improvement_plan(
    max_focus_areas: int = 5, student_id: UUID = Depends(security.get_current_student_id)
) -> dict:
    """Actionable 'what to improve next' view: weakest concepts/techniques
    (not yet 'solid'), each with a few recommended practice problems."""
    return mastery.build_improvement_plan(student_id, max_focus_areas=max_focus_areas)


def _learner_store():
    from mathbank_rest import stores

    return stores.get_store("learner")


@router.get("/route-attempts")
def list_route_attempts(
    student_id: Annotated[UUID, Depends(security.get_current_student_id)],
    route_release_id: UUID | None = None,
    status: Literal["IN_PROGRESS", "FINISHED", "ABANDONED"] | None = None,
    limit: int = 50,
    next_token: str | None = None,
) -> dict:
    """The learner's own route attempts, newest first (LRN-E13): ``{items, next_token}``."""
    return _learner_store().list_route_attempts(
        student_id, route_release_id=route_release_id, status=status,
        limit=max(1, min(limit, 200)), next_token=next_token)


@router.get("/feedback")
def list_my_feedback(
    student_id: Annotated[UUID, Depends(security.get_current_student_id)], limit: int = 50, next_token: str | None = None
) -> dict:
    """The learner's own retrieval reports with their review state (LRN-E14): ``{items, next_token}``."""
    return _learner_store().list_my_feedback(student_id, limit=max(1, min(limit, 200)), next_token=next_token)


@router.post("/feedback/{feedback_id}/withdraw")
def withdraw_feedback(feedback_id: UUID, student_id: Annotated[UUID, Depends(security.get_current_student_id)]) -> dict:
    """Withdraw an own PENDING report (it becomes DISMISSED); someone else's is 404, a reviewed one 409."""
    from mathbank_rest.step_runtime import RuntimeError_

    try:
        return _learner_store().withdraw_feedback(student_id, feedback_id)
    except RuntimeError_ as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from exc


@router.get("/micro-course-enrollments")
def list_my_micro_course_enrollments(
    status: Literal["IN_PROGRESS", "COMPLETED", "ABANDONED"] | None = None,
    limit: int = 100,
    student_id: UUID = Depends(security.get_current_student_id),
) -> dict:
    """The learner's own micro-course enrollments, newest first (LRN-E12): ``{items, total}``."""
    from mathbank_rest.routers.micro_courses import learner_call

    return learner_call("list_enrollments", str(student_id), status, max(1, min(limit, 200)))


@router.get("/misconceptions")
def list_my_misconceptions(student_id: UUID = Depends(security.get_current_student_id)) -> dict:
    """The learner's running confidence per misconception, strongest first (LRN-E20): ``{items, total}``."""
    from mathbank_rest.routers.micro_courses import learner_call

    return learner_call("list_misconceptions", str(student_id))


@router.get("/events")
def list_my_events(
    attempt_id: UUID | None = None,
    after: str | None = Query(None, max_length=64, description="ISO-8601 instant: only events after it, oldest first"),
    limit: int = Query(100, ge=1, le=500),
    next_token: str | None = Query(None, max_length=4000),
    student_id: UUID = Depends(security.get_current_student_id),
) -> dict:
    """The learner's own event feed (LRN-E01): newest first, or oldest first after the ``after`` instant, optionally for one
    attempt. ``{items, limit, next_token}``; the payload shows only what a learner may see (LRN-F01), never teacher evidence."""
    from mathbank_rest.step_logic import student_event_payload

    store = stores.get_store("learner")
    if after is not None:
        page = store.get_events_after(student_id, after, attempt_id=attempt_id, limit=limit, next_token=next_token, student_view=True)
    else:
        page = store.list_events_page(student_id, attempt_id=attempt_id, limit=limit, next_token=next_token, student_view=True)
    items = [{**e, "payload": student_event_payload(e["event_type"], e["payload"])} for e in page["items"]]
    return {**page, "items": items}


@router.get("/solve-attempts")
def list_my_solve_attempts(
    status: Literal["IN_PROGRESS", "SUBMITTED", "COMPLETED", "ABANDONED"] | None = None,
    limit: int = Query(50, ge=1, le=200),
    next_token: str | None = Query(None, max_length=4000),
    student_id: UUID = Depends(security.get_current_student_id),
) -> dict:
    """The learner's own step-by-step sessions, newest first (LRN-E10): ``{items, limit, next_token}``."""
    return stores.get_store("learner").list_solve_attempts(student_id, status, limit=limit, next_token=next_token)
