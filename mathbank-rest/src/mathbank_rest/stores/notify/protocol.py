"""Contract of the ``notify`` store (requirement 71 WP3): the student inbox and the shared admin inbox.

Both backends return the pydantic contracts of ``mathbank_rest.notifications`` so the routers do not care which one is
selected. Ownership is structural: the recipient comes from the caller's credential, never from the URL, and a
notification that is not the caller's is indistinguishable from one that does not exist (``NotFound``, HTTP 404).
"""
from __future__ import annotations

from typing import Protocol

from mathbank_rest.notifications import NotificationCreate, NotificationListResponse, RecipientType


class NotifyStore(Protocol):
    backend: str

    def record_notification(self, notification: NotificationCreate, *, dedupe_key: str | None = None) -> str:
        """Create one notification; returns its id. With ``dedupe_key`` a redelivery returns the first id and writes nothing."""

    def list_notifications(self, *, recipient_type: RecipientType, recipient_id: str, limit: int = 25, offset: int = 0,
                           next_token: str | None = None, unread_only: bool = False) -> NotificationListResponse: ...

    def count_unread(self, *, recipient_type: RecipientType, recipient_id: str) -> int: ...

    def mark_read(self, *, notification_id: str, recipient_id: str) -> bool:
        """Student marks their own notification read (idempotent). True when it was unread before; NotFound when not theirs."""

    def mark_all_read(self, *, recipient_id: str) -> int: ...

    def list_admin_notifications(self, *, limit: int = 25, offset: int = 0, next_token: str | None = None,
                                 unread_only: bool = False, notification_type: str | None = None) -> NotificationListResponse: ...

    def admin_ack(self, *, notification_id: str, actor_id: str) -> dict:
        """Staff acknowledges a notification of the shared admin inbox, recording who did it. Idempotent."""
