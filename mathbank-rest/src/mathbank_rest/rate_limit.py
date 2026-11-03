"""Per-caller token bucket and the caller dependencies guarding paid (embedding / model) requests.

Buckets live in process memory, so the cap applies per worker/Lambda instance; it bounds spend per
caller, not globally.
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials

from mathbank_rest import security
from mathbank_rest.config import settings

_MAX_BUCKETS = 10_000


@dataclass(frozen=True)
class Caller:
    """An authenticated caller allowed to trigger paid work. `key` is the rate-limit identity."""

    kind: Literal["learner", "admin"]
    key: str


class TokenBucketLimiter:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}

    def acquire(self, key: str, per_minute: int) -> float:
        """Take one token. Returns 0.0 when allowed, otherwise the seconds until a token is available."""
        rate = per_minute / 60.0
        now = self._clock()
        with self._lock:
            tokens, updated = self._buckets.get(key, (float(per_minute), now))
            tokens = min(float(per_minute), tokens + (now - updated) * rate)
            if tokens >= 1.0:
                self._store(key, tokens - 1.0, now)
                return 0.0
            self._store(key, tokens, now)
            return (1.0 - tokens) / rate

    def _store(self, key: str, tokens: float, now: float) -> None:
        if key not in self._buckets and len(self._buckets) >= _MAX_BUCKETS:
            self._buckets.pop(next(iter(self._buckets)))
        self._buckets[key] = (tokens, now)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


limiter = TokenBucketLimiter()


def enforce(caller: Caller, scope: str) -> None:
    """Raise 429 with Retry-After when the caller has used up `search_rate_limit_per_minute` for this scope."""
    wait = limiter.acquire(f"{scope}:{caller.key}", settings.search_rate_limit_per_minute)
    if wait > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="rate limit exceeded; retry later",
            headers={"Retry-After": str(max(1, math.ceil(wait)))},
        )


def _unauthenticated(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detail, headers={"WWW-Authenticate": "Bearer"}
    )


def _has_staff_cookie(request: Request) -> bool:
    if not request.cookies:
        return False
    from mathbank_rest import socratic_auth

    return socratic_auth.ACCESS_COOKIE in request.cookies


def optional_paid_caller(
    request: Request,
    x_admin_api_key: Annotated[str | None, Security(security._admin_api_key_scheme)] = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(security._bearer_scheme)] = None,
) -> Caller | None:
    """None for a request with no credentials at all; a presented-but-invalid credential is rejected."""
    if credentials is not None:
        try:
            return Caller("learner", f"learner:{security.get_current_student_id(credentials)}")
        except HTTPException:
            pass
    if x_admin_api_key or credentials is not None or _has_staff_cookie(request):
        actor = security.require_admin_api_key(request, x_admin_api_key, credentials)
        return Caller("admin", actor.id)
    return None


def require_paid_caller(
    request: Request,
    x_admin_api_key: Annotated[str | None, Security(security._admin_api_key_scheme)] = None,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(security._bearer_scheme)] = None,
) -> Caller:
    caller = optional_paid_caller(request, x_admin_api_key, credentials)
    if caller is None:
        raise _unauthenticated("sign in (learner token or admin credential) to use this endpoint")
    return caller


class EmbeddingsNotPermitted(PermissionError):
    pass


_embeddings_blocked: ContextVar[bool] = ContextVar("embeddings_blocked", default=False)


@contextmanager
def embeddings_blocked() -> Iterator[None]:
    """Fail closed: any query embedding attempted inside this block raises instead of calling the provider."""
    token = _embeddings_blocked.set(True)
    try:
        yield
    finally:
        _embeddings_blocked.reset(token)


def assert_embeddings_allowed() -> None:
    if _embeddings_blocked.get():
        raise EmbeddingsNotPermitted("query embedding is not permitted for this request")
