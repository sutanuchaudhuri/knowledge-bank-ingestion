"""Agent conversation transcripts (requirements/22_AGENT_SESSION_TRANSCRIPTS.md).

The ADK agent stores sessions/events in the framework-owned schema ``agent_sessions``. The project
table ``learner.agent_session_link`` maps a student to the agent sessions they own, so the whole
conversation can be rebuilt from ``agent_sessions.events.event_data`` for the student or an admin.

Read-only over ``agent_sessions``; the only write is the idempotent link upsert.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text


def _iso_utc(value: datetime | None) -> str | None:
    """ADK stores naive UTC timestamps; emit explicit UTC so browsers don't treat them as local."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()

AGENT_SCHEMA = "agent_sessions"
DEFAULT_APP_NAME = "mathbank_tutor"
SURFACES = ("HOME_CHAT", "SOLVE_WORKSPACE", "OTHER")
TOOL_PAYLOAD_LIMIT = 2000
TUTOR_IDLE_EVENT = re.compile(r"\[Tutor idle:([0-9a-f-]{36}):(hint|explain)\]")


class TranscriptError(Exception):
    status_code = 400
    code = "BAD_REQUEST"


class NotFound(TranscriptError):
    status_code = 404
    code = "NOT_FOUND"


class Conflict(TranscriptError):
    status_code = 409
    code = "SESSION_OWNED_BY_ANOTHER_STUDENT"


def _agent_schema_present(conn) -> bool:
    return conn.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": f"{AGENT_SCHEMA}.events"}).scalar()


def _truncate(value: Any) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    return raw if len(raw) <= TOOL_PAYLOAD_LIMIT else raw[:TOOL_PAYLOAD_LIMIT] + "…"


def build_transcript(events: list[dict], *, include_tools: bool) -> list[dict]:
    """Turn ADK event dumps (ordered) into transcript messages.

    Streaming ``partial`` chunks are dropped (the final event repeats the full text). Students see
    only their own text and the tutor's visible replies; admins also get thinking, tool calls and
    (truncated) tool results.
    """
    messages: list[dict] = []
    for ev in events:
        data = ev.get("event_data") or {}
        if data.get("partial"):
            continue
        author = data.get("author") or "unknown"
        role = "student" if author == "user" else "tutor"
        ts = ev.get("timestamp")
        parts = ((data.get("content") or {}).get("parts")) or []
        for part in parts:
            if part.get("text") is not None:
                if part.get("thought"):
                    if include_tools:
                        messages.append({"role": role, "kind": "thinking", "text": part["text"], "author": author, "timestamp": ts})
                    continue
                idle = TUTOR_IDLE_EVENT.fullmatch(part["text"].strip()) if author == "user" else None
                if idle:
                    if include_tools:
                        messages.append({
                            "role": "system", "kind": "text",
                            "text": f"Active thinking window elapsed: {idle.group(2)}.",
                            "author": "tutor_pacing", "timestamp": ts,
                        })
                    continue
                if part["text"].strip():
                    messages.append({"role": role, "kind": "text", "text": part["text"], "author": author, "timestamp": ts})
            elif include_tools and part.get("function_call"):
                fc = part["function_call"]
                messages.append({"role": role, "kind": "tool_call", "tool": fc.get("name"),
                                 "text": _truncate(fc.get("args") or {}), "author": author, "timestamp": ts})
            elif include_tools and part.get("function_response"):
                fr = part["function_response"]
                messages.append({"role": role, "kind": "tool_result", "tool": fr.get("name"),
                                 "text": _truncate(fr.get("response") or {}), "author": author, "timestamp": ts})
        if include_tools and data.get("error_message"):
            messages.append({"role": "system", "kind": "error", "text": str(data["error_message"])[:500],
                             "author": author, "timestamp": ts})
    return messages


