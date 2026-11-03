"""WP5 solve area: route-level parity of every solve/attempt route between the PostgreSQL contract and the DynamoDB backend.

The same scripted scenario runs through the real router (``TestClient``) twice. The "postgres" side is ``Oracle``, an in-memory
learner store that implements today's PostgreSQL state machine (``step_runtime``: version check, current-step guard, help ladder,
outcome transition, next-step choice, idempotent replay, events) independently of ``SolveDynamoDB``; the "dynamodb" side is the
composed ``DynamoDBLearnerStore`` on moto, with the content store on moto as well. Generated ids and timestamps are normalised, every
other difference fails the test unless it is listed as an intended behaviour change.
"""
from __future__ import annotations

import datetime as dt
import re
import sys
import uuid
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from parity_harness import diff
from test_wp5_solve import CODE, PROBLEM_ID, STATEMENT, seed_content

from mathbank_rest import security, stores
from mathbank_rest.main import app
from mathbank_rest.routers import step_runtime as routes
from mathbank_rest.step_logic import (
    DONE_STATES,
    HELP_LEVELS,
    IdempotencyKeyReused,
    InvalidTransition,
    NotFound,
    StateVersionConflict,
    attempt_is_correct,
    build_runtime_view,
    check_version,
    next_step,
    outcome_transition,
    request_hash,
    require_current_step,
    steps_from_dag,
)
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner import DynamoDBLearnerStore

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
TS_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")


