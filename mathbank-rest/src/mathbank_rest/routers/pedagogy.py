"""Read-only teaching context and provisional coaching contracts; paid or writing actions need sign-in."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import guided_orientation, pedagogy, rate_limit, route_runtime, solution_guidance
from mathbank_rest.db import topic_pedagogy
from mathbank_rest.enrichment import (
    EnrichmentUnavailable,
    enrichment_status,
    ensure_learning_metadata,
)
from mathbank_rest.practice_selection import load_profile
from mathbank_rest.security import get_current_student_id, get_optional_student_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/tutor", tags=["pedagogy"])


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_code: str = Field(min_length=1, max_length=200)
    topic: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=10, max_length=2000)

    @field_validator("problem_code", "topic", "reason")
    @classmethod
    def trim(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Feedback fields cannot be blank.")
        if value != value.strip():
            raise ValueError("Remove leading/trailing whitespace from feedback fields.")
        return value


@router.get("/topic-plan")
def topic_plan(q: str = Query(min_length=1, max_length=200)) -> dict:
    return _call(topic_pedagogy.topic_plan, q)


class TopicPracticeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: str = Field(min_length=1, max_length=200)
    profile_version: str = "topic-fit-v1"
    limit: int = Field(default=10, ge=1, le=25)
    target_difficulty: int | None = Field(default=None, ge=1, le=5)
    known_skills: list[str] = Field(default_factory=list, max_length=50)
    exposed_codes: list[str] | None = Field(default=None, max_length=100)
    exclude_codes: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("profile_version")
    @classmethod
    def profile_exists(cls, value: str) -> str:
        load_profile(value)
        return value


@router.post("/topic-practice")
def topic_practice(body: TopicPracticeRequest,
                   student_id: Annotated[UUID | None, Depends(get_optional_student_id)]) -> dict:
    try:
        return topic_pedagogy.topic_candidates(**body.model_dump(), student_id=student_id)
    except SQLAlchemyError as exc:
        logger.exception("Topic practice evidence unavailable")
        raise HTTPException(503, "Topic practice evidence unavailable.") from exc


@router.post("/feedback", status_code=201)
def feedback(body: FeedbackRequest, student_id: Annotated[UUID, Depends(get_current_student_id)]) -> dict:
    result = _call(
        topic_pedagogy.submit_feedback, student_id, body.problem_code, body.topic, body.reason
    )
    if result is None:
        raise HTTPException(404, "Unknown problem code.")
    return {
        **result,
        "message": "Report recorded for review; no annotation, graph or mastery was changed.",
    }


def _call(operation: Callable[..., dict], *args: Any) -> dict:
    try:
        return operation(*args)
    except pedagogy.UnknownLearningEntity as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pedagogy.CoachingUnavailable as exc:
        logger.exception("Provisional coaching unavailable")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except EnrichmentUnavailable as exc:
        logger.exception("Automatic teaching enrichment failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (Neo4jError, ServiceUnavailable, SessionExpired, SQLAlchemyError, RuntimeError) as exc:
        logger.exception("Pedagogical data service unavailable")
        raise HTTPException(
            status_code=503, detail="Learning data is unavailable; check database connectivity."
        ) from exc


@router.get("/learning-context/{problem_code}")
def learning_context(
    problem_code: str,
    enrich: Annotated[bool, Query(deprecated=True, description="Ignored: a GET never starts enrichment.")] = False,
) -> dict:
    """Stored teaching context only. `enrichment_status` says whether metadata exists; to generate it,
    sign in and POST /v1/tutor/learning-context/{problem_code}/enrich."""
    result = _call(pedagogy.learning_context, problem_code)
    result["enrichment_status"] = (
        "enriched" if result["metadata_status"] != "unenriched" else _enrichment_status(problem_code)
    )
    result["pedagogy_session"] = guided_orientation.orientation(result["problem"])
    return result


def _enrichment_status(problem_code: str) -> str:
    try:
        return enrichment_status(problem_code)
    except SQLAlchemyError:
        logger.exception("Enrichment status unavailable")
        return "unknown"


@router.post("/learning-context/{problem_code}/enrich")
def enrich_learning_context(
    problem_code: str, caller: Annotated[rate_limit.Caller, Depends(rate_limit.require_paid_caller)]
) -> dict:
    """Generate and publish teaching metadata (paid model call, writes the catalogue). Signed-in callers only."""
    rate_limit.enforce(caller, "enrich")
    result = _call(ensure_learning_metadata, problem_code)
    return {"problem_code": problem_code, "enrichment": result, "enrichment_status": _enrichment_status(problem_code)}


@router.get("/workspace/{problem_code}")
def workspace(problem_code: str) -> dict:
    """Canonical question and authored orientation without graph/enrichment."""
    problem = _call(pedagogy.problem_statement, problem_code)
    return {"problem": problem, "pedagogy_session": guided_orientation.orientation(problem)}


class MicroCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_code: str = Field(min_length=1, max_length=200)
    index: int = Field(ge=0, le=20, strict=True)
    response: str = Field(min_length=1, max_length=200)


class GuidancePlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_code: str = Field(min_length=1, max_length=200, pattern=r"^\S+$")
    allow_dynamic_fallback: bool = False


@router.post("/guidance-plan")
def guidance_plan(
    body: GuidancePlanRequest,
    caller: Annotated[rate_limit.Caller | None, Depends(rate_limit.optional_paid_caller)],
) -> dict:
    """Explicit planning action; raw solutions remain inside the REST service. The paid dynamic
    fallback needs a learner token or admin credential."""
    if body.allow_dynamic_fallback:
        if caller is None:
            raise _sign_in_required()
        rate_limit.enforce(caller, "tutor")
    return _call(solution_guidance.guidance_plan, body.problem_code, body.allow_dynamic_fallback)


@router.post("/micro-check")
def micro_check(body: MicroCheckRequest) -> dict:
    problem = _call(pedagogy.problem_statement, body.problem_code)
    try:
        return guided_orientation.check_orientation(problem, body.index, body.response)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/prerequisites/{skill_slug}")
def prerequisites(skill_slug: str, max_depth: int = Query(default=4, ge=1, le=8)) -> dict:
    return _call(pedagogy.prerequisite_path, skill_slug, max_depth)


@router.get("/practice/{problem_code}")
def practice(problem_code: str, limit: int = Query(default=5, ge=1, le=20)) -> dict:
    return _call(pedagogy.easier_practice, problem_code, limit)


def _sign_in_required() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="sign in (learner token or admin credential) to generate new coaching",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/coach")
def coach(
    body: pedagogy.CoachRequest,
    caller: Annotated[rate_limit.Caller | None, Depends(rate_limit.optional_paid_caller)],
) -> dict:
    """Published hints are served to anyone; generating new coaching is a paid model call for signed-in callers.
    Neither path starts enrichment."""
    if caller is None:
        stored = _call(route_runtime.coaching, body.problem_code, body.hint_level)
        if stored:
            return stored
        raise _sign_in_required()
    rate_limit.enforce(caller, "tutor")
    return _call(pedagogy.coach, body)
