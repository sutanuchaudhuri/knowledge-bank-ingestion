"""requirements/59: student/admin notifications REST endpoints.

Student routes require a valid student bearer token (get_current_student_id), matching
every other learner.*-scoped resource in this service. Admin listing/read is not
implemented in this pass (requirements/59 scopes notifications creation triggers before
an admin notification inbox UI).
"""
from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from mathbank_rest import notifications
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import get_current_student_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/notifications", tags=["notifications"])
StudentId = Annotated[UUID, Depends(get_current_student_id)]


@router.get("/me")
def list_my_notifications(student_id: StudentId, limit: int = 25, offset: int = 0):
    """TODO (requirements/59): calls notifications.list_notifications, currently a stub
    (raises NotImplementedError) — converted to a 501 here rather than a bare 500, same
    convention as mathbank-ml-inference's scaffolded routes."""
    try:
        with engine.connect() as conn:
            return notifications.list_notifications(
                conn, recipient_type="STUDENT", recipient_id=str(student_id),
                limit=limit, offset=offset,
            )
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


@router.post("/{notification_id}/read")
def mark_notification_read(notification_id: UUID, student_id: StudentId):
    """TODO (requirements/59): calls notifications.mark_read, currently a stub."""
    try:
        with engine.begin() as conn:
            notifications.mark_read(conn, notification_id=str(notification_id), recipient_id=str(student_id))
        return {"notification_id": str(notification_id), "read": True}
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