class Oracle:
    """PostgreSQL semantics in memory (the contract the router and the clients were built against)."""

    backend = "oracle"

    def __init__(self, *, with_mastery: bool) -> None:
        self.with_mastery = with_mastery
        self.attempts: dict[str, dict] = {}
        self.steps: dict[tuple[str, str], dict] = {}
        self.events: list[dict] = []
        self.idem: dict[tuple[str, str], tuple[str, str, dict]] = {}
        self.tick = 0

    # -- plumbing
    def _now(self) -> dt.datetime:
        self.tick += 1
        return dt.datetime(2026, 1, 1, tzinfo=dt.UTC) + dt.timedelta(microseconds=self.tick)

    def _event(self, sid, aid, event_type, actor, step=None, payload=None):
        self.events.append({"event_id": uuid.uuid4(), "solve_attempt_id": UUID(aid), "event_type": event_type, "event_time": self._now(),
                            "actor_type": actor, "solution_step_id": step, "payload": payload or {}, "_sid": sid})

    def _lock(self, aid, sid):
        a = self.attempts.get(str(aid))
        if a is None or (sid is not None and a["student_id"] != str(sid)):
            raise NotFound("attempt not found")
        return a

    def _idem(self, sid, key, op, body, run):
        if key and (sid, key) in self.idem:
            stored_op, stored_hash, stored = self.idem[(sid, key)]
            if stored_op != op or stored_hash != request_hash(op, body):
                raise IdempotencyKeyReused("Idempotency-Key was already used for a different request")
            return {**stored, "replayed": True}
        response = run()
        if key:
            self.idem[(sid, key)] = (op, request_hash(op, body), response)
        return {**response, "replayed": False}

    def _dag(self, a):
        return stores.get_store("content").get_solution_dag(problem_id=a["problem_id"])

    def _present(self, a, sid, step):
        key = (a["id"], step.solution_step_id)
        row = self.steps.setdefault(key, {"state": "PRESENTED", "help": 0, "count": 0, "response": None, "evaluation": None})
        if row["state"] == "FAILED":
            row["state"] = "RETRY_PRESENTED"
        self._event(sid, a["id"], "STEP_PRESENTED", "SYSTEM", step.solution_step_id)

    def _position(self, a, step, mode=None):
        a["part"], a["step"] = (step.solution_part_id, step.solution_step_id) if step else (None, None)
        a["version"] += 1
        a["mode"] = mode or a["mode"]
        return a["version"]

    # -- operations
    def start_attempt(self, student_id, problem_ref, idempotency_key=None):
        sid, content = str(student_id), stores.get_store("content")
        if not content.get_problems_by_codes([problem_ref]):
            raise NotFound("problem not found")
        dag = content.get_solution_dag(problem_code=problem_ref)
        pid = dag["problem_id"]

        def run():
            open_ = next((a for a in self.attempts.values()
                          if (a["student_id"], a["problem_id"], a["status"]) == (sid, pid, "IN_PROGRESS")), None)
            if open_:
                self._event(sid, open_["id"], "PROBLEM_VIEWED", "STUDENT", payload={"resumed": True})
                return {"solve_attempt_id": open_["id"], "resumed": True}
            steps, prereqs = steps_from_dag(dag)
            n = 1 + max((a["number"] for a in self.attempts.values() if (a["student_id"], a["problem_id"]) == (sid, pid)), default=0)
            aid = str(uuid.uuid4())
            a = self.attempts[aid] = {"id": aid, "student_id": sid, "problem_id": pid, "number": n, "status": "IN_PROGRESS",
                                      "mode": "SOLVING", "version": 1, "hints": 0, "part": None, "step": None,
                                      "started": self._now(), "submitted": None, "completed": None}
            self._event(sid, aid, "ATTEMPT_STARTED", "STUDENT", payload={"problem_id": pid})
            self._event(sid, aid, "PROBLEM_VIEWED", "STUDENT", payload={"resumed": False})
            first = next_step(steps, {}, prereqs)
            self._present(a, sid, first)
            self._position(a, first)
            return {"solve_attempt_id": aid, "resumed": False}

        out = self._idem(sid, idempotency_key, "start_attempt", {"problem_id": pid}, run)
        return {**out, "runtime": self.get_attempt_runtime(out["solve_attempt_id"], sid)}

    def get_attempt_runtime(self, attempt_id, student_id=None):
        a = self._lock(attempt_id, student_id)
        content = stores.get_store("content")
        dag = self._dag(a)
        attempt = {"solve_attempt_id": UUID(a["id"]), "student_id": UUID(a["student_id"]), "problem_id": UUID(a["problem_id"]),
                   "attempt_number": a["number"], "status": a["status"], "started_at": a["started"], "submitted_at": a["submitted"],
                   "completed_at": a["completed"], "current_solution_part_id": a["part"], "current_solution_step_id": a["step"],
                   "recovery_plan_id": None, "current_recovery_plan_id": None, "state_version": a["version"],
                   "current_mode": a["mode"], "problem_code": dag["problem_code"],
                   "statement_text": content.get_problems_by_codes([dag["problem_code"]])[0]["statement_text"]}
        states = {sid_: {"state": r["state"], "help_level_used": r["help"], "attempt_count": r["count"],
                         "last_response_text": r["response"], "last_evaluation": r["evaluation"]}
                  for (aid, sid_), r in self.steps.items() if aid == a["id"]}
        return build_runtime_view(attempt, dag, states, step_lookup=lambda s: content.get_step_details([s]).get(s),
                                  diagnosis_for_step=lambda s: None, recovery=None)

    def submit_step_response(self, student_id, attempt_id, step_id, response_text, state_version, idempotency_key=None):
        sid, a = str(student_id), self._lock(attempt_id, student_id)
        body = {"attempt_id": str(attempt_id), "step_id": step_id, "response_text": response_text, "state_version": state_version}

        def run():
            check_version(a["version"], state_version)
            require_current_step(a["status"], a["mode"], a["step"], step_id)
            row = self.steps[(a["id"], step_id)]
            row |= {"state": "ATTEMPTED", "count": row["count"] + 1, "response": response_text}
            self._event(sid, a["id"], "STEP_RESPONSE_SUBMITTED", "STUDENT", step_id, {"response": response_text})
            a["version"] += 1
            return {"event_id": str(self.events[-1]["event_id"]), "state": "ATTEMPTED", "evaluation_status": "PENDING",
                    "state_version": a["version"]}

        return self._idem(sid, idempotency_key, "step_response", body, run)

    def request_hint(self, student_id, attempt_id, step_id, state_version, idempotency_key=None):
        sid, a = str(student_id), self._lock(attempt_id, student_id)
        body = {"attempt_id": str(attempt_id), "step_id": step_id, "state_version": state_version}

        def run():
            check_version(a["version"], state_version)
            require_current_step(a["status"], a["mode"], a["step"], step_id)
            row = self.steps[(a["id"], step_id)]
            row["help"] = min(row["help"] + 1, 5)
            self._event(sid, a["id"], "HINT_REQUESTED", "STUDENT", step_id, {"help_level": row["help"], "help_kind": HELP_LEVELS[row["help"]]})
            a["hints"] += 1
            a["version"] += 1
            return {"help_level": row["help"], "help_kind": HELP_LEVELS[row["help"]], "hint_text": None, "state_version": a["version"]}

        return self._idem(sid, idempotency_key, "hint", body, run)

    def record_hint_presented(self, student_id, attempt_id, step_id, level, hint_source):
        self._event(str(student_id), str(attempt_id), "HINT_PRESENTED", "TUTOR", step_id,
                    {"help_level": level, "help_kind": HELP_LEVELS.get(level), "hint_source": hint_source})

    def get_step_tutor_state(self, attempt_id, step_id, *, student_id=None, conn=None):
        row = self.steps.get((str(attempt_id), step_id))
        return {"last_response_text": row["response"] if row else None, "help": row["help"] if row else 0}

    def record_step_outcome(self, attempt_id, step_id, result, state_version, *, actor="TUTOR", evaluation=None, idempotency_key=None):
        if actor not in ("TUTOR", "AGENT", "SYSTEM", "ADMIN"):
            raise InvalidTransition("step outcomes are recorded by the tutor/evaluator, not the student")
        a = self._lock(attempt_id, None)
        sid = a["student_id"]
        body = {"attempt_id": str(attempt_id), "step_id": step_id, "result": result, "state_version": state_version,
                "evaluation": evaluation or {}}

        def run():
            check_version(a["version"], state_version)
            require_current_step(a["status"], a["mode"], a["step"], step_id)
            row = self.steps[(a["id"], step_id)]
            new_state, event_type, independent = outcome_transition(result, row["help"])
            row |= {"state": new_state, "independent": independent, "evaluation": {"result": result, **(evaluation or {})}}
            self._event(sid, a["id"], "STEP_EVALUATED", actor, step_id, {"result": result, "evaluation": evaluation or {}})
            self._event(sid, a["id"], event_type, actor, step_id, {"help_level_used": row["help"]})
            dag = self._dag(a)
            steps, prereqs = steps_from_dag(dag)
            states = {s: r["state"] for (aid, s), r in self.steps.items() if aid == a["id"]}
            upcoming = next_step(steps, states, prereqs)
            if upcoming is not None:
                self._present(a, sid, upcoming)
            version = self._position(a, upcoming, "COMPLETED" if upcoming is None else None)
            outcome = None
            if upcoming is None:
                ok = attempt_is_correct(states)
                a.update({"status": "COMPLETED", "completed": self._now(), "submitted": a["submitted"] or self._now()})
                outcome = {"attempt_id": str(uuid.uuid4()), "is_correct": ok, "hint_count": a["hints"]}
                self._event(sid, a["id"], "ATTEMPT_COMPLETED", "SYSTEM", None, {"is_correct": ok, "hint_count": a["hints"],
                                                                              "outcome_attempt_id": outcome["attempt_id"]})
            return {"state": new_state, "independent_success": independent,
                    "current_step_id": upcoming.solution_step_id if upcoming else None, "attempt_completed": upcoming is None,
                    "outcome_attempt": outcome, "state_version": version, "student_id": sid, "problem_id": a["problem_id"],
                    "gap_status_changes": [], "diagnosis": None}

        out = self._idem(sid, idempotency_key, "step_outcome", body, run)
        if out["attempt_completed"] and not out["replayed"] and self.with_mastery:
            out["updated_mastery"] = {"concepts": {}, "techniques": {}}
        return out

    def submit_attempt(self, student_id, attempt_id, state_version, idempotency_key=None):
        sid, a = str(student_id), self._lock(attempt_id, student_id)
        body = {"attempt_id": str(attempt_id), "state_version": state_version}

        def run():
            check_version(a["version"], state_version)
            if a["status"] != "IN_PROGRESS":
                raise InvalidTransition(f"attempt is {a['status']}")
            if a["mode"] == "RECOVERY":
                raise InvalidTransition("leave the recovery detour before handing in the attempt")
            a.update({"status": "SUBMITTED", "submitted": self._now(), "mode": "REVIEW"})
            self._event(sid, a["id"], "ATTEMPT_SUBMITTED", "STUDENT")
            a["version"] += 1
            return {"status": "SUBMITTED", "state_version": a["version"]}

        return self._idem(sid, idempotency_key, "submit_attempt", body, run)

    def list_events(self, student_id, *, attempt_id=None, limit=100, student_view=False):
        rows = [e for e in self.events if e["_sid"] == str(student_id) and (attempt_id is None or str(e["solve_attempt_id"]) == str(attempt_id))]
        rows.sort(key=lambda e: e["event_time"], reverse=True)
        return [{k: v for k, v in e.items() if k != "_sid"} for e in rows[:limit]]

    def list_events_page(self, student_id, *, attempt_id=None, limit=100, next_token=None, student_view=False):
        items = self.list_events(student_id, attempt_id=attempt_id, limit=limit)
        return {"items": items, "limit": limit, "next_token": None}


