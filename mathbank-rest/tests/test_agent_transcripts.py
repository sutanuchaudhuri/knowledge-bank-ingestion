"""Agent session ↔ student links and transcript reconstruction (requirements/22).

Offline tests cover event → transcript shaping and route guards. Live tests
(MATHBANK_LIVE_STEP_RUNTIME_TEST=1) run inside one transaction that always rolls back.
"""
from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_rest import agent_transcripts as at
from mathbank_rest.main import app

client = TestClient(app)


def _auth(student_id):
    from mathbank_rest import security

    return {"Authorization": "Bearer " + security.create_access_token(student_id)}


def _ev(author, *parts, partial=False, ts="2026-01-01T00:00:00"):
    return {"timestamp": ts, "event_data": {"author": author, "partial": partial, "content": {"role": "x", "parts": list(parts)}}}


EVENTS = [
    _ev("user", {"text": "What is the power of a point?"}),
    _ev("mathbank_tutor", {"text": "Let me", "thought": False}, partial=True),
    _ev("mathbank_tutor", {"text": "I should search the corpus", "thought": True}),
    _ev("mathbank_tutor", {"function_call": {"name": "hybrid_search", "args": {"q": "power of a point"}}}),
    _ev("mathbank_tutor", {"function_response": {"name": "hybrid_search", "response": {"hits": ["x" * 5000]}}}),
    _ev("mathbank_tutor", {"text": "The power of P is PA·PB."}),
    _ev("mathbank_tutor", {"text": "   "}),
]


def test_student_transcript_hides_thinking_tools_and_partials():
    msgs = at.build_transcript(EVENTS, include_tools=False)
    assert [(m["role"], m["kind"], m["text"]) for m in msgs] == [
        ("student", "text", "What is the power of a point?"),
        ("tutor", "text", "The power of P is PA·PB."),
    ]


def test_admin_transcript_includes_thinking_and_truncated_tools():
    msgs = at.build_transcript(EVENTS, include_tools=True)
    kinds = [m["kind"] for m in msgs]
    assert kinds == ["text", "thinking", "tool_call", "tool_result", "text"]
    call = msgs[2]
    assert call["tool"] == "hybrid_search" and json.loads(call["text"]) == {"q": "power of a point"}
    assert len(msgs[3]["text"]) == at.TOOL_PAYLOAD_LIMIT + 1 and msgs[3]["text"].endswith("…")


def test_agent_session_routes_require_auth_and_admin_key():
    assert client.post("/v1/learner/agent-sessions", json={"agent_session_id": "s"}).status_code == 401
    assert client.get("/v1/learner/agent-sessions").status_code == 401
    assert client.get("/v1/learner/agent-sessions/s/transcript").status_code == 401
    assert client.get("/v1/admin/agent-sessions", headers=_auth(uuid4())).status_code == 401
    assert client.get("/v1/admin/agent-sessions/s/transcript", headers=_auth(uuid4())).status_code == 401


def test_link_request_rejects_unknown_surface():
    r = client.post("/v1/learner/agent-sessions", json={"agent_session_id": "s", "surface": "EMAIL"}, headers=_auth(uuid4()))
    assert r.status_code == 422


# ---------------------------------------------------------------- live (rolled back)

live = pytest.mark.skipif(os.getenv("MATHBANK_LIVE_STEP_RUNTIME_TEST") != "1", reason="Live Postgres opt-in")


@pytest.fixture
def live_conn():
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        tx = conn.begin()
        try:
            yield conn
        finally:
            tx.rollback()


def _student(conn):
    return conn.execute(text(
        "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
        "VALUES (:e, 'x', 'Live', 'Test', 'Live Test') RETURNING student_id"),
        {"e": f"live-{uuid4()}@example.com"}).scalar_one()


def _agent_session(conn, user_id, session_id):
    conn.execute(text(f"INSERT INTO {at.AGENT_SCHEMA}.sessions (app_name, user_id, id, state, create_time, update_time) "
                      "VALUES (:a, :u, :s, '{}'::jsonb, now(), now())"),
                 {"a": at.DEFAULT_APP_NAME, "u": user_id, "s": session_id})
    for i, (author, txt) in enumerate([("user", "Explain power of a point"), ("mathbank_tutor", "PA·PB is constant.")]):
        data = {"author": author, "content": {"role": "user" if author == "user" else "model", "parts": [{"text": txt}]}}
        conn.execute(text(f"INSERT INTO {at.AGENT_SCHEMA}.events (id, app_name, user_id, session_id, invocation_id, timestamp, event_data) "
                          "VALUES (:id, :a, :u, :s, 'inv', now() + make_interval(secs => :i), CAST(:d AS jsonb))"),
                     {"id": str(uuid4()), "a": at.DEFAULT_APP_NAME, "u": user_id, "s": session_id, "i": i, "d": json.dumps(data)})


@live
def test_live_link_list_and_transcripts(live_conn):
    sid = _student(live_conn)
    other = _student(live_conn)
    session_id = f"live-{uuid4()}"
    _agent_session(live_conn, str(sid), session_id)

    with pytest.raises(at.NotFound):  # cannot claim a session created under another identity
        at.register_link(live_conn, other, session_id)
    first = at.register_link(live_conn, sid, session_id, context={"problem_code": "X"})
    again = at.register_link(live_conn, sid, session_id)
    assert first["created"] and not again["created"]

    mine = at.list_student_sessions(live_conn, sid)
    assert [m["agent_session_id"] for m in mine] == [session_id]
    assert mine[0]["event_count"] == 2 and mine[0]["preview"].startswith("Explain")
    assert at.list_student_sessions(live_conn, other) == []

    t = at.transcript(live_conn, session_id, student_id=sid, include_tools=False)
    assert [m["role"] for m in t["messages"]] == ["student", "tutor"] and t["context"] == {"problem_code": "X"}
    with pytest.raises(at.NotFound):
        at.transcript(live_conn, session_id, student_id=other, include_tools=False)
    admin = at.transcript(live_conn, session_id, student_id=None, include_tools=True)
    assert admin["linked"] and admin["student_id"] == str(sid)
    assert any(r["agent_session_id"] == session_id for r in at.list_all_sessions(live_conn, str(sid))["linked"])


def test_naive_adk_timestamps_are_emitted_as_utc():
    from datetime import datetime, timedelta, timezone

    from mathbank_rest.agent_transcripts import _iso_utc

    assert _iso_utc(datetime(2026, 10, 5, 22, 5, 14)) == "2026-10-05T22:05:14+00:00"
    aware = datetime(2026, 10, 5, 18, 5, tzinfo=timezone(timedelta(hours=-4)))
    assert _iso_utc(aware) == "2026-10-05T18:05:00-04:00"
    assert _iso_utc(None) is None
