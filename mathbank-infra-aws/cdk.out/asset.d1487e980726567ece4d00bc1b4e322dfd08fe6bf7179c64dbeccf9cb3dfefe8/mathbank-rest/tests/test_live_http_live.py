"""HTTP golden flow through the fluid/live routers (opt-in: MATHBANK_LIVE_FLUID_TEST=1).

Routers commit, so this test cleans up after itself: live.session cascades, authoring rows are purged with
``authoring.allow_purge`` (test-only bypass of the published-plan immutability trigger), and the synthetic
student is deleted.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_rest import security
from mathbank_rest.config import settings
from mathbank_rest.main import app
from mathbank_rest.routers import live as live_router

pytestmark = pytest.mark.skipif(os.getenv("MATHBANK_LIVE_FLUID_TEST") != "1", reason="Live Postgres opt-in")

client = TestClient(app)
ADMIN = {"X-Admin-Api-Key": settings.admin_api_key or "", "X-Actor-Id": "pytest"}


@pytest.fixture
def world():
    from mathbank_rest.db.postgres import engine

    created = {"plans": [], "sessions": [], "students": []}
    yield created, engine
    with engine.begin() as conn:
        for sid in created["sessions"]:
            conn.execute(text("DELETE FROM visual.widget_spec WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid})
            conn.execute(text("DELETE FROM live.session WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid})
        conn.execute(text("SET LOCAL authoring.allow_purge = 'on'"))
        for pid in created["plans"]:
            conn.execute(text("DELETE FROM authoring.presentation_plan WHERE plan_id = CAST(:p AS uuid) "
                              "OR parent_plan_id = CAST(:p AS uuid)"), {"p": pid})
        for st in created["students"]:
            conn.execute(text("DELETE FROM learner.student_profile WHERE student_id = CAST(:s AS uuid)"), {"s": st})


def test_plan_to_live_session_http_flow(world, monkeypatch):
    created, engine = world
    if not settings.admin_api_key:
        pytest.skip("admin key not configured")

    plan = client.post("/v1/authoring/presentation-plans", headers=ADMIN, json={
        "title": "Power of a point (pytest)", "course_limit_seconds": 1500, "hard_limit": True,
        "topics": [{"title": "Secants", "planned_seconds": 600}, {"title": "Chords", "planned_seconds": 600,
                                                                   "required": False}]})
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["plan_id"]
    created["plans"].append(plan_id)

    chat = client.post("/v1/authoring/chat/sessions", headers=ADMIN, json={"plan_id": plan_id})
    assert chat.status_code in (200, 201), chat.text
    chat_id = chat.json()["chat_session_id"]
    reply = client.post(f"/v1/authoring/chat/sessions/{chat_id}/messages", headers=ADMIN,
                        json={"content": "add 10 minutes to topic 1"})
    assert reply.status_code in (200, 201), reply.text
    patch = reply.json()["patches"][-1]
    assert not patch["validation"]["valid"]  # 1500s hard limit would be exceeded
    alt = client.post(f"/v1/authoring/chat/sessions/{chat_id}/proposed-patches/{patch['patch_id']}/apply",
                      headers=ADMIN, json={"action": "ASK_FOR_ALTERNATIVE"})
    assert alt.status_code == 200, alt.text
    alternative = alt.json()["patches"][-1]
    assert alternative["validation"]["valid"] and alternative["proposer"] == "DETERMINISTIC_ALTERNATIVE"
    applied = client.post(f"/v1/authoring/chat/sessions/{chat_id}/proposed-patches/{alternative['patch_id']}/apply",
                          headers=ADMIN, json={"action": "APPLY"})
    assert applied.status_code == 200, applied.text

    assert client.post(f"/v1/authoring/presentation-plans/{plan_id}/approve", headers=ADMIN).status_code == 200

    session = client.post("/v1/live/sessions", headers=ADMIN, json={"plan_id": plan_id})
    assert session.status_code == 201, session.text
    s = session.json()
    created["sessions"].append(s["session_id"])
    sid = s["session_id"]

    started = client.post(f"/v1/live/sessions/{sid}/transition", headers=ADMIN,
                          json={"to": "START", "expected_session_version": s["state_version"]})
    assert started.status_code == 200, started.text
    version = started.json()["session_version"]
    stale = client.post(f"/v1/live/sessions/{sid}/transition", headers=ADMIN,
                        json={"to": "NEXT", "expected_session_version": version + 5})
    assert stale.status_code == 409

    with engine.begin() as conn:
        student_id = str(conn.execute(text(
            "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
            "VALUES (:e, 'x', 'Http', 'Fluid', 'Http Fluid') RETURNING student_id"),
            {"e": f"fluid-http-{uuid4()}@example.invalid"}).scalar_one())
    created["students"].append(student_id)
    student = {"Authorization": f"Bearer {security.create_access_token(student_id)}"}
    joined = client.post("/v1/live/sessions/join", headers=student, json={"join_code": s["join_code"]})
    assert joined.status_code == 200, joined.text
    view = client.get(f"/v1/live/sessions/{sid}/state", headers=student).json()
    assert view["me"]["role"] == "STUDENT" and "recommendations" not in view
    assert client.post(f"/v1/live/sessions/{sid}/commands", headers=student,
                       json={"command_type": "NEXT"}).status_code == 403

    monkeypatch.setattr(live_router, "RESPONDER",
                        lambda ctx, msg: {"text": r"Use $PA \cdot PB = PC \cdot PD$.", "widget_intent": "power of a point"})
    tutor = client.post(f"/v1/tutor/sessions/{sid}/messages", headers=ADMIN, json={"message": "help"})
    assert tutor.status_code == 200 and tutor.json()["delivered"] is True, tutor.text
    events = client.get(f"/v1/live/sessions/{sid}/events?after_sequence=0", headers=student).json()["events"]
    assert any(e["event_type"] == "tutor.message" for e in events)

    take = client.post(f"/v1/instructor/live/{sid}/overrides", headers=ADMIN, json={"action": "TAKEOVER"})
    assert take.status_code == 200, take.text
    blocked = client.post(f"/v1/tutor/sessions/{sid}/messages", headers=ADMIN, json={"message": "help"})
    assert blocked.status_code == 409

    rt = client.get(f"/v1/realtime/sessions/{sid}", headers=student).json()
    assert f"session:{sid}" in rt["rooms"] and any(r.startswith("student:") for r in rt["rooms"])