class BackendClient:
    """A TestClient of the shared app that serves its requests with one learner store."""

    def __init__(self, store) -> None:
        self.store, self.http = store, TestClient(app, raise_server_exceptions=True)

    def request(self, method, path, **kw):
        with stores.override_store("learner", self.store):
            return self.http.request(method, path, **kw)


def normalise(value):
    if isinstance(value, dict):
        return {k: normalise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalise(v) for v in value]
    if isinstance(value, str):
        return "<uuid>" if UUID_RE.match(value) else "<ts>" if TS_RE.match(value) else value
    return value


class Run:
    """The scenario against one backend: records (label, status, body) and tracks the ids it learns on the way."""

    def __init__(self, client: BackendClient, sid: str) -> None:
        self.c, self.sid, self.log, self.aid = client, sid, [], None

    def call(self, label, method, path, **kw):
        r = self.c.request(method, path.format(sid=self.sid, aid=self.aid), **kw)
        body = r.json()
        self.log.append((label, r.status_code, normalise(body)))
        return body


SCENARIO_EXPECTED_STATUS = {
    "start": 201, "start replay": 201, "start resume": 201, "stale version": 409, "wrong step": 409, "unknown attempt": 404,
    "foreign runtime": 404, "submit completed": 409, "unknown problem": 404, "key reuse": 422,
}


