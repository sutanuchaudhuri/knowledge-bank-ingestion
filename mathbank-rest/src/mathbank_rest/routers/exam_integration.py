"""requirements/64: service-to-service integration for `mathbank-exam-agent` (the AWS
Strands/Bedrock mock-exam agent). Admin-key-gated, not student-bearer-token-gated —
these endpoints write on behalf of a caller-supplied `student_id`, which only a trusted
backend service (never a student's own browser) should be able to do. Student-facing
exam-taking (fetch the paper, submit a response, review) reuses the existing,
unmodified `/v1/quiz/*` student endpoints — this router only covers what's new:
importing an already-generated/critic-reviewed paper, explicit exam submission, and
writing/reading the post-exam diagnosis report.
"""
from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from mathbank_rest import quiz_runtime
from mathbank_rest.db.learner import (
    create_student_for_cognito,
    get_mastery_summary,
    get_student_by_cognito_sub,
    get_student_profile,
)
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import create_access_token, require_admin_api_key

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/v1/quiz-integration", tags=["quiz-integration"],
    dependencies=[Depends(require_admin_api_key)],
)


def _call(operation, *args: Any, **kwargs: Any) -> dict:
    try:
        return operation(*args, **kwargs)
    except quiz_runtime.QuizError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc


class DiagramRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    object_key: str
    sha256: str


class InspirationSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_code: str = Field(min_length=1, max_length=64)
    note: str = Field(default="", max_length=500)


class ImportQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_type: str = Field(min_length=1, max_length=20)
    prompt_text: str = Field(min_length=1)
    prompt_latex: str | None = None
    options: list[dict] | None = None
    correct_answer: dict
    option_explanations: dict[str, str] = Field(default_factory=dict)
    solution_text: str = Field(min_length=1)
    solution_steps: list[str] = Field(
        default_factory=list, max_length=30,
        description="The solution broken into discrete, ordered steps (requirements/64 continued — "
                    "computed complexity signal: step_count is literally len(solution_steps)).",
    )
    key_insight: str = ""
    difficulty_band: str | None = None
    revision_log: list[dict] = Field(default_factory=list)
    concept_slugs: list[str] = Field(default_factory=list, max_length=10)
    technique_slugs: list[str] = Field(default_factory=list, max_length=10)
    skill_slugs: list[str] = Field(default_factory=list, max_length=10)
    inspiration_sources: list[InspirationSource] = Field(
        default_factory=list, max_length=5,
        description="Real corpus problems this question drew on (requirements/64 continued — "
                    "can be multiple), rank = list order, each with a note on what was actually "
                    "borrowed/changed.",
    )
    diagram: DiagramRef | None = None
    pool_question_id: UUID | None = Field(
        default=None, description="Set when this question was served from quiz.question_pool (migration 052).",
    )
    add_to_pool: bool = Field(
        default=False, description="Write this (critic-approved) question back into quiz.question_pool.",
    )


class ImportPaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    style: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    instructions: str = ""
    requested_question_count: int = Field(ge=1, le=20)
    requested_question_types: list[str]
    target_skill_slugs: list[str] = Field(default_factory=list, max_length=10)
    target_concept_slugs: list[str] = Field(default_factory=list, max_length=10)
    difficulty_band: str | None = None
    generated_by: str = Field(min_length=1, max_length=100)
    exam_mode: bool = True
    time_limit_seconds: int | None = Field(default=None, ge=60, le=36000)
    questions: list[ImportQuestion] = Field(min_length=1, max_length=20)


class StartPaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    style: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    instructions: str = ""
    requested_question_count: int = Field(ge=1, le=20)
    requested_question_types: list[str]
    target_skill_slugs: list[str] = Field(default_factory=list, max_length=10)
    target_concept_slugs: list[str] = Field(default_factory=list, max_length=10)
    difficulty_band: str | None = None
    generated_by: str = Field(min_length=1, max_length=100)
    exam_mode: bool = True
    time_limit_seconds: int | None = Field(default=None, ge=60, le=36000)


class FinalizePaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    generated_by: str | None = Field(default=None, max_length=100)
    questions: list[ImportQuestion] = Field(min_length=1, max_length=20)
    pool_topic: str | None = Field(default=None, max_length=500)
    pool_concept_slugs: list[str] = Field(default_factory=list, max_length=10)


class FailPaperRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    error_message: str = Field(min_length=1, max_length=500)


class MatchPoolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    style: str = Field(min_length=1, max_length=20)
    question_types: list[str] = Field(default_factory=list, max_length=3)
    difficulty_band: str | None = None
    topic: str | None = Field(default=None, max_length=500)
    concept_slugs: list[str] = Field(default_factory=list, max_length=10)
    limit: int = Field(default=20, ge=1, le=50)


class GenerationEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int = Field(ge=1)
    phase: str = Field(min_length=1, max_length=40)
    status: str = Field(min_length=1, max_length=10)
    question_ordinal: int | None = Field(default=None, ge=1)
    detail: str = Field(default="", max_length=500)


@router.post("/papers")
def import_paper(body: ImportPaperRequest) -> dict:
    return _call(
        quiz_runtime.import_paper,
        body.student_id,
        style=body.style, title=body.title, instructions=body.instructions,
        requested_question_count=body.requested_question_count,
        requested_question_types=body.requested_question_types,
        target_skill_slugs=body.target_skill_slugs, target_concept_slugs=body.target_concept_slugs,
        difficulty_band=body.difficulty_band, generated_by=body.generated_by,
        exam_mode=body.exam_mode, time_limit_seconds=body.time_limit_seconds,
        questions=[q.model_dump() for q in body.questions],
    )


@router.post("/papers/start")
def start_paper(body: StartPaperRequest) -> dict:
    """Mints a quiz_id immediately, status GENERATING (requirements/64 continued —
    parallel generation + live progress). The caller (mathbank-exam-agent) gets this id
    back right away, well before any question is drafted, so it can start polling
    generation-events for this quiz_id while a later call does the actual work."""
    quiz_id = _call(
        quiz_runtime.start_paper,
        body.student_id,
        style=body.style, title=body.title, instructions=body.instructions,
        requested_question_count=body.requested_question_count,
        requested_question_types=body.requested_question_types,
        target_skill_slugs=body.target_skill_slugs, target_concept_slugs=body.target_concept_slugs,
        difficulty_band=body.difficulty_band, generated_by=body.generated_by,
        exam_mode=body.exam_mode, time_limit_seconds=body.time_limit_seconds,
    )
    return {"quiz_id": str(quiz_id)}


@router.post("/papers/{quiz_id}/finalize")
def finalize_paper(quiz_id: UUID, body: FinalizePaperRequest) -> dict:
    """Inserts every question for an already-start_paper'd quiz_id and flips its status
    to READY (requirements/64 continued)."""
    return _call(
        quiz_runtime.finalize_paper, quiz_id, body.student_id,
        questions=[q.model_dump() for q in body.questions], generated_by=body.generated_by,
        pool_topic=body.pool_topic, pool_concept_slugs=body.pool_concept_slugs,
    )


@router.post("/papers/{quiz_id}/fail")
def fail_paper(quiz_id: UUID, body: FailPaperRequest) -> dict:
    return _call(quiz_runtime.fail_paper, quiz_id, body.student_id, body.error_message)


@router.post("/question-pool/match")
def match_question_pool(body: MatchPoolRequest) -> list[dict]:
    """Cached, critic-approved questions (with full solutions) for an "almost the same"
    request — same style/question type/difficulty plus a similar topic or overlapping
    concept, never one this student was already served (migration 052). The exam agent
    fills as many paper slots as possible from here before drafting anything new."""
    return quiz_runtime.match_pool_questions(
        body.student_id, style=body.style, question_types=body.question_types,
        difficulty_band=body.difficulty_band, topic=body.topic,
        concept_slugs=body.concept_slugs, limit=body.limit,
    )


@router.post("/papers/{quiz_id}/generation-events")
def post_generation_event(quiz_id: UUID, body: GenerationEventRequest) -> dict:
    """Appends one row to the generation-progress log (requirements/64 continued) —
    the web UI's live "what is the agent doing right now" view polls the GET below for
    exactly these rows."""
    quiz_runtime.post_generation_event(
        quiz_id, ordinal=body.ordinal, phase=body.phase, status=body.status,
        question_ordinal=body.question_ordinal, detail=body.detail,
    )
    return {"ok": True}


@router.get("/papers/{quiz_id}/generation-events")
def get_generation_events(quiz_id: UUID, student_id: UUID, since_ordinal: int = 0) -> list[dict]:
    return _call(quiz_runtime.list_generation_events, quiz_id, student_id, since_ordinal=since_ordinal)


@router.get("/papers/mine")
def list_my_papers(student_id: UUID, limit: int = 20) -> list[dict]:
    """Admin-gated equivalent of /v1/quiz/mine — mathbank-exam-agent resolves identity
    via Cognito (or an anonymous session), not mathbank-rest's own JWT, so it cannot use
    the student-bearer-token-gated endpoint at all (requirements/64 continued §0's
    "exam-taking flow is proxied through mathbank-exam-agent, not called directly")."""
    return quiz_runtime.list_my_quizzes(student_id, limit=limit)


