"""Step evaluator + hint ladder (v2 Phase 8). No paid calls: model providers are fakes.

Live tests (MATHBANK_LIVE_STEP_RUNTIME_TEST=1) use real Prasolov steps in a rolled-back transaction.
"""
from __future__ import annotations

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_rest import security, step_runtime as rt, step_tutor as tutor
from mathbank_rest.main import app
from mathbank_rest.routers import step_runtime as routes

client = TestClient(app)
STEP = "Let P and Q be the midpoints of AB and CD; let K and L be the intersection points of PQ with the diagonals AC and BD."


def _ctx(**kw):
    base = dict(problem_statement="Let the lengths of bases AD and BC of trapezoid ABCD be a and b.", part_label="A",
                step_type="SETUP_OR_CONSTRUCTION", tutor_role="ORIENT_OR_SETUP", skill_name="midline",
                previous_steps=[], canonical_step=STEP, student_response="Take midpoints.")
    return tutor.StepContext(**(base | kw))


# ---------------------------------------------------------------- pure helpers

def test_leak_guard_detects_copied_runs_but_not_paraphrase():
    assert tutor.leaks_solution("Try this: let K and L be the intersection points of PQ with the diagonals", STEP)
    assert not tutor.leaks_solution("Which special points on the non-parallel sides could help here?", STEP)


def test_leak_guard_ignores_text_the_student_already_has():
    statement = "let the lengths of bases ad and bc of trapezoid abcd be a and b"
    canonical = "Let the lengths of bases AD and BC of trapezoid ABCD be a and b, so the midline is (a+b)/2."
    hint = "Remember: let the lengths of bases AD and BC of trapezoid ABCD be a and b."
    assert tutor.leaks_solution(hint, canonical)
    assert not tutor.leaks_solution(hint, canonical, known=(statement,))


def test_leak_guard_short_canonical_step():
    assert tutor.leaks_solution("The answer: KL equals a minus b over 2", "KL equals a minus b over 2")
    assert not tutor.leaks_solution("anything", "x = 1")


@pytest.mark.parametrize(("verdict", "confidence", "result"), [
    ("CORRECT", 0.9, "SUCCESS"), ("CORRECT", 0.6, "SUCCESS"), ("CORRECT", 0.4, "FAILED"),
    ("PARTIALLY_CORRECT", 0.95, "FAILED"), ("INCORRECT", 0.99, "FAILED"), ("OFF_TOPIC", 1.0, "FAILED"),
])
def test_verdict_mapping(verdict, confidence, result):
    assert tutor.outcome_from_verdict({"verdict": verdict, "confidence": confidence}) == result


def test_failed_feedback_that_leaks_is_redacted_but_success_feedback_is_kept():
    leaky = {"verdict": "INCORRECT", "confidence": 0.9,
             "feedback": "You should let K and L be the intersection points of PQ with the diagonals AC."}
    redacted = tutor.sanitize_feedback(leaky, _ctx())
    assert redacted["feedback_redacted"] and "intersection points" not in redacted["feedback"]
    ok = {**leaky, "verdict": "CORRECT"}
    assert tutor.sanitize_feedback(ok, _ctx())["feedback"] == ok["feedback"]


def test_step_goal_never_contains_step_text():
    for step_type in tutor.STEP_GOALS:
        assert not tutor.leaks_solution(tutor.step_goal(step_type), STEP)
    assert tutor.step_goal(None)


def test_student_evaluation_hides_teacher_evidence():
    view = rt._student_evaluation({"result": "FAILED", "verdict": "INCORRECT", "feedback": "f",
                                   "evidence": "teacher only", "failure_mode": "CARELESS", "confidence": 0.8})
    assert view == {"result": "FAILED", "verdict": "INCORRECT", "feedback": "f"}


# ---------------------------------------------------------------- route orchestration (no DB)

@pytest.fixture
def student(monkeypatch):
    sid = uuid4()
    app.dependency_overrides[security.get_current_student_id] = lambda: sid
    yield sid
    app.dependency_overrides.clear()


