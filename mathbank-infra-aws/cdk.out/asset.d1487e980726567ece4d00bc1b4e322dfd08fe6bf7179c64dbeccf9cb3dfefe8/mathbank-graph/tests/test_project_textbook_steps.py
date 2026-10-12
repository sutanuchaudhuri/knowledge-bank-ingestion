"""Offline tests for the textbook step-graph row builder (no Neo4j/Postgres needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
import project_textbook_steps as pts  # noqa: E402


def fixture():
    step = {"id": "S1", "part_id": "P1", "skill_id": "sk", "concept_id": "c", "subconcept_id": None,
            "step_index_in_part": 1}
    return {
        "packages": [],
        "parts": [{"id": "P1", "solution_id": "sol", "part_ordinal": 1}],
        "steps": [step, dict(step, id="S2", skill_id=None, step_index_in_part=2)],
        "dependencies": [
            {"from_step_id": "S1", "to_step_id": "S2", "relationship_type": "NEXT"},
            {"from_step_id": "S1", "to_step_id": "S2", "relationship_type": "USES_RESULT"},
            {"from_step_id": "S1", "to_step_id": "S2", "relationship_type": "UNKNOWN_KIND"},
        ],
        "subconcepts": [],
        "learning_items": [
            {"id": "L1", "problem_id": "p", "skill_id": "sk", "concept_id": "c", "subconcept_id": "sc"},
            {"id": "L2", "problem_id": "p", "skill_id": None, "concept_id": "c", "subconcept_id": None},
        ],
        "anchors": [],
    }


def test_expected_counts_skip_null_endpoints_and_unknown_edges():
    jobs, expected, keys = pts.build_jobs(fixture())
    assert expected["SolutionPart"] == 1 and expected["SolutionStep"] == 2
    assert expected["HAS_STEP"] == 2
    assert expected["USES_SKILL"] == 1 and expected["USES_CONCEPT"] == 2 and expected["USES_SUBCONCEPT"] == 0
    assert expected["NEXT"] == 1 and expected["USES_RESULT_FROM"] == 1
    assert "UNKNOWN_KIND" not in expected
    assert len(keys) == len(set(keys))


def test_every_write_is_tagged_with_its_own_projection_kind():
    jobs, _, _ = pts.build_jobs(fixture())
    for label, query, _ in jobs:
        if label != "Subconcept":
            assert f"projection_kind = '{pts.KIND}'" in query
            assert "step_text" not in query
    assert pts.KIND != "pedagogy"


def test_learning_items_target_concept_and_subconcept_when_bridged():
    jobs, expected, keys = pts.build_jobs(fixture())
    assert expected["LearningItem"] == 2 and expected["DERIVED_FROM"] == 2
    assert expected["ASSESSES"] == 1
    assert expected["TARGETS_CONCEPT"] == 2 and expected["TARGETS_SUBCONCEPT"] == 1
    assert "TARGETS_CONCEPT|L2|c" in keys and "TARGETS_SUBCONCEPT|L2|None" not in keys
    queries = {label: query for label, query, _ in jobs}
    assert "MATCH (b:Concept {canonical_id: row.concept_id})" in queries["TARGETS_CONCEPT"]
    assert "MATCH (b:Subconcept {canonical_id: row.subconcept_id})" in queries["TARGETS_SUBCONCEPT"]


def test_step_techniques_project_uses_technique_with_provenance():
    data = fixture()
    data["step_techniques"] = [{"solution_step_id": "S1", "technique_id": "t1", "confidence": 0.85,
                                "source_type": "RULE_STEP_TEXT_IN_PROBLEM", "review_status": "APPROVED",
                                "approval_method": "automatic", "derivation_version": "rules-v1"}]
    jobs, expected, keys = pts.build_jobs(data)
    assert expected["USES_TECHNIQUE"] == 1 and "USES_TECHNIQUE|S1|t1" in keys
    query = {label: q for label, q, _ in jobs}["USES_TECHNIQUE"]
    assert "MATCH (b:Technique {canonical_id: row.technique_id})" in query
    assert "r.confidence = row.confidence" in query and "r.source_type = row.source_type" in query
    # Older callers without the key still build (no edges).
    assert pts.build_jobs(fixture())[1]["USES_TECHNIQUE"] == 0
