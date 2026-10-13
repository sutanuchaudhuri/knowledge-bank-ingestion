"""Admin quiz/activity authoring — Tier A (the activity bank itself) and Tier B (binding a
quiz into a micro-course state), per requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md.
"""

from __future__ import annotations

import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from mathbank_rest import micro_course_service as courses
from mathbank_rest import quiz_service as quizzes
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import require_admin_api_key

logger = logging.getLogger(__name__)

ActivityType = Literal[
    "MCQ", "MULTISELECT", "NUMERIC", "SHORT_RESPONSE", "SUBPROBLEM", "STEP_ORDERING",
    "ERROR_DIAGNOSIS", "CONFIDENCE_CHECK", "LIVE_POLL",
]
Purpose = Literal[
    "ENTRY_CHECK", "COMPREHENSION", "RECOGNITION", "MISCONCEPTION_DIAGNOSTIC",
    "EXECUTION", "EXIT_CHECK", "TRANSFER",
]

router = APIRouter(
    prefix="/v1/admin/activities",
    tags=["admin-activities"],
    dependencies=[Depends(require_admin_api_key)],
)
binding_router = APIRouter(
    prefix="/v1/admin/micro-courses/states",
    tags=["admin-micro-courses"],
    dependencies=[Depends(require_admin_api_key)],
)


def _call(operation, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return operation(conn, *args, **kwargs)
    except (quizzes.ActivityConflict, courses.MicroCourseConflict) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (quizzes.ActivityNotFound, courses.MicroCourseNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="The requested change conflicts with existing data.") from exc
    except SQLAlchemyError as exc:
        logger.exception("Quiz/activity admin operation failed")
        raise HTTPException(status_code=503, detail="Activity data is unavailable.") from exc


class ActivityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_type: ActivityType
    prompt: str = Field(min_length=1, max_length=4000)
    options: list[dict] = Field(default_factory=list)
    correctness_policy: dict = Field(default_factory=dict)
    estimated_seconds: int = Field(default=60, gt=0)
    skill_id: UUID | None = None
    source_problem_id: UUID | None = None
    created_by: str = Field(min_length=1, max_length=200)


class ActivityUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str | None = Field(default=None, min_length=1, max_length=4000)
    options: list[dict] | None = None
    correctness_policy: dict | None = None
    estimated_seconds: int | None = Field(default=None, gt=0)
    actor: str = Field(min_length=1, max_length=200)


class ActorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=200)


class SkillMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skill_id: UUID | None = None
    actor: str = Field(min_length=1, max_length=200)


class SourceMappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_problem_id: UUID | None = None
    actor: str = Field(min_length=1, max_length=200)


class AttachActivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: UUID
    ordinal: int = Field(ge=0)
    purpose: Purpose
    required: bool = True


class UpdateBindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordinal: int | None = Field(default=None, ge=0)
    purpose: Purpose | None = None
    required: bool | None = None


ItemKind = Literal["asset", "interaction", "learning_item", "activity"]


class SetItemSequenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence_position: int | None = Field(default=None, ge=0, le=32767)


# ---- Tier A: the activity/quiz bank itself ------------------------------------------------

@router.post("", status_code=201)
def create_activity(body: ActivityCreateRequest) -> dict:
    """Create a new INSTRUCTOR_CREATED, STATIC quiz question (requirements/46 QZA-1)."""
    return _call(
        quizzes.create_activity,
        activity_type=body.activity_type, prompt=body.prompt, options=body.options,
        correctness_policy=body.correctness_policy, estimated_seconds=body.estimated_seconds,
        skill_id=str(body.skill_id) if body.skill_id else None,
        source_problem_id=str(body.source_problem_id) if body.source_problem_id else None,
        created_by=body.created_by,
    )


