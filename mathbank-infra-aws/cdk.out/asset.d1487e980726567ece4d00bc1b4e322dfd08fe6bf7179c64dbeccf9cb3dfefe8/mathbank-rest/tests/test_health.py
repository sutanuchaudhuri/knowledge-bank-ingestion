from __future__ import annotations

from fastapi.testclient import TestClient

from mathbank_rest.main import app

client = TestClient(app)


def test_health_endpoint_reports_both_backends() -> None:
    response = client.get("/health")
    body = response.json()
    assert "postgres" in body
    assert "neo4j" in body
