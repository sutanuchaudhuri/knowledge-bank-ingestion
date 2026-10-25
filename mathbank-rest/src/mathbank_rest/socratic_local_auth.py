"""Explicit single-process, loopback-only staff sessions for development."""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import secrets
import threading
import time
from dataclasses import dataclass, field

import bcrypt
from fastapi import HTTPException, Request

from mathbank_rest.config import settings


class LocalAuthError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def check_request(request: Request | None) -> None:
    peer = request.client.host if request and request.client else ""
    try:
        loopback = ipaddress.ip_address(peer).is_loopback
    except ValueError:
        loopback = False
    if not (request and loopback and request.url.hostname in ("localhost", "127.0.0.1", "::1")):
        raise LocalAuthError(403, "LOCAL_STAFF_LOOPBACK_REQUIRED",
                             "Local staff authentication is restricted to loopback requests.")


def validate_configuration() -> None:
    if any(os.environ.get(key) for key in (
        "AWS_LAMBDA_FUNCTION_NAME", "AWS_EXECUTION_ENV",
        "ECS_CONTAINER_METADATA_URI", "ECS_CONTAINER_METADATA_URI_V4",
    )):
        raise LocalAuthError(503, "LOCAL_STAFF_NOT_ALLOWED", "Local authentication is disabled in AWS runtimes.")
    password_hash = settings.socratic_local_password_hash.get_secret_value()
    if not settings.socratic_local_username.strip() or not password_hash:
        raise LocalAuthError(503, "LOCAL_STAFF_NOT_CONFIGURED", "Local staff credentials are not configured.")
    try:
        bcrypt.checkpw(b"configuration-check", password_hash.encode())
    except ValueError:
        raise LocalAuthError(503, "LOCAL_STAFF_NOT_CONFIGURED", "Local staff password hash is invalid.") from None


def fingerprint() -> str:
    # Credential, signing-secret or capability changes invalidate existing local sessions.
    return hashlib.sha256(repr((
        settings.socratic_local_username,
        settings.socratic_local_password_hash.get_secret_value(),
        settings.socratic_csrf_secret.get_secret_value(),
        settings.socratic_local_capabilities,
    )).encode()).hexdigest()


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class LocalSession:
    access_hash: str
    refresh_hash: str
    configuration: str
    expires: float


@dataclass
class LocalSessionStore:
    sessions: dict[str, LocalSession] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    limit: int = 128

    def prune(self) -> None:
        now = time.monotonic()
        current = fingerprint()
        for key in list(self.sessions):
            session = self.sessions[key]
            if session.expires <= now or session.configuration != current:
                del self.sessions[key]

    def login(self, username: str, password: str) -> tuple[str, str]:
        expected = settings.socratic_local_password_hash.get_secret_value()
        valid_password = len(password.encode()) <= 72 and bcrypt.checkpw(password.encode(), expected.encode())
        if not hmac.compare_digest(username.encode(), settings.socratic_local_username.encode()) or not valid_password:
            raise LocalAuthError(401, "INVALID_STAFF_CREDENTIALS", "Staff credentials or session are invalid.")
        with self.lock:
            self.prune()
            if len(self.sessions) >= self.limit:
                raise LocalAuthError(429, "LOCAL_STAFF_SESSION_LIMIT", "Local session limit reached; sign out or wait.")
            access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            self.sessions[digest(access)] = LocalSession(
                digest(access), digest(refresh), fingerprint(),
                time.monotonic() + settings.socratic_session_seconds,
            )
            return access, refresh

    def load(self, access: str) -> None:
        with self.lock:
            self.prune()
            if digest(access) not in self.sessions:
                raise LocalAuthError(401, "INVALID_STAFF_CREDENTIALS", "Staff credentials or session are invalid.")

    def revoke(self, access: str, refresh: str) -> None:
        with self.lock:
            self.prune()
            session = self.sessions.get(digest(access))
            if not session or not hmac.compare_digest(session.refresh_hash, digest(refresh)):
                raise LocalAuthError(401, "INVALID_STAFF_CREDENTIALS", "Staff credentials or session are invalid.")
            del self.sessions[session.access_hash]


store = LocalSessionStore()


def reject(error: LocalAuthError) -> HTTPException:
    from mathbank_rest.socratic_auth import fail

    return fail(error.status, error.code, str(error))