@router.get("")
def list_activities(
    q: str = Query(default="", max_length=200),
    activity_type: ActivityType | None = None,
    source_type: Literal["PRECOMPILED", "CORPUS_DERIVED", "LIVE_AGENT_CREATED", "INSTRUCTOR_CREATED"] | None = None,
    status: Literal["ACTIVE", "INACTIVE", "ALL"] = "ALL",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List/search the activity bank, including inactive items when status=ALL (requirements/46 QZA-2)."""
    return _call(quizzes.list_activities, q=q, activity_type=activity_type, source_type=source_type,
                 status=status, limit=limit, offset=offset)


@router.get("/{activity_id}")
def get_activity(activity_id: UUID) -> dict:
    return _call(quizzes.get_activity, str(activity_id))


@router.patch("/{activity_id}")
def update_activity(activity_id: UUID, body: ActivityUpdateRequest) -> dict:
    """Update an INSTRUCTOR_CREATED activity's content; 409 for any other source_type (requirements/46 QZA-3)."""
    return _call(
        quizzes.update_activity, str(activity_id),
        prompt=body.prompt, options=body.options, correctness_policy=body.correctness_policy,
        estimated_seconds=body.estimated_seconds, actor=body.actor,
    )


@router.post("/{activity_id}/deactivate")
def deactivate_activity(activity_id: UUID, body: ActorRequest) -> dict:
    return _call(quizzes.deactivate_activity, str(activity_id), body.actor)


@router.post("/{activity_id}/reactivate")
def reactivate_activity(activity_id: UUID, body: ActorRequest) -> dict:
    return _call(quizzes.reactivate_activity, str(activity_id), body.actor)


@router.patch("/{activity_id}/skill-mapping")
def set_skill_mapping(activity_id: UUID, body: SkillMappingRequest) -> dict:
    """Map a quiz to the canonical knowledge.skill it measures (requirements/46 QZA-5)."""
    return _call(quizzes.set_skill_mapping, str(activity_id),
                 str(body.skill_id) if body.skill_id else None, body.actor)


@router.patch("/{activity_id}/source-mapping")
def set_source_mapping(activity_id: UUID, body: SourceMappingRequest) -> dict:
    """Map a quiz to its originating core.problem (requirements/46 QZA-6)."""
    return _call(quizzes.set_source_mapping, str(activity_id),
                 str(body.source_problem_id) if body.source_problem_id else None, body.actor)


# ---- Tier B: binding a quiz into a specific micro-course state ----------------------------

@binding_router.post("/{state_id}/activities", status_code=201)
def attach_activity(state_id: UUID, body: AttachActivityRequest) -> dict:
    """Bind a quiz into a course state, wiring the already-built/validated
    micro_course_service.attach_activity (requirements/46 QZA-4)."""
    _call(
        courses.attach_activity, str(state_id), str(body.activity_id), body.ordinal, body.purpose,
        required=body.required,
    )
    return {"state_id": str(state_id), "activity_id": str(body.activity_id)}


@binding_router.delete("/{state_id}/activities/{activity_id}", status_code=204)
def detach_activity(state_id: UUID, activity_id: UUID) -> None:
    _call(courses.detach_activity, str(state_id), str(activity_id))


@binding_router.patch("/{state_id}/activities/{activity_id}")
def update_activity_binding(state_id: UUID, activity_id: UUID, body: UpdateBindingRequest) -> dict:
    _call(
        courses.update_activity_binding, str(state_id), str(activity_id),
        ordinal=body.ordinal, purpose=body.purpose, required=body.required,
    )
    return {"state_id": str(state_id), "activity_id": str(activity_id)}


@binding_router.patch("/{state_id}/items/{item_kind}/{item_id}/sequence")
def set_item_sequence_position(
    state_id: UUID, item_kind: ItemKind, item_id: str, body: SetItemSequenceRequest
) -> dict:
    """Author (or clear) one item's cross-kind position within its state's student-facing
    item order — the one new field the per-item decomposed reader needs (requirements/47
    §2.1, MCN2-1). Works identically across all four child kinds (asset/interaction/
    learning_item/activity) via one generic endpoint."""
    _call(
        courses.set_item_sequence_position, str(state_id), item_kind, item_id,
        body.sequence_position,
    )
    return {"state_id": str(state_id), "item_kind": item_kind, "item_id": item_id,
            "sequence_position": body.sequence_position}
