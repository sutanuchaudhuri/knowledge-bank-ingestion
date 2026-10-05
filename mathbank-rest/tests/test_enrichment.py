"""Automatic metadata is explicit, validated, and never learner mastery."""

import pytest

from mathbank_rest import pedagogy
from mathbank_rest.enrichment import TeachingMetadata, build_manifest


def generated():
    return {
        "skills": [
            {
                "slug": "perform-arithmetic",
                "name": "Perform arithmetic",
                "objective": "Compute exact sums and products",
                "level": 1,
                "role": "prerequisite",
                "prerequisite_for": ["solve-linear-equation"],
                "concept_slugs": [],
            },
            {
                "slug": "solve-linear-equation",
                "name": "Solve a linear equation",
                "objective": "Isolate the unknown using inverse operations",
                "level": 2,
                "role": "primary",
                "prerequisite_for": [],
                "concept_slugs": ["algebra"],
            },
        ],
        "concept_slugs": ["algebra"],
        "technique_slugs": ["substitution"],
        "difficulty": {
            "conceptual_depth": 2,
            "technical_load": 1,
            "algebraic_load": 2,
            "insight_required": 2,
            "number_of_steps": 3,
            "prerequisite_depth": 1,
            "estimated_contest_level": "AIME introductory",
        },
        "confidence": 0.8,
    }


def test_generated_manifest_preserves_distinct_skills_and_prerequisites():
    result = TeachingMetadata.model_validate(generated())
    manifest = build_manifest("FIXTURE", result, {"algebra"}, {"substitution"})
    assert len(manifest["problem_skills"]) == 1
    assert len(manifest["skill_relations"]) == 1
    assert manifest["problem_pedagogy"][0]["number_of_steps"] == 3
    assert all(r["review_status"] == "PENDING" for r in manifest["skills"])


def test_unknown_taxonomy_and_prerequisite_cycles_are_rejected():
    result = TeachingMetadata.model_validate(generated())
    with pytest.raises(ValueError, match="outside"):
        build_manifest("FIXTURE", result, set(), {"substitution"})
    data = generated()
    data["skills"][1]["prerequisite_for"] = ["perform-arithmetic"]
    with pytest.raises(ValueError, match="cycle"):
        build_manifest(
            "FIXTURE", TeachingMetadata.model_validate(data), {"algebra"}, {"substitution"}
        )


def test_structured_generation_constrains_all_taxonomy_surfaces():
    from mathbank_rest.enrichment import generation_schema

    schema = generation_schema({"algebra"}, {"substitution"})
    assert schema["properties"]["concept_slugs"]["items"] == {"$ref": "#/$defs/ConceptSlug"}
    assert schema["properties"]["technique_slugs"]["items"] == {"$ref": "#/$defs/TechniqueSlug"}
    assert schema["$defs"]["Skill"]["properties"]["concept_slugs"]["items"] == {
        "$ref": "#/$defs/ConceptSlug"
    }
    assert schema["$defs"]["ConceptSlug"]["enum"] == ["algebra"]
    assert schema["$defs"]["TechniqueSlug"]["enum"] == ["substitution"]
    for model in [schema, *schema["$defs"].values()]:
        if "properties" not in model:
            continue
        assert set(model["required"]) == set(model["properties"])
        assert model["additionalProperties"] is False
        assert all("default" not in field for field in model["properties"].values())


def test_cycle_error_reports_a_real_closed_path():
    from mathbank_rest.db.pedagogy_admin import operator_module

    author = operator_module("author")
    with pytest.raises(ValueError, match=r"a -> b -> c -> a"):
        author.assert_acyclic([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")], "skill")


@pytest.mark.parametrize("corrected", [True, False])
def test_atomic_import_conflict_is_inside_model_correction_budget(monkeypatch, corrected):
    import json
    from types import SimpleNamespace

    from mathbank_rest import tutor
    from mathbank_rest.enrichment import EnrichmentUnavailable, generate_metadata

    calls = []
    imports = []

    def create(**kwargs):
        calls.append([dict(message) for message in kwargs["messages"]])
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(generated())))]
        )

    def persist(result, manifest):
        imports.append(manifest)
        if not corrected or len(imports) == 1:
            raise ValueError("Reviewed skill PREREQUISITE_OF cycle: a -> b -> a")

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options = lambda **kwargs: client
    monkeypatch.setattr(tutor, "_client", client)
    if corrected:
        generate_metadata("FIXTURE", [], {"algebra"}, {"substitution"}, persist)
        assert len(imports) == 2
    else:
        with pytest.raises(EnrichmentUnavailable, match="a -> b -> a"):
            generate_metadata("FIXTURE", [], {"algebra"}, {"substitution"}, persist)
        assert len(imports) == 3
    assert "a -> b -> a" in calls[1][-1]["content"]


@pytest.mark.parametrize("repair_succeeds", [True, False])
def test_model_repairs_invalid_catalog_slugs_with_bounded_feedback(monkeypatch, repair_succeeds):
    import json
    from types import SimpleNamespace

    from mathbank_rest import tutor
    from mathbank_rest.enrichment import EnrichmentUnavailable, generate_metadata

    invalid = generated()
    invalid["concept_slugs"] = ["invented-concept"]
    calls = []

    def create(**kwargs):
        calls.append([dict(message) for message in kwargs["messages"]])
        data = generated() if repair_succeeds and len(calls) > 1 else invalid
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(data)))]
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options = lambda **kwargs: client
    monkeypatch.setattr(tutor, "_client", client)
    if repair_succeeds:
        result, manifest = generate_metadata("FIXTURE", [], {"algebra"}, {"substitution"})
        assert result.concept_slugs == ["algebra"]
        assert manifest["problem_pedagogy"]
        assert len(calls) == 2
    else:
        with pytest.raises(EnrichmentUnavailable, match="three responses"):
            generate_metadata("FIXTURE", [], {"algebra"}, {"substitution"})
        assert len(calls) == 3
    assert "invented-concept" in calls[1][-1]["content"]


def test_automatic_context_is_not_presented_as_human_review(monkeypatch):
    monkeypatch.setattr(pedagogy, "problem_statement", lambda code: {"canonical_code": code})
    responses = iter(
        [
            [
                {
                    "skill": {"slug": "solve", "approval_method": "automatic"},
                    "edge": {"role": "primary", "approval_method": "automatic"},
                    "relation_type": "REQUIRES",
                }
            ],
            [{"label": "Concept", "slug": "algebra", "approval_method": "automatic"}],
            [
                {
                    "properties": {
                        "pedagogy_review_status": "REVIEWED",
                        "conceptual_depth": 2,
                        "pedagogy_approval_method": "automatic",
                    }
                }
            ],
            [],
            [],
        ]
    )
    monkeypatch.setattr(pedagogy, "graph_rows", lambda *args, **kwargs: next(responses))
    result = pedagogy.learning_context("FIXTURE")
    assert result["metadata_status"] == "automatic"
    assert result["difficulty"]["approval_method"] == "automatic"
    assert any("not human-verified" in warning for warning in result["warnings"])


def test_admin_attribute_validation_rejects_unsafe_fields_and_invalid_dimensions():
    from mathbank_rest.db.pedagogy_admin import edit

    key = {"problem_id": "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"}
    for changes in [
        {"approval_method": "human"},
        {"conceptual_depth": 6},
        {"technical_load": True},
        {"confidence": float("nan")},
        {"source": " "},
    ]:
        with pytest.raises(ValueError):
            edit("problem_pedagogy", key, "a" * 64, changes, "Fixture invalid input")
