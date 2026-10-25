"""Staff sessions: Cognito by default, explicit loopback-only local testing."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid4, uuid5

import boto3
import jwt
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict

from mathbank_rest import socratic_local_auth as local
from mathbank_rest.config import settings

logger = logging.getLogger(__name__)
COOKIE_PATH = "/v1/admin/socratic"
ACCESS_COOKIE = "mathbank_socratic_access"
REFRESH_COOKIE = "mathbank_socratic_refresh"
Capability = Literal["author", "review_mathematics", "review_pedagogy", "publish"]


class StaffActor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    actor_id: str
    username: str
    capabilities: list[Capability]


class StaffSession(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actor: StaffActor
    csrf_token: str
    auth_mode: Literal["cognito", "local"] = "cognito"


@dataclass(frozen=True)
class LoginResult:
    session: StaffSession
    access_token: str
    refresh_token: str
    max_age: int


def fail(status: int, code: str, message: str) -> HTTPException:
    correlation = str(uuid4())
    logger.warning("Socratic authentication rejected code=%s correlation_id=%s", code, correlation)
    return HTTPException(status, {
        "code": code, "message": message, "correlation_id": correlation,
        "retryable": status in (429, 503),
    }, headers={"Cache-Control": "no-store"})


def configured() -> None:
    if not (len(settings.socratic_csrf_secret.get_secret_value()) >= 32
            and settings.socratic_allowed_origins):
        raise fail(503, "STAFF_AUTH_NOT_CONFIGURED", "Staff authentication is not configured.")
    for origin in settings.socratic_allowed_origins:
        try:
            url = urlsplit(origin)
            _ = url.port
        except ValueError:
            raise fail(503, "STAFF_AUTH_NOT_CONFIGURED", "Staff origin configuration is invalid.") from None
        if (not url.hostname or any(character.isspace() for character in origin)
                or url.username or url.password or url.path or url.query or url.fragment
                or url.scheme not in ("http", "https")):
            raise fail(503, "STAFF_AUTH_NOT_CONFIGURED", "Staff origin configuration is invalid.")
        if url.scheme != "https" and (
            settings.socratic_cookie_secure or url.hostname not in ("127.0.0.1", "localhost", "::1")
        ):
            raise fail(503, "STAFF_AUTH_NOT_CONFIGURED", "Staff authentication requires HTTPS.")
        if not settings.socratic_cookie_secure and url.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise fail(503, "STAFF_AUTH_NOT_CONFIGURED", "Insecure staff cookies are loopback-only.")
        if settings.socratic_auth_mode == "local" and url.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise fail(503, "LOCAL_STAFF_LOOPBACK_REQUIRED", "Local staff origins must be loopback-only.")
    if settings.socratic_auth_mode == "local":
        try:
            local.validate_configuration()
        except local.LocalAuthError as exc:
            raise local.reject(exc) from None
    elif not (settings.cognito_user_pool_id and settings.cognito_client_id
              and settings.cognito_client_secret.get_secret_value() and settings.cognito_admin_group.strip()):
        raise fail(503, "STAFF_AUTH_NOT_CONFIGURED", "Staff authentication is not configured.")


def client():
    try:
        session = boto3.Session(profile_name=settings.socratic_aws_profile or None)
        return session.client("cognito-idp", region_name=settings.cognito_region, config=Config(
            connect_timeout=3, read_timeout=8,
            retries={"mode": "standard", "total_max_attempts": 1},
        ))
    except BotoCoreError:
        raise fail(503, "STAFF_IDENTITY_UNAVAILABLE", "Staff identity provider is unavailable.") from None


def provider_call(provider, operation: str, **params) -> dict:
    try:
        return getattr(provider, operation)(**params)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code in ("NotAuthorizedException", "UserNotFoundException", "PasswordResetRequiredException",
                    "UserNotConfirmedException"):
            raise fail(401, "INVALID_STAFF_CREDENTIALS", "Staff credentials or session are invalid.") from None
        if code in ("TooManyRequestsException", "LimitExceededException"):
            raise fail(429, "STAFF_AUTH_THROTTLED", "Staff authentication is temporarily rate limited.") from None
        raise fail(503, "STAFF_IDENTITY_UNAVAILABLE", "Staff identity provider is unavailable.") from None
    except BotoCoreError:
        raise fail(503, "STAFF_IDENTITY_UNAVAILABLE", "Staff identity provider is unavailable.") from None


def csrf_token(access_token: str) -> str:
    return hmac.new(settings.socratic_csrf_secret.get_secret_value().encode(),
                    b"socratic-staff-v1:" + access_token.encode(), hashlib.sha256).hexdigest()


def check_origin(request: Request) -> None:
    configured()
    check_local_request(request)
    if (request.headers.get("origin") not in settings.socratic_allowed_origins
            or request.headers.get("sec-fetch-site") == "cross-site"):
        raise fail(403, "STAFF_ORIGIN_DENIED", "Use the trusted same-origin Studio.")


def check_csrf(request: Request, access_token: str) -> None:
    check_origin(request)
    supplied = request.headers.get("X-CSRF-Token", "")
    if len(supplied) != 64 or not hmac.compare_digest(supplied.encode(), csrf_token(access_token).encode()):
        raise fail(403, "STAFF_CSRF_DENIED", "A valid staff CSRF token is required.")


def check_local_request(request: Request | None) -> None:
    if settings.socratic_auth_mode == "local":
        try:
            local.check_request(request)
        except local.LocalAuthError as exc:
            raise local.reject(exc) from None


def local_session(access: str) -> StaffSession:
    actor_id = "local:" + str(uuid5(NAMESPACE_URL, "mathbank-socratic-local:" + settings.socratic_local_username))
    return StaffSession(actor=StaffActor(
        actor_id=actor_id, username=settings.socratic_local_username,
        capabilities=settings.socratic_local_capabilities,
    ), csrf_token=csrf_token(access), auth_mode="local")


def load_session(access_token: str, provider=None, *, request: Request | None = None) -> StaffSession:
    configured()
    if not access_token or len(access_token) > 8192:
        raise fail(401, "STAFF_SESSION_REQUIRED", "Staff sign-in is required.")
    if settings.socratic_auth_mode == "local":
        check_local_request(request)
        try:
            local.store.load(access_token)
        except local.LocalAuthError as exc:
            raise local.reject(exc) from None
        return local_session(access_token)
    try:
        claims = jwt.decode(access_token, options={"verify_signature": False})
    except jwt.PyJWTError:
        raise fail(401, "INVALID_STAFF_CREDENTIALS", "Staff credentials or session are invalid.") from None
    expected_issuer = (f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
                       f"{settings.cognito_user_pool_id}")
    if (claims.get("iss") != expected_issuer or claims.get("client_id") != settings.cognito_client_id
            or claims.get("token_use") != "access" or not claims.get("sub")):
        raise fail(401, "INVALID_STAFF_CREDENTIALS", "Staff credentials or session are invalid.")
    provider = provider if provider is not None else client()
    # GetUser verifies the actual token, expiration and revocation. The decoded
    # claims above only restrict its pool/client; they never establish identity.
    user = provider_call(provider, "get_user", AccessToken=access_token)
    username = user.get("Username")
    attributes = {item["Name"]: item["Value"] for item in user.get("UserAttributes", [])}
    if not username or not attributes.get("sub"):
        raise fail(503, "STAFF_IDENTITY_INVALID", "Identity provider returned an incomplete staff identity.")
    if attributes["sub"] != claims["sub"]:
        raise fail(401, "INVALID_STAFF_CREDENTIALS", "Staff credentials or session are invalid.")
    groups: set[str] = set()
    token = None
    seen_tokens: set[str] = set()
    for _ in range(20):
        page = provider_call(provider, "admin_list_groups_for_user",
                             UserPoolId=settings.cognito_user_pool_id, Username=username,
                             **({"NextToken": token} if token else {}))
        groups.update(group["GroupName"] for group in page.get("Groups", []))
        token = page.get("NextToken")
        if not token:
            break
        if token in seen_tokens:
            raise fail(503, "STAFF_IDENTITY_INVALID", "Staff group lookup could not be completed.")
        seen_tokens.add(token)
    else:
        raise fail(503, "STAFF_IDENTITY_INVALID", "Staff group lookup exceeded its safety limit.")
    if settings.cognito_admin_group not in groups:
        raise fail(403, "STAFF_GROUP_REQUIRED", "Studio staff group membership is required.")
    capabilities: list[Capability] = ["author"]
    capability_groups: tuple[tuple[str, Capability], ...] = (
        (settings.socratic_math_reviewer_group, "review_mathematics"),
        (settings.socratic_pedagogy_reviewer_group, "review_pedagogy"),
        (settings.socratic_publisher_group, "publish"),
    )
    for group, capability in capability_groups:
        if group and group in groups:
            capabilities.append(capability)
    return StaffSession(actor=StaffActor(
        actor_id=attributes["sub"], username=username, capabilities=capabilities,
    ), csrf_token=csrf_token(access_token))


def login(username: str, password: str, *, request: Request | None = None) -> LoginResult:
    configured()
    if settings.socratic_auth_mode == "local":
        check_local_request(request)
        try:
            access, refresh = local.store.login(username, password)
        except local.LocalAuthError as exc:
            raise local.reject(exc) from None
        return LoginResult(local_session(access), access, refresh, settings.socratic_session_seconds)
    provider = client()
    secret_hash = base64.b64encode(hmac.new(
        settings.cognito_client_secret.get_secret_value().encode(),
        (username + settings.cognito_client_id).encode(), hashlib.sha256,
    ).digest()).decode()
    response = provider_call(provider, "admin_initiate_auth",
                             UserPoolId=settings.cognito_user_pool_id,
                             ClientId=settings.cognito_client_id,
                             AuthFlow="ADMIN_USER_PASSWORD_AUTH",
                             AuthParameters={"USERNAME": username, "PASSWORD": password,
                                             "SECRET_HASH": secret_hash})
    if response.get("ChallengeName"):
        raise fail(403, "STAFF_CHALLENGE_REQUIRED",
                   "This account requires an identity-provider challenge; Studio cannot complete it yet.")
    result = response.get("AuthenticationResult", {})
    access, refresh, expires = result.get("AccessToken"), result.get("RefreshToken"), result.get("ExpiresIn")
    if not isinstance(access, str) or not isinstance(refresh, str) or type(expires) is not int or expires < 60:
        raise fail(503, "STAFF_IDENTITY_INVALID", "Identity provider returned an incomplete session.")
    session = load_session(access, provider)
    return LoginResult(session, access, refresh, min(expires, settings.socratic_session_seconds))


def logout(request: Request, access_token: str, refresh_token: str) -> None:
    if not access_token or not refresh_token:
        raise fail(401, "STAFF_SESSION_REQUIRED", "Staff sign-in is required.")
    check_csrf(request, access_token)
    if settings.socratic_auth_mode == "local":
        try:
            local.store.revoke(access_token, refresh_token)
        except local.LocalAuthError as exc:
            raise local.reject(exc) from None
        return
    provider_call(client(), "revoke_token", Token=refresh_token,
                  ClientId=settings.cognito_client_id,
                  ClientSecret=settings.cognito_client_secret.get_secret_value())


def require_capability(session: StaffSession, capability: Capability) -> StaffActor:
    if capability not in session.actor.capabilities:
        raise fail(403, "STAFF_CAPABILITY_REQUIRED", "This staff capability is required.")
    return session.actor
