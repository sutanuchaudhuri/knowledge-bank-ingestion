"""Lightweight router-wiring tests for the theorem catalog REST surface
(requirements/61) — auth gating and request/response shape, mirroring
test_micro_course_service.py's router-level test style (no live DB writes here; the
real integration coverage lives in test_theorem_service.py).
"""
from fastapi.testclient import TestClient

from mathbank_rest.main import app
from mathbank_rest.security import require_admin_api_key


def test_admin_theorem_api_requires_admin_key():
    response = TestClient(app).get("/v1/admin/theorems")
    assert response.status_code == 401


def test_admin_theorem_create_requires_admin_key():
    response = TestClient(app).post(
        "/v1/admin/theorems",
        json={
            "slug": "unauthorized-attempt", "name": "x", "kind": "THEOREM", "field": "ALGEBRA",
            "statement_text": "x", "actor": "pytest",
        },
    )
    assert response.status_code == 401


def test_admin_theorem_create_passes_fields_to_service(monkeypatch):
    from mathbank_rest.routers import theorems

    calls = []
    monkeypatch.setattr(
        theorems.theorems, "create_theorem",
        lambda conn, **kwargs: calls.append(kwargs) or {"theorem_id": "x", "slug": kwargs["slug"]},
    )
    app.dependency_overrides[require_admin_api_key] = lambda: None
    try:
        response = TestClient(app).post(
            "/v1/admin/theorems",
            json={
                "slug": "api-test-theorem", "name": "API Test", "kind": "LEMMA", "field": "GEOMETRY",
                "statement_text": "A lemma statement.", "actor": "pytest",
            },
        )
    finally:
        app.dependency_overrides.pop(require_admin_api_key, None)

    assert response.status_code == 201
    assert calls[0]["slug"] == "api-test-theorem"
    assert calls[0]["kind"] == "LEMMA"
    assert calls[0]["actor"] == "pytest"


def test_student_theorem_endpoint_requires_no_key():
    """Student-facing reads are anonymous (doc 61 §12.1) — a 404 for an unknown slug
    proves no auth dependency is blocking the request before it reaches the service."""
    response = TestClient(app).get("/v1/theorems/definitely-does-not-exist")
    assert response.status_code == 404


def test_student_search_requires_no_key_and_validates_query():
    response = TestClient(app).get("/v1/theorems/search")
    assert response.status_code == 422  # missing required q


def test_theorem_cycle_maps_to_422(monkeypatch):
    from mathbank_rest.routers import theorems

    def _raise(conn, **kwargs):
        raise theorems.theorems.TheoremCycle("would create a cycle")

    monkeypatch.setattr(theorems.theorems, "add_theorem_relation", _raise)
    app.dependency_overrides[require_admin_api_key] = lambda: None
    try:
        response = TestClient(app).post(
            "/v1/admin/theorems/some-slug/relations",
            json={
                "to_slug": "other-slug", "relation_type": "DEPENDS_ON",
                "assertion_source": "human:pytest", "actor": "pytest",
            },
        )
    finally:
        app.dependency_overrides.pop(require_admin_api_key, None)
    assert response.status_code == 422
    assert "cycle" in response.json()["detail"]
