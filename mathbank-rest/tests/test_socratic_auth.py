import base64
import hashlib
import hmac
from typing import Annotated
from unittest.mock import Mock

import jwt
import pytest
from botocore.exceptions import ClientError, EndpointConnectionError, NoCredentialsError
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from mathbank_rest import socratic_auth as auth
from mathbank_rest.config import settings
from mathbank_rest.routers.socratic import require_staff, router

ORIGIN = "https://studio.example.test"
ACCESS_CLAIMS = {
    "iss": "https://cognito-idp.us-east-2.amazonaws.com/us-east-2_synthetic",
    "client_id": "synthetic-client", "token_use": "access", "sub": "stable-staff-sub",
}
ACCESS = jwt.encode(ACCESS_CLAIMS, "offline-provider-signature-key-only", algorithm="HS256")
REFRESH = "synthetic-provider-refresh"


@pytest.fixture
def provider(monkeypatch):
    for name, value in {
        "cognito_user_pool_id": "us-east-2_synthetic",
        "socratic_auth_mode": "cognito",
        "socratic_aws_profile": "",
        "cognito_client_id": "synthetic-client",
        "cognito_client_secret": SecretStr("synthetic-client-secret"),
        "cognito_admin_group": "Admins",
        "socratic_csrf_secret": SecretStr("synthetic-csrf-key-for-offline-tests-only"),
        "socratic_allowed_origins": [ORIGIN],
        "socratic_cookie_secure": True,
        "socratic_session_seconds": 900,
        "socratic_math_reviewer_group": "MathReviewers",
        "socratic_pedagogy_reviewer_group": "PedagogyReviewers",
        "socratic_publisher_group": "Publishers",
    }.items():
        monkeypatch.setattr(settings, name, value)
    mock = Mock()
    mock.admin_initiate_auth.return_value = {
        "AuthenticationResult": {"AccessToken": ACCESS, "RefreshToken": REFRESH, "ExpiresIn": 3600},
    }
    mock.get_user.return_value = {
        "Username": "canonical-staff", "UserAttributes": [{"Name": "sub", "Value": "stable-staff-sub"}],
    }
    mock.admin_list_groups_for_user.return_value = {"Groups": [{"GroupName": "Admins"}]}
    monkeypatch.setattr(auth, "client", lambda: mock)
    return mock


@pytest.fixture
def client(provider):
    app = FastAPI()
    app.include_router(router)

    @app.post("/v1/admin/socratic/test-write")
    def mutation(staff: Annotated[auth.StaffSession, Depends(require_staff)]):
        return {"actor": staff.actor.actor_id}

    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def sign_in(client):
    return client.post("/v1/admin/socratic/session",
                       headers={"Origin": ORIGIN},
                       json={"username": "login-alias", "password": "synthetic-password"})


def test_login_returns_stable_actor_and_scoped_http_only_cookies(client, provider):
    response = sign_in(client)
    assert response.status_code == 200
    assert response.json()["actor"] == {
        "actor_id": "stable-staff-sub", "username": "canonical-staff", "capabilities": ["author"],
    }
    assert ACCESS not in response.text and REFRESH not in response.text
    assert response.headers["Cache-Control"] == "no-store"
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    for cookie in cookies:
        assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie
        assert "Path=/v1/admin/socratic" in cookie and "Max-Age=900" in cookie
    params = provider.admin_initiate_auth.call_args.kwargs
    expected_hash = base64.b64encode(hmac.new(
        b"synthetic-client-secret", b"login-aliassynthetic-client", hashlib.sha256,
    ).digest()).decode()
    assert params["AuthFlow"] == "ADMIN_USER_PASSWORD_AUTH"
    assert params["AuthParameters"]["SECRET_HASH"] == expected_hash
    assert provider.get_user.call_args.kwargs == {"AccessToken": ACCESS}


def test_current_group_membership_is_rechecked_and_not_self_granted(client, provider):
    assert sign_in(client).status_code == 200
    assert client.get("/v1/admin/socratic/session").status_code == 200
    assert provider.get_user.call_count == 2
    assert provider.admin_list_groups_for_user.call_count == 2
    provider.admin_list_groups_for_user.return_value = {"Groups": [{"GroupName": "Publishers"}]}
    response = client.get("/v1/admin/socratic/session")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "STAFF_GROUP_REQUIRED"


def test_group_pagination_and_separate_review_publish_capabilities(provider):
    provider.admin_list_groups_for_user.side_effect = [
        {"Groups": [{"GroupName": "Admins"}], "NextToken": "next"},
        {"Groups": [{"GroupName": "MathReviewers"}, {"GroupName": "Publishers"}]},
    ]
    session = auth.load_session(ACCESS)
    assert session.actor.capabilities == ["author", "review_mathematics", "publish"]
    assert provider.admin_list_groups_for_user.call_args.kwargs["NextToken"] == "next"
    assert auth.require_capability(session, "publish").actor_id == "stable-staff-sub"
    with pytest.raises(auth.HTTPException) as exc:
        auth.require_capability(session, "review_pedagogy")
    assert exc.value.status_code == 403


