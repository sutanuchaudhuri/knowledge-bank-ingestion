"""Studio roles (admin ⇄ student), user management and access audit — offline, mocked Cognito."""
from datetime import datetime, timezone
from unittest.mock import Mock

import jwt
import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from mathbank_rest import socratic_auth as auth
from mathbank_rest import socratic_users as users
from mathbank_rest.config import settings
from mathbank_rest.routers.socratic import router

ORIGIN = "https://studio.example.test"
ACCESS = jwt.encode({
    "iss": "https://cognito-idp.us-east-2.amazonaws.com/us-east-2_synthetic", "client_id": "synthetic-client",
    "token_use": "access", "sub": "staff-sub",
}, "offline-provider-signature-key-only", algorithm="HS256")
SELF = "admin@example.test"
OTHER = "student@example.test"


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "synthetic"}}, "op")


@pytest.fixture
def provider(monkeypatch):
    for name, value in {
        "cognito_user_pool_id": "us-east-2_synthetic", "socratic_auth_mode": "cognito",
        "socratic_aws_profile": "", "cognito_client_id": "synthetic-client",
        "cognito_client_secret": SecretStr("synthetic-client-secret"), "cognito_admin_group": "Admins",
        "cognito_student_group": "Students",
        "socratic_csrf_secret": SecretStr("synthetic-csrf-key-for-offline-tests-only"),
        "socratic_allowed_origins": [ORIGIN], "socratic_cookie_secure": True, "socratic_session_seconds": 900,
        "socratic_math_reviewer_group": "", "socratic_pedagogy_reviewer_group": "", "socratic_publisher_group": "",
        "socratic_access_audit": False,
    }.items():
        monkeypatch.setattr(settings, name, value)
    mock = Mock()
    mock.admin_initiate_auth.return_value = {
        "AuthenticationResult": {"AccessToken": ACCESS, "RefreshToken": "refresh", "ExpiresIn": 3600}}
    mock.get_user.return_value = {"Username": SELF, "UserAttributes": [{"Name": "sub", "Value": "staff-sub"}]}
    mock.admin_list_groups_for_user.return_value = {"Groups": [{"GroupName": "Admins"}, {"GroupName": "Students"}]}
    created = datetime(2026, 10, 1, tzinfo=timezone.utc)
    other = {"Username": OTHER, "Enabled": True, "UserStatus": "CONFIRMED", "UserCreateDate": created,
             "UserLastModifiedDate": created,
             "Attributes": [{"Name": "email", "Value": OTHER}, {"Name": "email_verified", "Value": "true"}]}
    mock.list_users.return_value = {"Users": [other]}
    mock.list_users_in_group.side_effect = lambda **kw: {
        "Users": [{"Username": OTHER}] if kw["GroupName"] == "Students" else [{"Username": SELF}]}
    mock.admin_get_user.return_value = {**{k: v for k, v in other.items() if k != "Attributes"},
                                        "UserAttributes": other["Attributes"], "UserMFASettingList": []}
    monkeypatch.setattr(auth, "client", lambda: mock)
    return mock


@pytest.fixture
def audit(monkeypatch):
    events = []
    monkeypatch.setattr(users, "record", lambda request, action, subject, **kw: events.append(
        (action, subject, kw.get("detail") or {})))
    return events


@pytest.fixture
def client(provider, audit):
    app = FastAPI()
    app.include_router(router)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def sign_in(client):
    response = client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                           json={"username": SELF, "password": "synthetic-password"})
    assert response.status_code == 200
    return response.json()


def write(client, session, method, path, **kw):
    return client.request(method, path, headers={"Origin": ORIGIN, "X-CSRF-Token": session["csrf_token"]}, **kw)