def scenario(run: Run) -> None:
    base = "/v1/attempts/{aid}"
    first = run.call("start", "POST", "/v1/students/{sid}/problems/" + CODE + "/attempts", headers={"Idempotency-Key": "s1"})
    run.aid = first["solve_attempt_id"]
    run.call("start replay", "POST", "/v1/students/{sid}/problems/" + CODE + "/attempts", headers={"Idempotency-Key": "s1"})
    run.call("start resume", "POST", "/v1/students/{sid}/problems/" + CODE + "/attempts")
    run.call("runtime", "GET", base + "/runtime")
    run.call("admin runtime", "GET", "/v1/admin/attempts/{aid}/runtime")
    saved = run.call("response", "POST", base + "/steps/st1/responses", headers={"Idempotency-Key": "r1"},
                     json={"response_text": "midpoints", "state_version": 2, "evaluate": False})
    run.call("response replay", "POST", base + "/steps/st1/responses", headers={"Idempotency-Key": "r1"},
             json={"response_text": "midpoints", "state_version": 2, "evaluate": False})
    run.call("key reuse", "POST", base + "/steps/st1/responses", headers={"Idempotency-Key": "r1"},
             json={"response_text": "other", "state_version": 2, "evaluate": False})
    run.call("stale version", "POST", base + "/steps/st1/responses", json={"response_text": "x", "state_version": 2, "evaluate": False})
    run.call("wrong step", "POST", base + "/steps/st2/responses", json={"response_text": "x", "state_version": saved["state_version"],
                                                                         "evaluate": False})
    version = saved["state_version"]
    for i in range(6):                                          # the ladder caps at level 5
        hint = run.call(f"hint {i + 1}", "POST", base + "/steps/st1/hint", json={"state_version": version})
        version = hint["state_version"]
    run.call("hint replay", "POST", base + "/steps/st1/hint", json={"state_version": version - 1}, headers={"Idempotency-Key": "never"})
    run.call("hints list", "GET", base + "/steps/st1/hints")
    out = run.call("outcome with help", "POST", base + "/steps/st1/outcome", headers={"Idempotency-Key": "o1"},
                   json={"result": "SUCCESS", "state_version": version, "actor_type": "ADMIN", "evaluation": {"verdict": "CORRECT"}})
    run.call("outcome replay", "POST", base + "/steps/st1/outcome", headers={"Idempotency-Key": "o1"},
             json={"result": "SUCCESS", "state_version": version, "actor_type": "ADMIN", "evaluation": {"verdict": "CORRECT"}})
    saved = run.call("response graded", "POST", base + "/steps/st2/responses", json={"response_text": "because", "state_version":
                                                                                    out["state_version"]})
    failed = run.call("outcome failed", "POST", base + "/steps/st3/outcome",
                      json={"result": "FAILED", "state_version": saved["state_version"], "evaluation": {"verdict": "INCORRECT"}})
    run.call("runtime after failure", "GET", base + "/runtime")
    done = run.call("outcome skipped completes", "POST", base + "/steps/st3/outcome",
                    json={"result": "SKIPPED", "state_version": failed["state_version"]})
    run.call("runtime after completion", "GET", base + "/runtime")
    run.call("submit completed", "POST", base + "/submit", json={"state_version": done["state_version"]})
    run.call("events", "GET", "/v1/students/{sid}/events", params={"limit": 50})
    run.call("events of attempt", "GET", "/v1/students/{sid}/events", params={"attempt_id": run.aid, "limit": 3})
    run.call("learner feed", "GET", "/v1/learner/events", params={"limit": 4})
    second = run.call("start again", "POST", "/v1/students/{sid}/problems/" + CODE + "/attempts")
    run.aid = second["solve_attempt_id"]
    run.call("submit early", "POST", base + "/submit", headers={"Idempotency-Key": "u1"}, json={"state_version": 2})
    run.call("submit early replay", "POST", base + "/submit", headers={"Idempotency-Key": "u1"}, json={"state_version": 2})
    run.call("unknown attempt", "GET", f"/v1/attempts/{uuid.uuid4()}/runtime")
    run.call("unknown problem", "POST", "/v1/students/{sid}/problems/NO_SUCH/attempts")
    foreign = Run(run.c, str(uuid.uuid4()))                     # another learner asks for the first attempt
    foreign.aid = first["solve_attempt_id"]
    app.dependency_overrides[security.get_current_student_id] = lambda: UUID(foreign.sid)
    try:
        foreign.call("foreign runtime", "GET", base + "/runtime")
    finally:
        app.dependency_overrides[security.get_current_student_id] = lambda: UUID(run.sid)
    run.log += foreign.log


