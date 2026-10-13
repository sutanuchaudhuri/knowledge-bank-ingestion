from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from test_route_contracts import program

from mathbank_rest.route_contracts import RouteProgram, validate_enrichment
from mathbank_rest.route_enrichment import StepEnrichment, enrich


def value():
    return StepEnrichment(
        claim="Angle sum result",
        misconception="Wrong angle sum",
        symptom="Wrong sum",
        why_wrong="Wrong number of sides",
        correct_model="Count the sides",
        theory_title="Angle sum",
        theory="Sum is (n-2)*180",
        recognition_cues=["Count sides"],
        quiz_question="Sum for five sides?",
        quiz_answer="540 degrees",
    )


def bare():
    data = program()
    data["assets"] = []
    for step in data["steps"]:
        step.update(produces=[], uses_claims=[], asset_links=[])
    return RouteProgram.model_validate(data)


def test_every_step_requires_connected_mandatory_enrichment():
    validate_enrichment(RouteProgram.model_validate(program()))
    with pytest.raises(ValueError, match="requires claim"):
        validate_enrichment(bare())


@pytest.mark.parametrize("change", ["missing_theory", "disconnected_quiz", "blank_misconception"])
def test_substantive_connected_assets_not_just_counts(change):
    data = program()
    if change == "missing_theory":
        data["steps"][0]["asset_links"] = [
            link for link in data["steps"][0]["asset_links"] if link["role"] != "EXPLAINED_BY"
        ]
    elif change == "disconnected_quiz":
        data["assets"][3]["diagnoses"] = []
    else:
        data["assets"][1]["why_wrong"] = " "
    with pytest.raises(ValueError):
        validate_enrichment(RouteProgram.model_validate(data))


def test_enrichment_uses_two_error_guided_repairs_then_succeeds():
    provider = MagicMock()
    provider.complete.side_effect = [
        ("{}", {}),
        ("{}", {}),
        (value().model_dump_json(), {}),
        (value().model_dump_json(), {}),
    ]
    source = {"statement_text": "Test", "_generation_metadata": {"calls": []}}
    result = enrich(bare(), source, provider)
    validate_enrichment(result)
    assert provider.complete.call_count == 4
    assert [call["attempt"] for call in source["_generation_metadata"]["calls"]] == [0, 1, 2, 0]
    messages = provider.complete.call_args_list[2].args[0]
    assert "errors" in messages[-1]["content"]
    assert result.steps[1].uses_claims == ["CLAIM_STEP_1"]


def test_invalid_enrichment_never_returns_partial_route():
    provider = MagicMock()
    provider.complete.return_value = ("{}", {})
    with pytest.raises(ValidationError):
        enrich(bare(), {"statement_text": "Test", "_generation_metadata": {"calls": []}}, provider)
    assert provider.complete.call_count == 3
