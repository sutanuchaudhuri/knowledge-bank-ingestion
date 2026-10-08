import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from mathbank_rest import pedagogy, tutor
from mathbank_rest import solution_guidance as guidance
from mathbank_rest.main import app

AIME = {
    "canonical_code": "AIME_1985_Q01",
    "statement_text": (
        r"Let $x_1=97$, and for $n>1$, let $x_n=\frac{n}{x_{n-1}}$. "
        r"Calculate the product $x_1x_2x_3x_4x_5x_6x_7x_8$."
    ),
}
PENTAGON = {
    "canonical_code": "PAPER_HMMT_2018_NOV_GUTS_Q08",
    "statement_text": (
        "Pentagon JAMES is such that AM = SJ and the internal angles satisfy "
        "∠ J = ∠ A = ∠ E = 90 ◦ , and ∠ M = ∠ S . Given that there exists a "
        "diagonal of JAMES that bisects its area, find the ratio of the shortest "
        "side of JAMES to the longest side of JAMES."
    ),
}


def evidence(problem=None, references=None):
    return guidance.SolutionEvidence(
        problem or AIME,
        references
        if references is not None
        else [
            {
                "solution_id": "pair",
                "solution_kind": "AOPS_COMMUNITY",
                "revision": 1,
                "verification_status": "UNVERIFIED",
                "excerpted": False,
                "body_markdown": r"$x_n \cdot x_{n - 1} = n$. PRIVATE_SOLUTION_TEXT \boxed{384}",
            },
            {
                "solution_id": "cancel",
                "solution_kind": "AOPS_COMMUNITY",
                "revision": 2,
                "verification_status": "UNVERIFIED",
                "excerpted": False,
                "body_markdown": "An alternative cancellation route. PRIVATE_SECOND_SOLUTION",
            },
        ],
        "384",
        2,
    )


def test_aime_plan_is_source_and_statement_gated_without_provider_calls(monkeypatch):
    monkeypatch.setattr(guidance, "load_references", lambda code: evidence())
    create = MagicMock(side_effect=AssertionError("Authored plan must not call a provider"))
    monkeypatch.setattr(tutor._client.chat.completions, "create", create)
    result = guidance.guidance_plan("AIME_1985_Q01")
    assert result["selected_solution_id"] == "pair"
    assert result["solution_evidence"]["references_considered"] == 2
    assert len(result["stages"]) == 4
    assert "neighboring" in result["rationale"]
    assert "multiplying" in result["first_checkpoint"]
    assert "384" not in json.dumps(result) and "PRIVATE" not in json.dumps(result)
    assert result["solution_evidence"]["sources"][0]["verification_status"] == "UNVERIFIED"
    assert "certified" in result["warnings"][0]


def test_pentagon_opening_is_source_gated_and_withholds_intermediate_and_final_answers(monkeypatch):
    record = evidence(PENTAGON)
    record.references[0]["body_markdown"] = (
        "JAMS must be a rectangle. The only diagonal that can bisect the pentagon "
        "is MS. PRIVATE_SOLUTION_TEXT"
    )
    monkeypatch.setattr(guidance, "load_references", lambda code: record)
    monkeypatch.setattr(
        tutor._client,
        "with_options",
        lambda **kwargs: pytest.fail("Source-gated opening must not call the model"),
    )
    result = guidance.guidance_plan(PENTAGON["canonical_code"])
    assert result["provenance"]["source"] == "authored-source-gated"
    assert "five-sided polygon" in result["first_checkpoint"]
    text = json.dumps(result)
    assert "PRIVATE" not in text and "rectangle" not in text and "135" not in text
    assert "1/4" not in text and "is MS" not in text


@pytest.mark.parametrize("changed", ["statement", "reference"])
def test_pentagon_authored_opening_does_not_apply_to_mismatched_evidence(changed):
    record = evidence(PENTAGON)
    record.references[0]["body_markdown"] = (
        "JAMS must be a rectangle. The only diagonal that can bisect the pentagon is MS."
    )
    if changed == "statement":
        record.problem = {**PENTAGON, "statement_text": "A different pentagon problem."}
    else:
        record.references[0]["body_markdown"] = "Unrelated or incomplete solution."
    assert guidance._authored_plan(record) is None


def test_reference_query_is_bounded_and_does_not_emit_solution_text(monkeypatch):
    rows = [
        {
            **AIME,
            "official_answer": "384",
            "solution_id": "id",
            "solution_kind": "CURATED",
            "revision": 2,
            "verification_status": "UNVERIFIED",
            "body_markdown": "PRIVATE" * 3000,
            "total_records": 9,
        }
    ]
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.all.return_value = rows
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(guidance, "engine", engine)
    result = guidance.load_references("AIME_1985_Q01")
    assert connection.execute.call_args.args[1] == {"code": "AIME_1985_Q01", "limit": 6}
    assert len(result.references[0]["body_markdown"]) == guidance.TEXT_LIMIT
    assert result.references[0]["excerpted"]
    assert "PRIVATE" not in json.dumps(result.summary())
    assert len(result.warnings()) == 3


def test_missing_solutions_are_explicit_without_a_fake_grounded_plan(monkeypatch):
    monkeypatch.setattr(guidance, "load_references", lambda code: evidence(references=[]))
    result = guidance.guidance_plan("AIME_1985_Q01")
    assert result["status"] == "unavailable"
    assert "stages" not in result and result["warnings"]


@pytest.mark.parametrize(
    "bad", ["answer", "unknown_reference", "invalid_json", "refusal", "mismatched_statement"]
)
def test_generated_plan_checks_selected_reference_refusal_and_answer_withholding(monkeypatch, bad):
    record = evidence({**AIME, "canonical_code": "OTHER"})
    if bad == "mismatched_statement":
        record.problem = {**AIME, "statement_text": "This is a different recurrence."}
    monkeypatch.setattr(guidance, "load_references", lambda code: record)
    payload = {
        "selected_solution_id": "pair",
        "rationale": "Compare neighboring terms.",
        "stages": ["Read", "Explore", "Check"],
        "first_checkpoint": "Write a product.",
    }
    if bad == "answer":
        payload["first_checkpoint"] = r"The product is $\boxed{384}$."
    if bad == "unknown_reference":
        payload["selected_solution_id"] = "invented"
    content = None if bad == "refusal" else "bad" if bad == "invalid_json" else json.dumps(payload)
    create = MagicMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
    )
    monkeypatch.setattr(tutor._client, "with_options", lambda **kwargs: tutor._client)
    monkeypatch.setattr(tutor._client.chat.completions, "create", create)
    if bad == "mismatched_statement":
        assert guidance.guidance_plan("AIME_1985_Q01")["provenance"]["source"].startswith(
            "generated:"
        )
    else:
        with pytest.raises(pedagogy.CoachingUnavailable):
            guidance.guidance_plan("OTHER")
    sent = json.loads(create.call_args.kwargs["messages"][1]["content"])
    assert len(sent["solution_references"]) == 2
    assert "official_answer" not in sent


def test_plan_endpoint_does_not_load_graph_or_enrich_and_rejects_extra_fields(monkeypatch):
    monkeypatch.setattr(guidance, "load_references", lambda code: evidence())
    client = TestClient(app)
    result = client.post("/v1/tutor/guidance-plan", json={"problem_code": "AIME_1985_Q01"})
    assert result.status_code == 200 and result.json()["status"] == "ready"
    assert "PRIVATE" not in result.text and "384" not in result.text
    assert (
        client.post(
            "/v1/tutor/guidance-plan", json={"problem_code": " ", "solution": "spoiler"}
        ).status_code
        == 422
    )
