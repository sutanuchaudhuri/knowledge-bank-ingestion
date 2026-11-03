"""Route parity of the learner identity and outcome endpoints between the two learner-store backends (requirement 71 WP5 gate).

One FastAPI app, two backends chosen per request with ``stores.override_store``:

* ``postgres``  the real ``PostgresLearnerStore`` with ``db.learner`` replaced by an in-memory oracle that mirrors the SQL;
* ``dynamodb``  the real ``DynamoDBLearnerStore`` over moto.

Content is the WP4 corpus served by the (already parity-tested) DynamoDB content store on both sides, so only the learner store
differs. Differences the design allows are listed explicitly in ``ALLOWED`` or have a test of their own at the bottom.
"""
from __future__ import annotations

import datetime as dt
import sys
import uuid
from pathlib import Path
from uuid import UUID

import pytest
import test_wp4_catalog as wp4
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))
from parity_harness import ParityCase, assert_parity

from mathbank_rest import mastery, security, stores
from mathbank_rest.db import learner as learner_db
from mathbank_rest.main import app
from mathbank_rest.models.manual.learner_outcomes import DailyItem
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore, catalog
from mathbank_rest.stores.learner import DynamoDBLearnerStore, PostgresLearnerStore
from mathbank_rest.stores.learner.outcomes import OutcomesDynamoDB

PASSWORD = "correct horse battery"
EMAIL = "ada@example.org"
NOW = dt.datetime.now(dt.UTC)
ALLOWED = ["$.student_id", "$.access_token", "$.last_login_at", "$.attempt.attempt_id", "$.attempt.attempted_at",
           "$[*].attempt_id", "$[*].attempted_at", "$.concepts[*].last_attempt_at", "$.techniques[*].last_attempt_at"]
LIVE = {p.code: p for p in wp4.LIVE}
DAYS = ("2026-10-01", "2026-10-02", "2026-10-04")


# ------------------------------------------------------------------------------------------------ the SQL oracle