class _Conn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_runtime(monkeypatch, outcome):
    calls = []

    def fake_run(fn, *args, **kwargs):
        calls.append(fn.__name__)
        if fn is rt.submit_step_response:
            return {"event_id": "e1", "state": "ATTEMPTED", "evaluation_status": "PENDING", "state_version": 7}
        if fn is rt.record_step_outcome:
            assert args[3] == 7 and kwargs["actor"] == "TUTOR"
            return outcome(*args, **kwargs)
        raise AssertionError(fn)

    monkeypatch.setattr(routes, "_run", fake_run)
    monkeypatch.setattr(routes.engine, "connect", lambda: _Conn())
    return calls


def test_response_is_graded_after_commit_and_advances(monkeypatch, student):
    monkeypatch.setattr(tutor, "evaluate_step", lambda conn, a, s, ev: {
        "result": "SUCCESS", "verdict": "CORRECT", "confidence": 0.9, "feedback": "Nice.", "evidence": "secret"})
    calls = _patch_runtime(monkeypatch, lambda *a, **k: {
        "state": "SUCCESS_INDEPENDENT", "current_step_id": "next", "attempt_completed": False, "state_version": 9,
        "student_id": str(student), "problem_id": "p"})
    body = client.post(f"/v1/attempts/{uuid4()}/steps/s1/responses",
                       json={"response_text": "midpoints", "state_version": 6}).json()
    assert calls == ["submit_step_response", "record_step_outcome"]
    assert body["evaluation_status"] == "EVALUATED" and body["state_version"] == 9
    assert body["evaluation"] == {"result": "SUCCESS", "verdict": "CORRECT", "feedback": "Nice."}
    assert "student_id" not in body and "evidence" not in str(body)


def test_model_failure_keeps_the_saved_response(monkeypatch, student):
    def boom(*a):
        raise TimeoutError("model down")

    monkeypatch.setattr(tutor, "evaluate_step", boom)
    calls = _patch_runtime(monkeypatch, lambda *a, **k: pytest.fail("must not apply"))
    body = client.post(f"/v1/attempts/{uuid4()}/steps/s1/responses",
                       json={"response_text": "x", "state_version": 6}).json()
    assert body["evaluation_status"] == "UNAVAILABLE" and body["state_version"] == 7
    assert calls == ["submit_step_response"]


def test_concurrent_change_leaves_evaluation_pending(monkeypatch, student):
    from fastapi import HTTPException

    monkeypatch.setattr(tutor, "evaluate_step", lambda *a: {"result": "FAILED", "verdict": "INCORRECT"})

    def conflict(*a, **k):
        raise HTTPException(status_code=409, detail="stale")

    _patch_runtime(monkeypatch, conflict)
    body = client.post(f"/v1/attempts/{uuid4()}/steps/s1/responses",
                       json={"response_text": "x", "state_version": 6}).json()
    assert body["evaluation_status"] == "PENDING"


def test_evaluate_false_only_saves(monkeypatch, student):
    calls = _patch_runtime(monkeypatch, lambda *a, **k: pytest.fail("must not apply"))
    body = client.post(f"/v1/attempts/{uuid4()}/steps/s1/responses",
                       json={"response_text": "x", "state_version": 6, "evaluate": False}).json()
    assert body["evaluation_status"] == "PENDING" and calls == ["submit_step_response"]


@pytest.mark.parametrize("encoded", [True, False])
def test_step_ids_with_slashes_route(monkeypatch, student, encoded):
    """Prasolov step ids look like 'PRASOLOV_PGV1/STEP-1.1-A-01' (GOT-WEB-13)."""
    seen = {}

    def fake_run(fn, *args, **kwargs):
        seen["step"] = args[2]
        return {"event_id": "e", "state": "ATTEMPTED", "evaluation_status": "PENDING", "state_version": 2}

    monkeypatch.setattr(routes, "_run", fake_run)
    step = "PRASOLOV_PGV1%2FSTEP-1.1-A-01" if encoded else "PRASOLOV_PGV1/STEP-1.1-A-01"
    res = client.post(f"/v1/attempts/{uuid4()}/steps/{step}/responses",
                      json={"response_text": "x", "state_version": 1, "evaluate": False})
    assert res.status_code == 200 and seen["step"] == "PRASOLOV_PGV1/STEP-1.1-A-01"