@pytest.mark.parametrize("origin", [None, "https://attacker.example.test", "null"])
def test_login_requires_exact_trusted_origin(client, provider, origin):
    response = client.post("/v1/admin/socratic/session",
                           headers={"Origin": origin} if origin else {},
                           json={"username": "author", "password": "test-password"})
    assert response.status_code == 403
    provider.admin_initiate_auth.assert_not_called()


def test_mutations_require_csrf_and_origin_without_logging_secret(client, provider, caplog):
    signed_in = sign_in(client).json()
    csrf = signed_in["csrf_token"]
    response = client.post("/v1/admin/socratic/test-write", headers={"Origin": ORIGIN})
    assert response.status_code == 403
    assert client.post("/v1/admin/socratic/test-write",
                       headers={"Origin": ORIGIN, "X-CSRF-Token": csrf}).status_code == 200
    assert client.post("/v1/admin/socratic/test-write", headers={
        "Origin": "https://attacker.example.test", "X-CSRF-Token": csrf,
    }).status_code == 403
    assert client.post("/v1/admin/socratic/test-write", headers={
        "Origin": ORIGIN, "X-CSRF-Token": csrf, "Sec-Fetch-Site": "cross-site",
    }).status_code == 403
    assert ACCESS not in caplog.text and REFRESH not in caplog.text
    assert "synthetic-password" not in caplog.text


def test_shared_admin_key_and_learner_bearer_cannot_establish_staff_identity(client, provider):
    response = client.get("/v1/admin/socratic/session", headers={
        "X-Admin-Api-Key": settings.admin_api_key, "Authorization": "Bearer learner-token",
    })
    assert response.status_code == 401
    provider.get_user.assert_not_called()


@pytest.mark.parametrize("code,status", [
    ("NotAuthorizedException", 401), ("UserNotFoundException", 401),
    ("TooManyRequestsException", 429), ("AccessDeniedException", 503),
    ("InternalErrorException", 503),
])
def test_provider_errors_are_sanitized(client, provider, code, status, caplog):
    provider.admin_initiate_auth.side_effect = ClientError({
        "Error": {"Code": code, "Message": "private-provider-response"},
    }, "AdminInitiateAuth")
    response = sign_in(client)
    assert response.status_code == status
    assert "private-provider-response" not in response.text + caplog.text
    assert "correlation_id" in response.json()["detail"]
    assert response.json()["detail"]["retryable"] is (status in (429, 503))
    assert not response.headers.get_list("set-cookie")


def test_challenge_is_explicit_not_a_success_shaped_session(client, provider):
    provider.admin_initiate_auth.return_value = {
        "ChallengeName": "SOFTWARE_TOKEN_MFA", "Session": "private-challenge-token",
    }
    response = sign_in(client)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "STAFF_CHALLENGE_REQUIRED"
    assert "private-challenge-token" not in response.text
    provider.get_user.assert_not_called()


@pytest.mark.parametrize("result", [
    {}, {"AccessToken": ACCESS, "ExpiresIn": 3600},
    {"AccessToken": ACCESS, "RefreshToken": REFRESH, "ExpiresIn": True},
])
def test_incomplete_provider_result_is_rejected(client, provider, result):
    provider.admin_initiate_auth.return_value = {"AuthenticationResult": result}
    assert sign_in(client).status_code == 503