class SqlOracle:
    """``db.learner`` as the SQL behaves, for the calls the learner routes make."""

    def __init__(self):
        self.students: dict[str, dict] = {}
        self.attempts: list[dict] = []
        self.scores: dict[tuple[str, str, str], dict] = {}

    # identity
    def get_student_by_email(self, email):
        row = next((s for s in self.students.values() if s["email"] == email), None)
        keys = ("student_id", "email", "password_hash", "first_name", "last_name", "display_name", "status")
        return None if row is None else {k: row[k] for k in keys}

    def create_student(self, *, email, password_hash, first_name, last_name):
        sid = uuid.uuid4()
        row = {"student_id": sid, "email": email, "password_hash": password_hash, "first_name": first_name, "last_name": last_name,
               "display_name": f"{first_name} {last_name}".strip(), "status": "ACTIVE", "created_at": NOW, "last_login_at": None,
               "grade": None, "phone": None}
        self.students[str(sid)] = row
        return {k: row[k] for k in ("student_id", "email", "first_name", "last_name", "display_name", "status", "created_at")}

    def touch_last_login(self, student_id):
        self.students[str(student_id)]["last_login_at"] = dt.datetime.now(dt.UTC)

    def get_student_profile(self, student_id):
        row = self.students.get(str(student_id))
        keys = ("student_id", "email", "first_name", "last_name", "display_name", "status", "created_at", "last_login_at", "grade", "phone")
        return None if row is None else {k: row[k] for k in keys}

    def get_student_status(self, student_id):
        row = self.students.get(str(student_id))
        return None if row is None else row["status"]

    def update_student_profile(self, student_id, changes):
        row = self.students.get(str(student_id))
        if row is None:
            return None
        values = dict(changes)
        if "display_name" not in values and ("first_name" in values or "last_name" in values):
            values["display_name"] = f"{values.get('first_name', row['first_name'])} {values.get('last_name', row['last_name'])}".strip()
        row.update(values)
        return self.get_student_profile(student_id)

    def get_student_password_hash(self, student_id):
        row = self.students.get(str(student_id))
        return None if row is None else row["password_hash"]

    def set_student_password_hash(self, student_id, password_hash):
        self.students[str(student_id)]["password_hash"] = password_hash
        return True

    # outcomes
    def get_problem_id_by_code(self, code):
        return UUID(wp4.pid(code)) if code in LIVE else None

    @staticmethod
    def _problem(problem_id):
        return next(p for p in wp4.PROBLEMS if wp4.pid(p.code) == str(problem_id))

    def get_concepts_and_techniques_for_problem(self, problem_id):
        p = self._problem(problem_id)
        return {"concept_ids": [UUID(wp4.uid(f"concept:{s}")) for s, _, _ in p.concepts],
                "technique_ids": [UUID(wp4.uid(f"technique:{s}")) for s, _, _ in p.techniques]}

    def insert_attempt(self, *, student_id, problem_id, is_correct, submitted_answer, time_spent_seconds, hint_count, source):
        row = {"attempt_id": uuid.uuid4(), "attempted_at": dt.datetime.now(dt.UTC), "student_id": str(student_id),
               "problem_id": str(problem_id), "is_correct": is_correct, "submitted_answer": submitted_answer,
               "time_spent_seconds": time_spent_seconds, "hint_count": hint_count, "source": source}
        self.attempts.append(row)
        return {"attempt_id": row["attempt_id"], "attempted_at": row["attempted_at"]}

    def list_attempts(self, student_id, *, limit=50, offset=0):
        rows = sorted((a for a in self.attempts if a["student_id"] == str(student_id)), key=lambda a: a["attempted_at"], reverse=True)
        out = []
        for a in rows[offset:offset + limit]:
            p = self._problem(a["problem_id"])
            out.append({"attempt_id": a["attempt_id"], "is_correct": a["is_correct"], "submitted_answer": a["submitted_answer"],
                        "time_spent_seconds": a["time_spent_seconds"], "hint_count": a["hint_count"], "attempted_at": a["attempted_at"],
                        "source": a["source"], "canonical_code": p.code, "problem_number": p.num, "difficulty_band": "EASY",
                        "competition": p.comp_name, "year": p.year})
        return out

    def _evidence(self, student_id, kind, tag):
        key = "concept_ids" if kind == "C" else "technique_ids"
        rows = [{"is_correct": a["is_correct"], "attempted_at": a["attempted_at"], "hint_count": a["hint_count"], "difficulty_band": "EASY"}
                for a in self.attempts if a["student_id"] == str(student_id) and a["is_correct"] is not None
                and tag in self.get_concepts_and_techniques_for_problem(a["problem_id"])[key]]
        return sorted(rows, key=lambda r: r["attempted_at"])

    def get_attempts_for_concept(self, student_id, concept_id):
        return self._evidence(student_id, "C", concept_id)

    def get_attempts_for_technique(self, student_id, technique_id):
        return self._evidence(student_id, "T", technique_id)

    def upsert_concept_mastery(self, *, student_id, concept_id, **row):
        self.scores[("C", str(student_id), str(concept_id))] = row

    def upsert_technique_mastery(self, *, student_id, technique_id, **row):
        self.scores[("T", str(student_id), str(technique_id))] = row

    def get_mastery_summary(self, student_id):
        names = {"C": {wp4.uid(f"concept:{s}"): (s, n[0]) for s, n in wp4.CONCEPTS.items()},
                 "T": {wp4.uid(f"technique:{s}"): (s, n[0]) for s, n in wp4.TECHNIQUES.items()}}
        out = {"concepts": [], "techniques": []}
        for (kind, sid, tag), row in sorted(self.scores.items(), key=lambda kv: (kv[1]["mastery_score"], kv[0][2])):
            if sid == str(student_id):
                slug, name = names[kind][tag]
                out["concepts" if kind == "C" else "techniques"].append({
                    "slug": slug, "name": name, "mastery_score": row["mastery_score"], "attempts_count": row["attempts_count"],
                    "correct_count": row["correct_count"], "last_attempt_at": row["last_attempt_at"]})
        return out

    def get_practice_progress(self, student_id):
        attempted = {a["problem_id"] for a in self.attempts if a["student_id"] == str(student_id)}
        items = []
        for kind, themes, attr in (("concept", wp4.CONCEPTS, "concepts"), ("technique", wp4.TECHNIQUES, "techniques")):
            for slug, meta in themes.items():
                codes = {p.code for p in wp4.LIVE if any(s == slug for s, _, _ in getattr(p, attr))}
                done = len({wp4.pid(c) for c in codes} & attempted)
                items.append({"kind": kind, "slug": slug, "name": meta[0], "available": len(codes), "attempted": done,
                              "remaining": len(codes) - done})
        items.sort(key=lambda r: (r["kind"], r["name"].lower(), r["slug"]))
        return {"items": items}

    def list_daily_activity(self, student_id, date_from, date_to):
        return [{"activity_date": dt.date.fromisoformat(d), **COUNTERS[d]} for d in DAYS
                if date_from <= dt.date.fromisoformat(d) <= date_to]


