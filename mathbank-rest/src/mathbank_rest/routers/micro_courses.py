"""Admin authoring and student read APIs for deterministic micro-courses."""

from __future__ import annotations

import hashlib
import logging
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from mathbank_rest import micro_course_service as courses
from mathbank_rest import object_store
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import get_current_student_id, require_admin_api_key

logger = logging.getLogger(__name__)
_ASSET_TYPES = {
    "image/png": ("png", "IMAGE"),
    "image/jpeg": ("jpg", "IMAGE"),
    "image/webp": ("webp", "IMAGE"),
    "application/pdf": ("pdf", "DOCUMENT"),
    "text/plain": ("txt", "DOCUMENT"),
    "video/mp4": ("mp4", "VIDEO"),
    "audio/mpeg": ("mp3", "AUDIO"),
    "audio/mp4": ("m4a", "AUDIO"),
}
admin_router = APIRouter(
    prefix="/v1/admin/micro-courses",
    tags=["admin micro-courses"],
    dependencies=[Depends(require_admin_api_key)],
)
student_router = APIRouter(prefix="/v1/micro-courses", tags=["micro-courses"])


class CourseTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: Literal["CONCEPT", "TECHNIQUE", "SKILL"]
    target_id: UUID
    role: Literal["PRIMARY", "SECONDARY", "PREREQUISITE"] = "PRIMARY"


class CreateCourse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_code: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=300)
    description: str | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)
    difficulty_level: int | None = Field(default=None, ge=1, le=10)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_by: str = Field(min_length=1, max_length=200)
    targets: list[CourseTarget] = Field(min_length=1, max_length=30)


class CreateRelease(BaseModel):
    model_config = ConfigDict(extra="forbid")
    created_by: str = Field(min_length=1, max_length=200)
    parent_release_id: UUID | None = None


class CreateModule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module_key: str = Field(min_length=1, max_length=120)
    ordinal: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=300)
    objective: str | None = None
    estimated_seconds: int | None = Field(default=None, gt=0)
    required: bool = True


class CreateState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state_key: str = Field(min_length=1, max_length=120)
    ordinal: int = Field(ge=0)
    state_type: Literal[
        "ORIENTATION", "EXPLANATION", "SLIDE", "VIDEO", "READING", "VISUAL", "EXAMPLE",
        "CHECKPOINT", "QUIZ", "DIAGNOSTIC", "REMEDIATION", "PRACTICE", "SUMMARY", "TRANSFER",
    ]
    title: str = Field(min_length=1, max_length=300)
    module_id: UUID | None = None
    objective: str | None = None
    student_instruction: str | None = None
    estimated_seconds: int | None = Field(default=None, gt=0)
    required: bool = True
    skippable: bool = False
    agent_policy: dict = Field(default_factory=dict)


class StateBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: Literal["CONCEPT", "TECHNIQUE", "SKILL", "MISCONCEPTION"]
    target_id: UUID
    role: str = Field(min_length=1, max_length=40)
    importance: float | None = Field(default=None, ge=0, le=1)
    required_level: int | None = Field(default=None, ge=1, le=5)


class CreateTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_state_id: UUID
    to_state_id: UUID
    transition_type: Literal[
        "NEXT", "CORRECT", "INCORRECT", "RETRY", "MISCONCEPTION", "PREREQUISITE_GAP",
        "USER_CONTINUE", "USER_BACK", "USER_QUESTION_RESOLVED", "INTERVENTION_COMPLETE",
    ]
    condition_type: Literal[
        "ALWAYS", "LEARNING_ITEM_RESULT", "ACTIVITY_RESULT", "MISCONCEPTION_CODE",
        "SKILL_STATUS", "INTERVENTION_RESULT",
    ] = "ALWAYS"
    condition_payload: dict = Field(default_factory=dict)
    priority: int = 0


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["APPROVED", "NEEDS_REVISION", "REJECTED"]
    reviewer: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publisher: str = Field(min_length=1, max_length=200)


class AttachInteraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interaction_instance_id: UUID
    ordinal: int = Field(ge=0)
    required: bool = True


class AdvanceEnrollment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_state_version: int = Field(ge=0)
    action: Literal["CONTINUE", "BACK"]


class SubmitLearningItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learning_item_id: str = Field(min_length=1, max_length=200)
    choice_index: int = Field(ge=0)


class SubmitActivityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activity_id: UUID
    choice_index: int | None = Field(default=None, ge=0)
    value: float | None = None


class RecordInteractionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interaction_instance_id: UUID
    event_type: str = Field(min_length=1, max_length=100)
    semantic_action: str = Field(min_length=1, max_length=100)
    control_key: str | None = Field(default=None, max_length=100)
    object_id: str | None = Field(default=None, max_length=200)
    before_state: dict | None = None
    action_payload: dict = Field(default_factory=dict)
    after_state: dict | None = None


def _call(operation, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return operation(conn, *args, **kwargs)
    except courses.MicroCourseConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except courses.MicroCourseNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409, detail="The requested change conflicts with existing course data."
        ) from exc
    except SQLAlchemyError as exc:
        logger.exception("Micro-course database operation failed")
        raise HTTPException(status_code=503, detail="Micro-course data is unavailable.") from exc


@admin_router.get("/targets")
def search_targets(
    target_type: Literal["CONCEPT", "TECHNIQUE", "SKILL", "MISCONCEPTION"],
    q: str = Query(default="", max_length=120),
    limit: int = Query(default=20, ge=1, le=50),
) -> list[dict]:
    return _call(courses.search_canonical_targets, target_type, q, limit)


@admin_router.get("")
def list_admin_courses(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _call(courses.list_courses, limit, offset)


@admin_router.post("", status_code=201)
def create_admin_course(body: CreateCourse) -> dict:
    course_id = _call(
        courses.create_course,
        body.canonical_code,
        body.title,
        body.created_by,
        [target.model_dump(mode="json") for target in body.targets],
        description=body.description,
        estimated_minutes=body.estimated_minutes,
        difficulty_level=body.difficulty_level,
        metadata=body.metadata,
    )
    return {"micro_course_id": course_id}


@admin_router.get("/interactions")
def get_approved_interactions(
    limit: int = Query(default=100, ge=1, le=250),
) -> list[dict]:
    return _call(courses.list_approved_interactions, limit)


@admin_router.get("/templates")
def get_widget_library() -> dict:
    return _call(courses.get_widget_library)


@admin_router.get("/{canonical_code}")
def get_admin_course(canonical_code: str) -> dict:
    return _call(courses.get_course, canonical_code)


class ActorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: str = Field(min_length=1, max_length=200)


@admin_router.post("/{canonical_code}/deactivate")
def deactivate_admin_course(canonical_code: str, body: ActorRequest) -> dict:
    return _call(courses.deactivate_course, canonical_code, body.actor)


@admin_router.post("/{canonical_code}/reactivate")
def reactivate_admin_course(canonical_code: str, body: ActorRequest) -> dict:
    return _call(courses.reactivate_course, canonical_code, body.actor)


@admin_router.get("/{canonical_code}/activity")
def get_admin_course_activity(canonical_code: str) -> dict:
    return _call(courses.get_course_activity, canonical_code)


@admin_router.get("/{canonical_code}/preview")
def get_admin_course_preview(canonical_code: str, release_id: UUID | None = Query(default=None)) -> dict:
    """Backs "View as student" (requirements/43 AMC-14): the real student-reader
    shape for any release, including an unpublished DRAFT, so there is no second
    renderer to maintain."""
    return _call(courses.get_course_preview, canonical_code, str(release_id) if release_id else None)


@admin_router.post("/{canonical_code}/releases", status_code=201)
def create_admin_release(canonical_code: str, body: CreateRelease) -> dict:
    release_id = _call(
        courses.create_release,
        canonical_code,
        body.created_by,
        str(body.parent_release_id) if body.parent_release_id else None,
    )
    return {"release_id": release_id}


@admin_router.get("/releases/{release_id}")
def get_admin_release(release_id: UUID) -> dict:
    return _call(courses.get_release, str(release_id))


@admin_router.get("/releases/{release_id}/diff/{other_release_id}")
def diff_admin_releases(release_id: UUID, other_release_id: UUID) -> dict:
    return _call(courses.diff_releases, str(release_id), str(other_release_id))


@admin_router.post("/releases/{release_id}/modules", status_code=201)
def create_module(release_id: UUID, body: CreateModule) -> dict:
    module_id = _call(
        courses.add_module,
        str(release_id),
        body.module_key,
        body.ordinal,
        body.title,
        objective=body.objective,
        estimated_seconds=body.estimated_seconds,
        required=body.required,
    )
    return {"module_id": module_id}


@admin_router.post("/releases/{release_id}/states", status_code=201)
def create_state(release_id: UUID, body: CreateState) -> dict:
    state_id = _call(
        courses.add_state,
        str(release_id),
        body.state_key,
        body.ordinal,
        body.state_type,
        body.title,
        module_id=str(body.module_id) if body.module_id else None,
        objective=body.objective,
        student_instruction=body.student_instruction,
        estimated_seconds=body.estimated_seconds,
        required=body.required,
        skippable=body.skippable,
        agent_policy=body.agent_policy,
    )
    return {"state_id": state_id}


@admin_router.post("/states/{state_id}/bindings", status_code=201)
def bind_state(state_id: UUID, body: StateBinding) -> dict:
    _call(
        courses.bind_state_target,
        str(state_id),
        body.target_type,
        str(body.target_id),
        body.role,
        importance=body.importance,
        required_level=body.required_level,
    )
    return {"status": "BOUND"}


@admin_router.post("/states/{state_id}/interactions", status_code=201)
def bind_interaction(state_id: UUID, body: AttachInteraction) -> dict:
    _call(
        courses.attach_interaction,
        str(state_id),
        str(body.interaction_instance_id),
        body.ordinal,
        body.required,
    )
    return {"status": "BOUND"}


@admin_router.post("/states/{state_id}/assets", status_code=201)
async def upload_state_asset(
    state_id: UUID,
    request: Request,
    title: str = Query(min_length=1, max_length=300),
    presentation_role: Literal["PRIMARY", "SUPPORT", "EXAMPLE", "REFERENCE", "OPTIONAL"] = "SUPPORT",
    reviewed_by: str = Query(min_length=1, max_length=200),
    admin_confirmed: bool = Query(default=False),
    rights_note: str | None = Query(default=None, max_length=1000),
) -> dict:
    if not admin_confirmed:
        raise HTTPException(
            status_code=422,
            detail="Confirm that this asset has been reviewed before uploading it.",
        )
    mime_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    asset_type = _ASSET_TYPES.get(mime_type)
    if asset_type is None:
        raise HTTPException(status_code=415, detail="This asset media type is not supported.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > object_store.MAX_OBJECT_BYTES:
            raise HTTPException(status_code=413, detail="The uploaded asset exceeds 25 MB.")
        data.extend(chunk)
    if not data:
        raise HTTPException(status_code=422, detail="The uploaded asset is empty.")
    try:
        stored = object_store.put_bytes(bytes(data), asset_type[0])
    except (object_store.ObjectStoreError, ValueError) as exc:
        logger.exception("Micro-course asset upload failed")
        raise HTTPException(status_code=503, detail="Private asset storage is unavailable.") from exc
    try:
        asset_id = _call(
            courses.register_uploaded_asset,
            str(state_id),
            stored["object_key"],
            mime_type,
            stored["sha256"],
            stored["size_bytes"],
            title,
            asset_type[1],
            presentation_role,
            reviewed_by,
            rights_note,
        )
    except HTTPException:
        try:
            object_store.delete_object(stored["object_key"])
        except (object_store.ObjectStoreError, OSError, ValueError) as cleanup_error:
            logger.exception("Unregistered micro-course object cleanup failed")
            raise HTTPException(
                status_code=503,
                detail="Asset registration failed and private storage cleanup needs attention.",
            ) from cleanup_error
        raise
    return {"asset_id": asset_id, "size_bytes": stored["size_bytes"], "status": "VALID"}


@admin_router.post("/releases/{release_id}/transitions", status_code=201)
def create_transition(release_id: UUID, body: CreateTransition) -> dict:
    transition_id = _call(
        courses.add_transition,
        str(release_id),
        str(body.from_state_id),
        str(body.to_state_id),
        body.transition_type,
        condition_type=body.condition_type,
        condition_payload=body.condition_payload,
        priority=body.priority,
    )
    return {"transition_id": transition_id}


@admin_router.post("/releases/{release_id}/validate")
def validate_admin_release(release_id: UUID) -> dict:
    errors = _call(courses.validate_release, str(release_id))
    return {"status": "VALID" if not errors else "REJECTED", "errors": errors}


@admin_router.post("/releases/{release_id}/review")
def review_admin_release(release_id: UUID, body: ReviewRequest) -> dict:
    return _call(
        courses.review_release,
        str(release_id),
        body.status,
        body.reviewer,
        body.note,
    )


@admin_router.post("/releases/{release_id}/publish")
def publish_admin_release(release_id: UUID, body: PublishRequest) -> dict:
    return _call(courses.publish_release, str(release_id), body.publisher)


@student_router.get("")
def list_student_courses(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    return _call(courses.list_published_courses, limit, offset)


@student_router.get("/{canonical_code}")
def get_student_course(canonical_code: str) -> dict:
    return _call(courses.get_published_course, canonical_code)


@student_router.get("/{canonical_code}/assets/{asset_id}/content")
def get_student_asset(canonical_code: str, asset_id: UUID) -> Response:
    asset = _call(courses.get_published_asset, canonical_code, str(asset_id))
    try:
        data = object_store.read_bytes(asset["object_key"])
    except (object_store.ObjectStoreError, OSError, ValueError) as exc:
        logger.exception("Published course asset is unavailable or corrupt")
        raise HTTPException(status_code=503, detail="Published course asset is unavailable.") from exc
    digest = hashlib.sha256(data).hexdigest()
    if (
        digest != asset["content_hash"]
        or (asset["object_size_bytes"] is not None and len(data) != asset["object_size_bytes"])
    ):
        logger.error("Published course asset failed relational integrity verification")
        raise HTTPException(
            status_code=503,
            detail="Published course asset failed integrity verification.",
        )
    return Response(
        content=data,
        media_type=asset["mime_type"],
        headers={
            "Cache-Control": "private, no-store",
            "Content-Disposition": f'inline; filename="course-asset-{asset_id}"',
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@student_router.post("/{canonical_code}/enroll", status_code=201)
def enroll_in_course(
    canonical_code: str, student_id: UUID = Depends(get_current_student_id)
) -> dict:
    """Create (or resume) the logged-in student's in-progress enrollment and return
    the pinned release's current state, exactly as the shared service layer defines it."""
    return _call(courses.start_enrollment, canonical_code, str(student_id))


@student_router.get("/enrollments/{enrollment_id}")
def get_enrollment(
    enrollment_id: UUID, student_id: UUID = Depends(get_current_student_id)
) -> dict:
    return _call(courses.get_enrollment_runtime, str(enrollment_id), str(student_id))


@student_router.post("/enrollments/{enrollment_id}/advance")
def advance_enrollment(
    enrollment_id: UUID,
    body: AdvanceEnrollment,
    student_id: UUID = Depends(get_current_student_id),
) -> dict:
    return _call(
        courses.advance_enrollment,
        str(enrollment_id), str(student_id), body.expected_state_version, body.action,
    )


@student_router.post("/enrollments/{enrollment_id}/responses")
def submit_response(
    enrollment_id: UUID,
    body: SubmitLearningItemResponse,
    student_id: UUID = Depends(get_current_student_id),
) -> dict:
    return _call(
        courses.submit_learning_item_response,
        str(enrollment_id), str(student_id), body.learning_item_id, body.choice_index,
    )


@student_router.post("/enrollments/{enrollment_id}/activity-responses")
def submit_activity_response_endpoint(
    enrollment_id: UUID,
    body: SubmitActivityResponse,
    student_id: UUID = Depends(get_current_student_id),
) -> dict:
    return _call(
        courses.submit_activity_response,
        str(enrollment_id), str(student_id), str(body.activity_id),
        choice_index=body.choice_index, value=body.value,
    )


@student_router.post("/enrollments/{enrollment_id}/interaction-events")
def record_interaction_event_endpoint(
    enrollment_id: UUID,
    body: RecordInteractionEvent,
    student_id: UUID = Depends(get_current_student_id),
) -> dict:
    event_id = _call(
        courses.record_interaction_event,
        str(enrollment_id), str(student_id), str(body.interaction_instance_id),
        event_type=body.event_type, semantic_action=body.semantic_action,
        control_key=body.control_key, object_id=body.object_id,
        before_state=body.before_state, action_payload=body.action_payload,
        after_state=body.after_state,
    )
    return {"interaction_event_id": event_id}
