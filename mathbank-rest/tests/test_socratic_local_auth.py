from typing import Annotated

import bcrypt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from mathbank_rest import socratic_auth as auth
from mathbank_rest import socratic_local_auth as local
from mathbank_rest.config import settings
from mathbank_rest.routers.socratic import require_staff, router

ORIGIN = "http://127.0.0.1:5186"
PASSWORD = "synthetic-local-test-password"
PASSWORD_HASH = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture
def local_config(monkeypatch):
    for key, value in {
        "socratic_auth_mode": "local",
        "socratic_local_username": "local-author",
        "socratic_local_password_hash": SecretStr(PASSWORD_HASH),
        "socratic_local_capabilities": ["author"],
        "socratic_csrf_secret": SecretStr("offline-local-csrf-secret-32-characters"),
        "socratic_allowed_origins": [ORIGIN],
        "socratic_cookie_secure": False,
        "socratic_session_seconds": 60,
        "cognito_user_pool_id": "", "cognito_client_id": "",
        "cognito_client_secret": SecretStr(""),
    }.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(local, "store", local.LocalSessionStore())
    monkeypatch.setattr(auth, "client", lambda: pytest.fail("Local authentication must not call AWS"))


@pytest.fixture
def app(local_config):
    app = FastAPI()
    app.include_router(router)

    @app.post("/v1/admin/socratic/test-write")
    def write(staff: Annotated[auth.StaffSession, Depends(require_staff)]):
        return {"actor": staff.actor.actor_id}

    return app


@pytest.fixture
def client(app):
    with TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 43210)) as client:
        yield client


def login(client, password=PASSWORD):
    return client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                       json={"username": "local-author", "password": password})


def test_local_login_restore_csrf_logout_and_replay_without_cognito(client):
    signed_in = login(client)
    assert signed_in.status_code == 200
    session = signed_in.json()
    assert session["auth_mode"] == "local"
    assert session["actor"]["actor_id"].startswith("local:")
    assert session["actor"]["capabilities"] == ["author", "preview"]
    assert session["role"] == "admin" and session["roles"] == ["admin", "student"]
    assert PASSWORD not in signed_in.text
    cookies = client.cookies.get_dict() if hasattr(client.cookies, "get_dict") else dict(client.cookies)
    assert len(cookies) == 3  # access, refresh, active role
    for cookie in signed_in.headers.get_list("set-cookie"):
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie
        assert "Secure" not in cookie and "Path=/v1/admin/socratic" in cookie
    assert client.get("/v1/admin/socratic/session").json() == session
    assert client.post("/v1/admin/socratic/test-write", headers={"Origin": ORIGIN}).status_code == 403
    headers = {"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}
    assert client.post("/v1/admin/socratic/test-write", headers=headers).status_code == 200
    assert client.delete("/v1/admin/socratic/session", headers=headers).status_code == 204
    client.cookies.update(cookies)
    assert client.get("/v1/admin/socratic/session").status_code == 401


def test_wrong_password_and_long_utf8_password_fail_safely(client):
    assert login(client, "incorrect-password").status_code == 401
    assert login(client, "\u00e9" * 40).status_code == 401
    assert not local.store.sessions


def test_local_sessions_expire_and_restart_revokes_them(client, monkeypatch):
    login(client)
    now = local.time.monotonic()
    monkeypatch.setattr(local.time, "monotonic", lambda: now + 61)
    assert client.get("/v1/admin/socratic/session").status_code == 401
    login(client)
    monkeypatch.setattr(local, "store", local.LocalSessionStore())
    assert client.get("/v1/admin/socratic/session").status_code == 401


def test_local_capabilities_are_explicit_and_changes_invalidate_sessions(client, monkeypatch):
    login(client)
    monkeypatch.setattr(settings, "socratic_local_capabilities", ["author", "review_mathematics"])
    assert client.get("/v1/admin/socratic/session").status_code == 401
    session = login(client).json()
    assert session["actor"]["capabilities"] == ["author", "review_mathematics", "preview"]
    assert "publish" not in session["actor"]["capabilities"]


@pytest.mark.parametrize("peer,host", [
    ("192.0.2.1", ORIGIN), ("127.0.0.1", "http://studio.example.test"),
])
def test_local_auth_rejects_remote_peer_or_host(app, peer, host):
    with TestClient(app, base_url=host, client=(peer, 43210)) as client:
        assert login(client).status_code == 403
        client.cookies.set(auth.ACCESS_COOKIE, "made-up-token")
        assert client.get("/v1/admin/socratic/session").status_code == 403


def test_local_auth_rejects_remote_origin_and_missing_hash(client, monkeypatch):
    monkeypatch.setattr(settings, "socratic_allowed_origins", ["https://studio.example.test"])
    assert login(client).status_code == 503
    monkeypatch.setattr(settings, "socratic_allowed_origins", [ORIGIN])
    monkeypatch.setattr(settings, "socratic_local_password_hash", SecretStr(""))
    assert login(client).status_code == 503


def test_no_cognito_failure_fallback_to_local(client, monkeypatch):
    monkeypatch.setattr(settings, "socratic_auth_mode", "cognito")
    assert login(client).status_code == 503
    assert not local.store.sessions


def test_local_mode_is_rejected_inside_aws_runtimes(client, monkeypatch):
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "synthetic-function")
    response = login(client)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "LOCAL_STAFF_NOT_ALLOWED"


def test_local_session_limit_is_explicit_and_tokens_are_not_stored_in_clear(client):
    local.store.limit = 1
    login(client)
    assert login(client).status_code == 429
    token = client.cookies[auth.ACCESS_COOKIE]
    assert token not in repr(local.store.sessions)


def test_logout_with_wrong_refresh_cannot_revoke_another_session(client):
    csrf = login(client).json()["csrf_token"]
    client.cookies.clear()
    access, _ = local.store.login("local-author", PASSWORD)
    client.cookies.set(auth.ACCESS_COOKIE, access)
    client.cookies.set(auth.REFRESH_COOKIE, "wrong-refresh")
    # This request has a stale CSRF token as well; neither check may revoke a session.
    response = client.delete("/v1/admin/socratic/session",
                             headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
    assert response.status_code == 403
    assert len(local.store.sessions) == 2
    response = client.delete("/v1/admin/socratic/session",
                             headers={"Origin": ORIGIN, "X-CSRF-Token": auth.csrf_token(access)})
    assert response.status_code == 401
    assert len(local.store.sessions) == 2
