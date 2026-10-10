import json
import time
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from test_route_contracts import program
from test_route_enrichment import value as enrichment_value

from mathbank_rest import route_compiler, tutor


def atomic(bad_quote: str | None = None) -> dict:
    """Decomposition-only payload: no assets/produces/uses_claims/asset_links."""
    data = program()
    data["assets"] = []
    for index, step in enumerate(data["steps"], 1):
        step["produces"] = []
        step["uses_claims"] = []
        step["asset_links"] = []
        step["source_quote"] = bad_quote if bad_quote else step["source_quote"]
    return data


def provider(monkeypatch, payloads):
    payloads = json.loads(json.dumps(payloads))
    for payload in payloads:
        if (
            "steps" in payload
            and isinstance(payload["steps"][0], dict)
            and "source_quote" in payload["steps"][0]
        ):
            for step in payload["steps"]:
                quote = step.pop("source_quote")
                step["source_excerpt_index"] = (
                    1
                    if quote == "Given three right angles"
                    else 2
                    if quote == "Use the sum"
                    else 999
                )
    create = MagicMock(
        side_effect=[
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(payload)),
                        finish_reason="stop",
                    )
                ]
            )
            for payload in payloads
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(tutor._client, "with_options", lambda **options: client)
    return create


def test_invalid_source_quote_gets_one_bounded_repair(monkeypatch):
    bad = atomic(bad_quote="Invented unsupported excerpt")
    good = atomic()
    enrichment_payloads = [enrichment_value().model_dump() for _ in good["steps"]]
    create = provider(monkeypatch, [bad, good, *enrichment_payloads])
    result = route_compiler.generate(
        {
            "statement_text": "A test problem",
            "source": "Given three right angles. Use the sum.",
            "canonical_code": "TEST",
            "verification_status": "UNVERIFIED",
        },
        [],
        route_compiler.OpenAIChatProvider(),
    )
    assert len(result.steps) == 2 and len(result.assets) == 8
    assert create.call_count == 1 + 1 + 2
    repair = create.call_args_list[1].kwargs["messages"][-1]["content"]
    assert "excerpt index" in repair and "invent" in repair


def test_two_error_guided_repairs_do_not_accept_invalid_output(monkeypatch):
    bad = atomic(bad_quote="Not in source")
    create = provider(monkeypatch, [bad, bad, bad])
    with pytest.raises(ValueError, match="excerpt index"):
        route_compiler.generate(
            {
                "statement_text": "A test problem",
                "source": "Given three right angles. Use the sum.",
                "canonical_code": "TEST",
                "verification_status": "UNVERIFIED",
            },
            [],
            route_compiler.OpenAIChatProvider(),
        )
    assert create.call_count == 3


def test_source_hash_changes_on_statement_solution_or_verification_change():
    original = {
        "solution_id": "s",
        "statement_text": "statement",
        "source": "source",
        "verification_status": "UNVERIFIED",
    }
    for field in original:
        assert route_compiler.source_hash(original) != route_compiler.source_hash(
            {**original, field: "different"}
        )


def test_all_sources_has_no_ten_thousand_or_length_filter():
    sources = [
        {
            "solution_id": str(i),
            "statement_text": "p",
            "source": "s",
            "verification_status": "UNVERIFIED",
        }
        for i in range(10005)
    ]
    sources[-1]["source"] = "Long source " * 1000
    conn = MagicMock()
    conn.execute.side_effect = [
        SimpleNamespace(all=list),
        SimpleNamespace(mappings=lambda: sources),
    ]
    assert route_compiler.select_sources(conn, None) == sources
    query = str(conn.execute.call_args.args[0])
    assert "length(" not in query and "BETWEEN" not in query


def test_selected_scope_skips_existing_identical_release():
    source = {
        "solution_id": "s",
        "statement_text": "p",
        "source": "x",
        "verification_status": "UNVERIFIED",
    }
    conn = MagicMock()
    conn.execute.side_effect = [
        SimpleNamespace(all=lambda: [("s", route_compiler.source_hash(source))]),
        SimpleNamespace(mappings=lambda: [source]),
    ]
    assert route_compiler.select_sources(conn, None) == []


