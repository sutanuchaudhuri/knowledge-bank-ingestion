"""AWS Cognito-backed authentication (requirements/64, continued — "finally build a
cognito backed authorization to onboard new user, forgot password, collect first name
last name grade email(optional) phone(optional)"). All Cognito calls are admin-level
(`AdminCreateUser`, `AdminInitiateAuth` with `ADMIN_USER_PASSWORD_AUTH`) — the frontend
never talks to Cognito directly, only to this service's own `/v1/auth/*` endpoints, so
no SRP or public-client complexity is needed; the Cognito App Client has a secret, kept
server-side only (requires computing `SECRET_HASH` on every call that needs it).

Username choice: email if given, else phone, else an auto-generated, human-rememberable
code (`word-word-####`) shown to the student once at signup — both email and phone are
genuinely optional per the requirement, but *something* has to be the Cognito username,
and a raw UUID would be unusable for a student to type back in at login.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import random

import boto3
from botocore.exceptions import ClientError

from mathbank_exam_agent.config import get_settings

_WORDS = [
    "swift", "bright", "quiet", "bold", "calm", "eager", "fair", "gentle", "keen",
    "lively", "merry", "nimble", "proud", "sharp", "witty", "brave", "clever", "jolly",
]
_ANIMALS = [
    "fox", "owl", "lynx", "wren", "hawk", "deer", "crane", "otter", "falcon", "heron",
]


class CognitoAuthError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _client():
    return boto3.client("cognito-idp", region_name=get_settings().aws_region)


def _secret_hash(username: str) -> str:
    settings = get_settings()
    message = (username + settings.cognito_client_id).encode("utf-8")
    digest = hmac.new(settings.cognito_client_secret.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def generate_memorable_username() -> str:
    return f"{random.choice(_WORDS)}-{random.choice(_ANIMALS)}-{random.randint(1000, 9999)}"


def sign_up(
    *, password: str, first_name: str, last_name: str, grade: str | None = None,
    email: str | None = None, phone: str | None = None,
) -> dict:
    """Creates the Cognito identity. Returns {username, cognito_sub} — the caller
    (main.py) is responsible for then creating the matching mathbank-rest
    learner.student_profile row (requirements/64 continued: "in both cases StudentId
    is created during onboarding" — this function only covers the Cognito half)."""
    settings = get_settings()
    username = email or phone or generate_memorable_username()
    attributes = [{"Name": "given_name", "Value": first_name}, {"Name": "family_name", "Value": last_name}]
    if grade:
        attributes.append({"Name": "custom:grade", "Value": grade})
    if email:
        attributes.append({"Name": "email", "Value": email})
        attributes.append({"Name": "email_verified", "Value": "true"})
    if phone:
        attributes.append({"Name": "phone_number", "Value": phone})
        attributes.append({"Name": "phone_number_verified", "Value": "true"})
    client = _client()
    try:
        client.admin_create_user(
            UserPoolId=settings.cognito_user_pool_id, Username=username,
            UserAttributes=attributes, MessageAction="SUPPRESS",
        )
        client.admin_set_user_password(
            UserPoolId=settings.cognito_user_pool_id, Username=username, Password=password, Permanent=True,
        )
        sub = client.admin_get_user(
            UserPoolId=settings.cognito_user_pool_id, Username=username,
        )["UserAttributes"]
        cognito_sub = next(a["Value"] for a in sub if a["Name"] == "sub")
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UsernameExistsException":
            raise CognitoAuthError("USERNAME_EXISTS", "an account already exists with that email/phone") from exc
        if code == "InvalidPasswordException":
            raise CognitoAuthError("INVALID_PASSWORD", str(exc)) from exc
        raise CognitoAuthError("SIGNUP_FAILED", str(exc)) from exc
    return {"username": username, "cognito_sub": cognito_sub, "generated_username": not bool(email or phone)}


def login(*, username: str, password: str) -> dict:
    """Returns {access_token, id_token, refresh_token, cognito_sub}."""
    settings = get_settings()
    client = _client()
    try:
        resp = client.admin_initiate_auth(
            UserPoolId=settings.cognito_user_pool_id, ClientId=settings.cognito_client_id,
            AuthFlow="ADMIN_USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password, "SECRET_HASH": _secret_hash(username)},
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in ("NotAuthorizedException", "UserNotFoundException"):
            raise CognitoAuthError("INVALID_CREDENTIALS", "incorrect username or password") from exc
        raise CognitoAuthError("LOGIN_FAILED", str(exc)) from exc
    result = resp["AuthenticationResult"]
    return {
        "access_token": result["AccessToken"], "id_token": result["IdToken"],
        "refresh_token": result.get("RefreshToken"),
    }


def forgot_password(*, username: str) -> dict:
    """Triggers Cognito's own code delivery (email or SMS — whichever verified
    attribute the user has). Fails cleanly, not silently, if the user has neither
    (requirements/64 continued's own tradeoff for making both fields optional)."""
    settings = get_settings()
    client = _client()
    try:
        resp = client.forgot_password(
            ClientId=settings.cognito_client_id, Username=username, SecretHash=_secret_hash(username),
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "UserNotFoundException":
            raise CognitoAuthError("USER_NOT_FOUND", "no account with that username") from exc
        if code == "InvalidParameterException":
            raise CognitoAuthError(
                "NO_RECOVERY_CHANNEL",
                "this account has no email or phone on file, so a reset code cannot be sent",
            ) from exc
        raise CognitoAuthError("FORGOT_PASSWORD_FAILED", str(exc)) from exc
    delivery = resp.get("CodeDeliveryDetails", {})
    return {"destination": delivery.get("Destination"), "delivery_medium": delivery.get("DeliveryMedium")}


def confirm_forgot_password(*, username: str, confirmation_code: str, new_password: str) -> None:
    settings = get_settings()
    client = _client()
    try:
        client.confirm_forgot_password(
            ClientId=settings.cognito_client_id, Username=username, ConfirmationCode=confirmation_code,
            Password=new_password, SecretHash=_secret_hash(username),
        )
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code == "CodeMismatchException":
            raise CognitoAuthError("INVALID_CODE", "incorrect or expired reset code") from exc
        if code == "InvalidPasswordException":
            raise CognitoAuthError("INVALID_PASSWORD", str(exc)) from exc
        raise CognitoAuthError("RESET_FAILED", str(exc)) from exc
