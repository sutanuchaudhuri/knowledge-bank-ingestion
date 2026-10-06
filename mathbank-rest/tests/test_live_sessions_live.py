"""Live session runtime golden flows against real Postgres (opt-in: MATHBANK_LIVE_FLUID_TEST=1).

Everything runs inside one transaction that always rolls back — nothing persists (GOT-TEST-2).
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import live_runtime as lr

pytestmark = pytest.mark.skipif(os.getenv("MATHBANK_LIVE_FLUID_TEST") != "1", reason="Live Postgres opt-in")

TOPICS = [{"title": "Secants", "planned_seconds": 600, "required": True},
          {"title": "Chords", "planned_seconds": 600, "required": False},
          {"title": "Tangents", "planned_seconds": 600, "required": True}]


@pytest.fixture
def conn():
    from mathbank_rest.db.postgres import engine

    with engine.connect() as c:
        tx = c.begin()
        try:
            yield c
        finally:
            tx.rollback()


def _student(conn):
    return str(conn.execute(text(
        "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
        "VALUES (:e, 'x', 'Live', 'Fluid', 'Live Fluid') RETURNING student_id"),
        {"e": f"fluid-{uuid4()}@example.invalid"}).scalar_one())


def _cmd(conn, sid, command, actor="INSTRUCTOR", actor_id="instructor:test", version=None, payload=None, ccid=None):
    return lr.execute_command(conn, sid, command, actor, actor_id, ccid or f"t-{uuid4().hex}", version, payload)


def _session(conn, **kw):
    s = lr.create_session(conn, {"title": "Power of a point live", "topics": [dict(t) for t in TOPICS],
                                 "hard_limit": True, **kw}, actor="test")
    started = _cmd(conn, s["session_id"], "START", version=s["state_version"])
    assert started["status"] == "ACCEPTED", started
    return s["session_id"], started["session_version"]


def test_start_stale_version_and_idempotent_retry(conn):
    sid, v = _session(conn)
    stale = _cmd(conn, sid, "NEXT", version=v - 1)
    assert stale["status"] == "REJECTED" and stale["error"]["code"] == "STALE_VERSION"
    first = _cmd(conn, sid, "NEXT", version=v, ccid="same-id")
    again = _cmd(conn, sid, "NEXT", version=v, ccid="same-id")
    assert first["status"] == "ACCEPTED" and again["duplicate"] is True
    assert lr.get_session(conn, sid)["current_topic_index"] == 1  # applied exactly once


def test_rejected_command_leaves_no_partial_writes(conn):
    sid, v = _session(conn)
    before = lr.get_session(conn, sid)["last_sequence"]
    bad = _cmd(conn, sid, "SHOW_WIDGET", version=v, payload={"spec": {"widget_type": "IFRAME"}})
    assert bad["status"] == "REJECTED" and bad["error"]["http_status"] == 422
    assert lr.get_session(conn, sid)["last_sequence"] == before
    assert conn.execute(text("SELECT count(*) FROM visual.widget_spec WHERE live_session_id = CAST(:s AS uuid)"),
                        {"s": sid}).scalar() == 0


def test_student_join_poll_aggregate_and_branch_recommendation(conn):
    sid, v = _session(conn)
    code = lr.get_session(conn, sid)["join_code"]
    students = [lr.join_session(conn, code, _student(conn)) for _ in range(5)]
    opened = _cmd(conn, sid, "OPEN_ACTIVITY", version=v, payload={"definition": {
        "activity_type": "MCQ", "prompt": "PA·PB equals?", "options": [{"key": "A", "label": "PC·PD"},
                                                                       {"key": "B", "label": "PC+PD"}],
        "correctness_policy": {"correct_option": "A"}}})
    assert opened["status"] == "ACCEPTED", opened
    instance = opened["event"]["payload"]["activity_instance_id"]
    for i, st in enumerate(students):
        r = _cmd(conn, sid, "RESPONSE_SUBMIT", actor="STUDENT", actor_id=st["participant_id"],
                 payload={"activity_instance_id": instance, "option": "A" if i < 2 else "B"})
        assert r["status"] == "ACCEPTED", r
    dup = _cmd(conn, sid, "RESPONSE_SUBMIT", actor="STUDENT", actor_id=students[0]["participant_id"],
               payload={"activity_instance_id": instance, "option": "B"})
    agg = lr.aggregate(conn, instance)
    assert agg["response_count"] == 5 and agg["option_counts"]["A"] in (2, 1)  # one response per participant
    assert dup["status"] in ("ACCEPTED", "REJECTED")
    closed = _cmd(conn, sid, "CLOSE_ACTIVITY", version=lr.get_session(conn, sid)["state_version"],
                  payload={"activity_instance_id": instance})
    assert closed["status"] == "ACCEPTED", closed
    recs = lr.list_recommendations(conn, sid, "PROPOSED")
    branch = [r for r in recs if r["source"] == "POLL_BRANCH"]
    assert branch and branch[0]["action"]["payload"]["branch"] == "PREREQUISITE"  # <= 40% correct
    decided = lr.decide_recommendation(conn, sid, branch[0]["recommendation_id"], "ACCEPT", "instructor:test",
                                       lr.get_session(conn, sid)["state_version"])
    assert decided["status"] == "ACCEPTED", decided


def test_students_cannot_issue_control_commands(conn):
    sid, v = _session(conn)
    st = lr.join_session(conn, lr.get_session(conn, sid)["join_code"], _student(conn))
    r = _cmd(conn, sid, "NEXT", actor="STUDENT", actor_id=st["participant_id"], version=v)
    assert r["status"] == "REJECTED" and r["error"]["code"] == "FORBIDDEN_COMMAND"
    outsider = _cmd(conn, sid, "QUESTION_ASK", actor="STUDENT", actor_id="student:nobody", payload={"text": "?"})
    assert outsider["error"]["code"] == "NOT_A_PARTICIPANT"


def test_takeover_stales_ai_and_blocks_tutor_messages(conn):
    sid, v = _session(conn)
    proposal = lr.propose_ai_action(conn, sid, {"command_type": "SHOW_WIDGET", "payload": {"spec": {}}},
                                    "show a diagram", v)
    assert proposal["status"] in ("PROPOSED", "ACCEPTED", "REJECTED")
    take = _cmd(conn, sid, "TAKEOVER", version=lr.get_session(conn, sid)["state_version"],
                payload={"scope": "SESSION"})
    assert take["status"] == "ACCEPTED" and take["handoff_packet"]["scope"] == "SESSION" and "recommended_next_move" in take["handoff_packet"]
    assert not lr.list_recommendations(conn, sid, "PROPOSED")  # pending AI recommendations went STALE
    msg = _cmd(conn, sid, "TUTOR_MESSAGE", actor="AI_TUTOR", actor_id="tutor",
               version=lr.get_session(conn, sid)["state_version"], payload={"text": "hi"})
    assert msg["error"]["code"] == "AI_NOT_IN_CONTROL"
    released = _cmd(conn, sid, "RELEASE", version=lr.get_session(conn, sid)["state_version"],
                    payload={"scope": "SESSION"})
    assert released["status"] == "ACCEPTED"
    ok = _cmd(conn, sid, "TUTOR_MESSAGE", actor="AI_TUTOR", actor_id="tutor",
              version=lr.get_session(conn, sid)["state_version"], payload={"text": "hi again"})
    assert ok["status"] == "ACCEPTED"


def test_ai_must_carry_version_and_cannot_extend_hard_limit(conn):
    sid, v = _session(conn)
    no_version = _cmd(conn, sid, "TUTOR_MESSAGE", actor="AI_TUTOR", actor_id="tutor", payload={"text": "x"})
    assert no_version["error"]["code"] == "STALE_VERSION"
    with pytest.raises(lr.LiveError) as exc:
        lr.propose_ai_action(conn, sid, {"command_type": "EXTEND", "payload": {"seconds": 300}}, "more time", v)
    assert exc.value.code == "HARD_LIMIT"
    stale = lr.propose_ai_action(conn, sid, {"command_type": "NEXT"}, "move on", v - 1)
    assert stale["status"] == "STALE" and not stale["applied"]


def test_ai_auto_applies_allow_listed_actions_only_when_unlocked(conn):
    sid, v = _session(conn)
    applied = lr.propose_ai_action(conn, sid, {"command_type": "SHOW_WIDGET", "payload": {
        "spec": __import__("mathbank_rest.widgets", fromlist=["compose"]).compose("power of a point")["spec"]}},
        "diagram helps", v)
    assert applied["applied"] is True, applied
    _cmd(conn, sid, "LOCK_AGENT", version=lr.get_session(conn, sid)["state_version"])
    queued = lr.propose_ai_action(conn, sid, {"command_type": "NEXT"}, "move on",
                                  lr.get_session(conn, sid)["state_version"])
    assert queued["status"] == "PROPOSED" and not queued["applied"]


def test_events_are_ordered_and_audience_filtered(conn):
    sid, v = _session(conn)
    st = lr.join_session(conn, lr.get_session(conn, sid)["join_code"], _student(conn))
    _cmd(conn, sid, "QUESTION_ASK", actor="STUDENT", actor_id=st["participant_id"], payload={"text": "why?"})
    _cmd(conn, sid, "TAKEOVER", version=lr.get_session(conn, sid)["state_version"], payload={"scope": "SESSION"})
    staff = lr.list_events(conn, sid, 0, role="INSTRUCTOR")["events"]
    seqs = [e["sequence"] for e in staff]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    student = lr.list_events(conn, sid, 0, role="STUDENT", participant_id=st["participant_id"])["events"]
    types = {e["event_type"] for e in student}
    assert "student.question" not in types and "instructor.handoff_packet" not in types
    tail = lr.list_events(conn, sid, seqs[-2], role="INSTRUCTOR")["events"]
    assert [e["sequence"] for e in tail] == seqs[-1:]


def test_snapshot_and_tutor_context(conn):
    sid, _ = _session(conn)
    snap = lr.snapshot(conn, sid, "INSTRUCTOR")
    assert snap["status"] == "ACTIVE" and "time" in snap and len(snap["topic_runs"]) == 3
    assert "participants" in snap and "recommendations" in snap
    student_view = lr.snapshot(conn, sid, "STUDENT", "student:nobody")
    assert "recommendations" not in student_view and "participants" not in student_view
    ctx = lr.tutor_context(conn, sid)
    assert ctx["ai_in_control"] is True and ctx["session"]["status"] == "ACTIVE"


def test_nl_instructor_command_compiles_and_executes(conn):
    sid, _ = _session(conn)
    out = lr.instructor_nl(conn, sid, "next", "instructor:test", auto_apply=True)
    assert out["understood"] and out["actions"][0]["status"] == "ACCEPTED"
    assert out["actions"][0]["result"]["command_type"] == "NEXT"
    assert lr.get_session(conn, sid)["current_topic_index"] == 1
