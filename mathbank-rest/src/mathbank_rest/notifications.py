"""Student/admin notifications service (requirements/59) — explicitly NOT an ML concern
(requirements/54 §2); an event-driven side effect of existing grading/review paths.

STATUS: scaffolded. The record_* functions below are fully-typed and documented, but
NONE of the existing grading functions they're meant to be called from
(quiz_runtime.submit_response, micro_course_service.submit_learning_item_response,
micro_course_service.submit_activity_response, micro_course_service.review_release/
publish_release) have actually been edited to call them yet (requirements/59 NOTIF-5 —
this pass is additive-only, by design, to stay low-risk).
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

NotificationType = Literal[
    "QUIZ_GRADED",
    "MICRO_COURSE_ITEM_GRADED",
    "MICRO_COURSE_ACTIVITY_GRADED",
    "MASTERY_MILESTONE",
    "ADMIN_DATA_GAP",
    "ADMIN_REVIEW_NEEDED",
]
Severity = Literal["INFO", "SUCCESS", "WARNING", "ACTION_NEEDED"]
RecipientType = Literal["STUDENT", "ADMIN"]


class NotificationEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_id: UUID
    recipient_type: RecipientType
    recipient_id: str
    notification_type: NotificationType
    severity: Severity
    title: str
    body: str | None = None
    payload_json: dict = Field(default_factory=dict)
    read_at: str | None = None
    created_at: str


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_type: RecipientType
    recipient_id: str
    notification_type: NotificationType
    severity: Severity = "INFO"
    title: str
    body: str | None = None
    payload_json: dict = Field(default_factory=dict)


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notifications: list[NotificationEvent]
    unread_count: int


def record_notification(conn, notification: NotificationCreate) -> str:
    """Inserts one `notification.event` row. This is the one real, implemented function
    in this module — everything else is a convenience wrapper around it, documented with
    the exact existing call site it would be wired into.

    TODO: requires migration 043 to be applied first (not done in this pass — see
    scripts/migrate_notifications.py). Calling this against a database without the
    `notification` schema will raise a SQLAlchemy ProgrammingError, not silently no-op.
    """
    row = conn.execute(
        text("""
        INSERT INTO notification.event
            (recipient_type, recipient_id, notification_type, severity, title, body, payload_json)
        VALUES (:recipient_type, :recipient_id, :notification_type, :severity, :title, :body,
                CAST(:payload_json AS jsonb))
        RETURNING notification_id
    """),
        {
            "recipient_type": notification.recipient_type,
            "recipient_id": notification.recipient_id,
            "notification_type": notification.notification_type,
            "severity": notification.severity,
            "title": notification.title,
            "body": notification.body,
            "payload_json": notification.payload_json,
        },
    ).scalar_one()
    return str(row)


# ---------------------------------------------------------------------------
# requirements/59 §4 — one wrapper per trigger, each documenting its exact intended call
# site. None of these are actually called by that existing function yet.
# ---------------------------------------------------------------------------


def record_quiz_graded(conn, *, student_id: str, quiz_id: str, score: float, is_correct: bool) -> str:
    """TODO: call this from `mathbank_rest.quiz_runtime.submit_response`, right before
    its final `return` statement, passing the just-computed grading result. Not wired
    yet."""
    return record_notification(conn, NotificationCreate(
        recipient_type="STUDENT", recipient_id=student_id, notification_type="QUIZ_GRADED",
        severity="SUCCESS" if is_correct else "INFO",
        title="Your quiz was graded",
        body=f"Score: {score:.0%}" if score is not None else None,
        payload_json={"quiz_id": quiz_id, "is_correct": is_correct},
    ))


def record_micro_course_item_graded(conn, *, student_id: str, course_code: str, item_id: str,
                                      is_correct: bool, gave_up: bool) -> str:
    """TODO: call this from
    `mathbank_rest.micro_course_service.submit_learning_item_response`, right before its
    final `return` statement. Not wired yet."""
    return record_notification(conn, NotificationCreate(
        recipient_type="STUDENT", recipient_id=student_id, notification_type="MICRO_COURSE_ITEM_GRADED",
        severity="SUCCESS" if is_correct else "INFO",
        title=f"Checkpoint result in {course_code}",
        payload_json={"item_id": item_id, "is_correct": is_correct, "gave_up": gave_up},
    ))


def record_micro_course_activity_graded(conn, *, student_id: str, course_code: str, activity_id: str,
                                          is_correct: bool, gave_up: bool) -> str:
    """TODO: call this from
    `mathbank_rest.micro_course_service.submit_activity_response`, right before its final
    `return` statement. Not wired yet."""
    return record_notification(conn, NotificationCreate(
        recipient_type="STUDENT", recipient_id=student_id, notification_type="MICRO_COURSE_ACTIVITY_GRADED",
        severity="SUCCESS" if is_correct else "INFO",
        title=f"Quiz result in {course_code}",
        payload_json={"activity_id": activity_id, "is_correct": is_correct, "gave_up": gave_up},
    ))


def record_admin_review_needed(conn, *, admin_id: str, release_id: str, course_code: str) -> str:
    """TODO: call this from `mathbank_rest.micro_course_service.review_release` (or
    `create_release`) when a new draft is ready for review. Not wired yet — needs a real
    "which admin(s) should be notified" resolution strategy first (all admins? the
    course's original author? TODO: decide before wiring)."""
    return record_notification(conn, NotificationCreate(
        recipient_type="ADMIN", recipient_id=admin_id, notification_type="ADMIN_REVIEW_NEEDED",
        severity="ACTION_NEEDED",
        title=f"{course_code} has a release ready for review",
        payload_json={"release_id": release_id},
    ))


def list_notifications(conn, *, recipient_type: RecipientType, recipient_id: str,
                         limit: int = 25, offset: int = 0) -> NotificationListResponse:
    """TODO: implement the SELECT + unread count. Not implemented in this pass — the
    schema/contracts are considered the priority deliverable, not the read path (the read
    path is the same simple query shape used throughout this repo's other list
    endpoints, low risk to add later)."""
    raise NotImplementedError("requirements/59 — notification listing")


def mark_read(conn, *, notification_id: str, recipient_id: str) -> None:
    """TODO: implement. Must verify `recipient_id` owns the notification before marking
    it read — never let one recipient mark another's notification read."""
    raise NotImplementedError("requirements/59 — mark notification read")


def _publish_realtime(notification: NotificationEvent) -> None:
    """requirements/59 §5 — reuses mathbank-live's existing Socket.IO `emitTo(rooms,
    event, data)` (confirmed present in mathbank-live/server.mjs) via a small new
    endpoint on that service.

    TODO: (1) add the new endpoint to mathbank-live itself (not in this package's scope —
    tracked here only as the call site this function would hit); (2) implement the HTTP
    POST from here once that endpoint exists. Not implemented — real-time delivery is
    optional/deferred per requirements/59 §5.
    """
    raise NotImplementedError("requirements/59 §5 — real-time publish (deferred)")