def test_dual_member_sees_roles_and_switching_changes_server_side_access(client, audit):
    session = sign_in(client)
    assert session["role"] == "admin" and session["roles"] == ["admin", "student"]
    assert "manage_users" in session["actor"]["capabilities"]
    switched = write(client, session, "PUT", "/v1/admin/socratic/session/role", json={"role": "student"})
    assert switched.status_code == 200
    assert switched.json()["role"] == "student" and switched.json()["actor"]["capabilities"] == ["preview"]
    # The role cookie now narrows every request: no authoring, no user management.
    restored = client.get("/v1/admin/socratic/session").json()
    assert restored["role"] == "student"
    assert client.get("/v1/admin/socratic/users").status_code == 403
    assert client.get("/v1/admin/socratic/strategies").status_code == 403
    assert write(client, restored, "POST", "/v1/admin/socratic/workflows",
                 json={"title": "x", "domain": "y"}, ).status_code in (403, 422)
    back = write(client, restored, "PUT", "/v1/admin/socratic/session/role", json={"role": "admin"})
    assert back.json()["role"] == "admin"
    assert ("STUDIO_ROLE_SWITCHED", SELF, {"role": "student"}) in audit
    assert audit[0][0] == "STUDIO_SIGN_IN_SUCCEEDED"


def test_role_switch_requires_csrf_and_membership(client, provider):
    session = sign_in(client)
    no_csrf = client.put("/v1/admin/socratic/session/role", headers={"Origin": ORIGIN}, json={"role": "student"})
    assert no_csrf.status_code == 403
    provider.admin_list_groups_for_user.return_value = {"Groups": [{"GroupName": "Admins"}]}
    denied = write(client, session, "PUT", "/v1/admin/socratic/session/role", json={"role": "student"})
    assert denied.status_code == 403 and denied.json()["detail"]["code"] == "STAFF_ROLE_NOT_GRANTED"


def test_forged_role_cookie_cannot_grant_a_role(client, provider):
    sign_in(client)
    provider.admin_list_groups_for_user.return_value = {"Groups": [{"GroupName": "Admins"}]}
    client.cookies.set(auth.ROLE_COOKIE, "student", path="/v1/admin/socratic")
    assert client.get("/v1/admin/socratic/session").json()["role"] == "admin"


def test_students_only_members_cannot_enter_the_studio(client, provider):
    provider.admin_list_groups_for_user.return_value = {"Groups": [{"GroupName": "Students"}]}
    response = client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                           json={"username": OTHER, "password": "synthetic-password"})
    assert response.status_code == 403 and response.json()["detail"]["code"] == "STAFF_GROUP_REQUIRED"


def test_failed_sign_in_is_audited_without_the_password(client, provider, audit):
    provider.admin_initiate_auth.side_effect = client_error("NotAuthorizedException")
    response = client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                           json={"username": " Someone@Example.test ", "password": "never-logged"})
    assert response.status_code == 401
    assert audit == [("STUDIO_SIGN_IN_FAILED", "someone@example.test", {"code": "INVALID_STAFF_CREDENTIALS"})]
    assert "never-logged" not in repr(audit)


def test_user_list_merges_groups_and_filters_by_email_prefix(client, provider):
    sign_in(client)
    page = client.get("/v1/admin/socratic/users", params={"q": "stud@"}).json()
    assert page["users"][0]["username"] == OTHER and page["users"][0]["groups"] == ["Students"]
    assert page["manageable_groups"] == ["Admins", "Students"]
    assert page["role_matrix"]["student"] == ["preview"]
    assert provider.list_users.call_args.kwargs["Filter"] == 'email ^= "stud@"'


