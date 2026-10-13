from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from mathbank_rest.db import topic_pedagogy as db
from mathbank_rest.main import app
from mathbank_rest.routers import pedagogy, pedagogy_admin
from mathbank_rest.security import get_current_student_id, require_admin_api_key


def test_power_of_prime_cannot_match_power_of_point():
    assert db.topic_key("Power of point") == db.topic_key("Power of a point")
    assert db.topic_key("power of a prime") != db.topic_key("Power of a point")


def test_feedback_requires_actual_identity_and_does_not_auto_approve(monkeypatch):
    client = TestClient(app)
    response = client.post(
        "/v1/tutor/feedback",
        json={
            "problem_code": "WRONG",
            "topic": "Power of point",
            "reason": "Not related to the requested theorem.",
        },
    )
    assert response.status_code == 401
    student = uuid4()
    app.dependency_overrides[get_current_student_id] = lambda: student
    try:

        def submit(sid, code, topic, reason):
            assert sid == student
            return {"feedback_id": str(uuid4()), "status": "PENDING"}

        monkeypatch.setattr(db, "submit_feedback", submit)
        result = client.post(
            "/v1/tutor/feedback",
            json={
                "problem_code": "WRONG",
                "topic": "Power of point",
                "reason": "Not related to the requested theorem.",
            },
        )
        assert result.status_code == 201
        assert result.json()["status"] == "PENDING"
        assert "no annotation" in result.json()["message"].lower()
    finally:
        app.dependency_overrides.clear()


def test_invalid_or_identity_forging_feedback_rejected():
    for payload in [
        {"problem_code": "p", "topic": " ", "reason": "A sufficient reason"},
        {"problem_code": "p", "topic": "topic", "reason": " short "},
        {
            "problem_code": "p",
            "topic": "topic",
            "reason": "A sufficient reason",
            "student_id": str(uuid4()),
        },
    ]:
        with pytest.raises(ValidationError):
            pedagogy.FeedbackRequest(**payload)


def test_feedback_review_is_admin_only_and_conflicts_explicit(monkeypatch):
    client = TestClient(app)
    assert client.get("/v1/admin/pedagogy/feedback").status_code == 401
    app.dependency_overrides[require_admin_api_key] = lambda: None
    try:
        monkeypatch.setattr(db, "resolve_feedback", lambda *args: None)
        response = client.post(
            "/v1/admin/pedagogy/feedback-review",
            json={
                "feedback_id": str(uuid4()),
                "status": "RESOLVED",
                "note": "Reviewed source evidence.",
            },
        )
        assert response.status_code == 409
        with pytest.raises(ValidationError):
            pedagogy_admin.FeedbackDecision(
                feedback_id=uuid4(), status="APPROVED", note="Reviewed evidence"
            )
    finally:
        app.dependency_overrides.clear()