@pytest.fixture()
def clients(content_table, monkeypatch):
    """Both backends over one moto content store; the model calls are scripted."""
    seed_content()
    sid = str(uuid.uuid4())
    app.dependency_overrides[security.get_current_student_id] = lambda: UUID(sid)
    app.dependency_overrides[security.require_admin_api_key] = lambda: None
    monkeypatch.setattr(routes, "HINT_WRITER", lambda ctx, level, lower, stricter=False: f"hint level {level}")
    monkeypatch.setattr(routes, "EVALUATOR", lambda ctx: {"verdict": "CORRECT", "confidence": 0.95, "feedback": "Well done.",
                                                          "failure_mode": "NONE", "failure_location": "NONE", "evidence": "secret"})
    composed = DynamoDBLearnerStore()
    with stores.override_store("content", DynamoDBContentStore()):
        yield sid, {"postgres": BackendClient(Oracle(with_mastery=hasattr(composed, "stage_outcome"))),
                    "dynamodb": BackendClient(composed)}
    app.dependency_overrides.clear()


def test_every_solve_route_answers_identically_on_both_backends(clients):
    sid, backends = clients
    runs = {name: Run(client, sid) for name, client in backends.items()}
    for run in runs.values():
        scenario(run)
    pg, ddb = runs["postgres"].log, runs["dynamodb"].log
    assert [x[0] for x in pg] == [x[0] for x in ddb] and len(pg) > 30
    problems = []
    for (label, s0, b0), (_, s1, b1) in zip(pg, ddb, strict=True):
        if label in SCENARIO_EXPECTED_STATUS:
            assert (s0, s1) == (SCENARIO_EXPECTED_STATUS[label],) * 2, label
        found = [f"status {s0} vs {s1}"] if s0 != s1 else []
        found += diff(b0, b1, allowed=[
            "$.items[*].payload.*",                  # LRN-F01: the learner feed shows the allow-listed payload on DynamoDB only
            "$[*].payload.*",
        ] if label.startswith("events") else ["$.hint_source", "$.hints[*].hint_source"] if label.startswith("hint") else ())
        problems += [f"{label}: {f}" for f in found]
    assert not problems, "\n".join(problems)


