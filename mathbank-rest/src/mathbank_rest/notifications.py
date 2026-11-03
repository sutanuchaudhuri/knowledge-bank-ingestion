"""Student/admin notifications service (requirements/59) — explicitly NOT an ML concern
(requirements/54 §2); an event-driven side effect of existing grading/review paths.

Storage is behind `mathbank_rest.stores.get_store("notify")` (requirement 71 WP3): the routers and callers use the
store; this module keeps the contracts and the PostgreSQL SQL that `PostgresNotifyStore` delegates to.

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

from mathbank_rest.stores.errors import NotFound

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
    acknowledged_by: str | None = None


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
    next_token: str | None = None  # DynamoDB backend only: signed cursor for the next page


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


def _iso(value) -> str | None:
    return None if value is None else value.isoformat() if hasattr(value, "isoformat") else str(value)


def _event(row) -> NotificationEvent:
    return NotificationEvent(
        notification_id=row["notification_id"], recipient_type=row["recipient_type"], recipient_id=row["recipient_id"],
        notification_type=row["notification_type"], severity=row["severity"], title=row["title"], body=row["body"],
        payload_json=row["payload_json"] or {}, read_at=_iso(row["read_at"]), created_at=_iso(row["created_at"]))


def list_notifications(conn, *, recipient_type: RecipientType, recipient_id: str | None = None,
                         limit: int = 25, offset: int = 0, unread_only: bool = False) -> NotificationListResponse:
    """Newest first. `recipient_id=None` lists every recipient of that type (the admin inbox, which is shared)."""
    where = "recipient_type = :rt AND (CAST(:rid AS text) IS NULL OR recipient_id = :rid)"
    params = {"rt": recipient_type, "rid": recipient_id}
    rows = conn.execute(
        text(f"""
        SELECT notification_id, recipient_type, recipient_id, notification_type, severity, title, body,
               payload_json, read_at, created_at
          FROM notification.event
         WHERE {where} {"AND read_at IS NULL" if unread_only else ""}
         ORDER BY created_at DESC, notification_id DESC
         LIMIT :limit OFFSET :offset
    """),
        {**params, "limit": max(1, min(limit, 200)), "offset": max(0, offset)},
    ).mappings().all()
    unread = conn.execute(
        text(f"SELECT count(*) FROM notification.event WHERE {where} AND read_at IS NULL"), params).scalar_one()
    return NotificationListResponse(notifications=[_event(r) for r in rows], unread_count=int(unread))


def mark_read(conn, *, notification_id: str, recipient_id: str | None, recipient_type: RecipientType = "STUDENT") -> bool:
    """Marks one notification read; idempotent. The recipient is part of the WHERE clause, so one recipient can never
    mark another's notification: an id that is not theirs is `NotFound` (404), exactly like an unknown id.
    Returns True when it was unread before."""
    row = conn.execute(
        text("""
        WITH cur AS (
            SELECT notification_id, read_at FROM notification.event
             WHERE notification_id = :id AND recipient_type = :rt
               AND (CAST(:rid AS text) IS NULL OR recipient_id = :rid)
               FOR UPDATE
        )
        UPDATE notification.event e SET read_at = COALESCE(e.read_at, now())
          FROM cur WHERE e.notification_id = cur.notification_id
        RETURNING (cur.read_at IS NULL) AS was_unread
    """),
        {"id": notification_id, "rt": recipient_type, "rid": recipient_id},
    ).mappings().one_or_none()
    if row is None:
        raise NotFound("notification not found")
    return bool(row["was_unread"])


def mark_all_read(conn, *, recipient_type: RecipientType, recipient_id: str) -> int:
    return conn.execute(
        text("""
        UPDATE notification.event SET read_at = now()
         WHERE recipient_type = :rt AND recipient_id = :rid AND read_at IS NULL
    """),
        {"rt": recipient_type, "rid": recipient_id},
    ).rowcount


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