def register_link(conn, student_id: UUID, session_id: str, *, app_name: str = DEFAULT_APP_NAME,
                  surface: str = "HOME_CHAT", context: dict | None = None) -> dict:
    """Idempotently link an agent session to the student who owns it.

    The ADK session row must already exist with ``user_id = student_id`` — a student can never claim
    a session created under another identity (or an anonymous one).
    """
    if surface not in SURFACES:
        raise TranscriptError(f"surface must be one of {SURFACES}")
    if not _agent_schema_present(conn):
        raise NotFound("agent session store is not initialised")
    owner = str(student_id)
    exists = conn.execute(text(
        f"SELECT 1 FROM {AGENT_SCHEMA}.sessions WHERE app_name = :a AND user_id = :u AND id = :s"),
        {"a": app_name, "u": owner, "s": session_id}).scalar()
    if not exists:
        raise NotFound("agent session not found for this student")
    row = conn.execute(text(
        "INSERT INTO learner.agent_session_link (agent_app_name, agent_user_id, agent_session_id, student_id, surface, context) "
        "VALUES (:a, :u, :s, :sid, :surface, CAST(:ctx AS jsonb)) "
        "ON CONFLICT (agent_app_name, agent_session_id) DO UPDATE SET last_seen_at = now(), "
        "  context = learner.agent_session_link.context || EXCLUDED.context "
        "  WHERE learner.agent_session_link.student_id = EXCLUDED.student_id "
        "RETURNING agent_session_link_id::text, (xmax = 0) AS created"),
        {"a": app_name, "u": owner, "s": session_id, "sid": owner, "surface": surface,
         "ctx": json.dumps(context or {})}).mappings().first()
    if row is None:
        raise Conflict("agent session is linked to another student")
    return {"agent_session_link_id": row["agent_session_link_id"], "created": bool(row["created"]),
            "agent_session_id": session_id, "agent_app_name": app_name, "surface": surface}


_LIST_SQL = (
    "SELECT l.agent_session_link_id::text, l.agent_app_name, l.agent_session_id, l.agent_user_id, "
    "       l.student_id::text, sp.email, l.surface, l.context, l.created_at, l.last_seen_at, "
    "       s.update_time AS session_updated_at, "
    "       (SELECT count(*) FROM {schema}.events e WHERE e.app_name = l.agent_app_name AND e.user_id = l.agent_user_id "
    "          AND e.session_id = l.agent_session_id AND COALESCE((e.event_data->>'partial')::boolean, false) = false) AS event_count, "
    "       (SELECT e.event_data->'content'->'parts'->0->>'text' FROM {schema}.events e WHERE e.app_name = l.agent_app_name "
    "          AND e.user_id = l.agent_user_id AND e.session_id = l.agent_session_id AND e.event_data->>'author' = 'user' "
    "          ORDER BY e.timestamp LIMIT 1) AS first_message "
    "  FROM learner.agent_session_link l JOIN learner.student_profile sp ON sp.student_id = l.student_id "
    "  LEFT JOIN {schema}.sessions s ON s.app_name = l.agent_app_name AND s.user_id = l.agent_user_id AND s.id = l.agent_session_id "
)


def _shape(row) -> dict:
    out = dict(row)
    first = out.pop("first_message", None)
    out["preview"] = (first or "")[:160]
    for k in ("created_at", "last_seen_at", "session_updated_at"):
        if out.get(k) is not None:
            out[k] = _iso_utc(out[k])
    out["session_missing"] = out.get("session_updated_at") is None
    return out


def list_student_sessions(conn, student_id: UUID, limit: int = 50) -> list[dict]:
    if not _agent_schema_present(conn):
        return []
    rows = conn.execute(text(_LIST_SQL.format(schema=AGENT_SCHEMA) +
                             "WHERE l.student_id = :sid ORDER BY COALESCE(s.update_time, l.last_seen_at) DESC LIMIT :lim"),
                        {"sid": str(student_id), "lim": limit}).mappings().all()
    return [_shape(r) for r in rows]