@router.get("/papers/{quiz_id}")
def get_paper(quiz_id: UUID, student_id: UUID) -> dict:
    return _call(quiz_runtime.get_quiz, quiz_id, student_id)


class SaveExamProgressRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    current_question_ordinal: int = Field(ge=1, le=20)
    question_id: UUID | None = None
    selected_key: str | None = Field(default=None, max_length=10)
    response_text: str | None = Field(default=None, max_length=10000)


@router.put("/papers/{quiz_id}/progress")
def save_exam_progress(quiz_id: UUID, body: SaveExamProgressRequest) -> dict:
    raw_response = {k: v for k, v in (
        ("selected_key", body.selected_key), ("response_text", body.response_text),
    ) if v is not None}
    return _call(
        quiz_runtime.save_exam_progress, quiz_id, body.student_id,
        current_question_ordinal=body.current_question_ordinal,
        question_id=body.question_id, raw_response=raw_response or None,
    )


class RespondRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    selected_key: str | None = Field(default=None, max_length=10)
    response_text: str | None = Field(default=None, max_length=10000)
    time_spent_seconds: int | None = Field(default=None, ge=0, le=36000)


@router.post("/papers/{quiz_id}/questions/{question_id}/respond")
def respond(quiz_id: UUID, question_id: UUID, body: RespondRequest) -> dict:
    raw_response = {k: v for k, v in (
        ("selected_key", body.selected_key), ("response_text", body.response_text),
    ) if v is not None}
    if not raw_response:
        raise HTTPException(422, "supply selected_key (MCQ) or response_text (FREE_TEXT/PROOF)")
    return _call(
        quiz_runtime.submit_response, quiz_id, question_id, body.student_id,
        raw_response=raw_response, time_spent_seconds=body.time_spent_seconds,
    )


@router.get("/papers/{quiz_id}/review")
def review(quiz_id: UUID, student_id: UUID) -> dict:
    return _call(quiz_runtime.get_review, quiz_id, student_id)


@router.post("/papers/{quiz_id}/submit")
def submit_exam(quiz_id: UUID, student_id: UUID) -> dict:
    return _call(quiz_runtime.submit_exam, quiz_id, student_id)


@router.get("/papers/{quiz_id}/diagnosis-input")
def diagnosis_input(quiz_id: UUID, student_id: UUID) -> dict:
    return _call(quiz_runtime.get_paper_for_diagnosis, quiz_id, student_id)


class WriteDiagnosisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    time_management_verdict: str = Field(min_length=1)
    pacing_notes: list[dict] = Field(default_factory=list)
    reasoning_guidance: list[dict] = Field(default_factory=list)
    improvement_areas: list[dict] = Field(default_factory=list)
    generated_by: str = Field(min_length=1, max_length=100)


@router.post("/papers/{quiz_id}/diagnosis")
def write_diagnosis(quiz_id: UUID, body: WriteDiagnosisRequest) -> dict:
    return _call(
        quiz_runtime.write_diagnosis, quiz_id, body.student_id,
        time_management_verdict=body.time_management_verdict,
        pacing_notes=body.pacing_notes, reasoning_guidance=body.reasoning_guidance,
        improvement_areas=body.improvement_areas, generated_by=body.generated_by,
    )


@router.get("/students/{student_id}/mastery-summary")
def mastery_summary(student_id: UUID) -> dict:
    """Admin-gated equivalent of /v1/learner/mastery (which derives student_id from a
    student's own bearer token) — the generator agent (requirements/64 §5 point 2) needs
    a *specific* student's mastery for personalization, not the caller's own, so it
    cannot use the student-facing endpoint at all."""
    return get_mastery_summary(student_id)


