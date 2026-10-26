"""Studio user management (Cognito user directory) and best-effort access audit.

Admin actions go to the configured Cognito user pool through the Lambda role (no static keys).
Every sign-in, role switch, password change and admin action is appended to `audit.action_log`
(entity_type STAFF_USER, entity_id = the affected username) when SOCRATIC_ACCESS_AUDIT is on.
Cognito's own sign-in history needs the Plus tier (threat protection), so the Studio keeps its own.
"""
from __future__ import annotations

import ipaddress
import json
import logging
from datetime import datetime
from typing import Literal

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import socratic_auth as auth
from mathbank_rest.config import settings
from mathbank_rest.db.postgres import engine

logger = logging.getLogger(__name__)
ENTITY = "STAFF_USER"
AccessAction = Literal[
    "STUDIO_SIGN_IN_SUCCEEDED", "STUDIO_SIGN_IN_FAILED", "STUDIO_SIGN_OUT", "STUDIO_ROLE_SWITCHED",
    "STUDIO_PASSWORD_CHANGED", "ADMIN_PASSWORD_RESET", "ADMIN_GLOBAL_SIGN_OUT", "ADMIN_GROUP_ADDED",
    "ADMIN_GROUP_REMOVED", "ADMIN_USER_DISABLED", "ADMIN_USER_ENABLED",
]


class UserSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str
    email: str | None = None
    email_verified: bool = False
    name: str | None = None
    status: str
    enabled: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
    groups: list[str] = []


class AccessEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str
    actor_type: str
    actor_id: str | None = None
    occurred_at: datetime
    detail: dict = {}


class AccessSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_sign_in_at: datetime | None = None
    sign_ins_30d: int = 0
    failed_sign_ins_30d: int = 0
    role_switches_30d: int = 0
    admin_actions_30d: int = 0
    audit_enabled: bool = False


class UserDetail(UserSummary):
    mfa: list[str] = []
    access: AccessSummary
    events: list[AccessEvent] = []


class UserPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    users: list[UserSummary]
    next_token: str | None = None
    manageable_groups: list[str]
    role_matrix: dict[str, list[str]]


def manageable_groups() -> list[str]:
    groups = [settings.cognito_admin_group, settings.cognito_student_group, settings.socratic_math_reviewer_group,
              settings.socratic_pedagogy_reviewer_group, settings.socratic_publisher_group]
    return [group for index, group in enumerate(groups) if group and group not in groups[:index]]


def role_matrix() -> dict[str, list[str]]:
    admin = ["author", "manage_users", "preview"]
    return {"admin": admin, "student": list(auth.STUDENT_CAPABILITIES)}


def _local_unavailable() -> None:
    if settings.socratic_auth_mode == "local":
        raise auth.fail(409, "USER_DIRECTORY_UNAVAILABLE",
                        "User management needs the Cognito user pool; it is not available in a local test session.")


def _call(operation: str, **params) -> dict:
    """Admin directory call with admin-appropriate error mapping (not the sign-in mapping)."""
    try:
        return getattr(auth.client(), operation)(UserPoolId=settings.cognito_user_pool_id, **params)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code == "UserNotFoundException":
            raise auth.fail(404, "STAFF_USER_NOT_FOUND", "User not found.") from None
        if code in ("ResourceNotFoundException",):
            raise auth.fail(404, "STAFF_GROUP_NOT_FOUND", "Group not found in the user pool.") from None
        if code in ("InvalidParameterException", "NotAuthorizedException"):
            raise auth.fail(409, "STAFF_USER_ACTION_REJECTED", "The identity provider rejected this action for this user.") from None
        if code in ("TooManyRequestsException", "LimitExceededException"):
            raise auth.fail(429, "STAFF_AUTH_THROTTLED", "The identity provider is rate limiting; retry shortly.") from None
        if code == "AccessDeniedException":
            raise auth.fail(503, "USER_DIRECTORY_FORBIDDEN", "The Studio is not permitted to manage users.") from None
        raise auth.fail(503, "STAFF_IDENTITY_UNAVAILABLE", "Staff identity provider is unavailable.") from None
    except BotoCoreError:
        raise auth.fail(503, "STAFF_IDENTITY_UNAVAILABLE", "Staff identity provider is unavailable.") from None


