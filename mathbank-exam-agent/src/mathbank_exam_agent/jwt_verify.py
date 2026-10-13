"""Verifies a Cognito access token's signature/claims against the User Pool's own JWKS
(requirements/64, continued). No Cognito SDK call needed to verify a token — this is
the standard, offline JWT-signature-verification pattern, using PyJWT's JWK support
directly against Cognito's public well-known keys (cached in-process, refreshed only
when a token references a `kid` not yet seen — e.g. after Cognito rotates its keys).
"""
from __future__ import annotations

from functools import lru_cache

import jwt
from jwt import PyJWKClient

from mathbank_exam_agent.config import get_settings


class TokenVerificationError(RuntimeError):
    pass


@lru_cache
def _jwks_client() -> PyJWKClient:
    settings = get_settings()
    jwks_url = (
        f"https://cognito-idp.{settings.aws_region}.amazonaws.com/"
        f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
    )
    return PyJWKClient(jwks_url)


def verify_access_token(token: str) -> dict:
    """Returns the decoded claims (`sub`, `username`, `token_use`, ...) or raises
    TokenVerificationError. Access tokens (not ID tokens) are the ones this project
    verifies — `token_use` must be `"access"`; Cognito access tokens carry no
    `aud`/audience claim at all (confirmed real Cognito behaviour, unlike ID tokens),
    so PyJWT's audience check is deliberately not used here."""
    settings = get_settings()
    try:
        signing_key = _jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, signing_key.key, algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{settings.cognito_user_pool_id}",
        )
    except jwt.PyJWTError as exc:
        raise TokenVerificationError(str(exc)) from exc
    if claims.get("token_use") != "access":
        raise TokenVerificationError("not an access token")
    if claims.get("client_id") != settings.cognito_client_id:
        raise TokenVerificationError("token was not issued for this client")
    return claims