@router.get("/difficulty-distribution")
def difficulty_distribution(concept_slug: str | None = None, technique_slug: str | None = None) -> dict:
    """Real, corpus-grounded core.problem.difficulty_band counts for a resolved
    concept/technique (requirements/64 §5 point 1) — neither hybrid_search.search_problems
    nor the mathbank-mcp-competitions search_problems MCP tool project this column today
    (confirmed live, requirements/64), so this is a small, new, additive query rather
    than overloading either of those already-audited retrieval paths."""
    if not concept_slug and not technique_slug:
        raise HTTPException(422, "supply concept_slug or technique_slug")
    if concept_slug:
        query = text("""
            SELECT p.difficulty_band, count(*) AS n
            FROM core.problem p
            JOIN knowledge.problem_concept pc ON pc.problem_id = p.problem_id
            JOIN knowledge.concept c ON c.concept_id = pc.concept_id
            WHERE c.slug = :slug AND p.difficulty_band IS NOT NULL
            GROUP BY p.difficulty_band
        """)
        params = {"slug": concept_slug}
    else:
        query = text("""
            SELECT p.difficulty_band, count(*) AS n
            FROM core.problem p
            JOIN knowledge.problem_technique pt ON pt.problem_id = p.problem_id
            JOIN knowledge.technique t ON t.technique_id = pt.technique_id
            WHERE t.slug = :slug AND p.difficulty_band IS NOT NULL
            GROUP BY p.difficulty_band
        """)
        params = {"slug": technique_slug}
    with engine.connect() as conn:
        rows = conn.execute(query, params).mappings().all()
    return {"distribution": {r["difficulty_band"]: r["n"] for r in rows}}


@router.get("/papers/{quiz_id}/diagnosis")
def get_diagnosis(quiz_id: UUID, student_id: UUID) -> dict:
    return _call(quiz_runtime.get_diagnosis, quiz_id, student_id)


# --------------------------------------------------------------------------- requirements/64
# (continued): Cognito-backed student onboarding + the exam-taking interaction timeline.

class OnboardStudentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cognito_sub: str | None = Field(default=None, description="Null for an anonymous session")
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    grade: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=30)
    is_anonymous: bool = False


@router.post("/students/onboard")
def onboard_student(body: OnboardStudentRequest) -> dict:
    """Creates the one `learner.student_profile` row for a new identity — both the
    named (Cognito signup) and anonymous paths call this, each exactly once per new
    identity (requirements/64 continued: "in both cases StudentId is created during
    onboarding"). The caller (mathbank-exam-agent) is responsible for only calling this
    once per Cognito `sub` — see GET /students/by-cognito-sub/{sub} for the "does this
    identity already have a student_id" check that makes that safe across repeat logins."""
    return create_student_for_cognito(
        cognito_sub=body.cognito_sub, first_name=body.first_name, last_name=body.last_name,
        grade=body.grade, email=body.email, phone=body.phone, is_anonymous=body.is_anonymous,
    )


@router.get("/students/by-cognito-sub/{cognito_sub}")
def student_by_cognito_sub(cognito_sub: str) -> dict:
    student = get_student_by_cognito_sub(cognito_sub)
    if student is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "no student for this Cognito identity"})
    return student


@router.get("/students/{student_id}")
def student_profile(student_id: UUID) -> dict:
    student = get_student_profile(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "no such student"})
    return student


@router.post("/students/{student_id}/mint-session-token")
def mint_session_token(student_id: UUID) -> dict:
    """Issues a normal `mathbank-rest` student JWT (`security.create_access_token`,
    the exact same token type/verification `/v1/learner/login` already issues and every
    `/v1/learner/*`/`/v1/quiz/*` endpoint already accepts) for an identity a caller has
    *already* authenticated some other way — Cognito, here. This is the one bridge point
    that lets `mathbank-web`/`mathbank-live` move their login UX to Cognito while every
    other student-facing endpoint in this service stays completely unchanged: Cognito
    replaces the password check and the login *screen*, not the ongoing API session
    token or any downstream authorization logic."""
    student = get_student_profile(student_id)
    if student is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "no such student"})
    if student["status"] != "ACTIVE":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "account is not active"})
    token = create_access_token(student_id)
    return {
        "access_token": token, "token_type": "bearer", "student_id": str(student_id),
        "first_name": student.get("first_name"), "last_name": student.get("last_name"),
        "display_name": student.get("display_name"),
    }


class LogEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    student_id: UUID
    event_type: str = Field(min_length=1, max_length=20)
    option_key: str | None = Field(default=None, max_length=10)
    client_timestamp_ms: int | None = None


@router.post("/papers/{quiz_id}/questions/{question_id}/events")
def log_event(quiz_id: UUID, question_id: UUID, body: LogEventRequest) -> dict:
    return _call(
        quiz_runtime.log_response_event, quiz_id, question_id, body.student_id,
        event_type=body.event_type, option_key=body.option_key,
        client_timestamp_ms=body.client_timestamp_ms,
    )


@router.get("/papers/{quiz_id}/events")
def get_events(quiz_id: UUID, student_id: UUID) -> list[dict]:
    return _call(quiz_runtime.get_response_events, quiz_id, student_id)