def _attrs(items: list[dict] | None) -> dict[str, str]:
    return {item["Name"]: item["Value"] for item in items or []}


def _summary(user: dict, groups: list[str]) -> UserSummary:
    attributes = _attrs(user.get("Attributes") or user.get("UserAttributes"))
    return UserSummary(
        username=user["Username"], email=attributes.get("email"),
        email_verified=attributes.get("email_verified") == "true", name=attributes.get("name"),
        status=user.get("UserStatus", "UNKNOWN"), enabled=bool(user.get("Enabled", True)),
        created_at=user.get("UserCreateDate"), updated_at=user.get("UserLastModifiedDate"), groups=groups,
    )


def _members() -> dict[str, list[str]]:
    membership: dict[str, list[str]] = {}
    for group in manageable_groups():
        token = None
        for _ in range(20):
            try:
                page = _call("list_users_in_group", GroupName=group, Limit=60, **({"NextToken": token} if token else {}))
            except Exception as exc:  # a configured but absent group must not break the list
                if getattr(exc, "status_code", None) == 404:
                    break
                raise
            for user in page.get("Users", []):
                membership.setdefault(user["Username"], []).append(group)
            token = page.get("NextToken")
            if not token:
                break
    return membership


def list_users(query: str | None, limit: int, next_token: str | None) -> UserPage:
    _local_unavailable()
    params: dict = {"Limit": limit}
    if query:
        cleaned = query.strip().replace('"', "").replace("\\", "")[:64]
        if cleaned:
            params["Filter"] = f'{"email" if "@" in cleaned else "username"} ^= "{cleaned}"'
    if next_token:
        params["PaginationToken"] = next_token
    page = _call("list_users", **params)
    membership = _members()
    return UserPage(users=[_summary(user, membership.get(user["Username"], [])) for user in page.get("Users", [])],
                    next_token=page.get("PaginationToken"), manageable_groups=manageable_groups(),
                    role_matrix=role_matrix())


def get_user(username: str) -> UserDetail:
    _local_unavailable()
    user = _call("admin_get_user", Username=username)
    groups: list[str] = []
    token = None
    for _ in range(20):
        page = _call("admin_list_groups_for_user", Username=username, **({"NextToken": token} if token else {}))
        groups.extend(group["GroupName"] for group in page.get("Groups", []))
        token = page.get("NextToken")
        if not token:
            break
    summary = _summary(user, groups)
    summary_data = summary.model_dump()
    summary_data["username"] = user["Username"]
    access, events = access_history(user["Username"])
    return UserDetail(**summary_data, mfa=list(user.get("UserMFASettingList") or []), access=access, events=events)


def _guard_self(actor: auth.StaffActor, username: str, what: str) -> None:
    if username == actor.username:
        raise auth.fail(409, "STAFF_SELF_LOCKOUT", f"You cannot {what} your own account from the Studio.")


def add_group(actor: auth.StaffActor, username: str, group: str, request: Request) -> UserDetail:
    _local_unavailable()
    if group not in manageable_groups():
        raise auth.fail(422, "STAFF_GROUP_NOT_MANAGEABLE", "This group is not managed by the Studio.")
    _call("admin_add_user_to_group", Username=username, GroupName=group)
    record(request, "ADMIN_GROUP_ADDED", username, actor=actor, detail={"group": group})
    return get_user(username)


def remove_group(actor: auth.StaffActor, username: str, group: str, request: Request) -> UserDetail:
    _local_unavailable()
    if group not in manageable_groups():
        raise auth.fail(422, "STAFF_GROUP_NOT_MANAGEABLE", "This group is not managed by the Studio.")
    if group == settings.cognito_admin_group:
        _guard_self(actor, username, "remove the admin group from")
    _call("admin_remove_user_from_group", Username=username, GroupName=group)
    record(request, "ADMIN_GROUP_REMOVED", username, actor=actor, detail={"group": group})
    return get_user(username)


def reset_password(actor: auth.StaffActor, username: str, request: Request) -> UserDetail:
    """Cognito emails a verification code; the user sets a new password through 'forgot password'."""
    _local_unavailable()
    _guard_self(actor, username, "reset the password of")
    _call("admin_reset_user_password", Username=username)
    record(request, "ADMIN_PASSWORD_RESET", username, actor=actor)
    return get_user(username)


