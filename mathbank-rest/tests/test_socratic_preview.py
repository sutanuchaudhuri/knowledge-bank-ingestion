"""Offline preview tests: routing, DTO allowlist and contracts. No database, AWS or model calls."""
import pytest
from fastapi import FastAPI
from pydantic import ValidationError

from mathbank_rest import socratic_preview as preview
from mathbank_rest.activity_scoring import AR_OPTIONS
from mathbank_rest.routers.socratic import router
from mathbank_rest.socratic_contracts import Program, Respond, Transition


def program(max_transitions=30, edges=None):
    return Program.model_validate({
        "strategy_code": "ALG_PATTERN", "source": {}, "entry": "start", "fallback_key": "review",
        "max_transitions": max_transitions,
        "nodes": [{"key": key, "label": key, "type": kind, "prompt": key} for key, kind in (
            ("start", "START"), ("quiz", "QUIZ"), ("a", "LESSON"), ("b", "LESSON"),
            ("review", "HUMAN_REVIEW"), ("done", "COMPLETE"))],
        "edges": edges if edges is not None else [
            {"from_key": "start", "to_key": "quiz", "outcome": "ALWAYS", "priority": 0},
            {"from_key": "quiz", "to_key": "b", "outcome": "SUCCESS", "priority": 7},
            {"from_key": "quiz", "to_key": "a", "outcome": "SUCCESS", "priority": 2},
            {"from_key": "quiz", "to_key": "done", "outcome": "ALWAYS", "priority": 0},
        ],
    })


def test_lowest_priority_exact_outcome_wins_then_always_then_fallback():
    graph = program()
    chosen = preview.route(graph, "quiz", "SUCCESS", 0)
    assert chosen["to_key"] == "a" and chosen["rule_id"] == "quiz:SUCCESS:2" and chosen["counts"]
    assert preview.route(graph, "quiz", "UNCERTAIN", 0)["to_key"] == "done"
    fallback = preview.route(graph, "a", "SUCCESS", 0)
    assert fallback["decision_source"] == "FALLBACK" and fallback["to_key"] == "review"


def test_retry_without_rule_stays_and_fallback_without_rule_ends():
    graph = program()
    stay = preview.route(graph, "a", "RETRY", 0)
    assert stay["decision_source"] == "STAY_ON_NODE" and stay["to_key"] == "a" and not stay["counts"]
    end = preview.route(graph, "review", "SUCCESS", 0)
    assert end["decision_source"] == "NO_ELIGIBLE_RULE" and end.get("complete")


def test_budget_exhaustion_routes_to_fallback_and_completes():
    exhausted = preview.route(program(max_transitions=2), "quiz", "SUCCESS", 2)
    assert exhausted["decision_source"] == "BUDGET_EXHAUSTED" and exhausted["to_key"] == "review"
    assert exhausted.get("complete")


def test_public_activity_allowlists_prompt_and_safe_options_only():
    snapshot = {"activity_id": "id", "revision": "r", "kind": "ASSERTION_REASON", "prompt": "A and R",
                "options": list(AR_OPTIONS), "activity_type": "MCQ",
                "policy": {"correct_index": 0, "explanation": "secret", "hints": ["secret hint"]}}
    public = preview._public_activity(snapshot)
    assert set(public) == {"activity_id", "revision", "kind", "prompt", "options"}
    assert [option["key"] for option in public["options"]] == ["AR1", "AR2", "AR3", "AR4", "AR5"]
    assert "secret" not in str(public)
    numeric = preview._public_activity(snapshot | {"kind": "NUMERIC_EXACT", "options": []})
    assert "options" not in numeric


@pytest.mark.parametrize("payload", [
    {"response": {"selected_keys": ["AR1"], "is_correct": True}},
    {"response": {"selected_keys": []}},
    {"response": {"text": ""}},
    {"score": 1},
    {"idempotency_key": "has spaces"},
    {"expected_version": 0},
])
def test_respond_rejects_client_grades_and_malformed_commands(payload):
    body = {"expected_version": 1, "idempotency_key": "k1", "current_node_key": "quiz",
            "activity_id": "id", "activity_revision": "r", "response": {"selected_keys": ["AR1"]}}
    with pytest.raises(ValidationError):
        Respond.model_validate(body | payload)


def test_transition_requires_known_outcome():
    with pytest.raises(ValidationError):
        Transition.model_validate({"expected_version": 1, "idempotency_key": "k", "outcome": "PASS"})


def test_preview_routes_are_registered_with_csrf_documentation():
    app = FastAPI()
    app.include_router(router)
    paths = app.openapi()["paths"]
    base = "/v1/admin/socratic"
    assert "post" in paths[f"{base}/workflows/{{workflow_id}}/simulate"]
    assert "get" in paths[f"{base}/previews/{{preview_id}}"]
    for action in ("respond", "assist", "reveal", "transition"):
        operation = paths[f"{base}/previews/{{preview_id}}/{action}"]["post"]
        assert {p["name"] for p in operation["parameters"]} >= {"Origin", "X-CSRF-Token"}
