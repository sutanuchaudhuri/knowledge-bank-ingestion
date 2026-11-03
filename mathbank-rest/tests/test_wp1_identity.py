"""WP1 identity fixes (LRN-F02, LRN-F11, KNP-F03 mastery attribution) — offline, no database."""
from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from mathbank_rest import security
from mathbank_rest.config import settings
from mathbank_rest.db import learner as learner_db
from mathbank_rest.main import app
from mathbank_rest.security import SERVICE_ACTOR


@pytest.fixture(autouse=True)
def _clean_cache():
    security._status_cache.clear()
    yield
    security._status_cache.clear()
    app.dependency_overrides.clear()


def _bearer(student_id: UUID) -> dict:
    return {"Authorization": "Bearer " + security.create_access_token(student_id)}


def _statuses(monkeypatch, mapping: dict, calls: list | None = None):
    def load(student_id):
        if calls is not None:
            calls.append(student_id)
        return mapping.get(student_id)

    monkeypatch.setattr(security, "_load_student_status", load)


# ── LRN-F11: status enforced on every learner request ───────────────────────────────────────────────────────────

def test_active_student_token_is_accepted(monkeypatch):
    sid = uuid4()
    _statuses(monkeypatch, {sid: "ACTIVE"})
    monkeypatch.setattr(learner_db, "get_student_profile", lambda s: {"student_id": s, "status": "ACTIVE"})
    response = TestClient(app).get("/v1/learner/me", headers=_bearer(sid))
    assert response.status_code == 200


@pytest.mark.parametrize("state", ["DISABLED", "DELETED", "SOMETHING_ELSE"])
def test_non_active_student_valid_jwt_is_rejected(monkeypatch, state):
    sid = uuid4()
    _statuses(monkeypatch, {sid: state})
    response = TestClient(app).get("/v1/learner/me", headers=_bearer(sid))
    assert response.status_code == 401


def test_unknown_student_valid_jwt_is_rejected(monkeypatch):
    _statuses(monkeypatch, {})
    assert TestClient(app).get("/v1/learner/mastery", headers=_bearer(uuid4())).status_code == 401


