"""Catalog stages must preserve relationship semantics and reject fabricated edges."""

import pytest

from mathbank_rest.relationship_enrichment import Proposal, schema_for, validate_proposal


def proposal(kind="PART_OF", start="component", end="composite"):
    return Proposal.model_validate(
        {
            "relationships": [
                {
                    "from_slug": start,
                    "to_slug": end,
                    "relation_type": kind,
                    "confidence": 0.9,
                    "rationale": "The component action is explicitly required within the composite action.",
                }
            ],
            "explanation": "Catalog definitions justify this observable component relationship.",
        }
    )


@pytest.mark.parametrize(
    "kind,allowed",
    [
        ("skill", ["PART_OF", "BUILDS_ON"]),
        ("concept", ["PREREQUISITE_OF"]),
    ],
)
def test_structured_output_has_exact_catalog_and_distinct_stage_types(kind, allowed):
    schema = schema_for(kind, {"component", "composite"})
    assert schema["$defs"]["Relationship"]["properties"]["relation_type"]["enum"] == allowed
    assert schema["$defs"]["CatalogSlug"]["enum"] == ["component", "composite"]
    assert schema["$defs"]["Relationship"]["properties"]["from_slug"] == {
        "$ref": "#/$defs/CatalogSlug"
    }
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "stage,edge,match",
    [
        ("skill", proposal("PREREQUISITE_OF"), "type"),
        ("concept", proposal("PART_OF"), "type"),
        ("skill", proposal(start="unknown"), "Unknown"),
        ("skill", proposal(start="component", end="component"), "distinct"),
    ],
)
def test_invalid_stage_endpoints_and_self_edges_are_rejected(stage, edge, match):
    with pytest.raises(ValueError, match=match):
        validate_proposal(stage, "component", {"component", "composite"}, edge)


def test_unrelated_and_duplicate_proposals_are_rejected():
    with pytest.raises(ValueError, match="anchor"):
        validate_proposal("skill", "anchor", {"anchor", "component", "composite"}, proposal())
    duplicate = proposal()
    duplicate.relationships *= 2
    with pytest.raises(ValueError, match="Duplicate"):
        validate_proposal("skill", "component", {"component", "composite"}, duplicate)


def test_empty_proposal_is_explicit_success_not_forced_metadata():
    empty = Proposal(
        relationships=[],
        explanation="The available definitions do not justify any catalog relationships.",
    )
    validate_proposal("skill", "component", {"component"}, empty)
    with pytest.raises(ValueError):
        Proposal(relationships=[], explanation="")


def test_global_publication_mode_is_explicit(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from mathbank_rest import publication

    calls = []
    monkeypatch.setattr(publication, "engine", SimpleNamespace(connect=lambda: nullcontext(None)))
    monkeypatch.setattr(publication, "fingerprint", lambda conn: "snapshot")
    monkeypatch.setattr(publication, "publish", lambda *args: calls.append(args))
    publication.publish_current(None)
    assert calls == [("snapshot", None)]
    with pytest.raises(ValueError):
        publication.publish_current([])


def test_task_dispatch_preserves_distinct_catalog_and_question_operations(monkeypatch):
    from scripts import enrich_corpus as worker

    calls = []
    monkeypatch.setattr(
        worker, "enrich_relationships", lambda kind, slug: calls.append((kind, slug)) or {}
    )
    monkeypatch.setattr(worker, "enrich_problem", lambda code: calls.append(code) or {})
    worker.execute_task("relations:skill:component")
    worker.execute_task("relations:concept:algebra")
    worker.execute_task("AIME_1983_Q01")
    assert calls == [("skill", "component"), ("concept", "algebra"), "AIME_1983_Q01"]
    with pytest.raises(ValueError):
        worker.execute_task("relations:unknown:anchor")


def test_mixed_coordinator_uses_one_relation_slot_and_global_publication(monkeypatch):
    import threading
    from concurrent.futures import Future
    from contextlib import nullcontext
    from types import SimpleNamespace

    from scripts import enrich_corpus as worker

    state = {"relation": False, "published": False}
    submitted = []
    publication_scopes = []
    coordinator_thread = threading.get_ident()

    class Executor:
        def submit(self, operation, code):
            submitted.append(code)
            future = Future()
            future.set_result(operation(code))
            return future

    conn = SimpleNamespace(
        execute=lambda query: SimpleNamespace(
            scalar_one=lambda: int(state["relation"] and not state["published"]),
        )
    )
    monkeypatch.setattr(worker, "engine", SimpleNamespace(connect=lambda: nullcontext(conn)))
    monkeypatch.setattr(
        worker, "select_anchor", lambda conn: None if state["relation"] else ("skill", "anchor")
    )
    monkeypatch.setattr(
        worker,
        "select_work",
        lambda conn, limit, excluded: (
            ["ONE", "TWO", "THREE"] if len(submitted) else [],
            ["ONE", "TWO", "THREE"][:limit] if not submitted else [],
        ),
    )

    def generate(kind, slug):
        state["relation"] = True
        return {"status": "automatically_approved"}

    def publish(scope):
        assert threading.get_ident() == coordinator_thread
        publication_scopes.append(scope)
        state["published"] = True
        monkeypatch.setattr(worker, "select_work", lambda conn, limit, excluded: ([], []))

    monkeypatch.setattr(worker, "enrich_relationships", generate)
    monkeypatch.setattr(worker, "enrich_problem", lambda code: {"status": "automatically_approved"})
    monkeypatch.setattr(worker, "publish_current", publish)
    worker.coordinate(False, 4, 4, threading.Event(), Executor(), relationships=True)
    assert submitted == ["ONE", "TWO", "THREE", "relations:skill:anchor"]
    assert publication_scopes == [None]
