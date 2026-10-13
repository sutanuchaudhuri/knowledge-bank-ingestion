"""Contract tests for /v1/tutor/* — request validation (no OpenAI calls, no DB).
Live decompose/check-subproblem behavior is verified manually against the real
server (see 00_implementation_progress.md Round 11) since mocking OpenAI's
JSON-mode responses meaningfully would just test the mock, not the integration.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from mathbank_rest.main import app

client = TestClient(app)


def test_decompose_rejects_missing_problem_code() -> None:
    response = client.post("/v1/tutor/decompose", json={})
    assert response.status_code == 422


def test_decompose_rejects_max_steps_out_of_range() -> None:
    response = client.post(
        "/v1/tutor/decompose", json={"problem_code": "AIME_1983_Q01", "max_steps": 10}
    )
    assert response.status_code == 422


def test_check_subproblem_rejects_missing_fields() -> None:
    response = client.post("/v1/tutor/check-subproblem", json={"subproblem_prompt": "..."})
    assert response.status_code == 422
