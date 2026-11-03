"""WP5 gate (requirement 71): the whole learner runtime answers a real student journey with ZERO PostgreSQL access.

The runtime app is built from the runtime profile plus every learner-facing router; ``learner`` and ``content`` stores are
``dynamodb`` (moto), real JWT authentication is used (no dependency overrides), every SQLAlchemy engine reachable from
``mathbank_rest`` is replaced by the runtime guard (any use raises), and model calls (hint writer, evaluator) are scripted.
A route that still reaches SQL surfaces as a 500 and fails the journey; a negative control proves the guard bites.

Journey: register -> login -> profile -> solve a problem (response, hints, outcomes to completion) -> history, mastery, activity,
events, solve sessions, practice progress -> enrol in a micro-course -> feedback/route/agent-session listings -> isolation between
two students -> an admin disables the account and the token stops working.
"""
from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from test_wp4_catalog import seed as seed_catalog
from test_wp4_learning import seed_course, seed_keys
from test_wp5_solve import CODE, STEPS, seed_content

from mathbank_rest import profiles
from mathbank_rest.config import settings
from mathbank_rest.db.postgres import RuntimeProfileHasNoPostgres
from mathbank_rest.routers import step_runtime as step_routes
from mathbank_rest.stores.content import catalog

ADMIN = {"X-Admin-Api-Key": "gate-key"}
# The runtime profile ALONE serves the journey: v1, learner, step_runtime, micro_course_student, theorems_student,
# tutoring_routes_student and notifications (profiles.RUNTIME_ROUTERS). Nothing is mounted on top.


@pytest.fixture()
def runtime(content_table, monkeypatch):
    for k, v in (("content_store", "dynamodb"), ("learner_store", "dynamodb"), ("admin_api_key", "gate-key")):
        monkeypatch.setattr(settings, k, v)
    catalog._CATALOGUES.clear()
    seed_catalog()
    seed_content()
    seed_course()
    seed_keys()
    monkeypatch.setattr(step_routes, "HINT_WRITER", lambda ctx, level, lower, stricter=False: f"hint level {level}")
    guard, replaced = RuntimeProfileHasNoPostgres(), 0
    for name, mod in list(sys.modules.items()):
        if name.startswith("mathbank_rest") and isinstance(getattr(mod, "engine", None), Engine):
            monkeypatch.setattr(mod, "engine", guard)
            replaced += 1
    assert replaced >= 5, "the guard replaced too few engines; the gate would prove nothing"
    app = profiles.create_app("runtime")
    yield TestClient(app, raise_server_exceptions=False)
    catalog._CATALOGUES.clear()


def register(c: TestClient, email: str) -> tuple[str, dict]:
    r = c.post("/v1/learner/register", json={"email": email, "password": "correct horse 1", "first_name": "Ada", "last_name": "Lovelace"})
    assert r.status_code == 201, r.text
    body = r.json()
    return body["student_id"], {"Authorization": f"Bearer {body['access_token']}"}


def ok(r, status=200):
    assert r.status_code == status, f"{r.request.method} {r.request.url.path}: {r.status_code} {r.text[:300]}"
    return r.json()