def test_group_changes_password_reset_sign_out_and_enable(client, provider, audit):
    session = sign_in(client)
    base = f"/v1/admin/socratic/users/{OTHER}"
    assert write(client, session, "PUT", f"{base}/groups/Admins").status_code == 200
    provider.admin_add_user_to_group.assert_called_with(UserPoolId="us-east-2_synthetic", Username=OTHER, GroupName="Admins")
    assert write(client, session, "DELETE", f"{base}/groups/Students").status_code == 200
    assert write(client, session, "PUT", f"{base}/groups/Root").status_code == 422
    assert write(client, session, "POST", f"{base}/password-reset").status_code == 200
    provider.admin_reset_user_password.assert_called_once()
    assert write(client, session, "POST", f"{base}/sign-out").status_code == 200
    provider.admin_user_global_sign_out.assert_called_once()
    assert write(client, session, "PUT", f"{base}/enabled", json={"enabled": False}).status_code == 200
    provider.admin_disable_user.assert_called_once()
    actions = [event[0] for event in audit]
    for action in ("ADMIN_GROUP_ADDED", "ADMIN_GROUP_REMOVED", "ADMIN_PASSWORD_RESET",
                   "ADMIN_GLOBAL_SIGN_OUT", "ADMIN_USER_DISABLED"):
        assert action in actions


def test_user_mutations_require_csrf(client, provider):
    sign_in(client)
    response = client.post(f"/v1/admin/socratic/users/{OTHER}/password-reset", headers={"Origin": ORIGIN})
    assert response.status_code == 403
    provider.admin_reset_user_password.assert_not_called()


def test_admins_cannot_lock_themselves_out(client, provider):
    session = sign_in(client)
    base = f"/v1/admin/socratic/users/{SELF}"
    for method, path, body in (("DELETE", f"{base}/groups/Admins", None), ("PUT", f"{base}/enabled", {"enabled": False}),
                               ("POST", f"{base}/sign-out", None), ("POST", f"{base}/password-reset", None)):
        response = write(client, session, method, path, **({"json": body} if body else {}))
        assert response.status_code == 409 and response.json()["detail"]["code"] == "STAFF_SELF_LOCKOUT"
    provider.admin_remove_user_from_group.assert_not_called()
    provider.admin_disable_user.assert_not_called()


def test_unknown_user_is_404_not_a_sign_in_error(client, provider):
    sign_in(client)
    provider.admin_get_user.side_effect = client_error("UserNotFoundException")
    response = client.get("/v1/admin/socratic/users/ghost@example.test")
    assert response.status_code == 404 and response.json()["detail"]["code"] == "STAFF_USER_NOT_FOUND"


def test_self_service_password_change(client, provider, audit):
    session = sign_in(client)
    body = {"current_password": "old-password", "new_password": "new-password-123"}
    provider.change_password.side_effect = client_error("NotAuthorizedException")
    wrong = write(client, session, "POST", "/v1/admin/socratic/session/password", json=body)
    assert wrong.status_code == 401 and wrong.json()["detail"]["code"] == "CURRENT_PASSWORD_INVALID"
    provider.change_password.side_effect = client_error("InvalidPasswordException")
    weak = write(client, session, "POST", "/v1/admin/socratic/session/password", json=body)
    assert weak.status_code == 422 and "new-password-123" not in weak.text
    provider.change_password.side_effect = None
    assert write(client, session, "POST", "/v1/admin/socratic/session/password", json=body).status_code == 204
    assert provider.change_password.call_args.kwargs == {
        "PreviousPassword": "old-password", "ProposedPassword": "new-password-123", "AccessToken": ACCESS}
    assert ("STUDIO_PASSWORD_CHANGED", SELF, {}) in audit


def test_ip_prefix_keeps_only_the_network():
    request = Mock()
    request.headers = {"x-forwarded-for": "203.0.113.77, 10.0.0.1"}
    assert users._ip_prefix(request) == "203.0.113.0/24"
    request.headers = {"x-forwarded-for": "2001:db8:1234:5678::1"}
    assert users._ip_prefix(request) == "2001:db8:1234::/48"


def test_audit_is_a_no_op_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "socratic_access_audit", False)
    engine = Mock()
    monkeypatch.setattr(users, "engine", engine)
    users.record(None, "STUDIO_SIGN_OUT", "x")
    engine.begin.assert_not_called()
