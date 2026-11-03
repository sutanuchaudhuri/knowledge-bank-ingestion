"""requirements/59: student/admin notifications REST endpoints, served by the ``notify`` store (requirement 71 WP3).

Student routes require a valid student bearer token (get_current_student_id). The recipient is always the token's
student: it is part of the storage key, never of the URL, so another student's notification id is a 404, not a 403.

Admin routes (`/v1/admin/notifications`) take the admin credential and record who acted (`Actor.id`, never a
client-supplied name): the shared admin inbox lists, and acknowledging stores the actor on the notification.
"""
from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from mathbank_rest import stores
from mathbank_rest.notifications import NotificationListResponse
from mathbank_rest.security import Actor, get_current_student_id, require_admin_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/notifications", tags=["notifications"])
admin_router = APIRouter(prefix="/v1/admin/notifications", tags=["notifications"])
StudentId = Annotated[UUID, Depends(get_current_student_id)]
AdminActor = Annotated[Actor, Depends(require_admin_api_key)]
Limit = Annotated[int, Query(ge=1, le=200)]


@router.get("/me", response_model=NotificationListResponse)
def list_my_notifications(student_id: StudentId, limit: Limit = 25, offset: Annotated[int, Query(ge=0)] = 0,
                          next_token: str | None = None, unread: bool = False):
    return stores.get_store("notify").list_notifications(
        recipient_type="STUDENT", recipient_id=str(student_id), limit=limit, offset=offset, next_token=next_token,
        unread_only=unread)


@router.post("/me/read-all")
def mark_all_my_notifications_read(student_id: StudentId):
    return {"updated": stores.get_store("notify").mark_all_read(recipient_id=str(student_id))}


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: UUID, student_id: StudentId):
    stores.get_store("notify").mark_read(notification_id=str(notification_id), recipient_id=str(student_id))
    return {"notification_id": str(notification_id), "read": True}


@admin_router.get("", response_model=NotificationListResponse)
def list_admin_notifications(actor: AdminActor, limit: Limit = 25, offset: Annotated[int, Query(ge=0)] = 0,
                             next_token: str | None = None, unread: bool = False, notification_type: str | None = None):
    return stores.get_store("notify").list_admin_notifications(
        limit=limit, offset=offset, next_token=next_token, unread_only=unread, notification_type=notification_type)


@admin_router.post("/{notification_id}/ack")
def acknowledge_admin_notification(notification_id: UUID, actor: AdminActor):
    result = stores.get_store("notify").admin_ack(notification_id=str(notification_id), actor_id=actor.id)
    logger.info("notification %s acknowledged by %s", notification_id, actor.id)
    return result
