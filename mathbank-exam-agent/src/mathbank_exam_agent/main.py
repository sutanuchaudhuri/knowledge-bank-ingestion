"""FastAPI app for mathbank-exam-agent (requirements/64). Thin — the real logic lives
in exam_service.py/cognito_auth.py/rest_client.py; this module only handles HTTP
request/response shaping, auth, and CORS (mathbank-exam-web is a separate-origin SPA).
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

from mathbank_exam_agent import cognito_auth, exam_service, rest_client
from mathbank_exam_agent.auth_dependency import get_current_student_id
from mathbank_exam_agent.jwt_verify import verify_access_token

logger = logging.getLogger(__name__)
app = FastAPI(title="MathBank Mock Exam Agent")

app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

StudentId = Annotated[str, Depends(get_current_student_id)]


def _rest_error(exc: rest_client.RestError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mathbank-exam-agent"}


# --------------------------------------------------------------------------- auth / onboarding

class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    grade: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8, max_length=256)


@app.post("/v1/auth/signup")
def signup(body: SignupRequest) -> dict:
    try:
        cognito = cognito_auth.sign_up(
            password=body.password, first_name=body.first_name, last_name=body.last_name,
            grade=body.grade, email=body.email, phone=body.phone,
        )
    except cognito_auth.CognitoAuthError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "message": str(exc)}) from exc
    try:
        student = rest_client.onboard_student(
            cognito_sub=cognito["cognito_sub"], first_name=body.first_name, last_name=body.last_name,
            grade=body.grade, email=body.email, phone=body.phone, is_anonymous=False,
        )
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc
    login = cognito_auth.login(username=cognito["username"], password=body.password)
    return {
        "access_token": login["access_token"], "student_id": student["student_id"],
        "username": cognito["username"], "generated_username": cognito["generated_username"],
    }


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@app.post("/v1/auth/login")
def login(body: LoginRequest) -> dict:
    try:
        result = cognito_auth.login(username=body.username, password=body.password)
    except cognito_auth.CognitoAuthError as exc:
        raise HTTPException(status_code=401, detail={"code": exc.code, "message": str(exc)}) from exc
    claims = verify_access_token(result["access_token"])
    student = rest_client.get_student_by_cognito_sub(claims["sub"])
    if student is None:
        raise HTTPException(status_code=409, detail="this account has no MathBank student profile yet")
    return {"access_token": result["access_token"], "student_id": student["student_id"]}


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1)


@app.post("/v1/auth/forgot-password")
def forgot_password(body: ForgotPasswordRequest) -> dict:
    try:
        return cognito_auth.forgot_password(username=body.username)
    except cognito_auth.CognitoAuthError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc


class ConfirmForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1)
    confirmation_code: str = Field(min_length=1, max_length=20)
    new_password: str = Field(min_length=8, max_length=256)


@app.post("/v1/auth/confirm-forgot-password")
def confirm_forgot_password(body: ConfirmForgotPasswordRequest) -> dict:
    try:
        cognito_auth.confirm_forgot_password(
            username=body.username, confirmation_code=body.confirmation_code, new_password=body.new_password,
        )
    except cognito_auth.CognitoAuthError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"ok": True}


@app.post("/v1/auth/anonymous")
def anonymous_session() -> dict:
    try:
        student = rest_client.onboard_student(
            cognito_sub=None, first_name="Anonymous", last_name="Student", is_anonymous=True,
        )
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc
    return {"access_token": f"anon.{student['student_id']}", "student_id": student["student_id"]}


@app.get("/v1/auth/me")
def me(student_id: StudentId) -> dict:
    try:
        return rest_client.get_student_profile(student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


# --------------------------------------------------------------------------- exam papers

class GeneratePaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nl_request: str = Field(min_length=1, max_length=2000)
    exam_mode: bool = True


@app.post("/v1/exam-papers")
def start_paper(body: GeneratePaperRequest, student_id: StudentId) -> dict:
    """Phase 1 of 2 (requirements/64 continued — live-progress design): parses the
    request and mints a quiz_id immediately, status GENERATING. Fast — returns well
    before any question is drafted, so the caller can start polling
    generation-progress and then call `/run` (phase 2) separately."""
    try:
        quiz_id = exam_service.start_generation(student_id, body.nl_request, exam_mode=body.exam_mode)
        return {"quiz_id": quiz_id}
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


class RunGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nl_request: str = Field(min_length=1, max_length=2000)


@app.post("/v1/exam-papers/{quiz_id}/run")
async def run_paper(quiz_id: str, body: RunGenerationRequest, student_id: StudentId) -> dict:
    """Phase 2 of 2: the actual parallel generate+critique+aggregate-diversity work.
    Long-running (comfortably within this Lambda's 300s timeout even with the parallel
    speedup) — the caller doesn't need to wait on this response to navigate; it polls
    generation-progress and/or GET /v1/exam-papers/{quiz_id} for status instead."""
    try:
        return await exam_service.run_generation_async(quiz_id, student_id, body.nl_request)
    except exam_service.GenerationQualityError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "QUALITY_REJECTED", "message": str(exc)},
        ) from exc
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.get("/v1/exam-papers/{quiz_id}/generation-progress")
def generation_progress(quiz_id: str, student_id: StudentId, since_ordinal: int = 0) -> list[dict]:
    """What the agent/subagent is doing right now (requirements/64 continued) — the web
    UI polls this every ~1-2s while a paper's status is GENERATING, rendering each
    phase/question-ordinal step live instead of one static spinner message."""
    try:
        return rest_client.list_generation_events(quiz_id, student_id, since_ordinal=since_ordinal)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.get("/v1/exam-papers/mine")
def list_my_papers(student_id: StudentId) -> list[dict]:
    try:
        return rest_client.list_my_papers(student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.get("/v1/exam-papers/{quiz_id}")
def get_paper(quiz_id: str, student_id: StudentId) -> dict:
    try:
        return rest_client.get_paper(quiz_id, student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


class SaveExamProgressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_question_ordinal: int = Field(ge=1, le=20)
    question_id: str | None = None
    selected_key: str | None = Field(default=None, max_length=10)
    response_text: str | None = Field(default=None, max_length=10000)


@app.put("/v1/exam-papers/{quiz_id}/progress")
def save_exam_progress(
    quiz_id: str, body: SaveExamProgressRequest, student_id: StudentId,
) -> dict:
    try:
        return rest_client.save_exam_progress(
            quiz_id, student_id,
            current_question_ordinal=body.current_question_ordinal,
            question_id=body.question_id, selected_key=body.selected_key,
            response_text=body.response_text,
        )
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: str = Field(min_length=1, max_length=20)
    option_key: str | None = Field(default=None, max_length=10)
    client_timestamp_ms: int | None = None


@app.post("/v1/exam-papers/{quiz_id}/questions/{question_id}/events")
def log_event(quiz_id: str, question_id: str, body: EventRequest, student_id: StudentId) -> dict:
    try:
        return rest_client.log_event(
            quiz_id, question_id, student_id, event_type=body.event_type,
            option_key=body.option_key, client_timestamp_ms=body.client_timestamp_ms,
        )
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.get("/v1/exam-papers/{quiz_id}/events")
def get_events(quiz_id: str, student_id: StudentId) -> list[dict]:
    try:
        return rest_client.get_events(quiz_id, student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


class RespondRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_key: str | None = Field(default=None, max_length=10)
    response_text: str | None = Field(default=None, max_length=10000)
    time_spent_seconds: int | None = Field(default=None, ge=0, le=36000)


@app.post("/v1/exam-papers/{quiz_id}/questions/{question_id}/respond")
def respond(quiz_id: str, question_id: str, body: RespondRequest, student_id: StudentId) -> dict:
    if not body.selected_key and not body.response_text:
        raise HTTPException(422, "supply selected_key (MCQ) or response_text (FREE_TEXT/PROOF)")
    try:
        return rest_client.respond(
            quiz_id, question_id, student_id, selected_key=body.selected_key,
            response_text=body.response_text, time_spent_seconds=body.time_spent_seconds,
        )
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.post("/v1/exam-papers/{quiz_id}/submit")
def submit_exam(quiz_id: str, student_id: StudentId) -> dict:
    try:
        return rest_client.submit_exam(quiz_id, student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.get("/v1/exam-papers/{quiz_id}/review")
def review(quiz_id: str, student_id: StudentId) -> dict:
    try:
        return rest_client.review(quiz_id, student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.post("/v1/exam-papers/{quiz_id}/diagnosis")
def diagnose_exam(quiz_id: str, student_id: StudentId) -> dict:
    try:
        return exam_service.diagnose_exam(quiz_id, student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc


@app.get("/v1/exam-papers/{quiz_id}/diagnosis")
def get_diagnosis(quiz_id: str, student_id: StudentId) -> dict:
    try:
        return rest_client.get_diagnosis(quiz_id, student_id)
    except rest_client.RestError as exc:
        raise _rest_error(exc) from exc
