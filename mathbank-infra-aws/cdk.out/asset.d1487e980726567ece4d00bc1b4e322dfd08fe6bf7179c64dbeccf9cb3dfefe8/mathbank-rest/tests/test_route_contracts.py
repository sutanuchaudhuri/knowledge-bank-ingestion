import pytest
from pydantic import ValidationError

from mathbank_rest.route_contracts import RouteProgram, content_hash, validate_source


def program():
    instruction = {
        key: key
        for key in (
            "goal_text",
            "recognition_cue",
            "reasoning_explanation",
            "why_this_works",
            "prerequisite_recap",
            "connection_to_previous_step",
            "connection_to_next_step",
            "common_error_summary",
            "student_prompt",
            "expected_response",
            "short_explanation",
            "full_explanation",
        )
    } | {"has_diagram": False, "diagram_description": "", "diagram_instructions": ""}
    payload = {
        "approach_name": "Angle sum",
        "approach_summary": "Use the given angles.",
        "difficulty_level": 2,
        "conceptual_load": 2,
        "algebraic_load": 1,
        "insight_load": 1,
        "assets": [],
        "steps": [
            {
                "mathematical_result": "result",
                "source_quote": "Given three right angles",
                "depends_on": [],
                "produces": [],
                "uses_claims": [],
                "requirements": [],
                "instruction": instruction,
                "hints": ["orient", "recognize", "setup", "near"],
                "asset_links": [],
            },
            {
                "mathematical_result": "result2",
                "source_quote": "Use the sum",
                "depends_on": [1],
                "produces": [],
                "uses_claims": [],
                "requirements": [],
                "instruction": instruction,
                "hints": ["orient", "recognize", "setup", "near"],
                "asset_links": [],
            },
        ],
    }
    from mathbank_rest.route_enrichment import StepEnrichment, attach_enrichment

    value = RouteProgram.model_validate(payload)
    for index in range(1, 3):
        attach_enrichment(
            value,
            index,
            StepEnrichment(
                claim=f"Step {index} result",
                misconception="Use the wrong angle sum.",
                symptom="Incorrect angle total",
                why_wrong="The polygon has five sides.",
                correct_model="Use the pentagon angle sum.",
                theory_title="Polygon angles",
                theory="For n sides the interior angles sum to (n-2)*180 degrees.",
                recognition_cues=["Count the sides."],
                quiz_question="Which angle sum applies?",
                quiz_answer="540 degrees for a pentagon.",
            ),
        )
    return value.model_dump()


def test_source_grounding_and_canonical_ids_are_checked():
    value = RouteProgram.model_validate(program())
    validate_source(value, "Given three right angles. Use the sum.", set())
    with pytest.raises(ValueError, match="source excerpt"):
        validate_source(value, "Different source.", set())
    value.steps[0].requirements = []
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})


@pytest.mark.parametrize(
    "change", ["cycle", "future", "missing_claim", "missing_asset", "missing_hint"]
)
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


def test_diagram_description_required_only_when_diagram_present():
    data = program()
    data["steps"][0]["instruction"]["has_diagram"] = True
    data["steps"][0]["instruction"]["diagram_description"] = "A labeled triangle ABC."
    data["steps"][0]["instruction"]["diagram_instructions"] = (
        "Draw triangle ABC with right angle at B; label AB=3, BC=4, AC=5."
    )
    RouteProgram.model_validate(data)  # does not raise


def proposed_requirement(**overrides):
    base = {
        "taxonomy_node_id": "ALG.C01.S02",
        "role": "REQUIRED",
        "required_level": 2,
        "importance": 0.5,
        "blocking": True,
        "proposed_node_type": "SUBCONCEPT",
        "proposed_name": "Sum of a geometric series",
        "proposed_description": "Closed form for the sum of a finite geometric series.",
    }
    return base | overrides


def test_well_formed_unknown_taxonomy_id_can_be_proposed():
    data = program()
    data["steps"][0]["requirements"] = [proposed_requirement()]
    value = RouteProgram.model_validate(data)
    validate_source(value, "Given three right angles. Use the sum.", set())  # no raise


def test_proposal_fields_must_all_be_present_or_all_blank():
    data = program()
    data["steps"][0]["requirements"] = [proposed_requirement(proposed_name="")]
    with pytest.raises(ValidationError, match="together"):
        RouteProgram.model_validate(data)


def test_proposed_id_must_follow_dotted_uppercase_convention():
    data = program()
    data["steps"][0]["requirements"] = [proposed_requirement(taxonomy_node_id="not valid")]
    with pytest.raises(ValidationError, match="dotted uppercase"):
        RouteProgram.model_validate(data)


def test_cannot_propose_new_metadata_for_an_already_known_id():
    data = program()
    known_id = "GEO.KNOWN"
    data["steps"][0]["requirements"] = [proposed_requirement(taxonomy_node_id=known_id)]
    value = RouteProgram.model_validate(data)
    with pytest.raises(ValueError, match="already-known"):
        validate_source(value, "Given three right angles. Use the sum.", {known_id})


def test_same_proposed_id_reused_for_a_different_concept_is_rejected():
    data = program()
    data["steps"][0]["requirements"] = [proposed_requirement()]
    data["steps"][1]["requirements"] = [
        proposed_requirement(proposed_name="A different concept entirely")
    ]
    value = RouteProgram.model_validate(data)
    with pytest.raises(ValueError, match="two different concepts"):
        validate_source(value, "Given three right angles. Use the sum.", set())


def test_same_proposed_id_reused_for_the_identical_concept_is_allowed():
    data = program()
    data["steps"][0]["requirements"] = [proposed_requirement()]
    data["steps"][1]["requirements"] = [proposed_requirement()]
    value = RouteProgram.model_validate(data)
    validate_source(value, "Given three right angles. Use the sum.", set())  # no raise


def test_proposed_asset_taxonomy_ids_are_accepted_but_unknown_ones_are_not():
    data = program()
    data["steps"][0]["requirements"] = [proposed_requirement()]
    data["assets"][0]["taxonomy_node_ids"] = ["ALG.C01.S02"]
    value = RouteProgram.model_validate(data)
    validate_source(value, "Given three right angles. Use the sum.", set())  # no raise

    other = program()
    other["assets"][0]["taxonomy_node_ids"] = ["NEVER_PROPOSED_OR_KNOWN"]
    with pytest.raises(ValueError, match="Asset refers to an unknown"):
        validate_source(
            RouteProgram.model_validate(other), "Given three right angles. Use the sum.", set()
        )


@pytest.mark.parametrize(
    "change",
    ["flag_true_blank_description", "flag_true_blank_instructions", "flag_false_nonblank"],
)
def test_diagram_fields_must_be_consistent_with_has_diagram(change):
    data = program()
    if change == "flag_true_blank_description":
        data["steps"][0]["instruction"]["has_diagram"] = True
        data["steps"][0]["instruction"]["diagram_instructions"] = "Draw a triangle."
    elif change == "flag_true_blank_instructions":
        data["steps"][0]["instruction"]["has_diagram"] = True
        data["steps"][0]["instruction"]["diagram_description"] = "A triangle."
    else:
        data["steps"][0]["instruction"]["diagram_description"] = "Invented figure."
    with pytest.raises(ValidationError, match="diagram"):
        RouteProgram.model_validate(data)
