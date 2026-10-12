from unittest.mock import Mock

from fastapi.testclient import TestClient

from mathbank_rest import guided_orientation, guided_visuals, pedagogy
from mathbank_rest.main import app
from mathbank_rest.routers import pedagogy as routes

PROBLEM = {
    "canonical_code": guided_visuals.Q31,
    "statement_text": (
        "Given a convex quadrilateral ABCD and the centers A1, B1, C1 and D1 of the "
        "circumscribed circles of triangles BCD, CDA, DAB and ABC, respectively. "
        "For quadrilat- eral A1B1C1D1 points A2, B2, C2 and D2 are similarly defined. "
        "Prove the quadrilaterals are similar."
    ),
}


def test_exact_two_level_definitions_are_canonical_not_model_coordinates():
    setup = guided_visuals.circumcenter_setup(PROBLEM)
    assert setup["iterations"] == 2 and len(setup["definitions"]) == 8
    definitions = {item["id"]: item for item in setup["definitions"]}
    assert definitions["A1"]["triangle"] == ["B", "C", "D"]
    assert definitions["B1"]["triangle"] == ["C", "D", "A"]
    assert definitions["C1"]["triangle"] == ["D", "A", "B"]
    assert definitions["D1"]["triangle"] == ["A", "B", "C"]
    assert definitions["A2"]["triangle"] == ["B1", "C1", "D1"]
    assert all(item["provenance"] == "canonical-statement-definition" for item in definitions.values())
    assert "coordinates" not in setup


def test_incomplete_reordered_and_unrelated_statements_fail_closed():
    for statement in [
        "A convex quadrilateral ABCD",
        PROBLEM["statement_text"].replace("BCD, CDA", "CDA, BCD"),
        PROBLEM["statement_text"].replace("A2, B2, C2 and D2", "X2, Y2, Z2 and W2"),
    ]:
        assert guided_visuals.circumcenter_setup({**PROBLEM, "statement_text": statement}) is None
    assert guided_visuals.visual_intent({**PROBLEM, "canonical_code": "UNRELATED"}, 0) is None


def test_current_prompt_controls_required_objects_and_second_level_gate():
    for index, goal in enumerate(["DEFINE_A1", "SHARED_CD", "EQUAL_RADII", "ITERATE_CIRCUMCENTERS"]):
        session = guided_orientation.orientation(PROBLEM, index)
        intent = session["visual_intent"]
        assert intent["current_step"] == goal
        assert intent["max_level"] == (1 if index < 3 else 2)
        assert "similarity-proof" in intent["forbidden_claims"]
    assert {"A1", "triangle_BCD"} <= set(guided_visuals.visual_intent(PROBLEM, 0)["must_show"])


def test_workspace_read_does_not_wait_for_graph_or_enrichment(monkeypatch):
    monkeypatch.setattr(pedagogy, "problem_statement", lambda code: PROBLEM)
    graph = Mock(side_effect=AssertionError("Workspace must not query teaching graph"))
    enrich = Mock(side_effect=AssertionError("Workspace must not enrich"))
    monkeypatch.setattr(pedagogy, "graph_rows", graph)
    monkeypatch.setattr(routes, "ensure_learning_metadata", enrich)
    response = TestClient(app).get(f"/v1/tutor/workspace/{guided_visuals.Q31}")
    assert response.status_code == 200
    data = response.json()
    assert data["problem"] == PROBLEM
    assert data["pedagogy_session"]["visual_intent"]["current_step"] == "DEFINE_A1"
    graph.assert_not_called()
    enrich.assert_not_called()
