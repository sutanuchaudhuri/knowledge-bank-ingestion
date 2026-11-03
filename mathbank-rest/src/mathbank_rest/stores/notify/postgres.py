"""``notify`` store, PostgreSQL backend: delegates to the SQL in ``mathbank_rest.notifications`` (``notification.event``,
migration 043). Behaviour of the existing ``record_notification`` is unchanged; Postgres has no dedupe or acknowledged_by
column, so ``dedupe_key`` is ignored and the acknowledging actor is only logged.
"""
from __future__ import annotations

import logging

from mathbank_rest import notifications
from mathbank_rest.db.postgres import engine
from mathbank_rest.notifications import NotificationCreate, NotificationListResponse, RecipientType

LOG = logging.getLogger("mathbank_rest.stores.notify")


class PostgresNotifyStore:
    backend = "postgres"

    def record_notification(self, notification: NotificationCreate, *, dedupe_key: str | None = None) -> str:
        with engine.begin() as conn:
            return notifications.record_notification(conn, notification)

    def list_notifications(self, *, recipient_type: RecipientType, recipient_id: str, limit: int = 25, offset: int = 0,
                           next_token: str | None = None, unread_only: bool = False) -> NotificationListResponse:
        with engine.connect() as conn:
            return notifications.list_notifications(conn, recipient_type=recipient_type, recipient_id=recipient_id,
                                                    limit=limit, offset=offset, unread_only=unread_only)

    def count_unread(self, *, recipient_type: RecipientType, recipient_id: str) -> int:
        return self.list_notifications(recipient_type=recipient_type, recipient_id=recipient_id, limit=1).unread_count

    def mark_read(self, *, notification_id: str, recipient_id: str) -> bool:
        with engine.begin() as conn:
            return notifications.mark_read(conn, notification_id=notification_id, recipient_id=recipient_id)

    def mark_all_read(self, *, recipient_id: str) -> int:
        with engine.begin() as conn:
            return notifications.mark_all_read(conn, recipient_type="STUDENT", recipient_id=recipient_id)

    def list_admin_notifications(self, *, limit: int = 25, offset: int = 0, next_token: str | None = None,
                                 unread_only: bool = False, notification_type: str | None = None) -> NotificationListResponse:
        with engine.connect() as conn:
            page = notifications.list_notifications(conn, recipient_type="ADMIN", recipient_id=None, limit=limit,
                                                    offset=offset, unread_only=unread_only)
        if notification_type:
            page.notifications = [n for n in page.notifications if n.notification_type == notification_type]
        return page

    def admin_ack(self, *, notification_id: str, actor_id: str) -> dict:
        with engine.begin() as conn:
            newly = notifications.mark_read(conn, notification_id=notification_id, recipient_id=None, recipient_type="ADMIN")
        LOG.info("notification %s acknowledged by %s", notification_id, actor_id)
        return {"notification_id": notification_id, "acknowledged": True, "acknowledged_by": actor_id,
                "newly_acknowledged": newly}
