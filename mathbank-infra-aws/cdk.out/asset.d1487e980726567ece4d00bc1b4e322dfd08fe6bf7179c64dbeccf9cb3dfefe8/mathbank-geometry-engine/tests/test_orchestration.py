import json
from pathlib import Path

import pytest

from geometry_scene.errors import GeometryError
from geometry_scene.orchestration import (
    GeometryPlan,
    GeometryRequest,
    OrchestrationFailure,
    orchestrate,
    validate_evidence,
)
from geometry_scene.schemas import Relation, SceneInput, VisualDelta
from geometry_scene.service import create_scene
from geometry_scene.theorems import establish, lookup

ROOT = Path(__file__).resolve().parents[1]


class ScriptedProvider:
    model = "test-script-not-model-acceptance"

    def __init__(self, responses):
        self.responses = iter(responses)
        self.records = []

    def complete(self, role, payload, output_type, timeout):
        self.records.append({"role": role, "timeout": timeout})
        value = next(self.responses)
        return output_type.model_validate(value)


def setup():
    source = "ABCD is a convex quadrilateral. A1 is the circumcenter of BCD."
    request = GeometryRequest(problem_text=source, goal="Help understand A1")
    initial = {
        "problem_text": source,
        "objects": {p: {} for p in ["A", "B", "C", "D", "A1"]},
        "relations": [
            {
                "id": "quad",
                "type": "QUADRILATERAL",
                "args": ["A", "B", "C", "D"],
                "status": "GIVEN",
            },
            {
                "id": "center",
                "type": "CIRCUMCENTER",
                "args": ["A1", "B", "C", "D"],
                "status": "GIVEN",
            },
        ],
    }
    plan = {
        "initial": initial,
        "evidence": [
            {"relation_id": "quad", "source_quote": "ABCD is a convex quadrilateral."},
            {"relation_id": "center", "source_quote": "A1 is the circumcenter of BCD."},
        ],
    }
    return request, plan


def test_roles_and_required_a1_semantics():
    request, plan = setup()
    provider = ScriptedProvider(
        [plan, {"highlight": ["triangle_BCD", "point_A1"]}, {"accept": True}]
    )
    frame, evidence = orchestrate(request, provider)
    assert frame.validation.valid
    assert {"point_A1", "triangle_BCD", "quadrilateral_ABCD"} <= frame.scene_state.entities.keys()
    assert [r["role"] for r in provider.records] == ["reasoning", "presentation", "review"]
    assert evidence["status"] == "ACCEPTED" and evidence["calls"] == 3


def test_wrong_triangle_revised_before_acceptance():
    request, plan = setup()
    bad = json.loads(json.dumps(plan))
    bad["initial"]["relations"][1]["args"] = ["A1", "A", "B", "C"]
    provider = ScriptedProvider([bad, {}, plan, {}, {"accept": True}])
    frame, evidence = orchestrate(request, provider)
    assert "triangle_BCD" in frame.scene_state.entities
    assert len(evidence["attempts"]) == 2
    assert evidence["attempts"][0]["status"] == "FAILED"


def test_unproved_relation_cannot_be_promoted_by_quote():
    request, plan = setup()
    plan["initial"]["relations"][1]["status"] = "PROVEN"
    with pytest.raises(GeometryError, match="cannot authorize PROVEN"):
        validate_evidence(request, GeometryPlan.model_validate(plan), None)


def test_model_cannot_declare_a_disproof_from_its_own_prose():
    request, plan = setup()
    plan["initial"]["relations"][1]["status"] = "DISPROVEN"
    with pytest.raises(GeometryError, match="cannot authorize DISPROVEN"):
        validate_evidence(request, GeometryPlan.model_validate(plan), None)


