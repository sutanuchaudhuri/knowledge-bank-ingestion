"""API-contract tests for the learner router that don't require a live DB —
auth guard behavior and request validation. Full register/login/attempt
round-trips against a real Postgres are covered by
scripts/test_learner_flow.sh (see Makefile `test-learner-flow`), since they
need the learner.* schema applied (make -C ../mathbank-db migrate-learner).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from mathbank_rest.main import app

client = TestClient(app)


def test_attempts_requires_auth() -> None:
    response = client.post("/v1/learner/attempts", json={"problem_code": "AIME_1983_Q01", "is_correct": True})
    assert response.status_code == 401


def test_mastery_requires_auth() -> None:
    response = client.get("/v1/learner/mastery")
    assert response.status_code == 401


def test_attempts_list_requires_auth() -> None:
    response = client.get("/v1/learner/attempts")
    assert response.status_code == 401


def test_me_requires_auth() -> None:
    response = client.get("/v1/learner/me")
    assert response.status_code == 401


def test_me_rejects_garbage_bearer_token() -> None:
    response = client.get("/v1/learner/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


def test_register_rejects_short_password() -> None:
    response = client.post(
        "/v1/learner/register",
        json={"email": "student@example.com", "password": "short", "first_name": "A", "last_name": "B"},
    )
    assert response.status_code == 422


def test_register_rejects_invalid_email() -> None:
    response = client.post(
        "/v1/learner/register",
        json={"email": "not-an-email", "password": "longenoughpassword", "first_name": "A", "last_name": "B"},
    )
    assert response.status_code == 422


def test_register_requires_first_and_last_name() -> None:
    response = client.post(
        "/v1/learner/register",
        json={"email": "student@example.com", "password": "longenoughpassword"},
    )
    assert response.status_code == 422
