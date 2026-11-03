"""Student authentication: bcrypt password hashing + JWT bearer tokens.

Kept separate from db/learner.py on purpose — this module has no SQL in it,
only pure crypto/token logic, so it can be unit-tested without a database.
"""
from __future__ import annotations

import hmac
import threading
import time
from contextvars import ContextVar
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


def create_access_token(student_id: UUID, token_version: int | None = None) -> str:
    """`token_version` (the `tv` claim) is the account's current version in the DynamoDB learner store; a password change or an
    account disable bumps it and so revokes every older token. PostgreSQL accounts have none and mint tokens without `tv`."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(student_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    if token_version is not None:
        payload["tv"] = int(token_version)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> UUID:
    """Raises jwt.PyJWTError (caught by callers) on invalid/expired tokens. The token's `tv` claim is remembered for the current
    request context so `assert_student_active(student_id)` (also called by routers that decode themselves) can check it."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    student_id = UUID(payload["sub"])
    claim = payload.get("tv")
    _token_claim.set((student_id, claim if isinstance(claim, int) and not isinstance(claim, bool) else None))
    return student_id


_token_claim: ContextVar[tuple[UUID, int | None] | None] = ContextVar("student_token_claim", default=None)


_status_cache: dict[UUID, tuple[float, str, int]] = {}
_status_cache_lock = threading.Lock()
_STATUS_CACHE_MAX = 10_000


def invalidate_student_status(student_id: UUID) -> None:
    """Drop the cached status so the next request re-reads it (called on disable/enable/delete)."""
    with _status_cache_lock:
        _status_cache.pop(student_id, None)


def _learner_store():
    # lazy: keeps this module free of the store layer at import time
    from mathbank_rest import stores

    return stores.get_store("learner")


def _load_student_status(student_id: UUID) -> str | None:
    return _learner_store().get_student_status(student_id)


def _load_student_token_version(student_id: UUID) -> int:
    return _learner_store().get_student_token_version(student_id)


def _status_unavailable(exc: Exception) -> bool:
    """A database or store outage while reading the status: answered 503, never treated as 'unknown student' (401)."""
    from botocore.exceptions import BotoCoreError, ClientError

    from mathbank_rest.stores.errors import StoreUnavailable

    return isinstance(exc, SQLAlchemyError | BotoCoreError | ClientError | StoreUnavailable)


def assert_student_active(student_id: UUID, token_version: int | None = None) -> None:
    """Reject (401) a token whose student is missing, DISABLED, DELETED or ERASING, or whose `tv` claim is not the account's current
    token version (tokens without `tv` are accepted only while the version is 0). The read is cached for `auth_status_cache_seconds`
    per student so it is not a query on every request; admin disable/enable drop the cache entry."""
    ttl = settings.auth_status_cache_seconds
    now = time.monotonic()
    if token_version is None:
        seen = _token_claim.get()
        if seen is not None and seen[0] == student_id:
            token_version = seen[1]
    with _status_cache_lock:
        cached = _status_cache.get(student_id)
    if cached is not None and cached[0] > now:
        account_status, current_version = cached[1], cached[2]
    else:
        try:
            account_status = _load_student_status(student_id)
            current_version = _load_student_token_version(student_id) if account_status == "ACTIVE" else 0
        except Exception as exc:
            if not _status_unavailable(exc):
                raise
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="account status unavailable"
            ) from None
        if account_status is not None and ttl > 0:
            with _status_cache_lock:
                if len(_status_cache) >= _STATUS_CACHE_MAX:
                    for key in [k for k, (expires, _, _) in _status_cache.items() if expires <= now]:
                        del _status_cache[key]
                    if len(_status_cache) >= _STATUS_CACHE_MAX:
                        _status_cache.clear()
                _status_cache[student_id] = (now + ttl, account_status, current_version)
    if account_status != "ACTIVE" or (token_version or 0) != current_version:
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
        from mathbank_rest import (
            socratic_auth as staff_auth,  # lazy: keeps this module free of the Studio stack
        )

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