def test_the_scenario_exercises_the_interesting_branches(clients):
    """Guards the guard: the parity run really produced conflicts, replays, a completion and an early submit."""
    sid, backends = clients
    run = Run(backends["dynamodb"], sid)
    scenario(run)
    log = {label: (status, body) for label, status, body in run.log}
    assert log["start"][1]["resumed"] is False and log["start replay"][1]["replayed"] is True and log["start resume"][1]["resumed"] is True
    assert log["stale version"][1]["detail"]["code"] == "STATE_VERSION_CONFLICT"
    assert log["wrong step"][1]["detail"]["code"] == "INVALID_TRANSITION" and log["key reuse"][1]["detail"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert [log[f"hint {i}"][1]["help_level"] for i in range(1, 7)] == [1, 2, 3, 4, 5, 5]
    assert log["hint 5"][1]["hint_text"] == "step text 1" and log["hint 1"][1]["hint_text"] == "hint level 1"
    assert log["outcome with help"][1]["state"] == "SUCCESS_WITH_HELP" and log["outcome replay"][1]["replayed"] is True
    assert log["response graded"][1]["evaluation_status"] == "EVALUATED" and "evidence" not in str(log["response graded"][1])
    assert log["outcome failed"][1]["current_step_id"] == "<uuid>" or log["outcome failed"][1]["state"] == "FAILED"
    assert log["outcome skipped completes"][1]["attempt_completed"] is True
    assert log["runtime after completion"][1]["attempt"]["status"] == "COMPLETED"
    assert log["submit early replay"][1]["replayed"] is True and log["submit early"][1]["status"] == "SUBMITTED"
    assert log["learner feed"][1]["limit"] == 4 and len(log["learner feed"][1]["items"]) == 4
    assert STATEMENT in str(log["runtime"][1]) and PROBLEM_ID  # the statement is served; ids are normalised away
    admin = log["admin runtime"][1]
    assert set(admin) == {"attempt", "current_step_id", "steps", "progress", "recovery"} and admin["current_step_id"] == "st1"
    assert "statement_text" not in admin["attempt"] and "step text" not in str(admin)           # no step text for the admin view
    assert [s["state"] for s in admin["steps"]] == ["PRESENTED", "LOCKED", "LOCKED"]


def test_the_learner_feed_hides_teacher_evidence_on_both_routes(clients):
    sid, backends = clients
    run = Run(backends["dynamodb"], sid)
    scenario(run)
    for label in ("events", "events of attempt", "learner feed"):
        blob = str([b for lab, _, b in run.log if lab == label])
        for forbidden in ("confidence", "failure_mode", "failure_location", "TEACHER", "'evidence'"):
            assert forbidden not in blob, (label, forbidden)
    feed = next(b for lab, _, b in run.log if lab == "learner feed")
    assert set(feed) == {"items", "limit", "next_token"} and all(set(e) >= {"event_id", "event_type", "payload"} for e in feed["items"])


def test_a_stale_state_version_conflicts_and_a_double_submit_is_idempotent_through_the_router(clients):
    sid, backends = clients
    client = backends["dynamodb"]
    started = client.request("POST", f"/v1/students/{sid}/problems/{CODE}/attempts").json()
    aid = started["solve_attempt_id"]
    url = f"/v1/attempts/{aid}/steps/st1/responses"
    body = {"response_text": "x", "state_version": 2, "evaluate": False}
    first = client.request("POST", url, json=body, headers={"Idempotency-Key": "dbl"})
    again = client.request("POST", url, json=body, headers={"Idempotency-Key": "dbl"})
    assert first.status_code == again.status_code == 200 and again.json() == {**first.json(), "replayed": True}
    conflict = client.request("POST", url, json=body)
    assert conflict.status_code == 409 and conflict.json()["detail"]["code"] == "STATE_VERSION_CONFLICT"
    assert client.request("GET", f"/v1/attempts/{aid}/runtime").json()["current_step"]["attempt_count"] == 1


def test_solve_attempts_and_event_after_cursor_routes(clients):
    sid, backends = clients
    client = backends["dynamodb"]
    aid = client.request("POST", f"/v1/students/{sid}/problems/{CODE}/attempts").json()["solve_attempt_id"]
    client.request("POST", f"/v1/attempts/{aid}/submit", json={"state_version": 2})
    mine = client.request("GET", "/v1/learner/solve-attempts", params={"status": "SUBMITTED"}).json()
    assert [r["solve_attempt_id"] for r in mine["items"]] == [aid] and mine["items"][0]["problem_code"] == CODE
    assert client.request("GET", "/v1/learner/solve-attempts", params={"status": "COMPLETED"}).json()["items"] == []
    feed = client.request("GET", "/v1/learner/events", params={"limit": 2}).json()
    assert len(feed["items"]) == 2 and feed["next_token"]
    rest = client.request("GET", "/v1/learner/events", params={"limit": 50, "next_token": feed["next_token"]}).json()
    assert len(feed["items"]) + len(rest["items"]) == 4 and rest["next_token"] is None
    oldest = rest["items"][-1]["event_time"]
    after = client.request("GET", "/v1/learner/events", params={"after": oldest, "limit": 50}).json()
    assert len(after["items"]) == 3 and after["items"][0]["event_time"] > oldest
    assert client.request("GET", "/v1/learner/events", params={"after": "tomorrow"}).status_code == 422
    assert client.request("GET", "/v1/learner/events", params={"next_token": "forged"}).status_code in (400, 422)
    assert client.request("GET", "/v1/learner/events", params={"attempt_id": str(uuid.uuid4())}).json()["items"] == []


@pytest.mark.parametrize("op", ["start_attempt", "get_attempt_runtime", "submit_step_response", "request_hint", "record_hint_presented",
                                "record_step_outcome", "submit_attempt", "abandon_stale_attempts", "list_events"])
def test_the_postgres_store_delegates_to_step_runtime_at_call_time(monkeypatch, op):
    """Behaviour unchanged by default: SolvePostgres runs the SQL layer in one transaction, looking it up at call time."""
    from mathbank_rest import step_runtime
    from mathbank_rest.db import postgres
    from mathbank_rest.stores.learner import PostgresLearnerStore

    conn, seen = object(), []

    class Tx:
        def __enter__(self):
            return conn

        def __exit__(self, *exc):
            return False

    class Engine:
        begin = connect = staticmethod(lambda: Tx())

    monkeypatch.setattr(postgres, "engine", Engine())
    target = {"start_attempt": "start_attempt", "get_attempt_runtime": "get_runtime"}.get(op, op)
    stub = {"start_attempt": {"solve_attempt_id": "a1", "resumed": False}, "get_runtime": {"attempt": {}}}.get(target, {"ok": op})
    monkeypatch.setattr(step_runtime, "resolve_problem", lambda c, ref: seen.append(("resolve", ref)) or "pid")
    monkeypatch.setattr(step_runtime, "get_runtime", lambda c, a, s: seen.append(("get_runtime", a, s)) or {"attempt": {}})
    if target != "get_runtime":
        monkeypatch.setattr(step_runtime, target, lambda c, *a, **k: seen.append((target, a, k)) or stub)
    store = PostgresLearnerStore()
    args = {"start_attempt": ("s", "CODE", "k"), "get_attempt_runtime": ("a", "s"), "submit_step_response": ("s", "a", "st", "t", 2, "k"),
            "request_hint": ("s", "a", "st", 2, "k"), "record_hint_presented": ("s", "a", "st", 3, "GEN"),
            "record_step_outcome": ("a", "st", "SUCCESS", 2), "submit_attempt": ("s", "a", 2, "k"),
            "abandon_stale_attempts": (30, 5), "list_events": ("s",)}[op]
    getattr(store, op)(*args)
    assert seen and seen[0][0] in (target, "resolve")
    if op == "record_step_outcome":
        assert seen == [("record_step_outcome", ("a", "st", "SUCCESS", 2), {"actor": "TUTOR", "evaluation": None, "idempotency_key": None})]


def test_done_states_are_the_ones_the_oracle_and_the_store_share():
    assert DONE_STATES == {"SUCCESS_INDEPENDENT", "SUCCESS_WITH_HELP", "SKIPPED"}
    assert StateVersionConflict.status_code == 409
