import json
from unittest.mock import MagicMock

import pytest
from test_route_contracts import program

from mathbank_rest.route_contracts import RouteProgram, program_digest
from mathbank_rest.route_critic import Evaluation, evaluate, validate_critic_metadata
from mathbank_rest.route_ollama import OllamaProvider


def verdict(**changes):
    return {
        "verdict": "PASS",
        "source_faithfulness": 4,
        "mathematical_consistency": 4,
        "current_step_only": 4,
        "instructional_quality": 4,
        "misconception_correctness": 4,
        "quiz_correctness": 4,
        "taxonomy_alignment": 4,
        "issues": [],
        "summary": "Synthetic test evaluation.",
    } | changes


def accepted_metadata(value, metadata=None):
    base = {"provider": "ollama", "model": "test-generator", "digest": "test-generator-digest"}
    base.update(metadata or {})
    base["critic"] = {
        "model": "test-critic",
        "digest": "test-critic-digest",
        "accepted": True,
        "program_hash": program_digest(value),
        "evaluations": [
            {"step_index": index, "evaluation": verdict()}
            for index in range(1, len(value.steps) + 1)
        ],
    }
    return base


@pytest.mark.parametrize(
    "changes",
    [
        {"verdict": "FAIL"},
        {"verdict": "ABSTAIN"},
        {"quiz_correctness": 2},
        {"issues": ["Wrong answer"]},
        {"summary": " "},
    ],
)
def test_eval_acceptance_requires_verdict_all_thresholds_and_no_issues(changes):
    assert not Evaluation.model_validate(verdict(**changes)).accepted()


def test_critic_cannot_be_same_model_or_digest():
    provider = OllamaProvider(model="same", digest="same")
    with pytest.raises(ValueError, match="different"):
        evaluate(RouteProgram.model_validate(program()), {}, provider, provider, [])


def test_different_model_evals_are_bound_to_exact_program_hash(monkeypatch):
    generator = OllamaProvider(model="generator", digest="generator-digest")
    critic = OllamaProvider(model="critic", digest="critic-digest")
    complete = MagicMock(return_value=(json.dumps(verdict()), {"eval_count": 50}))
    monkeypatch.setattr(OllamaProvider, "complete", complete)
    value = RouteProgram.model_validate(program())
    source = {
        "statement_text": "Problem",
        "source": "Given three right angles. Use the sum.",
        "verification_status": "UNVERIFIED",
        "_generation_metadata": {"model": generator.model, "digest": generator.digest},
    }
    result = evaluate(value, source, critic, generator, [])
    assert result["accepted"] and len(result["evaluations"]) == 2
    assert result["model"] == "critic" and result["calls"][0]["eval_count"] == 50
    validate_critic_metadata(source["_generation_metadata"], 2, program_digest(value))
    with pytest.raises(ValueError, match="different critic"):
        validate_critic_metadata(source["_generation_metadata"], 2, "changed-hash")


def test_rejected_eval_is_persistable_as_diagnostics_but_never_accepted(monkeypatch):
    monkeypatch.setattr(
        OllamaProvider,
        "complete",
        lambda *args: (
            json.dumps(
                verdict(verdict="FAIL", mathematical_consistency=1, issues=["Wrong angle sum"])
            ),
            {},
        ),
    )
    value = RouteProgram.model_validate(program())
    source = {
        "statement_text": "Problem",
        "source": "Given three right angles. Use the sum.",
        "verification_status": "UNVERIFIED",
        "_generation_metadata": {"model": "gen", "digest": "gen"},
    }
    result = evaluate(
        value,
        source,
        OllamaProvider(model="critic", digest="critic"),
        OllamaProvider(model="gen", digest="gen"),
        [],
    )
    assert not result["accepted"]
    with pytest.raises(ValueError):
        validate_critic_metadata(source["_generation_metadata"], 2, program_digest(value))


def test_critic_json_has_two_repairs(monkeypatch):
    complete = MagicMock(
        side_effect=[
            ("{}", {}),
            ("{}", {}),
            (json.dumps(verdict()), {}),
            (json.dumps(verdict()), {}),
        ]
    )
    monkeypatch.setattr(OllamaProvider, "complete", complete)
    source = {
        "statement_text": "Problem",
        "source": "Source",
        "verification_status": "UNVERIFIED",
        "_generation_metadata": {},
    }
    evaluate(
        RouteProgram.model_validate(program()),
        source,
        OllamaProvider(model="critic", digest="critic"),
        OllamaProvider(model="gen", digest="gen"),
        [],
    )
    assert complete.call_count == 4


def test_critic_retries_truncation_with_brevity_hint(monkeypatch):
    from mathbank_rest.route_ollama import OutputTruncated

    complete = MagicMock(
        side_effect=[
            OutputTruncated("too long"),
            (json.dumps(verdict()), {}),
            (json.dumps(verdict()), {}),
        ]
    )
    monkeypatch.setattr(OllamaProvider, "complete", complete)
    source = {
        "statement_text": "Problem",
        "source": "Source",
        "verification_status": "UNVERIFIED",
        "_generation_metadata": {},
    }
    result = evaluate(
        RouteProgram.model_validate(program()),
        source,
        OllamaProvider(model="critic", digest="critic"),
        OllamaProvider(model="gen", digest="gen"),
        [],
    )
    assert complete.call_count == 3 and result["accepted"]
    retry_prompt = complete.call_args_list[1].args[0][-1]["content"]
    assert "SHORTER" in retry_prompt
