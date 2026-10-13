from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from mathbank_rest import guided_orientation, pedagogy
from mathbank_rest.main import app

Q31 = {
    "canonical_code": "PRASOLOV_PGV1_CH06_P031",
    "statement_text": "Centers of circumscribed circles of triangles BCD, CDA, DAB, ABC.",
}


def test_orientation_is_statement_gated_and_answer_free():
    session = guided_orientation.orientation(Q31)
    assert session["active_prompt"]["action"] == "ASK_MICRO_CHECK"
    assert session["orientation_count"] == 3
    assert "answer" not in session["active_prompt"]
    assert guided_orientation.orientation({**Q31, "statement_text": "Different text"})["orientation_count"] == 0


def test_wrong_answer_does_not_advance_or_reveal_answer():
    result = guided_orientation.check_orientation(Q31, 0, "CDA")
    assert result["correct"] is False
    assert result["session"]["completed_orientation"] == 0
    assert "center of the circle through" not in result["explanation"]


def test_correct_responses_end_at_student_work_not_a_solution():
    for index, response in enumerate(["BCD", "CD", "$A_1C=A_1D$"]):
        result = guided_orientation.check_orientation(Q31, index, response)
        assert result["correct"] is True
        assert result["session"]["completed_orientation"] == index + 1
    assert result["session"]["active_prompt"]["action"] == "REQUEST_STUDENT_STEP"
    assert "cot" not in str(result)


def test_explicit_nudge_and_invalid_index():
    result = guided_orientation.check_orientation(Q31, 0, "hint")
    assert result["hint"] and result["session"]["completed_orientation"] == 0
    with pytest.raises(ValueError):
        guided_orientation.check_orientation(Q31, 10, "BCD")


def test_micro_check_route_validates_before_graph_or_enrichment(monkeypatch):
    monkeypatch.setattr(pedagogy, "problem_statement", lambda code: Q31)
    client = TestClient(app)
    response = client.post("/v1/tutor/micro-check", json={
        "problem_code": Q31["canonical_code"], "index": 0, "response": "BCD",
    })
    assert response.status_code == 200 and response.json()["correct"]
    assert client.post("/v1/tutor/micro-check", json={
        "problem_code": Q31["canonical_code"], "index": 10, "response": "BCD",
    }).status_code == 422
    for index in (True, 0.5, -1, 21):
        assert client.post("/v1/tutor/micro-check", json={
            "problem_code": Q31["canonical_code"], "index": index, "response": "BCD",
        }).status_code == 422
    assert client.post("/v1/tutor/micro-check", json={
        "problem_code": Q31["canonical_code"], "index": 0, "response": "answer outside choices",
    }).status_code == 422
    assert client.post("/v1/tutor/micro-check", json={
        "problem_code": Q31["canonical_code"], "index": 0, "response": "BCD", "student_id": "untrusted",
    }).status_code == 422


def test_graph_reads_use_driver_managed_retry_transaction(monkeypatch):
    session = MagicMock()
    session.__enter__.return_value = session
    transaction = MagicMock()
    record = MagicMock()
    record.data.return_value = {"value": 1}
    transaction.run.return_value = [record]
    session.execute_read.side_effect = lambda operation: operation(transaction)
    driver = MagicMock()
    driver.session.return_value = session
    monkeypatch.setattr(pedagogy, "driver", driver)
    assert pedagogy.graph_rows("RETURN $value", value=1) == [{"value": 1}]
    transaction.run.assert_called_once_with("RETURN $value", parameters={"value": 1})
    session.run.assert_not_called()


def test_empty_approved_prerequisites_skip_impossible_deeper_traversal(monkeypatch):
    read = MagicMock(return_value=[])
    monkeypatch.setattr(pedagogy, "graph_rows", read)
    assert pedagogy._prerequisites(["fixture"], 4) == ([], [])
    read.assert_called_once()
    assert "*1..4" in read.call_args.args[0]


def test_aime_orientation_is_statement_gated_and_stops_before_product():
    problem = {
        "canonical_code": "AIME_1985_Q01",
        "statement_text": "Let $x_1=97$ and $x_n=n/x_{n-1}$. Find the product.",
    }
    assert guided_orientation.orientation(problem)["orientation_count"] == 2
    first = guided_orientation.check_orientation(problem, 0, "$x_1=97$")
    assert first["correct"] and first["session"]["completed_orientation"] == 1
    result = guided_orientation.check_orientation(problem, 1, "$2/97$")
    assert result["correct"]
    assert result["session"]["active_prompt"]["action"] == "REQUEST_STUDENT_STEP"
    assert guided_orientation.orientation({**problem, "statement_text": "Different recurrence"})["orientation_count"] == 0
