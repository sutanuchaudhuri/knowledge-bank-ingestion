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
    with pytest.raises(ValueError, match="no partial"):
        OllamaProvider(model="test").complete([{"content": "x"}], {})
