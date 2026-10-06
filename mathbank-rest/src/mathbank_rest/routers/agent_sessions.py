"""Agent conversation transcripts (requirements/22_AGENT_SESSION_TRANSCRIPTS.md).

Students (JWT) register and read only their own linked agent sessions — user text and the tutor's
visible replies. Admins (X-Admin-Api-Key) list any student's sessions and read full transcripts
including thinking, tool calls and truncated tool results.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from mathbank_rest import agent_transcripts as at
from mathbank_rest import security
from mathbank_rest.db.postgres import engine

router = APIRouter(prefix="/v1", tags=["agent-sessions"])


class AgentSessionLinkRequest(BaseModel):
    agent_session_id: str = Field(min_length=1, max_length=200)
    surface: Literal["HOME_CHAT", "SOLVE_WORKSPACE", "OTHER"] = "HOME_CHAT"
    context: dict = Field(default_factory=dict, description="e.g. problem_code, solve_attempt_id")


def _run(fn, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return fn(conn, *args, **kwargs)
    except at.TranscriptError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from None


@router.post("/learner/agent-sessions")
def link_agent_session(body: AgentSessionLinkRequest,
                       current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Link an ADK session (created under this student's id) to the student. Idempotent."""
    return _run(at.register_link, current, body.agent_session_id, surface=body.surface, context=body.context)


@router.get("/learner/agent-sessions")
def my_agent_sessions(limit: int = Query(50, ge=1, le=200),
                      current: UUID = Depends(security.get_current_student_id)) -> list[dict]:
    """The student's conversations, newest first, with message counts and a preview."""
    return _run(at.list_student_sessions, current, limit)


@router.get("/learner/agent-sessions/{agent_session_id}/transcript")
def my_agent_transcript(agent_session_id: str, current: UUID = Depends(security.get_current_student_id)) -> dict:
    """Rebuilt conversation (student text + tutor replies only)."""
    return _run(at.transcript, agent_session_id, student_id=current, include_tools=False)


@router.get("/admin/agent-sessions", dependencies=[Depends(security.require_admin_api_key)])
def admin_agent_sessions(student: str | None = Query(None, max_length=200, description="e-mail substring or student uuid"),
                         limit: int = Query(100, ge=1, le=500)) -> dict:
    """Internal (X-Admin-Api-Key): linked conversations across students + count of unlinked (anonymous) sessions."""
    return _run(at.list_all_sessions, student, limit)


@router.get("/admin/agent-sessions/{agent_session_id}/transcript", dependencies=[Depends(security.require_admin_api_key)])
def admin_agent_transcript(agent_session_id: str) -> dict:
    """Internal (X-Admin-Api-Key): full transcript incl. thinking, tool calls and truncated tool results."""
    return _run(at.transcript, agent_session_id, student_id=None, include_tools=True)
