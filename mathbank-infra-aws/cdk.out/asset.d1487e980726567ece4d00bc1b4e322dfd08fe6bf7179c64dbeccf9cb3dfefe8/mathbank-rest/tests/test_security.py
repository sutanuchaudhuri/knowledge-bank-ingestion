"""Unit tests for password hashing + JWT tokens — no DB/network needed."""
from __future__ import annotations

from uuid import uuid4

import jwt
import pytest

from mathbank_rest import security


def test_hash_password_is_not_plaintext_and_verifies() -> None:
    hashed = security.hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert security.verify_password("correct horse battery staple", hashed)
    assert not security.verify_password("wrong password", hashed)


def test_verify_password_rejects_malformed_hash() -> None:
    assert not security.verify_password("anything", "not-a-real-bcrypt-hash")


def test_create_and_decode_access_token_roundtrip() -> None:
    student_id = uuid4()
    token = security.create_access_token(student_id)
    decoded = security.decode_access_token(token)
    assert decoded == student_id


def test_decode_access_token_rejects_tampered_token() -> None:
    token = security.create_access_token(uuid4())
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(tampered)