def test_optional_student_dependency_also_enforces_status(monkeypatch):
    from fastapi.security import HTTPAuthorizationCredentials

    sid = uuid4()
    _statuses(monkeypatch, {sid: "DISABLED"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=security.create_access_token(sid))
    with pytest.raises(security.HTTPException) as exc:
        security.get_optional_student_id(creds)
    assert exc.value.status_code == 401
    assert security.get_optional_student_id(None) is None


def test_database_outage_fails_closed_with_503(monkeypatch):
    def boom(_):
        raise OperationalError("select", {}, Exception("down"))

    monkeypatch.setattr(security, "_load_student_status", boom)
    assert TestClient(app).get("/v1/learner/mastery", headers=_bearer(uuid4())).status_code == 503


def test_status_lookup_is_cached_within_ttl(monkeypatch):
    sid = uuid4()
    calls: list = []
    _statuses(monkeypatch, {sid: "ACTIVE"}, calls)
    monkeypatch.setattr(settings, "auth_status_cache_seconds", 30)
    for _ in range(3):
        security.assert_student_active(sid)
    assert calls == [sid]


def test_status_cache_expires(monkeypatch):
    sid = uuid4()
    calls: list = []
    _statuses(monkeypatch, {sid: "ACTIVE"}, calls)
    monkeypatch.setattr(settings, "auth_status_cache_seconds", 30)
    clock = [1000.0]
    monkeypatch.setattr(security.time, "monotonic", lambda: clock[0])
    security.assert_student_active(sid)
    clock[0] += 31
    security.assert_student_active(sid)
    assert calls == [sid, sid]


def test_zero_ttl_disables_the_cache(monkeypatch):
    sid = uuid4()
    calls: list = []
    _statuses(monkeypatch, {sid: "ACTIVE"}, calls)
    monkeypatch.setattr(settings, "auth_status_cache_seconds", 0)
    security.assert_student_active(sid)
    security.assert_student_active(sid)
    assert len(calls) == 2


def test_invalidate_takes_effect_before_ttl(monkeypatch):
    sid = uuid4()
    mapping = {sid: "ACTIVE"}
    _statuses(monkeypatch, mapping)
    monkeypatch.setattr(settings, "auth_status_cache_seconds", 300)
    security.assert_student_active(sid)
    mapping[sid] = "DISABLED"
    security.assert_student_active(sid)  # stale, still within the TTL
    security.invalidate_student_status(sid)
    with pytest.raises(security.HTTPException) as exc:
        security.assert_student_active(sid)
    assert exc.value.status_code == 401


def test_login_refuses_non_active_account(monkeypatch):
    from mathbank_rest.routers import learner as learner_router

    password = "correct horse battery"
    row = {
        "student_id": uuid4(), "email": "a@example.com", "password_hash": security.hash_password(password),
        "first_name": "A", "last_name": "B", "display_name": "A B", "status": "DISABLED",
    }
    monkeypatch.setattr(learner_router.learner_db, "get_student_by_email", lambda e: row)
    touched = []
    monkeypatch.setattr(learner_router.learner_db, "touch_last_login", touched.append)
    response = TestClient(app).post("/v1/learner/login", json={"email": "a@example.com", "password": password})
    assert response.status_code == 403
    assert touched == []
    row["status"] = "ACTIVE"
    assert TestClient(app).post(
        "/v1/learner/login", json={"email": "a@example.com", "password": password}
    ).status_code == 200


# ── LRN-F11: admin disable / enable ─────────────────────────────────────────────────────────────────────────────

@contextmanager
def _admin_client():
    app.dependency_overrides.clear()
    yield TestClient(app), {"X-Admin-Api-Key": settings.admin_api_key}


def test_disable_requires_admin_credentials():
    assert TestClient(app).post(f"/v1/admin/students/{uuid4()}/disable").status_code == 401
    assert TestClient(app).post(f"/v1/admin/students/{uuid4()}/enable").status_code == 401


def test_disable_records_actor_and_invalidates_cache(monkeypatch):
    sid = uuid4()
    seen = []
    monkeypatch.setattr(
        learner_db, "set_student_status",
        lambda student_id, new_status, actor_id: seen.append((student_id, new_status, actor_id))
        or {"student_id": student_id, "status": new_status, "disabled_at": None},
    )
    mapping = {sid: "ACTIVE"}
    _statuses(monkeypatch, mapping)
    monkeypatch.setattr(settings, "auth_status_cache_seconds", 300)
    client = TestClient(app)
    assert client.get("/v1/learner/mastery", headers=_bearer(sid)).status_code != 401  # warms the cache as ACTIVE

    mapping[sid] = "DISABLED"
    with _admin_client() as (admin, headers):
        response = admin.post(f"/v1/admin/students/{sid}/disable", headers={**headers, "X-Actor-Id": "mallory"})
    assert response.status_code == 200
    assert seen == [(sid, "DISABLED", SERVICE_ACTOR.id)]
    assert client.get("/v1/learner/mastery", headers=_bearer(sid)).status_code == 401  # no TTL wait


def test_enable_and_unknown_or_deleted_student(monkeypatch):
    sid = uuid4()

    def fake(student_id, new_status, actor_id):
        if student_id == sid:
            return {"student_id": student_id, "status": new_status, "disabled_at": None}
        if new_status == "ACTIVE" and student_id.int % 2:
            raise ValueError("account is deleted")
        return None

    monkeypatch.setattr(learner_db, "set_student_status", fake)
    with _admin_client() as (admin, headers):
        assert admin.post(f"/v1/admin/students/{sid}/enable", headers=headers).json()["status"] == "ACTIVE"
        assert admin.post(f"/v1/admin/students/{UUID(int=2)}/disable", headers=headers).status_code == 404
        assert admin.post(f"/v1/admin/students/{UUID(int=3)}/enable", headers=headers).status_code == 409


class _FakeResult:
    def __init__(self, rows=None, scalar=None):
        self._rows, self._scalar = rows or [], scalar

    def scalar(self):
        return self._scalar

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)

    def __iter__(self):
        return iter(self._rows)


