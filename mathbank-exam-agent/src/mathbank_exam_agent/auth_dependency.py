"""Resolves the current student's identity from the Authorization header — either a
real Cognito access token, or a lightweight anonymous-session token (requirements/64,
continued: "student login may be anonymous or with studentId").

Anonymous tokens are the literal string `anon.<student_id>` — deliberately
unsigned/unverified. This is an acceptable risk for this feature specifically: an
anonymous student_id is a random, practically-unguessable UUID, every data access is
already scoped to "rows owned by this exact student_id" (quiz_runtime.py's
`_require_owned_paper`), and there is no privilege to escalate (an anonymous session
can only ever see its own, synthetic, data — never a real account's). A real Cognito
token, by contrast, is always cryptographically verified (jwt_verify.py).
"""
from __future__ import annotations

from fastapi import Header, HTTPException

from mathbank_exam_agent import rest_client
from mathbank_exam_agent.jwt_verify import TokenVerificationError, verify_access_token

_ANON_PREFIX = "anon."


def get_current_student_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token.startswith(_ANON_PREFIX):
        return token.removeprefix(_ANON_PREFIX)
    try:
        claims = verify_access_token(token)
    except TokenVerificationError as exc:
        raise HTTPException(status_code=401, detail=f"invalid or expired token: {exc}") from exc
    student = rest_client.get_student_by_cognito_sub(claims["sub"])
    if student is None:
        # A verified Cognito identity with no matching mathbank-rest row — can only
        # happen if onboarding (POST /v1/auth/signup) was somehow skipped/failed after
        # the Cognito user was created; a real, reportable inconsistency, not a 401.
        raise HTTPException(
            status_code=409,
            detail="this account has no MathBank student profile yet — contact support",
        )
    return student["student_id"]