def test_problem_image_outside_repo_is_refused(monkeypatch):
    class Result:
        def scalar(self):
            return "/etc/hosts"

    class Conn(_Conn):
        def execute(self, *a, **k):
            return Result()

    monkeypatch.setattr(routes.engine, "connect", lambda: Conn())
    assert client.get(f"/v1/problem-images/{uuid4()}").status_code == 404


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


@live
def test_live_hint_ladder_cache_and_evaluated_outcome(live_conn):
    conn = live_conn
    student = conn.execute(text(
        "INSERT INTO learner.student_profile (email, password_hash, first_name, last_name, display_name) "
        "VALUES (:e, 'x', 'Live', 'Test', 'Live Test') RETURNING student_id"),
        {"e": f"live-{uuid4()}@example.invalid"}).scalar_one()
    problem = conn.execute(text(
        "SELECT problem_id::text FROM pedagogy.solution_step WHERE publication_status = 'PUBLISHED' "
        "GROUP BY problem_id HAVING count(*) >= 3 ORDER BY problem_id LIMIT 1")).scalar_one()
    attempt = rt.start_attempt(conn, student, problem)["solve_attempt_id"]
    runtime = rt.get_runtime(conn, attempt, student)
    step, version = runtime["current_step"]["solution_step_id"], runtime["attempt"]["state_version"]
    assert runtime["current_step"]["goal"]
    locked = [t for t in runtime["timeline"] if t["state"] == "LOCKED"]
    assert locked and all("step_type" not in t and "reference_text" not in t for t in locked)

    written = []

    def writer(ctx, level, lower, stricter=False):
        written.append(level)
        assert len(lower) == level - 1  # escalates from the cached lower levels
        return f"Generic level {level} nudge about {ctx.skill_name}."

    for level in (1, 2):
        version = rt.request_hint(conn, student, attempt, step, version)["state_version"]
        assert tutor.get_or_create_hint(conn, attempt, step, level, writer)["hint_source"] == "GENERATED"
    assert tutor.get_or_create_hint(conn, attempt, step, 1, writer)["hint_source"] == "CACHED"
    assert written == [1, 2]
    reveal = tutor.get_or_create_hint(conn, attempt, step, 5, writer)
    canonical = conn.execute(text("SELECT step_text FROM pedagogy.solution_step WHERE solution_step_id=:s"),
                             {"s": step}).scalar()
    assert reveal == {"hint_text": canonical, "hint_source": "REFERENCE_STEP"}

    version = rt.submit_step_response(conn, student, attempt, step, "my reasoning", version)["state_version"]
    seen = {}

    def evaluator(ctx):
        seen["ctx"] = ctx
        return {"verdict": "CORRECT", "confidence": 0.8, "feedback": "Good.", "failure_mode": "NONE",
                "failure_location": "NONE", "evidence": "matches"}

    verdict = tutor.evaluate_step(conn, attempt, step, evaluator)
    assert seen["ctx"].student_response == "my reasoning" and seen["ctx"].canonical_step == canonical
    out = rt.record_step_outcome(conn, attempt, step, verdict["result"], version, evaluation=verdict)
    assert out["state"] == "SUCCESS_WITH_HELP"  # hints were used
    after = rt.get_runtime(conn, attempt, student)
    done = next(t for t in after["timeline"] if t["solution_step_id"] == step)
    assert done["reference_text"] == canonical and done["state"] == "SUCCESS_WITH_HELP"
    if after["current_step"]:
        assert after["current_step"]["last_evaluation"] is None
