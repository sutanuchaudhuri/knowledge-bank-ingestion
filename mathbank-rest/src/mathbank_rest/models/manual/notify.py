"""Hand-written item models for ``mb-notify`` (student / admin notification inbox).

Source: requirement 70 §13 (C5) only. ``mathbank-db/aws/dynamo/specs/staff.py`` declares the table but has no
mapping (``notification.event`` never existed in Neon), so every shape below comes from the design and from
``mathbank_rest.notifications``. They are hand-written because the context had no data when the generated models
were built, so there was nothing to infer them from.
"""
from __future__ import annotations

from typing import Annotated, Any, ClassVar, Literal
from uuid import UUID

from pydantic import Field, StrictBool, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, JsonDoc, S3Ref, UtcDateTime

_UUID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_RCPT_PK = f"^RCPT#(STUDENT#{_UUID}|ADMIN)$"

NotificationType = Literal[
    "QUIZ_GRADED", "MICRO_COURSE_ITEM_GRADED", "MICRO_COURSE_ACTIVITY_GRADED", "MASTERY_MILESTONE",
    "ADMIN_DATA_GAP", "ADMIN_REVIEW_NEEDED"]
Severity = Literal["INFO", "SUCCESS", "WARNING", "ACTION_NEEDED"]
RecipientType = Literal["STUDENT", "ADMIN"]


class NotifyNotificationPayload(JsonDoc):
    """Union of the payload keys of every ``notification_type`` (``mathbank_rest.notifications.record_*``); the
    per-type split (NTF-S05) is not defined for MASTERY_MILESTONE / ADMIN_DATA_GAP yet, so unknown keys stay allowed."""

    quiz_id: StrictStr | None = None  # QUIZ_GRADED
    item_id: StrictStr | None = None  # MICRO_COURSE_ITEM_GRADED
    activity_id: StrictStr | None = None  # MICRO_COURSE_ACTIVITY_GRADED
    release_id: StrictStr | None = None  # ADMIN_REVIEW_NEEDED
    is_correct: StrictBool | None = None
    gave_up: StrictBool | None = None


class NotifyNotification(DdbItem, ctx="notify", item_type="NOTIFICATION"):
    type: Literal["NOTIFICATION"] = "NOTIFICATION"
    PK: str = Field(pattern=_RCPT_PK)
    SK: str = Field(pattern=f"^N#{_UUID}$")  # UUIDv7: time-ordered
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"payload", "body"})
    OFFLOAD_DOCS: ClassVar[dict[str, Any]] = {"payload": NotifyNotificationPayload}
    acknowledged_by: StrictStr | None = None
    body: StrictStr | None = None
    created_at: UtcDateTime
    dedupe_key: StrictStr | None = None
    notification_id: UUID | None = None
    notification_type: NotificationType
    payload: NotifyNotificationPayload | None = None
    read_at: UtcDateTime | None = None
    recipient_id: StrictStr | None = None
    recipient_type: RecipientType | None = None
    severity: Severity
    title: StrictStr
    body_ref: S3Ref | None = None
    payload_ref: S3Ref | None = None


class NotifyDedupe(DdbItem, ctx="notify", item_type="DEDUPE"):
    """UNIQUE(recipient, dedupe_key) sentinel, written in the same transaction as the notification."""

    type: Literal["DEDUPE"] = "DEDUPE"
    PK: str = Field(pattern=_RCPT_PK)
    SK: str = Field(pattern="^DEDUPE#.+$")  # dedupe_key is ``<table>#<PK>#<SK>#<version>``: it contains '#'
    notification_id: UUID


class NotifyInboxCounter(DdbItem, ctx="notify", item_type="INBOX_COUNTER"):
    type: Literal["INBOX_COUNTER"] = "INBOX_COUNTER"
    PK: str = Field(pattern=_RCPT_PK)
    SK: str = Field(pattern="^COUNTER$")
    unread_count: StrictInt = Field(ge=0)


ITEM_MODELS = [NotifyDedupe, NotifyInboxCounter, NotifyNotification]
NotifyItem = Annotated[NotifyDedupe | NotifyInboxCounter | NotifyNotification, Field(discriminator="type")]