def test_logout_revokes_only_current_token_family_before_clearing_cookies(client, provider):
    csrf = sign_in(client).json()["csrf_token"]
    response = client.delete("/v1/admin/socratic/session",
                             headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
    assert response.status_code == 204 and not response.content
    provider.revoke_token.assert_called_once_with(
        Token=REFRESH, ClientId="synthetic-client", ClientSecret="synthetic-client-secret",
    )
    assert all("Max-Age=0" in cookie for cookie in response.headers.get_list("set-cookie"))
    provider.global_sign_out.assert_not_called()
    assert client.get("/v1/admin/socratic/session").status_code == 401


def test_failed_logout_retains_cookies_for_explicit_retry(client, provider):
    csrf = sign_in(client).json()["csrf_token"]
    provider.revoke_token.side_effect = EndpointConnectionError(endpoint_url="https://private.invalid")
    response = client.delete("/v1/admin/socratic/session",
                             headers={"Origin": ORIGIN, "X-CSRF-Token": csrf})
    assert response.status_code == 503
    assert not response.headers.get_list("set-cookie")
    assert "private.invalid" not in response.text


def test_revoked_or_expired_token_is_checked_by_cognito(client, provider):
    sign_in(client)
    provider.get_user.side_effect = ClientError({
        "Error": {"Code": "NotAuthorizedException", "Message": "expired"},
    }, "GetUser")
    assert client.get("/v1/admin/socratic/session").status_code == 401


@pytest.mark.parametrize("patch", [
    {"iss": "https://cognito-idp.us-east-2.amazonaws.com/us-east-2_other"},
    {"client_id": "other-client"}, {"token_use": "id"}, {"sub": ""},
])
def test_tokens_from_another_pool_or_client_cannot_borrow_staff_groups(provider, patch):
    token = jwt.encode({**ACCESS_CLAIMS, **patch}, "offline-provider-signature-key-only", algorithm="HS256")
    with pytest.raises(auth.HTTPException) as exc:
        auth.load_session(token)
    assert exc.value.status_code == 401
    provider.get_user.assert_not_called()
    provider.admin_list_groups_for_user.assert_not_called()


def test_decoded_claims_alone_never_grant_identity(provider):
    provider.get_user.return_value["UserAttributes"] = [{"Name": "sub", "Value": "other-sub"}]
    with pytest.raises(auth.HTTPException) as exc:
        auth.load_session(ACCESS)
    assert exc.value.status_code == 401
    provider.admin_list_groups_for_user.assert_not_called()


def test_configuration_fails_closed_and_local_http_is_explicit(client, provider, monkeypatch):
    monkeypatch.setattr(settings, "socratic_csrf_secret", SecretStr(""))
    assert sign_in(client).status_code == 503
    provider.admin_initiate_auth.assert_not_called()
    monkeypatch.setattr(settings, "socratic_csrf_secret", SecretStr("x" * 32))
    monkeypatch.setattr(settings, "socratic_allowed_origins", ["http://127.0.0.1:5186"])
    with pytest.raises(auth.HTTPException):
        auth.configured()
    monkeypatch.setattr(settings, "socratic_cookie_secure", False)
    auth.configured()
    monkeypatch.setattr(settings, "socratic_allowed_origins", ["https://studio.example.test"])
    with pytest.raises(auth.HTTPException):
        auth.configured()


def test_repeating_group_pagination_fails_closed(provider):
    provider.admin_list_groups_for_user.return_value = {
        "Groups": [{"GroupName": "Admins"}], "NextToken": "repeat",
    }
    with pytest.raises(auth.HTTPException) as exc:
        auth.load_session(ACCESS)
    assert exc.value.status_code == 503


@pytest.mark.parametrize("origin", ["https://[invalid", "https://localhost:bad", "https://invalid host"])
def test_invalid_origin_configuration_is_a_safe_service_error(provider, monkeypatch, origin):
    monkeypatch.setattr(settings, "socratic_allowed_origins", [origin])
    with pytest.raises(auth.HTTPException) as exc:
        auth.configured()
    assert exc.value.status_code == 503


def test_non_ascii_csrf_header_is_rejected_without_server_error(provider):
    request = auth.Request({"type": "http", "headers": [
        (b"origin", ORIGIN.encode()), (b"x-csrf-token", b"a" * 63 + b"\xff"),
    ]})
    with pytest.raises(auth.HTTPException) as exc:
        auth.check_csrf(request, ACCESS)
    assert exc.value.status_code == 403


def test_overposted_actor_and_empty_password_are_rejected(client, provider):
    response = client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                           json={"username": "author", "password": "test", "actor": "publisher"})
    assert response.status_code == 422
    assert client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                       json={"username": "author", "password": ""}).status_code == 422
    provider.admin_initiate_auth.assert_not_called()


def test_invalid_password_is_not_echoed_in_validation_errors(client, provider):
    password = "private-invalid-password" * 30
    response = client.post("/v1/admin/socratic/session", headers={"Origin": ORIGIN},
                           json={"username": "author", "password": password})
    assert response.status_code == 422
    assert password not in response.text
    assert response.json()["detail"]["code"] == "INVALID_STAFF_REQUEST"
    provider.admin_initiate_auth.assert_not_called()


def test_aws_client_configuration_failure_is_safe(provider, monkeypatch):
    monkeypatch.undo()
    monkeypatch.setattr(auth.boto3, "Session", Mock(side_effect=NoCredentialsError()))
    with pytest.raises(auth.HTTPException) as exc:
        auth.client()
    assert exc.value.status_code == 503


def test_router_is_mounted_with_documented_cookie_scheme():
    from mathbank_rest.main import app

    schema = app.openapi()
    assert set(schema["paths"]["/v1/admin/socratic/session"]) == {"post", "get", "delete"}
    get = schema["paths"]["/v1/admin/socratic/session"]["get"]
    assert get["security"] == [{"SocraticStaffCookie": []}]
    assert get["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("StaffSession")
