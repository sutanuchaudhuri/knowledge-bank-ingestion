"""Auth-contract tests for /v1/admin/* — no live DB needed (the admin API-key
dependency runs before any DB call, same reasoning as test_learner_auth_contract.py).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from mathbank_rest.main import app

client = TestClient(app)


def test_create_competition_requires_admin_key() -> None:
    response = client.post(
        "/v1/admin/competitions", json={"external_code": "X", "name": "X Competition"}
    )
    assert response.status_code == 401


def test_register_paper_requires_admin_key() -> None:
    response = client.post(
        "/v1/admin/papers",
        json={
            "paper_external_code": "PAPER_X_2027_Q01",
            "competition_external_code": "X",
            "year": 2027,
            "problem_url": "https://example.com",
        },
    )
    assert response.status_code == 401


def test_list_papers_requires_admin_key() -> None:
    response = client.get("/v1/admin/papers")
    assert response.status_code == 401


def test_pipeline_runs_requires_admin_key() -> None:
    response = client.get("/v1/admin/pipeline/runs")
    assert response.status_code == 401


def test_pipeline_jobs_requires_admin_key() -> None:
    assert client.get("/v1/admin/pipeline/jobs").status_code == 401


def test_rejects_wrong_admin_key() -> None:
    response = client.get("/v1/admin/papers", headers={"X-Admin-Api-Key": "wrong-key"})
    assert response.status_code == 401


def test_register_paper_rejects_invalid_source_kind() -> None:
    import mathbank_rest.config as config_module

    headers = {"X-Admin-Api-Key": config_module.settings.admin_api_key}
    response = client.post(
        "/v1/admin/papers",
        json={
            "paper_external_code": "PAPER_X_2027_Q01",
            "competition_external_code": "X",
            "year": 2027,
            "problem_url": "https://example.com",
            "source_kind": "CSV",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_register_paper_rejects_lowercase_or_invalid_paper_code() -> None:
    import mathbank_rest.config as config_module

    headers = {"X-Admin-Api-Key": config_module.settings.admin_api_key}
    response = client.post(
        "/v1/admin/papers",
        json={
            "paper_external_code": "paper-x-2027-q01",
            "competition_external_code": "X",
            "year": 2027,
            "problem_url": "https://example.com",
        },
        headers=headers,
    )
    assert response.status_code == 422