def test_given_cannot_be_demoted_to_escape_its_constraints():
    from geometry_scene.schemas import StateDelta
    from geometry_scene.service import apply_delta

    _request, plan = setup()
    frame = create_scene(SceneInput.model_validate(plan["initial"]))
    with pytest.raises(GeometryError, match="cannot change a supplied given"):
        apply_delta(
            frame,
            StateDelta(
                expected_version=0,
                change_status=[
                    {
                        "relation_id": "quad",
                        "status": "UNKNOWN",
                        "provenance": "Model changed its mind",
                    }
                ],
            ),
        )


def test_review_rejection_exhausts_budget_and_keeps_evidence():
    request, plan = setup()
    provider = ScriptedProvider(
        [plan, {}, {"accept": False, "reasons": ["Wrong pedagogical focus"]}]
    )
    with pytest.raises(OrchestrationFailure) as caught:
        orchestrate(request, provider, max_attempts=1, max_calls=3)
    assert caught.value.evidence["status"] == "FAILED"
    assert caught.value.evidence["attempts"][0]["candidate"]["validation"]["valid"]
    assert caught.value.evidence["calls"] == 3


def test_presentation_truth_mutation_is_rejected():
    with pytest.raises(ValueError):
        VisualDelta.model_validate({"add_relations": []})


def test_stale_or_missing_base_fails_before_paid_calls():
    request, _plan = setup()
    provider = ScriptedProvider([])
    with pytest.raises(GeometryError, match="missing accepted"):
        orchestrate(
            request.model_copy(update={"scene_id": "scene_x", "expected_version": 0}), provider
        )
    assert provider.records == []


def test_source_evidence_must_be_exact():
    request, plan = setup()
    plan["evidence"][0]["source_quote"] = "ABCD is cyclic."
    with pytest.raises(GeometryError, match="not grounded"):
        validate_evidence(request, GeometryPlan.model_validate(plan), None)


@pytest.mark.parametrize("status", ["GIVEN", "ASSUMED_FOR_CONSTRUCTION"])
def test_initial_goal_cannot_become_authoritative_fact(status):
    request = GeometryRequest(
        problem_text="Prove A, B, C are collinear.", goal="Explain the problem"
    )
    plan = GeometryPlan(
        initial={
            "problem_text": request.problem_text,
            "objects": {p: {} for p in "ABC"},
            "relations": [
                {"id": "target", "type": "COLLINEAR", "args": ["A", "B", "C"], "status": status}
            ],
        },
        evidence=[{"relation_id": "target", "source_quote": request.problem_text}],
    )
    with pytest.raises(GeometryError, match="not a given|cannot become"):
        validate_evidence(request, plan, None)


def test_theorem_prerequisites_are_mathematical_not_prose():
    document = json.loads((ROOT / "fixtures/03_tangent_contact.json").read_text())
    frame = create_scene(SceneInput.model_validate(document["initial"]))
    conclusion = Relation(
        id="perp", type="PERPENDICULAR", args=("O", "T", "P", "T"), status="PROVEN"
    )
    establish(
        "tangent_radius",
        conclusion,
        frame.math_state.relations,
        frame.math_state.objects,
        ["tangent"],
    )
    with pytest.raises(GeometryError, match="does not justify"):
        establish(
            "tangent_radius",
            conclusion.model_copy(update={"args": ("O", "P", "P", "T")}),
            frame.math_state.relations,
            frame.math_state.objects,
            ["tangent"],
        )
    assert lookup()["snapshot"] == "geometry-theorems-v1"
    with pytest.raises(GeometryError, match="unknown theorem"):
        lookup("invented")


def test_failed_candidate_preserves_previous_state():
    request, plan = setup()
    previous = create_scene(SceneInput.model_validate(plan["initial"]))
    before = previous.model_dump_json()
    req = request.model_copy(
        update={"scene_id": previous.scene_state.scene_id, "expected_version": 0}
    )
    bad = {
        "delta": {"expected_version": 0, "visual": {}},
        "required_entities": ["point_nonexistent"],
    }
    provider = ScriptedProvider([bad, {}])
    with pytest.raises(OrchestrationFailure):
        orchestrate(req, provider, previous, max_attempts=1)
    assert previous.model_dump_json() == before
