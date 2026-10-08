import json
from pathlib import Path
from unittest.mock import Mock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from geometry_scene.orchestration import GeometryRequest
from geometry_scene.schemas import SceneInput
from geometry_scene.service import create_scene

from mathbank_rest.geometry_orchestration import interpret
from mathbank_rest.routers import geometry_interpretation as routes
from mathbank_rest.routers.fluid import staff_or_student
from mathbank_rest.routers.geometry_scenes import get_geometry_repository

ROOT = Path(__file__).resolve().parents[2] / "geometry-scene-engine/fixtures"


def frame():
    return create_scene(
        SceneInput.model_validate(
            json.loads((ROOT / "09_midpoint_auxiliary.json").read_text())["initial"]
        )
    )


def test_idempotency_replay_avoids_model_and_has_scene_block_fields():
    accepted = frame()
    store = Mock()
    store.lookup_receipt.return_value = accepted
    provider = Mock()
    result = interpret(
        GeometryRequest(problem_text="ABCD", goal="Focus"), store, "learner", "key", provider
    )
    assert result["replayed"] and result["validation"]["valid"]
    provider.complete.assert_not_called()
    assert {"scene_id", "version", "caption", "current_math_step"} <= result.keys()


def test_reviewed_publication_uses_request_hash_and_unique_identity(monkeypatch):
    accepted = frame()
    store = Mock()
    store.lookup_receipt.return_value = None
    store.commit_candidate.side_effect = lambda frame, *args, **kwargs: (frame, False)
    monkeypatch.setattr(
        "mathbank_rest.geometry_orchestration.orchestrate",
        lambda *args, **kwargs: (accepted, {"attempts": [{"attempt": 1, "status": "ACCEPTED"}]}),
    )
    request = GeometryRequest(problem_text="ABCD", goal="Focus")
    first = interpret(request, store, "learner", "key", Mock())
    second = interpret(request, store, "learner", "different", Mock())
    assert first["scene_id"] != second["scene_id"]
    assert store.commit_candidate.call_args.kwargs["request_body"] == request.model_dump(
        mode="json"
    )
    assert store.save_run.call_count == 2


def client():
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_geometry_repository] = lambda: Mock()
    app.dependency_overrides[staff_or_student] = lambda: {
        "role": "STUDENT",
        "student_id": "test-learner",
    }
    return TestClient(app)


def test_learner_cannot_forge_authoritative_proof():
    response = client().post(
        "/v1/geometry-scenes/interpret",
        json={
            "problem_text": "ABCD",
            "goal": "Focus",
            "trusted_facts": [
                {"id": "bad", "type": "COLLINEAR", "args": ["A", "B", "C"], "status": "PROVEN"}
            ],
        },
    )
    assert response.status_code == 422
    assert "authoritative" in response.json()["detail"]["message"]


def test_interpretation_route_calls_orchestrator_and_surfaces_error(monkeypatch):
    from geometry_scene.errors import GeometryError

    monkeypatch.setattr(
        routes, "interpret", lambda *args: (_ for _ in ()).throw(GeometryError("model failed"))
    )
    response = client().post(
        "/v1/geometry-scenes/interpret", json={"problem_text": "ABCD", "goal": "Focus"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "model failed"


def test_failed_run_reference_is_public_but_evidence_is_private(monkeypatch):
    from geometry_scene.orchestration import OrchestrationFailure

    error = OrchestrationFailure("No candidate accepted", {"private": "rejected plan"})
    error.details["run_id"] = "run_test"
    monkeypatch.setattr(routes, "interpret", lambda *args: (_ for _ in ()).throw(error))
    response = client().post(
        "/v1/geometry-scenes/interpret", json={"problem_text": "ABCD", "goal": "Focus"}
    )
    assert response.json()["detail"] == {
        "code": "GEOMETRY_PLAN_EXHAUSTED",
        "message": "No candidate accepted",
        "run_id": "run_test",
    }
