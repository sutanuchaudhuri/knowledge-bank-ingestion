import json
from unittest.mock import MagicMock

import httpx
import pytest
from test_route_contracts import program

from mathbank_rest import route_compiler, route_ollama, tutor
from mathbank_rest.route_enrichment import StepEnrichment
from mathbank_rest.route_ollama import OllamaError, OllamaProvider


def test_local_generation_never_calls_openai_and_records_model_usage(monkeypatch):
    value = program()
    for index, step in enumerate(value["steps"], 1):
        step.pop("source_quote")
        step["source_excerpt_index"] = index
        step["produces"] = []
        step["uses_claims"] = []
        step["asset_links"] = []
    value["assets"] = []
    enrichment = StepEnrichment(
        claim="Use the sum",
        misconception="Wrong angle total",
        symptom="Wrong total",
        why_wrong="Wrong number of sides",
        correct_model="Count the sides",
        theory_title="Angle sum",
        theory="Sum is (n-2)*180",
        recognition_cues=["Count sides"],
        quiz_question="What is the pentagon sum?",
        quiz_answer="540 degrees",
    )
    complete = MagicMock(
        side_effect=[
            (json.dumps(value), {"eval_count": 123, "total_duration": 5000}),
            (enrichment.model_dump_json(), {"eval_count": 40}),
            (enrichment.model_dump_json(), {"eval_count": 41}),
        ]
    )
    provider = OllamaProvider(model="qwen2.5:7b", digest="test-digest")
    monkeypatch.setattr(
        OllamaProvider,
        "complete",
        complete,
    )
    paid = MagicMock(side_effect=AssertionError("No paid fallback allowed"))
    monkeypatch.setattr(tutor._client, "with_options", paid)
    source = {
        "solution_id": "test",
        "source": "Given three right angles. Use the sum.",
        "statement_text": "Problem",
        "canonical_code": "TEST",
        "verification_status": "UNVERIFIED",
    }
    result = route_compiler.generate(source, [], provider)
    assert len(result.steps) == 2
    metadata = source["_generation_metadata"]
    assert metadata["provider"] == "ollama" and metadata["model"] == "qwen2.5:7b"
    assert metadata["digest"] == "test-digest" and metadata["calls"][0]["eval_count"] == 123
    assert metadata["validation"] == "source_structure_taxonomy_dag_enrichment_passed"
    assert len(result.assets) == 8 and complete.call_count == 3
    paid.assert_not_called()


def test_remote_endpoint_refused_before_any_request():
    with pytest.raises(ValueError, match="loopback"):
        OllamaProvider(model="test", endpoint="https://example.com").preflight()


def test_oversized_prompt_fails_before_transport():
    with pytest.raises(ValueError, match="no truncation"):
        OllamaProvider(model="test").complete(
            [{"role": "user", "content": "x" * 20000}],
            {},
        )


def test_http_failure_never_falls_back(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.side_effect = httpx.ConnectError("private exception text")
    monkeypatch.setattr(route_ollama.httpx, "Client", lambda **kwargs: client)
    with pytest.raises(OllamaError, match="no paid fallback") as failure:
        OllamaProvider(model="test").complete([{"content": "x"}], {})
    assert "private exception text" not in str(failure.value)


def test_truncated_output_never_accepted(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.post.return_value.json.return_value = {"done_reason": "length"}
    monkeypatch.setattr(route_ollama.httpx, "Client", lambda **kwargs: client)
    with pytest.raises(route_ollama.OutputTruncated, match="no partial"):
        OllamaProvider(model="test").complete([{"content": "x"}], {})


def test_decomposition_retries_truncation_with_brevity_hint_then_succeeds(monkeypatch):
    value = program()
    for index, step in enumerate(value["steps"], 1):
        step.pop("source_quote")
        step["source_excerpt_index"] = index
        step["produces"] = []
        step["uses_claims"] = []
        step["asset_links"] = []
    value["assets"] = []
    complete = MagicMock(
        side_effect=[
            route_ollama.OutputTruncated("Ollama output exceeded token budget"),
            (json.dumps(value), {"eval_count": 50}),
        ]
    )
    monkeypatch.setattr(OllamaProvider, "complete", complete)
    monkeypatch.setattr(route_compiler, "validate_enrichment", lambda program: None)
    monkeypatch.setattr(
        "mathbank_rest.route_enrichment.enrich", lambda program, source, provider: program
    )
    source = {
        "solution_id": "test",
        "source": "Given three right angles. Use the sum.",
        "statement_text": "Problem",
        "canonical_code": "TEST",
        "verification_status": "UNVERIFIED",
    }
    provider = OllamaProvider(model="qwen2.5:1.5b", digest="small-digest")
    result = route_compiler.generate(source, [], provider)
    assert len(result.steps) == 2 and complete.call_count == 2
    retry_prompt = complete.call_args.args[0][-1]["content"]
    assert "SHORTER" in retry_prompt
    calls = source["_generation_metadata"]["calls"]
    assert calls[0]["stage"] == "decomposition" and calls[0]["attempt"] == 0 and "error" in calls[0]
    assert calls[1]["attempt"] == 1 and calls[1]["eval_count"] == 50


def test_decomposition_truncation_still_fails_after_three_attempts(monkeypatch):
    complete = MagicMock(side_effect=route_ollama.OutputTruncated("too long"))
    monkeypatch.setattr(OllamaProvider, "complete", complete)
    source = {
        "solution_id": "test",
        "source": "Given three right angles. Use the sum.",
        "statement_text": "Problem",
        "canonical_code": "TEST",
        "verification_status": "UNVERIFIED",
    }
    with pytest.raises(route_ollama.OutputTruncated):
        route_compiler.generate(source, [], OllamaProvider(model="qwen2.5:1.5b"))
    assert complete.call_count == 3


def test_enrichment_retries_truncation_with_brevity_hint(monkeypatch):
    from test_route_enrichment import bare, value

    from mathbank_rest.route_enrichment import enrich

    complete = MagicMock(
        side_effect=[
            route_ollama.OutputTruncated("too long"),
            (value().model_dump_json(), {"eval_count": 30}),
            (value().model_dump_json(), {"eval_count": 31}),
        ]
    )
    provider = OllamaProvider(model="small", digest="small")
    monkeypatch.setattr(OllamaProvider, "complete", complete)
    source = {"statement_text": "Problem", "_generation_metadata": {"calls": []}}
    result = enrich(bare(), source, provider)
    assert complete.call_count == 3 and len(result.assets) == 8
    retry_prompt = complete.call_args_list[1].args[0][-1]["content"]
    assert "SHORTER" in retry_prompt
    calls = source["_generation_metadata"]["calls"]
    assert calls[0]["step_index"] == 1 and calls[0]["attempt"] == 0 and "error" in calls[0]
    assert calls[1]["step_index"] == 1 and calls[1]["attempt"] == 1 and calls[1]["eval_count"] == 30