COUNTERS = {
    "2026-10-01": {"attempts_started": 2, "attempts_completed": 1, "attempts_abandoned": 0, "steps_evaluated": 6, "steps_succeeded": 4,
                   "gaps_diagnosed": 1, "knowledge_gaps_created": 1, "recovery_plans_created": 1, "recovery_plans_completed": 0},
    "2026-10-02": {"attempts_started": 1, "attempts_completed": 1, "attempts_abandoned": 0, "steps_evaluated": 3, "steps_succeeded": 3,
                   "gaps_diagnosed": 0, "knowledge_gaps_created": 0, "recovery_plans_created": 0, "recovery_plans_completed": 0},
    "2026-10-04": {"attempts_started": 1, "attempts_completed": 0, "attempts_abandoned": 1, "steps_evaluated": 0, "steps_succeeded": 0,
                   "gaps_diagnosed": 0, "knowledge_gaps_created": 0, "recovery_plans_created": 0, "recovery_plans_completed": 0},
}


# ------------------------------------------------------------------------------------------------ fixtures

class Backend:
    """A TestClient pinned to one learner store; ``$TOKEN`` in the Authorization header is this backend's own token."""

    def __init__(self, store):
        self.store, self.client, self.token = store, TestClient(app), None

    def request(self, method, path, json=None, params=None, headers=None):
        headers = dict(headers or {})
        if headers.get("Authorization") == "$TOKEN":
            headers["Authorization"] = f"Bearer {self.token}"
        with stores.override_store("learner", self.store), stores.override_store("content", DynamoDBContentStore()):
            return self.client.request(method, path, json=json, params=params, headers=headers)


@pytest.fixture()
def clients(content_table, monkeypatch):
    catalog._CATALOGUES.clear()
    OutcomesDynamoDB._themes.clear()
    wp4.seed()
    oracle = SqlOracle()
    for name in [n for n in dir(oracle) if not n.startswith("_") and hasattr(learner_db, n)]:
        monkeypatch.setattr(learner_db, name, getattr(oracle, name))
    frozen = dt.datetime.now(dt.UTC)
    real = mastery.recency_weight
    monkeypatch.setattr(mastery, "recency_weight", lambda attempted_at, *, now=None: real(attempted_at, now=frozen))
    monkeypatch.setattr(security, "_load_student_status", lambda student_id: security._learner_store().get_student_status(student_id))
    security._status_cache.clear()
    yield {"postgres": Backend(PostgresLearnerStore()), "dynamodb": Backend(DynamoDBLearnerStore())}
    security._status_cache.clear()
    catalog._CATALOGUES.clear()
    OutcomesDynamoDB._themes.clear()


def run(clients, name, method, path, *, json=None, params=None, status=200, auth=True, allowed=(), unordered=()):
    case = ParityCase(name, method, path, json=json, params=params, expect_status=status, unordered=unordered,
                      headers={"Authorization": "$TOKEN"} if auth else None)
    return assert_parity(clients, case, allowed=[*ALLOWED, *allowed])


def sign_up(clients, email=EMAIL):
    res = run(clients, "register", "POST", "/v1/learner/register", status=201, auth=False,
              json={"email": email, "password": PASSWORD, "first_name": "Ada", "last_name": "Lovelace"})
    for backend, (_, body) in res.items():
        clients[backend].token = body["access_token"]
    return res


def seed_daily(sid):
    for d in DAYS:
        typed.put(DailyItem(PK=toolkit.student_pk(sid), SK=f"DAILY#{d}", student_id=UUID(sid), activity_date=dt.date.fromisoformat(d),
                            updated_at=NOW, **COUNTERS[d]))


# ------------------------------------------------------------------------------------------------ identity routes