def test_a_student_journey_runs_without_postgres(runtime):
    c = runtime
    sid, auth = register(c, "ada@example.org")

    # identity
    assert c.post("/v1/learner/register", json={"email": "ada@example.org", "password": "correct horse 1", "first_name": "A",
                                                 "last_name": "B"}).status_code == 409
    login = ok(c.post("/v1/learner/login", json={"email": "ada@example.org", "password": "correct horse 1"}))
    assert login["student_id"] == sid
    assert c.post("/v1/learner/login", json={"email": "ada@example.org", "password": "wrong password"}).status_code == 401
    assert ok(c.get("/v1/learner/me", headers=auth))["student_id"] == sid
    ok(c.patch("/v1/learner/me", headers=auth, json={"first_name": "Augusta"}))
    assert ok(c.get("/v1/learner/me", headers=auth))["first_name"] == "Augusta"
    assert c.get("/v1/learner/me").status_code in (401, 403)                                  # no token, no data

    # solving a problem
    first = ok(c.post(f"/v1/students/{sid}/problems/{CODE}/attempts", headers={**auth, "Idempotency-Key": "a1"}), 201)
    aid = first["solve_attempt_id"]
    assert ok(c.post(f"/v1/students/{sid}/problems/{CODE}/attempts", headers={**auth, "Idempotency-Key": "a1"}), 201)["solve_attempt_id"] == aid
    runtime_view = ok(c.get(f"/v1/attempts/{aid}/runtime", headers=auth))
    assert runtime_view["attempt"]["solve_attempt_id"] == aid and runtime_view["current_step"]
    version = runtime_view["attempt"]["state_version"]
    saved = ok(c.post(f"/v1/attempts/{aid}/steps/{STEPS[0]}/responses", headers=auth,
                      json={"response_text": "the midpoints", "state_version": version, "evaluate": False}))
    hint = ok(c.post(f"/v1/attempts/{aid}/steps/{STEPS[0]}/hint", headers=auth, json={"state_version": saved["state_version"]}))
    version = hint["state_version"]
    for step in STEPS:                                         # an internal actor records each step outcome until completion
        out = ok(c.post(f"/v1/attempts/{aid}/steps/{step}/outcome", headers=ADMIN,
                        json={"result": "SUCCESS", "state_version": version, "actor_type": "ADMIN",
                              "evaluation": {"verdict": "CORRECT"}}))
        version = out["state_version"]
    assert ok(c.get(f"/v1/attempts/{aid}/runtime", headers=auth))["attempt"]["status"] == "COMPLETED"

    # what the student sees afterwards
    attempts = ok(c.get("/v1/learner/attempts", headers=auth))
    assert isinstance(attempts, (list, dict))
    for path in ("/v1/learner/mastery", "/v1/learner/mastery/improvement-plan", "/v1/learner/activity", "/v1/learner/events",
                 "/v1/learner/solve-attempts", "/v1/learner/practice-progress", "/v1/learner/route-attempts", "/v1/learner/feedback",
                 "/v1/learner/misconceptions", "/v1/learner/micro-course-enrollments"):
        r = c.get(path, headers=auth)
        assert r.status_code == 200, f"GET {path}: {r.status_code} {r.text[:300]}"
    events = ok(c.get(f"/v1/students/{sid}/events", headers=auth, params={"limit": 50}))
    assert events
    solves = ok(c.get("/v1/learner/solve-attempts", headers=auth))
    assert any(str(s["solve_attempt_id"]) == aid for s in solves["items"])

    # a micro-course (content from mb-content, state in mb-learner)
    enrolled = ok(c.post("/v1/micro-courses/MC-1/enroll", headers={**auth, "Idempotency-Key": "e1"}), 201)
    eid = enrolled.get("enrollment_id") or enrolled.get("id")
    assert eid
    ok(c.get(f"/v1/micro-courses/enrollments/{eid}", headers=auth))
    listing = ok(c.get("/v1/learner/micro-course-enrollments", headers=auth))
    assert listing["total"] >= 1

    # isolation: another student sees none of it
    _, other = register(c, "grace@example.org")
    assert c.get(f"/v1/attempts/{aid}/runtime", headers=other).status_code == 404
    assert c.get(f"/v1/micro-courses/enrollments/{eid}", headers=other).status_code == 404
    assert ok(c.get("/v1/learner/solve-attempts", headers=other))["items"] == []
    assert c.get(f"/v1/students/{sid}/events", headers=other).status_code in (403, 404)

    # an admin disables the account (admin routes live in the admin app; the store call is the same one they make): the very
    # next request with the old token is refused
    from uuid import UUID

    from mathbank_rest import security, stores

    stores.get_store("learner").set_student_status(UUID(sid), "DISABLED", "service:admin-key")
    security.invalidate_student_status(UUID(sid))
    assert c.get("/v1/learner/me", headers=auth).status_code == 401
    assert c.get("/v1/learner/me", headers=other).status_code == 200                           # other students are unaffected


def test_the_runtime_profile_serves_the_learner_routes(runtime):
    paths = set(runtime.get("/openapi.json").json()["paths"])
    assert {"/v1/learner/me", "/v1/attempts/{attempt_id}/runtime", "/v1/tutor/route-attempts", "/v1/learner/solve-attempts",
            "/v1/micro-courses/{canonical_code}/enroll", "/v1/competitions", "/v1/notifications/me"} <= paths, sorted(paths)[:5]
    assert "/v1/admin/learner/students" not in paths and "/v1/admin/content/reconcile" not in paths    # the authoring plane is not here


def test_the_gate_would_catch_a_route_that_still_uses_sql(runtime, monkeypatch):
    """Negative control: with the learner store on Postgres the same route reaches SQL and the guard turns it into a 500."""
    _, auth = register(runtime, "control@example.org")
    monkeypatch.setattr(settings, "learner_store", "postgres")
    assert runtime.get("/v1/learner/me", headers=auth).status_code in (500, 503)