def global_sign_out(actor: auth.StaffActor, username: str, request: Request) -> UserDetail:
    _local_unavailable()
    _guard_self(actor, username, "sign out every session of")
    _call("admin_user_global_sign_out", Username=username)
    record(request, "ADMIN_GLOBAL_SIGN_OUT", username, actor=actor)
    return get_user(username)


def set_enabled(actor: auth.StaffActor, username: str, enabled: bool, request: Request) -> UserDetail:
    _local_unavailable()
    _guard_self(actor, username, "disable or enable")
    _call("admin_enable_user" if enabled else "admin_disable_user", Username=username)
    record(request, "ADMIN_USER_ENABLED" if enabled else "ADMIN_USER_DISABLED", username, actor=actor)
    return get_user(username)


# ---- access audit -------------------------------------------------------------------------

def _ip_prefix(request: Request | None) -> str | None:
    if request is None:
        return None
    raw = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (
        request.client.host if request.client else "")
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return None
    # Store a network prefix, not the full address: enough to spot unusual access, less personal data.
    network = ipaddress.ip_network(f"{address}/{24 if address.version == 4 else 48}", strict=False)
    return str(network)


def record(request: Request | None, action: AccessAction, subject: str, *,
           actor: auth.StaffActor | None = None, detail: dict | None = None) -> None:
    if not settings.socratic_access_audit:
        return
    evidence = {**(detail or {}), "ip_prefix": _ip_prefix(request),
                "user_agent": ((request.headers.get("user-agent") or "")[:160] if request else None)}
    try:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '3s'"))
            conn.execute(text("""
                INSERT INTO audit.action_log(actor_type, actor_id, action, entity_type, entity_id, after_state)
                VALUES (:actor_type, :actor_id, :action, :entity, :subject, CAST(:evidence AS jsonb))
            """), {"actor_type": "ADMIN" if actor else "SYSTEM", "actor_id": actor.actor_id if actor else None,
                   "action": action, "entity": ENTITY, "subject": subject[:128],
                   "evidence": json.dumps(evidence, sort_keys=True)})
    except SQLAlchemyError:
        logger.warning("Studio access audit write failed action=%s", action)


def access_history(username: str, limit: int = 25) -> tuple[AccessSummary, list[AccessEvent]]:
    if not settings.socratic_access_audit:
        return AccessSummary(audit_enabled=False), []
    try:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '5s'"))
            stats = conn.execute(text("""
                SELECT max(created_at) FILTER (WHERE action = 'STUDIO_SIGN_IN_SUCCEEDED') AS last_sign_in_at,
                       count(*) FILTER (WHERE action = 'STUDIO_SIGN_IN_SUCCEEDED') AS sign_ins,
                       count(*) FILTER (WHERE action = 'STUDIO_SIGN_IN_FAILED') AS failed,
                       count(*) FILTER (WHERE action = 'STUDIO_ROLE_SWITCHED') AS switches,
                       count(*) FILTER (WHERE action LIKE 'ADMIN\\_%') AS admin_actions
                  FROM audit.action_log
                 WHERE entity_type = :entity AND entity_id = :subject AND created_at > now() - interval '30 days'
            """), {"entity": ENTITY, "subject": username}).mappings().one()
            rows = conn.execute(text("""
                SELECT action, actor_type, actor_id, created_at, after_state
                  FROM audit.action_log
                 WHERE entity_type = :entity AND entity_id = :subject
                 ORDER BY created_at DESC LIMIT :limit
            """), {"entity": ENTITY, "subject": username, "limit": limit}).mappings().all()
    except SQLAlchemyError:
        logger.warning("Studio access history unavailable")
        return AccessSummary(audit_enabled=True), []
    summary = AccessSummary(last_sign_in_at=stats["last_sign_in_at"], sign_ins_30d=stats["sign_ins"],
                            failed_sign_ins_30d=stats["failed"], role_switches_30d=stats["switches"],
                            admin_actions_30d=stats["admin_actions"], audit_enabled=True)
    return summary, [AccessEvent(action=row["action"], actor_type=row["actor_type"], actor_id=row["actor_id"],
                                 occurred_at=row["created_at"], detail=row["after_state"] or {}) for row in rows]
