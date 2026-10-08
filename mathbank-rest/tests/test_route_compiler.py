import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from test_route_contracts import program

from mathbank_rest import route_compiler, tutor


def provider(monkeypatch, payloads):
    payloads = json.loads(json.dumps(payloads))
    for payload in payloads:
        for step in payload["steps"]:
            quote = step.pop("source_quote")
            step["source_excerpt_index"] = (
                1 if quote == "Given three right angles" else 2 if quote == "Use the sum" else 999
            )
    create = MagicMock(
        side_effect=[
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
            )
            for payload in payloads
        ]
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(tutor._client, "with_options", lambda **options: client)
    return create


def test_invalid_source_quote_gets_one_bounded_repair(monkeypatch):
    bad = program()
    bad["steps"][0]["source_quote"] = "Invented unsupported excerpt"
    create = provider(monkeypatch, [bad, program()])
    result = route_compiler.generate(
        {
            "statement_text": "A test problem",
            "source": "Given three right angles. Use the sum.",
            "canonical_code": "TEST",
            "verification_status": "UNVERIFIED",
        },
        [],
    )
    assert len(result.steps) == 2 and create.call_count == 2
    repair = create.call_args.kwargs["messages"][-1]["content"]
    assert "excerpt index" in repair and "invent" in repair


def test_second_rejected_output_is_not_persisted_or_silently_accepted(monkeypatch):
    bad = program()
    bad["steps"][0]["source_quote"] = "Not in source"
    create = provider(monkeypatch, [bad, bad])
    with pytest.raises(ValueError, match="excerpt index"):
        route_compiler.generate(
            {
                "statement_text": "A test problem",
                "source": "Given three right angles. Use the sum.",
                "canonical_code": "TEST",
                "verification_status": "UNVERIFIED",
            },
            [],
        )
    assert create.call_count == 2


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
        "operator",
    )
    assert result["status"] == "FAILED" and result["error_code"] == "StateVersionConflict"


def test_blank_source_fails_before_paid_call():
    with pytest.raises(ValueError, match="no nonempty canonical source"):
        route_compiler.generate({"source": " ", "statement_text": "Problem"}, [])


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