def test_register_login_me_parity(clients):
    sign_up(clients)
    run(clients, "duplicate register", "POST", "/v1/learner/register", status=409, auth=False,
        json={"email": EMAIL, "password": PASSWORD, "first_name": "Other", "last_name": "Person"})
    run(clients, "login with a wrong password", "POST", "/v1/learner/login", status=401, auth=False,
        json={"email": EMAIL, "password": "wrong password"})
    run(clients, "login for an unknown address", "POST", "/v1/learner/login", status=401, auth=False,
        json={"email": "nobody@example.org", "password": PASSWORD})
    res = run(clients, "login", "POST", "/v1/learner/login", auth=False, json={"email": EMAIL, "password": PASSWORD})
    for backend, (_, body) in res.items():
        clients[backend].token = body["access_token"]
    me = run(clients, "me", "GET", "/v1/learner/me")
    assert me["dynamodb"][1]["last_login_at"] is not None and me["dynamodb"][1]["email"] == EMAIL
    run(clients, "me without a token", "GET", "/v1/learner/me", status=401, auth=False)


def test_patch_me_parity(clients):
    sign_up(clients)
    run(clients, "patch names and grade", "PATCH", "/v1/learner/me", json={"first_name": "Augusta", "grade": "11", "phone": "555-0100"})
    run(clients, "patch display name only", "PATCH", "/v1/learner/me", json={"display_name": "Countess"})
    run(clients, "clear the grade", "PATCH", "/v1/learner/me", json={"grade": None})
    run(clients, "empty patch", "PATCH", "/v1/learner/me", json={})
    run(clients, "patch with an unknown field", "PATCH", "/v1/learner/me", status=422, json={"email": "evil@example.org"})
    run(clients, "blank name", "PATCH", "/v1/learner/me", status=422, json={"first_name": "  "})
    run(clients, "cannot clear a name", "PATCH", "/v1/learner/me", status=422, json={"last_name": None})
    run(clients, "me after the edits", "GET", "/v1/learner/me")


def test_change_password_parity_and_login_with_the_new_password(clients):
    sign_up(clients)
    run(clients, "wrong current password", "POST", "/v1/learner/me/password", status=403,
        json={"current_password": "nope nope nope", "new_password": "a brand new password"})
    run(clients, "too short", "POST", "/v1/learner/me/password", status=422,
        json={"current_password": PASSWORD, "new_password": "short"})
    res = run(clients, "change", "POST", "/v1/learner/me/password",
              json={"current_password": PASSWORD, "new_password": "a brand new password"})
    assert res["postgres"][1]["changed"] is True and res["postgres"][1]["token_type"] == "bearer"
    for backend, (_, body) in res.items():
        clients[backend].token = body["access_token"]
    run(clients, "old password no longer works", "POST", "/v1/learner/login", status=401, auth=False,
        json={"email": EMAIL, "password": PASSWORD})
    run(clients, "new password works", "POST", "/v1/learner/login", auth=False,
        json={"email": EMAIL, "password": "a brand new password"})
    run(clients, "the fresh token works", "GET", "/v1/learner/me")


def test_documented_difference_tokens_issued_before_a_password_change_stop_working_only_in_dynamodb(clients):
    sign_up(clients)
    old = {b: c.token for b, c in clients.items()}
    run(clients, "change", "POST", "/v1/learner/me/password",
        json={"current_password": PASSWORD, "new_password": "a brand new password"})
    statuses = {}
    for backend, client in clients.items():
        client.token = old[backend]
        statuses[backend] = client.request("GET", "/v1/learner/me", headers={"Authorization": "$TOKEN"}).status_code
    assert statuses == {"postgres": 200, "dynamodb": 401}


# ------------------------------------------------------------------------------------------------ outcome routes

