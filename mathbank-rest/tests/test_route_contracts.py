import pytest
from pydantic import ValidationError

from mathbank_rest.route_contracts import RouteProgram, content_hash, validate_source


def program():
    instruction = {key: key for key in (
        "goal_text", "recognition_cue", "reasoning_explanation", "why_this_works",
        "prerequisite_recap", "connection_to_previous_step", "connection_to_next_step",
        "common_error_summary", "student_prompt", "expected_response", "short_explanation",
        "full_explanation",
    )}
    return {
        "approach_name": "Angle sum", "approach_summary": "Use the given angles.",
        "difficulty_level": 2, "conceptual_load": 2, "algebraic_load": 1, "insight_load": 1,
        "assets": [],
        "steps": [{
            "mathematical_result": "result", "source_quote": "Given three right angles",
            "depends_on": [], "produces": [], "uses_claims": [], "requirements": [],
            "instruction": instruction, "hints": ["orient", "recognize", "setup", "near"],
            "asset_links": [],
        }, {
            "mathematical_result": "result2", "source_quote": "Use the sum",
            "depends_on": [1], "produces": [], "uses_claims": [], "requirements": [],
            "instruction": instruction, "hints": ["orient", "recognize", "setup", "near"],
            "asset_links": [],
        }],
    }


def test_source_grounding_and_canonical_ids_are_checked():
    value = RouteProgram.model_validate(program())
    validate_source(value, "Given three right angles. Use the sum.", set())
    with pytest.raises(ValueError, match="source excerpt"):
        validate_source(value, "Different source.", set())
    value.steps[0].requirements = []
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


@pytest.mark.parametrize("change", ["cycle", "future", "missing_claim", "missing_asset", "missing_hint"])
def test_structurally_invalid_route_is_rejected(change):
    data = program()
    if change in {"cycle", "future"}:
        data["steps"][0]["depends_on"] = [1 if change == "cycle" else 2]
    elif change == "missing_claim":
        data["steps"][0]["uses_claims"] = ["UNKNOWN"]
    elif change == "missing_asset":
        data["steps"][0]["asset_links"] = [{"asset_key": "UNKNOWN", "role": "CHECKED_BY"}]
    else:
        data["steps"][0]["hints"] = ["one"]
    with pytest.raises(ValidationError):
        RouteProgram.model_validate(data)
