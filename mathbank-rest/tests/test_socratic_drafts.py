from copy import deepcopy
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from mathbank_rest import socratic_service as service
from mathbank_rest.routers.socratic import require_staff, router
from mathbank_rest.socratic_auth import StaffActor, StaffSession
from mathbank_rest.socratic_contracts import Program, Source, content_digest, initial_program


@pytest.mark.parametrize("mutation", [
    "duplicate", "dangling", "start", "fallback", "ambiguous", "unknown", "unbounded", "code",
])
def test_ir_rejects_unsafe_or_incompatible_graphs(mutation):
    program = initial_program("ALG_PATTERN").model_dump(mode="json")
    if mutation == "duplicate":
        program["nodes"].append(program["nodes"][0])
    elif mutation == "dangling":
        program["edges"][0]["to_key"] = "missing"
    elif mutation == "start":
        program["nodes"][1]["type"] = "START"
    elif mutation == "fallback":
        program["fallback_key"] = "missing"
    elif mutation == "ambiguous":
        program["edges"].append(deepcopy(program["edges"][0]))
    elif mutation == "unknown":
        program["nodes"][0]["type"] = "EXECUTE_LAMBDA"
    elif mutation == "unbounded":
        program["max_transitions"] = 0
    else:
        program["nodes"][0]["tool_arn"] = "untrusted"
    with pytest.raises(ValidationError):
        Program.model_validate(program)


def test_ir_preserves_prototype_annotations_accessibility_and_source_revision():
    program = initial_program("ALG_PATTERN").model_dump(mode="json")
    program["nodes"][0].update(topic="Algebra", objective="Explain equivalence",
                                accessible_alternative="Describe the diagram", source_claim_ref="claim:1")
    program["edges"][0]["annotation"] = "Explain this transition."
    parsed = Program.model_validate(program)
    assert parsed.model_dump(mode="json") == program
    assert content_digest({"b": 2, "a": 1}) == content_digest({"a": 1, "b": 2})
    with pytest.raises(ValidationError):
        Source(problem_code="FIXTURE", solution_id=uuid4())


def test_storage_failure_is_explicit_and_sanitized(monkeypatch):
    engine = MagicMock()
    engine.connect.side_effect = OperationalError("private-dsn", {}, Exception("private-password"))
    monkeypatch.setattr(service, "engine", engine)
    with pytest.raises(HTTPException) as error:
        service.strategies()
    assert error.value.status_code == 503
    assert "private" not in str(error.value.detail)


def test_draft_routes_require_staff_and_reject_overposted_identity(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    actor = StaffActor(actor_id="synthetic-author", username="author", capabilities=["author"])
    app.dependency_overrides[require_staff] = lambda: StaffSession(actor=actor, csrf_token="csrf")
    create = MagicMock(side_effect=HTTPException(422, "synthetic-input-rejected"))
    monkeypatch.setattr(service, "create_workflow", create)
    with TestClient(app) as client:
        response = client.post("/v1/admin/socratic/workflows", headers={"Idempotency-Key": "create-one"},
                               json={"title": "Test draft", "domain": "Algebra", "owner_id": "another-user"})
        assert response.status_code == 422
        create.assert_not_called()
        response = client.post("/v1/admin/socratic/workflows",
                               json={"title": "Test draft", "domain": "Algebra"})
        assert response.status_code == 422
        create.assert_not_called()


def test_non_author_cannot_reach_persistence(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_staff] = lambda: StaffSession(
        actor=StaffActor(actor_id="reviewer", username="reviewer", capabilities=["publish"]), csrf_token="csrf",
    )
    operation = MagicMock()
    monkeypatch.setattr(service, "list_workflows", operation)
    assert TestClient(app).get("/v1/admin/socratic/workflows").status_code == 403
    operation.assert_not_called()


def test_published_route_must_match_current_compiler_source_hash():
    from mathbank_rest.route_compiler import source_hash

    solution_id = uuid4()
    program = initial_program("ALG_PATTERN")
    program.source = Source(problem_code="SYNTHETIC", solution_id=solution_id,
                            solution_revision=3, route_release_id=uuid4())
    strategy = {"code": "ALG_PATTERN", "domain": "Algebra"}
    problem = {"problem_id": uuid4(), "statement_text": "Synthetic statement"}
    solution = {"solution_id": solution_id, "revision": 3, "body_markdown": "Synthetic solution",
                "body_latex": None, "source": "Synthetic solution", "verification_status": "VERIFIED"}
    route = {"content_hash": "a" * 64, "source_hash": "b" * 64, "status": "PUBLISHED"}
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.first.side_effect = [strategy, problem, solution, route]
    with pytest.raises(HTTPException) as stale:
        service.dependency_snapshot(conn, program, "Algebra")
    assert stale.value.status_code == 409 and stale.value.detail["code"] == "SOCRATIC_ROUTE_STALE"
    route["source_hash"] = source_hash({
        "solution_id": str(solution_id), "statement_text": problem["statement_text"],
        "source": solution["source"], "verification_status": solution["verification_status"],
    })
    conn.execute.return_value.mappings.return_value.first.side_effect = [strategy, problem, solution, route]
    assert service.dependency_snapshot(conn, program, "Algebra")["source"]["route"]["source_hash"] == route["source_hash"]