class _FakeConn:
    def __init__(self, handler):
        self.handler, self.executed = handler, []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.executed.append((sql, params))
        return self.handler(sql, params)


class _FakeEngine:
    def __init__(self, handler):
        self.conn = _FakeConn(handler)

    def begin(self):
        return self._ctx()

    connect = begin

    @contextmanager
    def _ctx(self):
        yield self.conn


def test_set_student_status_writes_audit_row_with_actor(monkeypatch):
    sid = uuid4()

    def handler(sql, params):
        if sql.startswith("SELECT status"):
            return _FakeResult(scalar="ACTIVE")
        if sql.startswith("UPDATE"):
            return _FakeResult(rows=[{"student_id": sid, "status": "DISABLED", "disabled_at": None}])
        return _FakeResult()

    fake = _FakeEngine(handler)
    monkeypatch.setattr(learner_db, "engine", fake)
    result = learner_db.set_student_status(sid, "DISABLED", "staff:42")
    assert result["status"] == "DISABLED"
    audit = [p for s, p in fake.conn.executed if "audit.action_log" in s]
    assert len(audit) == 1
    assert audit[0]["actor_id"] == "staff:42" and audit[0]["action"] == "STUDENT_DISABLED"
    assert audit[0]["entity_id"] == str(sid)


def test_set_student_status_refuses_deleted_and_missing(monkeypatch):
    monkeypatch.setattr(learner_db, "engine", _FakeEngine(lambda sql, p: _FakeResult(scalar="DELETED")))
    with pytest.raises(ValueError):
        learner_db.set_student_status(uuid4(), "ACTIVE", "x")
    monkeypatch.setattr(learner_db, "engine", _FakeEngine(lambda sql, p: _FakeResult(scalar=None)))
    assert learner_db.set_student_status(uuid4(), "DISABLED", "x") is None


# ── LRN-F02: Cognito onboarding must not take over a password account ───────────────────────────────────────────

def _onboarding_engine(existing: dict | None):
    """Fake DB: `existing` is the already-registered profile (with its cognito_sub), or None."""
    profile = {
        "student_id": uuid4(), "email": "victim@example.com", "first_name": "V", "last_name": "V",
        "display_name": "V V", "grade": None, "phone": None, "status": "ACTIVE",
    }

    def handler(sql, params):
        if sql.startswith("INSERT"):
            if existing is None:
                return _FakeResult(rows=[{**profile, "email": params["email"]}])
            return _FakeResult()
        if sql.startswith("SELECT"):
            return _FakeResult(rows=[{**profile, **existing}])
        return _FakeResult()

    return _FakeEngine(handler), profile


def _onboard(**kw):
    return learner_db.create_student_for_cognito(
        cognito_sub=kw.pop("cognito_sub", "sub-new"), first_name="M", last_name="M",
        email="victim@example.com", **kw,
    )


def _updates(fake):
    return [s for s, _ in fake.conn.executed if s.startswith("UPDATE")]


def test_unverified_email_never_links_existing_password_account(monkeypatch):
    fake, _ = _onboarding_engine({"cognito_sub": None})
    monkeypatch.setattr(learner_db, "engine", fake)
    with pytest.raises(learner_db.EmailAlreadyRegistered) as exc:
        _onboard()
    assert exc.value.status_code == 409 and exc.value.detail["code"] == "EMAIL_ALREADY_REGISTERED"
    assert _updates(fake) == []


