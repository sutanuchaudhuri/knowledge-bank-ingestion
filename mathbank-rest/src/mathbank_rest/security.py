"""Student authentication: bcrypt password hashing + JWT bearer tokens.

Kept separate from db/learner.py on purpose — this module has no SQL in it,
only pure crypto/token logic, so it can be unit-tested without a database.
"""
from __future__ import annotations

import hmac
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)
_admin_api_key_scheme = APIKeyHeader(
    name="X-Admin-Api-Key",
    auto_error=False,
    description="Shared admin key configured in ADMIN_API_KEY (root .env). Required on every "
    "legacy /v1/admin/* operation. Socratic Studio uses its separate staff cookies.",
)


def hash_password(plain_password: str) -> str:
    """Hash a password for storage. Never log or persist the plaintext."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Malformed hash (shouldn't happen for rows we wrote ourselves).
        return False


def create_access_token(student_id: UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(student_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID:
    """Raises jwt.PyJWTError (caught by callers) on invalid/expired tokens."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    return UUID(payload["sub"])


_status_cache: dict[UUID, tuple[float, str]] = {}
_status_cache_lock = threading.Lock()
_STATUS_CACHE_MAX = 10_000


def invalidate_student_status(student_id: UUID) -> None:
    """Drop the cached status so the next request re-reads it (called on disable/enable/delete)."""
    with _status_cache_lock:
        _status_cache.pop(student_id, None)


def _load_student_status(student_id: UUID) -> str | None:
    from mathbank_rest.db import learner as learner_db  # lazy: keeps this module free of the database layer

    return learner_db.get_student_status(student_id)


def assert_student_active(student_id: UUID) -> None:
    """Reject (401) a token whose student is missing, DISABLED or DELETED. The status read is cached for
    `auth_status_cache_seconds` per student so it is not a query on every request."""
    ttl = settings.auth_status_cache_seconds
    now = time.monotonic()
    with _status_cache_lock:
        cached = _status_cache.get(student_id)
    if cached is not None and cached[0] > now:
        account_status = cached[1]
    else:
        try:
            account_status = _load_student_status(student_id)
        except SQLAlchemyError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="account status unavailable"
            ) from None
        if account_status is not None and ttl > 0:
            with _status_cache_lock:
                if len(_status_cache) >= _STATUS_CACHE_MAX:
                    for key in [k for k, (expires, _) in _status_cache.items() if expires <= now]:
                        del _status_cache[key]
                    if len(_status_cache) >= _STATUS_CACHE_MAX:
                        _status_cache.clear()
                _status_cache[student_id] = (now + ttl, account_status)
    if account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_student_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UUID:
    """FastAPI dependency: require a valid `Authorization: Bearer <token>` header for an ACTIVE student."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        student_id = decode_access_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    assert_student_active(student_id)
    return student_id


def get_optional_student_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UUID | None:
    """Anonymous grounding is allowed; a supplied invalid bearer must fail."""
    return get_current_student_id(credentials) if credentials is not None else None


# ── Admin identity (requirement 71 WP1a; product decision 2026-11-03: staff login first) ─────────────────────
#
# /v1/admin/* accepts either
#   * a staff session — the Studio sign-in (Cognito, or the loopback `local` mode): an `Authorization: Bearer
#     <access token>` header, or the HttpOnly access cookie (mutating requests then also need the CSRF header).
#     The session is rechecked on every request and names the real person, and
#   * the shared `X-Admin-Api-Key`, kept as a **service credential with no person behind it** (ETL, CI, agents,
#     the web proxy). Its actor is always `service:admin-key`, so audit rows never pretend a person acted.
# Routers that record who did something use `Actor.id`; they never accept an actor name from the client.

STAFF_ADMIN_CAPABILITIES: tuple[str, ...] = ("author", "publish", "manage_users", "review_mathematics", "review_pedagogy")
_ALL_CAPABILITIES = frozenset({*STAFF_ADMIN_CAPABILITIES, "preview"})
_SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
SERVICE_ACTOR_ID = "service:admin-key"


@dataclass(frozen=True)
class Actor:
    """Who is performing an admin operation. `id` is the stable value to store in audit/reviewer columns."""

    kind: Literal["staff", "service"]
    id: str
    display: str
    capabilities: frozenset[str] = frozenset()

    def has(self, capability: str) -> bool:
        return self.kind == "service" or capability in self.capabilities


SERVICE_ACTOR = Actor("service", SERVICE_ACTOR_ID, "admin API key", _ALL_CAPABILITIES)


def _unauthorised(detail: str = "invalid admin API key") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def admin_actor(*capabilities: str):
    """Dependency factory for admin routes. With no arguments any staff admin capability is enough;
    `admin_actor("publish")` requires that capability (the service credential holds all of them).

        router = APIRouter(dependencies=[Depends(require_admin_api_key)])        # authenticate
        def publish(actor: Actor = Depends(admin_actor("publish"))): ...        # authenticate + who
    """
    need = capabilities or STAFF_ADMIN_CAPABILITIES

    def dependency(
        request: Request,
        x_admin_api_key: Annotated[str | None, Security(_admin_api_key_scheme)] = None,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)] = None,
    ) -> Actor:
        if x_admin_api_key and hmac.compare_digest(x_admin_api_key.encode(), settings.admin_api_key.encode()):
            return SERVICE_ACTOR
        from mathbank_rest import socratic_auth as staff_auth  # lazy: keeps this module free of the Studio stack

        cookie = request.cookies.get(staff_auth.ACCESS_COOKIE)
        token = cookie or (credentials.credentials if credentials is not None else None)
        if not token:
            raise _unauthorised()
        if cookie and request.method not in _SAFE_METHODS:
            staff_auth.check_csrf(request, cookie)  # ambient credentials need CSRF; an explicit bearer does not
        session = staff_auth.load_session(token, request=request)
        if session.role != "admin" or not any(c in session.actor.capabilities for c in need):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="staff capability required")
        a = session.actor
        return Actor("staff", f"staff:{a.actor_id}", a.username, frozenset(a.capabilities))

    return dependency


# Kept under its historical name: 17 routers already use it as `Depends(require_admin_api_key)`. It now returns
# the Actor, so a router that cares who acted can simply add `actor: Actor = Depends(require_admin_api_key)`.
require_admin_api_key = admin_actor()
