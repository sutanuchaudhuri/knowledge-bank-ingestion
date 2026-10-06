"""Step runtime (v2 Phase 6): pure state logic, route guards, and opt-in live golden flows.

Live tests (MATHBANK_LIVE_STEP_RUNTIME_TEST=1) run against real Prasolov steps inside one
transaction that always rolls back — nothing persists (GOT-TEST-2).
"""
from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_rest import security
from mathbank_rest import step_runtime as rt
from mathbank_rest.main import app
from mathbank_rest.step_runtime import StepRef

client = TestClient(app)


# ---------------------------------------------------------------- pure logic

@pytest.mark.parametrize(("result", "help_level", "expected"), [
    ("SUCCESS", 0, ("SUCCESS_INDEPENDENT", "STEP_COMPLETED_INDEPENDENTLY", True)),
    ("SUCCESS", 1, ("SUCCESS_WITH_HELP", "STEP_COMPLETED_WITH_HELP", False)),
    ("SUCCESS", 5, ("SUCCESS_WITH_HELP", "STEP_COMPLETED_WITH_HELP", False)),
    ("FAILED", 0, ("FAILED", "STEP_FAILED", None)),
    ("SKIPPED", 2, ("SKIPPED", "STEP_SKIPPED", None)),
])
def test_outcome_transition(result, help_level, expected):
    assert rt.outcome_transition(result, help_level) == expected


def test_outcome_transition_rejects_unknown_result():
    with pytest.raises(ValueError):
        rt.outcome_transition("CORRECT", 0)


STEPS = [StepRef("s1", "pA", 1), StepRef("s2", "pA", 2), StepRef("s3", "pB", 3)]


def test_next_step_follows_order_and_failed_step_stays_current():
    assert rt.next_step(STEPS, {}, {}).solution_step_id == "s1"
    assert rt.next_step(STEPS, {"s1": "FAILED"}, {}).solution_step_id == "s1"
    assert rt.next_step(STEPS, {"s1": "SUCCESS_WITH_HELP"}, {}).solution_step_id == "s2"
    done = {"s1": "SUCCESS_INDEPENDENT", "s2": "SKIPPED", "s3": "SUCCESS_WITH_HELP"}
    assert rt.next_step(STEPS, done, {}) is None


def test_next_step_respects_hard_prerequisites():
    # s2 depends on s3 (cross-order DEPENDS_ON): s3 must be done before s2 becomes eligible.
    prereqs = {"s2": {"s3"}}
    assert rt.next_step(STEPS, {"s1": "SUCCESS_INDEPENDENT"}, prereqs).solution_step_id == "s3"
    states = {"s1": "SUCCESS_INDEPENDENT", "s3": "SUCCESS_INDEPENDENT"}
    assert rt.next_step(STEPS, states, prereqs).solution_step_id == "s2"


def test_request_hash_is_stable_and_body_sensitive():
    assert rt.request_hash("hint", {"a": 1, "b": 2}) == rt.request_hash("hint", {"b": 2, "a": 1})
    assert rt.request_hash("hint", {"a": 1}) != rt.request_hash("hint", {"a": 2})
    assert rt.request_hash("hint", {"a": 1}) != rt.request_hash("step_response", {"a": 1})


# ---------------------------------------------------------------- route guards (no DB access)

def _auth(student_id):
    return {"Authorization": f"Bearer {security.create_access_token(student_id)}"}


def test_runtime_routes_require_auth():
    attempt = uuid4()
    assert client.get(f"/v1/attempts/{attempt}/runtime").status_code == 401
    assert client.post(f"/v1/attempts/{attempt}/steps/x/hint", json={"state_version": 1}).status_code == 401
    assert client.get("/v1/solution-steps/x/practice").status_code == 401


def test_student_cannot_start_attempt_for_someone_else():
    response = client.post(f"/v1/students/{uuid4()}/problems/P1/attempts", headers=_auth(uuid4()))
    assert response.status_code == 403


def test_student_cannot_record_an_outcome():
    response = client.post(f"/v1/attempts/{uuid4()}/steps/x/outcome", headers=_auth(uuid4()),
                           json={"result": "SUCCESS", "state_version": 1})
    assert response.status_code == 401


# ---------------------------------------------------------------- live golden flows (rolled back)

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
        {"e": f"live-{uuid4()}@example.invalid"}).scalar_one()


def _problem_with_steps(conn, minimum=3):
    return conn.execute(text(
        "SELECT problem_id::text FROM pedagogy.solution_step WHERE publication_status = 'PUBLISHED' "
        "GROUP BY problem_id HAVING count(*) >= :n ORDER BY problem_id LIMIT 1"), {"n": minimum}).scalar_one()