def test_requested_auto_approval_uses_shared_review_in_persistence_transaction(monkeypatch):
    from mathbank_rest import route_runtime

    release = str(uuid4())
    value = route_compiler.RouteProgram.model_validate(program())
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.one.return_value = {
        "status": "DRAFT",
        "content_hash": "h",
    }
    monkeypatch.setattr(route_compiler, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
    monkeypatch.setattr(route_compiler, "generate", lambda *args: value)
    monkeypatch.setattr(route_compiler, "persist", lambda *args: release)
    reviewer = MagicMock()
    monkeypatch.setattr(route_runtime, "review", reviewer)
    result = route_compiler.compile_source(
        {"solution_id": "s", "canonical_code": "TEST"},
        [],
        "run",
        route_compiler.OpenAIChatProvider(),
        "operator-bulk-approval",
    )
    assert result["status"] == "REVIEWED"
    reviewer.assert_called_once_with(
        conn, route_compiler.UUID(release), "operator-bulk-approval", "h"
    )


def test_review_rejection_is_a_failed_job_not_approval(monkeypatch):
    from mathbank_rest import route_runtime
    from mathbank_rest.step_runtime import StateVersionConflict

    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.one.return_value = {
        "status": "DRAFT",
        "content_hash": "h",
    }
    monkeypatch.setattr(route_compiler, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
    monkeypatch.setattr(
        route_compiler,
        "generate",
        lambda *args: route_compiler.RouteProgram.model_validate(program()),
    )
    monkeypatch.setattr(route_compiler, "persist", lambda *args: str(uuid4()))
    monkeypatch.setattr(
        route_runtime, "review", MagicMock(side_effect=StateVersionConflict("Source changed"))
    )
    result = route_compiler.compile_source(
        {"solution_id": "s", "canonical_code": "TEST"},
        [],
        "run",
        route_compiler.OpenAIChatProvider(),
        "operator",
    )
    assert result["status"] == "FAILED" and result["error_code"] == "StateVersionConflict"


def test_blank_source_fails_before_paid_call():
    with pytest.raises(ValueError, match="no nonempty canonical source"):
        route_compiler.generate(
            {"source": " ", "statement_text": "Problem"}, [], route_compiler.OpenAIChatProvider()
        )


@pytest.mark.parametrize("eventual_pass", [False, True])
def test_compile_source_critic_feedback_loop(monkeypatch, eventual_pass):
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.one.return_value = {
        "status": "DRAFT",
        "content_hash": "h",
    }
    monkeypatch.setattr(route_compiler, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
    value = route_compiler.RouteProgram.model_validate(program())
    generate_calls = []
    monkeypatch.setattr(
        route_compiler,
        "generate",
        lambda source, *a: (generate_calls.append(source.get("_critic_feedback")), value)[1],
    )
    monkeypatch.setattr(route_compiler, "persist", lambda *args: str(uuid4()))
    rejected = {"accepted": False, "evaluations": [{"step_index": 1, "issues": ["Wrong taxonomy"]}]}
    accepted = {"accepted": True, "evaluations": []}
    critic_eval = MagicMock(
        side_effect=[rejected, rejected, accepted if eventual_pass else rejected]
    )
    monkeypatch.setattr(route_compiler, "evaluate", critic_eval)
    source = {"solution_id": "s", "canonical_code": "TEST", "_generation_metadata": {}}
    result = route_compiler.compile_source(
        source,
        [],
        "run",
        route_compiler.OpenAIChatProvider(model="gpt-4o-mini"),
        None,
        route_compiler.OpenAIChatProvider(model="gpt-4.1-mini"),
    )
    assert critic_eval.call_count == 3
    assert generate_calls[0] is None and generate_calls[1]  # feedback flows into the next attempt
    if eventual_pass:
        assert result["status"] == "DRAFT"
        assert len(source["_generation_metadata"]["critic_attempt_history"]) == 3
    else:
        assert result["status"] == "FAILED" and result["error_code"] == "CriticRejected"


def test_compile_source_without_critic_never_calls_evaluate(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.mappings.return_value.one.return_value = {
        "status": "DRAFT",
        "content_hash": "h",
    }
    monkeypatch.setattr(route_compiler, "engine", SimpleNamespace(begin=lambda: nullcontext(conn)))
    value = route_compiler.RouteProgram.model_validate(program())
    monkeypatch.setattr(route_compiler, "generate", lambda *a: value)
    monkeypatch.setattr(route_compiler, "persist", lambda *args: str(uuid4()))
    evaluate = MagicMock(side_effect=AssertionError("critic must not run when disabled"))
    monkeypatch.setattr(route_compiler, "evaluate", evaluate)
    result = route_compiler.compile_source(
        {"solution_id": "s", "canonical_code": "TEST"},
        [],
        "run",
        route_compiler.OpenAIChatProvider(),
    )
    assert result["status"] == "DRAFT"
    evaluate.assert_not_called()


def test_resume_report_counts_complete_cohort_and_actual_release_states(monkeypatch):
    conn = MagicMock()
    conn.execute.side_effect = [
        SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: {"run_id": "r"})),
        SimpleNamespace(all=lambda: [("DRAFT", 17), ("FAILED", 3), ("QUEUED", 5)]),
        SimpleNamespace(all=lambda: [("REVIEWED", 17)]),
    ]
    monkeypatch.setattr(
        route_compiler, "engine", SimpleNamespace(connect=lambda: nullcontext(conn))
    )
    report = route_compiler.run_report("r")
    assert report["selected"] == 25 and report["remaining"] == 5
    assert report["reviewed"] == 17 and report["failures"] == 3


def test_incremental_report_replaces_snapshot_atomically(tmp_path):
    path = tmp_path / "progress.json"
    route_compiler.write_report(path, {"remaining": 18})
    route_compiler.write_report(path, {"remaining": 17, "reviewed": 1})
    assert json.loads(path.read_text()) == {"remaining": 17, "reviewed": 1}
    assert not path.with_suffix(".json.tmp").exists()


def test_taxonomy_cache_refreshes_only_after_ttl(monkeypatch):
    calls = []

    def fake_taxonomy(conn):
        calls.append(1)
        return [{"taxonomy_node_id": f"N{len(calls)}", "node_type": "CONCEPT", "name": "x"}]

    monkeypatch.setattr(route_compiler, "taxonomy", fake_taxonomy)
    monkeypatch.setattr(
        route_compiler, "engine", SimpleNamespace(connect=lambda: nullcontext(MagicMock()))
    )
    cache = route_compiler.TaxonomyCache(refresh_seconds=1000)
    first = cache.get()
    second = cache.get()
    assert first == second and len(calls) == 1  # no re-query within the TTL window
    cache._loaded_at -= 2000  # force expiry without sleeping in the test
    third = cache.get()
    assert third != first and len(calls) == 2  # picks up newly added taxonomy after TTL


def test_compile_source_accepts_plain_list_or_live_cache(monkeypatch):
    seen = []
    dummy_program = SimpleNamespace(steps=[])
    monkeypatch.setattr(
        route_compiler, "engine", SimpleNamespace(begin=lambda: nullcontext(MagicMock()))
    )

    def fake_generate(source, nodes, provider):
        seen.append(nodes)
        return dummy_program

    monkeypatch.setattr(route_compiler, "generate", fake_generate)
    monkeypatch.setattr(route_compiler, "persist", lambda *args: str(uuid4()))
    static_nodes = [{"taxonomy_node_id": "STATIC"}]
    route_compiler.compile_source(
        {"solution_id": "s", "canonical_code": "TEST"},
        static_nodes,
        "run",
        route_compiler.OpenAIChatProvider(),
    )
    assert seen[-1] is static_nodes  # existing plain-list callers are unaffected

    cache = route_compiler.TaxonomyCache(refresh_seconds=1000)
    cache._nodes = [{"taxonomy_node_id": "LIVE"}]
    cache._loaded_at = time.monotonic()
    route_compiler.compile_source(
        {"solution_id": "s", "canonical_code": "TEST"},
        cache,
        "run",
        route_compiler.OpenAIChatProvider(),
    )
    assert seen[-1] == [{"taxonomy_node_id": "LIVE"}]