def test_attempts_mastery_plan_progress_and_activity_parity(clients):
    sid = sign_up(clients)["dynamodb"][1]["student_id"]
    seed_daily(sid)
    run(clients, "attempt for an unknown problem", "POST", "/v1/learner/attempts", status=404,
        json={"problem_code": "NOPE_0000_Q01", "is_correct": True})
    run(clients, "attempts need a token", "GET", "/v1/learner/attempts", status=401, auth=False)
    empty = run(clients, "no attempts yet", "GET", "/v1/learner/attempts")
    assert empty["dynamodb"][1] == []
    run(clients, "no mastery yet", "GET", "/v1/learner/mastery")
    for body in (
        {"problem_code": "AIME_2005_I_Q01", "is_correct": True, "submitted_answer": "123", "time_spent_seconds": 40, "hint_count": 1},
        {"problem_code": "AIME_2005_I_Q02", "is_correct": False, "submitted_answer": "9", "hint_count": 0},
        {"problem_code": "AIME_2005_I_Q01", "is_correct": False, "source": "agent_chat"},
        {"problem_code": "AMC10_2005B_Q01", "is_correct": True, "hint_count": 3},
    ):
        res = run(clients, f"attempt {body['problem_code']}", "POST", "/v1/learner/attempts", status=201, json=body)
        assert set(res["dynamodb"][1]) == {"attempt", "updated_mastery"}
    run(clients, "attempts newest first", "GET", "/v1/learner/attempts")
    run(clients, "attempts paged", "GET", "/v1/learner/attempts", params={"limit": 2, "offset": 1})
    summary = run(clients, "mastery", "GET", "/v1/learner/mastery")["dynamodb"][1]
    assert len(summary["concepts"]) == 3 and len(summary["techniques"]) == 1
    plan = run(clients, "improvement plan", "GET", "/v1/learner/mastery/improvement-plan", params={"max_focus_areas": 3})["dynamodb"][1]
    assert len(plan["focus_areas"]) == 3 and plan["total_struggling_areas"] >= 3
    progress = run(clients, "practice progress", "GET", "/v1/learner/practice-progress")["dynamodb"][1]
    assert sum(r["attempted"] for r in progress["items"]) >= 4
    assert run(clients, "activity default window is empty", "GET", "/v1/learner/activity")["dynamodb"][1]["total"] == 0
    window = run(clients, "activity range", "GET", "/v1/learner/activity", params={"from": "2026-10-01", "to": "2026-10-03"})["dynamodb"][1]
    assert [i["activity_date"] for i in window["items"]] == ["2026-10-01", "2026-10-02"] and window["total"] == 2
    run(clients, "activity paged", "GET", "/v1/learner/activity", params={"from": "2026-10-01", "to": "2026-10-31", "limit": 1, "offset": 1})
    run(clients, "activity from after to", "GET", "/v1/learner/activity", status=422, params={"from": "2026-10-05", "to": "2026-10-01"})
    run(clients, "activity range too long", "GET", "/v1/learner/activity", status=422, params={"from": "2024-01-01", "to": "2026-01-01"})


def test_idempotency_key_replays_only_on_the_dynamodb_store(clients):
    sign_up(clients)
    body = {"problem_code": "AIME_2005_I_Q01", "is_correct": True}
    headers = {"Idempotency-Key": "attempt-1"}
    dynamo = clients["dynamodb"]
    with stores.override_store("learner", dynamo.store), stores.override_store("content", DynamoDBContentStore()):
        auth = {"Authorization": f"Bearer {dynamo.token}", **headers}
        first = dynamo.client.post("/v1/learner/attempts", json=body, headers=auth)
        again = dynamo.client.post("/v1/learner/attempts", json=body, headers=auth)
        listing = dynamo.client.get("/v1/learner/attempts", headers=auth)
    assert first.status_code == again.status_code == 201 and again.json() == first.json()
    assert len(listing.json()) == 1


def test_a_frozen_learner_store_still_signs_in_and_reads_but_rejects_writes(clients):
    sign_up(clients)
    frozen = Backend(stores.FrozenProxy("learner", clients["dynamodb"].store))
    login = frozen.request("POST", "/v1/learner/login", json={"email": EMAIL, "password": PASSWORD})
    assert login.status_code == 200
    frozen.token = login.json()["access_token"]
    assert frozen.request("GET", "/v1/learner/me", headers={"Authorization": "$TOKEN"}).status_code == 200
    blocked = frozen.request("PATCH", "/v1/learner/me", json={"grade": "9"}, headers={"Authorization": "$TOKEN"})
    assert blocked.status_code == 503 and blocked.headers["Retry-After"]
    assert frozen.request("POST", "/v1/learner/register", json={
        "email": "new@example.org", "password": PASSWORD, "first_name": "N", "last_name": "N"}).status_code == 503