@live
def test_live_golden_flows(live_conn):
    conn = live_conn
    student = _student(conn)
    problem = _problem_with_steps(conn)
    started = rt.start_attempt(conn, student, problem, "start-1")
    attempt_id = started["solve_attempt_id"]

    # H: refresh/retry of start never duplicates the session.
    assert rt.start_attempt(conn, student, problem, "start-1")["replayed"] is True
    assert rt.start_attempt(conn, student, problem, "start-2")["solve_attempt_id"] == attempt_id
    assert conn.execute(text("SELECT count(*) FROM learner.solve_attempt WHERE student_id = :s"),
                        {"s": student}).scalar_one() == 1

    # I: no canonical step text of any step leaks into the student runtime payload.
    runtime = rt.get_runtime(conn, attempt_id, student)
    payload = json.dumps(runtime, default=str)
    for step_text in conn.execute(text(
            "SELECT step_text FROM pedagogy.solution_step WHERE problem_id = CAST(:p AS uuid) "
            "AND length(step_text) > 20"), {"p": problem}).scalars():
        assert step_text not in payload
    assert "step_text" not in payload
    step1, version = runtime["current_step"]["solution_step_id"], runtime["attempt"]["state_version"]
    assert runtime["current_step"]["state"] == "PRESENTED"

    # Other students cannot see or act on this attempt.
    with pytest.raises(rt.NotFound):
        rt.get_runtime(conn, attempt_id, uuid4())

    # C: independent success advances to the next eligible step.
    resp = rt.submit_step_response(conn, student, attempt_id, step1, "my reasoning", version, "resp-1")
    assert rt.submit_step_response(conn, student, attempt_id, step1, "my reasoning", version,
                                   "resp-1")["replayed"] is True
    with pytest.raises(rt.IdempotencyKeyReused):
        rt.submit_step_response(conn, student, attempt_id, step1, "different", version, "resp-1")
    with pytest.raises(rt.StateVersionConflict):
        rt.request_hint(conn, student, attempt_id, step1, version, None)
    out = rt.record_step_outcome(conn, attempt_id, step1, "SUCCESS", resp["state_version"])
    assert out["state"] == "SUCCESS_INDEPENDENT" and out["independent_success"] is True
    step2 = out["current_step_id"]
    assert step2 and step2 != step1

    # D: a hint before success yields SUCCESS_WITH_HELP (never independent).
    hint = rt.request_hint(conn, student, attempt_id, step2, out["state_version"], None)
    assert hint["help_level"] == 1
    out2 = rt.record_step_outcome(conn, attempt_id, step2, "SUCCESS", hint["state_version"])
    assert out2["state"] == "SUCCESS_WITH_HELP" and out2["independent_success"] is False

    # Failure keeps the step current and re-presents it for retry.
    step3 = out2["current_step_id"]
    out3 = rt.record_step_outcome(conn, attempt_id, step3, "FAILED", out2["state_version"])
    assert out3["current_step_id"] == step3
    assert rt.get_runtime(conn, attempt_id, student)["current_step"]["state"] == "RETRY_PRESENTED"

    # Completing every step closes the session and writes one legacy mastery attempt row.
    version, current = out3["state_version"], step3
    while current:
        out = rt.record_step_outcome(conn, attempt_id, current, "SUCCESS", version)
        version, current = out["state_version"], out["current_step_id"]
    assert out["attempt_completed"] is True
    assert out["outcome_attempt"]["is_correct"] is True and out["outcome_attempt"]["hint_count"] == 1
    assert conn.execute(text("SELECT source FROM learner.attempt WHERE attempt_id = CAST(:a AS uuid)"),
                        {"a": out["outcome_attempt"]["attempt_id"]}).scalar_one() == "step_runtime"
    assert conn.execute(text("SELECT count(*) FROM pipeline.outbox_event WHERE aggregate_id = :a"),
                        {"a": attempt_id}).scalar_one() >= 2
    types = {e["event_type"] for e in rt.list_events(conn, student, attempt_id=attempt_id, limit=500)}
    assert {"ATTEMPT_STARTED", "STEP_PRESENTED", "STEP_RESPONSE_SUBMITTED", "HINT_REQUESTED",
            "STEP_EVALUATED", "STEP_COMPLETED_INDEPENDENTLY", "STEP_COMPLETED_WITH_HELP", "STEP_FAILED",
            "ATTEMPT_COMPLETED"} <= types


@live
def test_live_events_are_append_only(live_conn):
    conn = live_conn
    student = _student(conn)
    attempt_id = rt.start_attempt(conn, student, _problem_with_steps(conn, 1))["solve_attempt_id"]
    savepoint = conn.begin_nested()
    with pytest.raises(Exception, match="append-only"):
        conn.execute(text("UPDATE learner.event SET payload = '{}' WHERE solve_attempt_id = :a"), {"a": attempt_id})
    savepoint.rollback()