def test_email_verified_defaults_to_false(monkeypatch):
    fake, _ = _onboarding_engine({"cognito_sub": None})
    monkeypatch.setattr(learner_db, "engine", fake)
    with pytest.raises(learner_db.EmailAlreadyRegistered):
        learner_db.create_student_for_cognito(
            cognito_sub="s", first_name="M", last_name="M", email="victim@example.com",
        )


def test_verified_email_links_account_without_cognito_identity(monkeypatch):
    fake, profile = _onboarding_engine({"cognito_sub": None})
    monkeypatch.setattr(learner_db, "engine", fake)
    result = _onboard(email_verified=True)
    assert result["student_id"] == profile["student_id"]
    assert "cognito_sub" not in result and "password_hash" not in result
    updates = _updates(fake)
    assert len(updates) == 1 and "cognito_sub IS NULL" in updates[0]


def test_verified_email_cannot_rebind_an_account_already_linked_to_another_identity(monkeypatch):
    fake, _ = _onboarding_engine({"cognito_sub": "someone-else"})
    monkeypatch.setattr(learner_db, "engine", fake)
    with pytest.raises(learner_db.EmailAlreadyRegistered):
        _onboard(email_verified=True)
    assert _updates(fake) == []


def test_repeat_onboarding_of_same_identity_is_idempotent(monkeypatch):
    fake, profile = _onboarding_engine({"cognito_sub": "sub-new"})
    monkeypatch.setattr(learner_db, "engine", fake)
    assert _onboard()["student_id"] == profile["student_id"]
    assert _updates(fake) == []


def test_anonymous_onboarding_cannot_claim_a_real_email(monkeypatch):
    fake, _ = _onboarding_engine({"cognito_sub": None})
    monkeypatch.setattr(learner_db, "engine", fake)
    with pytest.raises(learner_db.EmailAlreadyRegistered):
        _onboard(cognito_sub=None, email_verified=True)


def test_new_email_creates_profile(monkeypatch):
    fake, _ = _onboarding_engine(None)
    monkeypatch.setattr(learner_db, "engine", fake)
    assert _onboard()["email"] == "victim@example.com"
    assert not any("DO UPDATE" in s for s, _ in fake.conn.executed)


def test_onboard_route_maps_collision_to_409(monkeypatch):
    from mathbank_rest.routers import exam_integration

    def collide(**_):
        raise learner_db.EmailAlreadyRegistered()

    monkeypatch.setattr(exam_integration, "create_student_for_cognito", collide)
    response = TestClient(app).post(
        "/v1/quiz-integration/students/onboard",
        headers={"X-Admin-Api-Key": settings.admin_api_key},
        json={"cognito_sub": "s", "first_name": "A", "last_name": "B", "email": "victim@example.com"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "EMAIL_ALREADY_REGISTERED"


# ── KNP-F03: REJECTED tags never feed mastery ───────────────────────────────────────────────────────────────────

def _capture_sql(monkeypatch, rows=None):
    statements = []

    def handler(sql, params):
        statements.append(sql)
        return _FakeResult(rows=rows)

    monkeypatch.setattr(learner_db, "engine", _FakeEngine(handler))
    return statements


def test_problem_fanout_excludes_rejected_tags(monkeypatch):
    statements = _capture_sql(monkeypatch)
    learner_db.get_concepts_and_techniques_for_problem(uuid4())
    assert len(statements) == 2
    assert all("review_status <> 'REJECTED'" in s for s in statements)


def test_mastery_attempt_queries_exclude_rejected_tags(monkeypatch):
    statements = _capture_sql(monkeypatch)
    learner_db.get_attempts_for_concept(uuid4(), uuid4())
    learner_db.get_attempts_for_technique(uuid4(), uuid4())
    assert "pc.review_status <> 'REJECTED'" in statements[0]
    assert "pt.review_status <> 'REJECTED'" in statements[1]


def test_practice_progress_ignores_rejected_concept_tags(monkeypatch):
    statements = _capture_sql(monkeypatch)
    learner_db.get_practice_progress(uuid4())
    assert "pc.review_status <> 'REJECTED'" in statements[0]
