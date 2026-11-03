"""Admin identity (requirement 71 WP1a): staff session or service key, never a client-supplied actor.

Staff login uses the loopback `local` mode, so no AWS is involved. The service credential (`X-Admin-Api-Key`)
keeps working for ETL, CI and the web proxy, but its actor is always `service:admin-key`.
"""
from __future__ import annotations

from typing import Annotated

import bcrypt
import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from mathbank_rest import socratic_auth as auth
from mathbank_rest import socratic_local_auth as local
from mathbank_rest.config import settings
from mathbank_rest.routers.socratic import router as socratic_router
from mathbank_rest.security import SERVICE_ACTOR_ID, Actor, admin_actor, require_admin_api_key

ORIGIN = "http://127.0.0.1:5186"
PASSWORD = "synthetic-admin-actor-test-password"
KEY = "unit-test-admin-key"


@pytest.fixture
def staff_config(monkeypatch):
    for k, v in {
        "admin_api_key": KEY,
        "socratic_auth_mode": "local",
        "socratic_local_username": "local-author",
        "socratic_local_password_hash": SecretStr(bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()),
        "socratic_local_capabilities": ["author"],
        "socratic_csrf_secret": SecretStr("offline-local-csrf-secret-32-characters"),
        "socratic_allowed_origins": [ORIGIN],
        "socratic_cookie_secure": False,
        "socratic_session_seconds": 60,
        "cognito_user_pool_id": "", "cognito_client_id": "", "cognito_client_secret": SecretStr(""),
    }.items():
        monkeypatch.setattr(settings, k, v)
    monkeypatch.setattr(local, "store", local.LocalSessionStore())
    monkeypatch.setattr(auth, "client", lambda: pytest.fail("local staff auth must not call AWS"))


@pytest.fixture
def client(staff_config):
    app = FastAPI()
    app.include_router(socratic_router)
    admin = APIRouter(prefix="/v1/admin/probe", dependencies=[Depends(require_admin_api_key)])

    @admin.get("/who")
    def who(actor: Annotated[Actor, Depends(require_admin_api_key)]):
        return {"kind": actor.kind, "id": actor.id, "display": actor.display}

    @admin.post("/write")
    def write(actor: Annotated[Actor, Depends(require_admin_api_key)]):
        return {"id": actor.id}

    @admin.post("/publish")
    def publish(actor: Annotated[Actor, Depends(admin_actor("publish"))]):
        return {"id": actor.id}

    app.include_router(admin)
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 43210)) as c:
        yield c


def sign_in(client):
    r = client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                    json={"username": "local-author", "password": PASSWORD})
    assert r.status_code == 200
    token = client.cookies.get(auth.ACCESS_COOKIE)
    return token, r.json()["csrf_token"], r.json()["actor"]["actor_id"]


def test_shared_key_is_a_service_actor_never_a_person(client):
    r = client.get("/v1/admin/probe/who", headers={"X-Admin-Api-Key": KEY})
    assert r.status_code == 200 and r.json() == {"kind": "service", "id": SERVICE_ACTOR_ID, "display": "admin API key"}
    # a client-supplied actor header is ignored, not trusted
    r = client.get("/v1/admin/probe/who", headers={"X-Admin-Api-Key": KEY, "X-Actor-Id": "alice", "X-Actor": "alice"})
    assert r.json()["id"] == SERVICE_ACTOR_ID


def test_no_credential_and_wrong_key_keep_the_historical_401(client):
    for headers in ({}, {"X-Admin-Api-Key": "wrong"}, {"X-Admin-Api-Key": ""}):
        r = client.get("/v1/admin/probe/who", headers=headers)
        assert r.status_code == 401 and r.json()["detail"] == "invalid admin API key"


def test_staff_bearer_token_identifies_the_person(client):
    token, _, actor_id = sign_in(client)
    client.cookies.clear()
    r = client.get("/v1/admin/probe/who", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"kind": "staff", "id": f"staff:{actor_id}", "display": "local-author"}


def test_bearer_needs_no_csrf_but_cookie_mutations_do(client):
    token, csrf, actor_id = sign_in(client)
    # The Studio cookie is scoped to /v1/admin/socratic, so a browser would not send it to other admin routes.
    # A same-origin proxy that forwards it (or a later widening of the path) reaches this branch; model that here.
    client.cookies.clear()
    client.cookies.set(auth.ACCESS_COOKIE, token, path="/")
    assert client.get("/v1/admin/probe/who").status_code == 200       # safe method, cookie only
    denied = client.post("/v1/admin/probe/write", headers={"Origin": ORIGIN})
    assert denied.status_code == 403 and denied.json()["detail"]["code"] == "STAFF_CSRF_DENIED"
    ok = client.post("/v1/admin/probe/write", headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
    assert ok.status_code == 200 and ok.json()["id"] == f"staff:{actor_id}"
    client.cookies.clear()
    assert client.post("/v1/admin/probe/write", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_capability_is_enforced_per_route_and_the_service_key_holds_all(client):
    token, _, _ = sign_in(client)                      # local author: capabilities = author (+preview)
    client.cookies.clear()
    bearer = {"Authorization": f"Bearer {token}"}
    assert client.post("/v1/admin/probe/write", headers=bearer).status_code == 200
    assert client.post("/v1/admin/probe/publish", headers=bearer).status_code == 403
    assert client.post("/v1/admin/probe/publish", headers={"X-Admin-Api-Key": KEY}).status_code == 200


def test_invalid_or_foreign_bearer_is_rejected(client):
    for bearer in ("not-a-staff-token", "eyJhbGciOiJIUzI1NiJ9.e30.x"):  # incl. a learner-style JWT
        r = client.get("/v1/admin/probe/who", headers={"Authorization": f"Bearer {bearer}"})
        assert r.status_code == 401


def test_expired_staff_session_is_rejected(client, monkeypatch):
    token, _, _ = sign_in(client)
    client.cookies.clear()
    now = local.time.monotonic()
    monkeypatch.setattr(local.time, "monotonic", lambda: now + 61)
    assert client.get("/v1/admin/probe/who", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_a_valid_key_wins_over_a_bad_bearer(client):
    r = client.get("/v1/admin/probe/who", headers={"X-Admin-Api-Key": KEY, "Authorization": "Bearer junk"})
    assert r.status_code == 200 and r.json()["kind"] == "service"


def test_dependency_is_a_drop_in_for_the_existing_routers():
    """17 routers use Depends(require_admin_api_key); it must remain one callable shared instance."""
    from mathbank_rest.routers import admin_corpus, tutoring_routes

    assert tutoring_routes.require_admin_api_key is require_admin_api_key
    assert admin_corpus.require_admin_api_key is require_admin_api_key