def list_all_sessions(conn, student: str | None = None, limit: int = 100) -> dict:
    if not _agent_schema_present(conn):
        return {"linked": [], "unlinked_count": 0}
    where, params = "", {"lim": limit}
    if student:
        where = "WHERE (l.student_id::text = :who OR sp.email ILIKE '%' || :who || '%') "
        params["who"] = student
    rows = conn.execute(text(_LIST_SQL.format(schema=AGENT_SCHEMA) + where +
                             "ORDER BY COALESCE(s.update_time, l.last_seen_at) DESC LIMIT :lim"), params).mappings().all()
    unlinked = conn.execute(text(
        f"SELECT count(*) FROM {AGENT_SCHEMA}.sessions s WHERE NOT EXISTS (SELECT 1 FROM learner.agent_session_link l "
        "WHERE l.agent_app_name = s.app_name AND l.agent_session_id = s.id AND l.agent_user_id = s.user_id)")).scalar()
    return {"linked": [_shape(r) for r in rows], "unlinked_count": int(unlinked or 0)}


def _events(conn, app_name: str, user_id: str, session_id: str) -> list[dict]:
    rows = conn.execute(text(
        f"SELECT timestamp, event_data FROM {AGENT_SCHEMA}.events "
        "WHERE app_name = :a AND user_id = :u AND session_id = :s ORDER BY timestamp, id"),
        {"a": app_name, "u": user_id, "s": session_id}).mappings().all()
    out = []
    for r in rows:
        data = r["event_data"]
        if isinstance(data, str):
            data = json.loads(data)
        out.append({"timestamp": _iso_utc(r["timestamp"]), "event_data": data})
    return out


def transcript(conn, session_id: str, *, student_id: UUID | None, include_tools: bool,
               app_name: str = DEFAULT_APP_NAME) -> dict:
    """Rebuild one conversation. ``student_id`` set → must be that student's linked session."""
    if not _agent_schema_present(conn):
        raise NotFound("agent session store is not initialised")
    link = conn.execute(text(
        "SELECT l.agent_user_id, l.student_id::text, sp.email, l.surface, l.context, l.created_at "
        "FROM learner.agent_session_link l JOIN learner.student_profile sp ON sp.student_id = l.student_id "
        "WHERE l.agent_app_name = :a AND l.agent_session_id = :s"), {"a": app_name, "s": session_id}).mappings().first()
    if student_id is not None:
        if link is None or link["student_id"] != str(student_id):
            raise NotFound("conversation not found")
        user_id = link["agent_user_id"]
    elif link is not None:
        user_id = link["agent_user_id"]
    else:
        owners = conn.execute(text(f"SELECT user_id FROM {AGENT_SCHEMA}.sessions WHERE app_name = :a AND id = :s"),
                              {"a": app_name, "s": session_id}).scalars().all()
        if not owners:
            raise NotFound("conversation not found")
        if len(owners) > 1:
            raise TranscriptError("session id is ambiguous across agent users")
        user_id = owners[0]
    session = conn.execute(text(
        f"SELECT create_time, update_time FROM {AGENT_SCHEMA}.sessions WHERE app_name = :a AND user_id = :u AND id = :s"),
        {"a": app_name, "u": user_id, "s": session_id}).mappings().first()
    messages = build_transcript(_events(conn, app_name, user_id, session_id), include_tools=include_tools)
    result = {
        "agent_session_id": session_id,
        "agent_app_name": app_name,
        "student_id": link["student_id"] if link else None,
        "surface": link["surface"] if link else None,
        "context": link["context"] if link else {},
        "created_at": _iso_utc(session["create_time"]) if session else None,
        "updated_at": _iso_utc(session["update_time"]) if session else None,
        "messages": messages,
    }
    if include_tools:
        result["email"] = link["email"] if link else None
        result["agent_user_id"] = user_id
        result["linked"] = link is not None
    return result
