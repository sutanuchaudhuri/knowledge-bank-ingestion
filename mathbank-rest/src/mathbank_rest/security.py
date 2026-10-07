"""Student authentication: bcrypt password hashing + JWT bearer tokens.

Kept separate from db/learner.py on purpose — this module has no SQL in it,
only pure crypto/token logic, so it can be unit-tested without a database.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mathbank_rest.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)


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


def get_current_student_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> UUID:
    """FastAPI dependency: require a valid `Authorization: Bearer <token>` header."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_optional_student_id(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> UUID | None:
    """Anonymous grounding is allowed; a supplied invalid bearer must fail."""
    return get_current_student_id(credentials) if credentials is not None else None


def require_admin_api_key(x_admin_api_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency guarding /v1/admin/* — single shared key, not a per-user
    role system (see routers/admin.py module docstring for the follow-up plan).
    """
    if not x_admin_api_key or x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin API key")
