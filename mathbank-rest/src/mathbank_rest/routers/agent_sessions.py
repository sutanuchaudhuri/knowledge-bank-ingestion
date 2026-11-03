"""Agent conversation transcripts (requirements/22_AGENT_SESSION_TRANSCRIPTS.md).

Students (JWT) register and read only their own linked agent sessions — user text and the tutor's
visible replies. Admins (X-Admin-Api-Key) list any student's sessions and read full transcripts
including thinking, tool calls and truncated tool results.
"""
from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import agent_transcripts as at
from mathbank_rest import security, stores

router = APIRouter(prefix="/v1", tags=["agent-sessions"])
Student = Annotated[UUID, Depends(security.get_current_student_id)]


class AgentSessionLinkRequest(BaseModel):
    agent_session_id: str = Field(min_length=1, max_length=200)
    surface: Literal["HOME_CHAT", "SOLVE_WORKSPACE", "OTHER"] = "HOME_CHAT"
    context: dict = Field(default_factory=dict, description="e.g. problem_code, solve_attempt_id")


def _run(fn):
    """``fn(learner_store)`` with the transcript errors mapped to their HTTP status."""
    try:
        return fn(stores.get_store("learner"))
    except at.TranscriptError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from None
    except SQLAlchemyError as exc:
        raise HTTPException(503, "Agent session data unavailable.") from exc


@router.post("/learner/agent-sessions")
def link_agent_session(body: AgentSessionLinkRequest,
                       current: Student) -> dict:
    """Link an ADK session (created under this student's id) to the student. Idempotent."""
    return _run(lambda store: store.register_agent_link(current, body.agent_session_id, surface=body.surface,
                                                        context=body.context))


@router.get("/learner/agent-sessions")
def my_agent_sessions(current: Student, limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    """The student's conversations, newest first, with message counts and a preview."""
    return _run(lambda store: store.list_student_sessions(current, limit))


@router.get("/learner/agent-sessions/{agent_session_id}")
def my_agent_session(agent_session_id: str, current: Student) -> dict:
    """One of the student's linked conversations (same shape as a list entry); anyone else's is 404."""
    found = next((row for row in _run(lambda store: store.list_student_sessions(current, 200))
                  if row["agent_session_id"] == agent_session_id), None)
    if found is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "conversation not found"})
    return found


@router.delete("/learner/agent-sessions/{agent_session_id}", status_code=204)
def unlink_agent_session(agent_session_id: str, current: Student) -> Response:
    """Remove the link only (the ADK transcript stays); anyone else's session is 404."""
    if not _run(lambda store: store.unlink_agent_session(current, agent_session_id)):
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "conversation not found"})
    return Response(status_code=204)


@router.get("/learner/agent-sessions/{agent_session_id}/transcript")
def my_agent_transcript(agent_session_id: str, current: Student) -> dict:
    """Rebuilt conversation (student text + tutor replies only)."""
    return _run(lambda _store: at.read_transcript(agent_session_id, student_id=current, include_tools=False))


@router.get("/admin/agent-sessions", dependencies=[Depends(security.require_admin_api_key)])
def admin_agent_sessions(student: str | None = Query(None, max_length=200, description="e-mail substring or student uuid"),
                         limit: int = Query(100, ge=1, le=500),
                         next_token: str | None = Query(None, max_length=2000)) -> dict:
    """Internal (X-Admin-Api-Key): linked conversations across students + count of unlinked (anonymous) sessions."""
    return _run(lambda store: store.list_all_sessions(student, limit, next_token))


@router.get("/admin/agent-sessions/{agent_session_id}/transcript", dependencies=[Depends(security.require_admin_api_key)])
def admin_agent_transcript(agent_session_id: str) -> dict:
    """Internal (X-Admin-Api-Key): full transcript incl. thinking, tool calls and truncated tool results."""
    return _run(lambda _store: at.read_transcript(agent_session_id, student_id=None, include_tools=True))
