"""Teaching contracts with synthetic database/model fixtures, no remote writes."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable

from mathbank_rest import pedagogy, tutor
from mathbank_rest.main import app

client = TestClient(app)
PROBLEM = {"canonical_code": "FIXTURE", "statement_text": "Count a fixed-size subset."}
SKILL = {
    "slug": "select",
    "name": "Select",
    "objective": "Count subsets",
    "source": "fixture-skill",
    "confidence": 0.8,
    "review_status": "REVIEWED",
}
EDGE = {
    "role": "primary",
    "required_level": 2,
    "importance": 1,
    "source": "fixture-mapping",
    "confidence": 0.9,
    "review_status": "REVIEWED",
}


@pytest.mark.parametrize(
    "field,value",
    [
        ("problem_code", " "),
        ("student_attempt", ""),
        ("student_attempt", " " * 5),
        ("diagnosis", "mastered"),
        ("hint_level", 0),
        ("hint_level", 4),
        ("hint_level", True),
        ("hint_level", 1.5),
        ("official_answer", "secret"),
    ],
)
def test_invalid_coaching_rejected_before_external_calls(field, value):
    body = {
        "problem_code": "FIXTURE",
        "diagnosis": "strategy",
        "student_attempt": "I tried choosing a subset.",
        "hint_level": 1,
    }
    body[field] = value
    assert client.post("/v1/tutor/coach", json=body).status_code == 422


def test_unenriched_context_is_explicit_and_answer_free(monkeypatch):
    monkeypatch.setattr(pedagogy, "problem_statement", lambda code: PROBLEM)
    responses = iter(
        [
            [{"skill": None, "edge": None, "relation_type": None}],
            [],
            [
                {
                    "properties": {
                        "official_answer": "secret",
                        "algebraic_load": 5,
                        "pedagogy_review_status": "PENDING",
                    }
                }
            ],
        ]
    )
    monkeypatch.setattr(pedagogy, "graph_rows", lambda *args, **kwargs: next(responses))
    result = pedagogy.learning_context("FIXTURE")
    assert result["metadata_status"] == "unenriched"
    assert not result["skills"] and not result["prerequisites"]
    assert result["difficulty"]["algebraic_load"] is None
    assert "secret" not in str(result)
    assert len(result["diagnostic_options"]) == 5
    assert result["warnings"]


def test_reviewed_context_keeps_node_mapping_and_path_provenance(monkeypatch):
    monkeypatch.setattr(pedagogy, "problem_statement", lambda code: PROBLEM)
    responses = iter(
        [
            [{"skill": SKILL, "edge": EDGE, "relation_type": "REQUIRES"}],
            [],
            [
                {
                    "properties": {
                        "conceptual_depth": 2,
                        "pedagogy_review_status": "REVIEWED",
                        "pedagogy_source": "fixture-assessment",
                        "pedagogy_confidence": 0.7,
                    }
                }
            ],
            [
                {
                    "skill": {**SKILL, "slug": "prior"},
                    "depth": 1,
                    "required_for": ["select"],
                    "evidence": [
                        {
                            "from_slug": "prior",
                            "to_slug": "select",
                            "source": "fixture-prerequisite",
                            "review_status": "REVIEWED",
                        }
                    ],
                }
            ],
            [],
        ]
    )
    calls = []

    def graph(query, **params):
        calls.append(query)
        return next(responses)

    monkeypatch.setattr(pedagogy, "graph_rows", graph)
    result = pedagogy.learning_context("FIXTURE")
    assert result["metadata_status"] == "reviewed"
    assert result["skills"][0]["source"] == "fixture-mapping"
    assert result["skills"][0]["skill_source"] == "fixture-skill"
    assert result["prerequisites"][0]["evidence"][0]["source"] == "fixture-prerequisite"
    assert result["difficulty"]["source"] == "fixture-assessment"
    assert "r.review_status = 'REVIEWED'" in calls[0]
    assert "all(n IN nodes(path)" in calls[3]
    assert "all(r IN relationships(path)" in calls[3]
    assert len(calls) == 5


def test_prerequisite_boundary_and_row_limit_are_reported(monkeypatch):
    row = {"skill": SKILL, "depth": 2, "required_for": ["select"], "evidence": []}
    responses = iter([[{"skill": SKILL}], [row] * 101, [{"found": 1}]])
    monkeypatch.setattr(pedagogy, "graph_rows", lambda *a, **kw: next(responses))
    result = pedagogy.prerequisite_path("select", 2)
    assert len(result["prerequisites"]) == 100 and result["truncated"]
    assert len(result["warnings"]) == 2


def test_practice_evidence_is_not_overall_difficulty(monkeypatch):
    monkeypatch.setattr(pedagogy, "problem_statement", lambda code: PROBLEM)
    graph = MagicMock(return_value=[{"canonical_code": "LOWER", "evidence": [EDGE]}] * 3)
    monkeypatch.setattr(pedagogy, "graph_rows", graph)
    result = pedagogy.easier_practice("FIXTURE", 2)
    query = graph.call_args.args[0]
    assert "b.required_level < a.required_level" in query
    assert "type(a) = type(b) AND a.role = b.role" in query
    assert result["truncated"] and len(result["results"]) == 2
    assert "overall" in result["warnings"][0]


def test_statement_sql_does_not_select_solutions_or_answer(monkeypatch):
    connection = MagicMock()
    connection.execute.return_value.mappings.return_value.first.return_value = PROBLEM
    fake_engine = MagicMock()
    fake_engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(pedagogy, "engine", fake_engine)
    assert pedagogy.problem_statement("FIXTURE") == PROBLEM
    query = str(connection.execute.call_args.args[0])
    assert "solution" not in query and "official_answer" not in query
    assert connection.execute.call_args.args[1] == {"code": "FIXTURE"}


def test_generated_coaching_is_pending_and_prompt_has_no_solution(monkeypatch):
    monkeypatch.setattr(
        pedagogy,
        "learning_context",
        lambda code: {
            "problem": PROBLEM,
            "skills": [],
            "prerequisites": [],
            "warnings": ["Unenriched"],
        },
    )
    create = MagicMock(
        return_value=SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"micro_lesson":"Order distinguishes arrangements.",'
                        '"hint":"Compare two choices.","return_prompt":"Try again."}'
                    )
                )
            ]
        )
    )
    monkeypatch.setattr(tutor._client.chat.completions, "create", create)
    monkeypatch.setattr(tutor._client, "with_options", lambda **kwargs: tutor._client)
    result = pedagogy.coach(
        pedagogy.CoachRequest(
            problem_code="FIXTURE",
            diagnosis="strategy",
            student_attempt="I counted orders.",
        )
    )
    assert result["provenance"]["review_status"] == "PENDING"
    assert result["hint_level"] == 1 and result["diagnostic_question"]
    assert "official_answer" not in str(create.call_args)
    assert "solution" not in create.call_args.kwargs["messages"][1]["content"]
    assert "Unenriched" in result["warnings"]


@pytest.mark.parametrize(
    "choices",
    [
        [],
        [SimpleNamespace(message=SimpleNamespace(content=None))],
        [SimpleNamespace(message=SimpleNamespace(content='{"hint":"incomplete"}'))],
        [SimpleNamespace(message=SimpleNamespace(content="not json"))],
    ],
)
def test_invalid_model_output_is_explicit_failure(monkeypatch, choices):
    monkeypatch.setattr(
        pedagogy,
        "learning_context",
        lambda code: {
            "problem": PROBLEM,
            "skills": [],
            "prerequisites": [],
            "warnings": [],
        },
    )
    monkeypatch.setattr(
        tutor._client.chat.completions, "create", lambda **kwargs: SimpleNamespace(choices=choices)
    )
    monkeypatch.setattr(tutor._client, "with_options", lambda **kwargs: tutor._client)
    with pytest.raises(pedagogy.CoachingUnavailable):
        pedagogy.coach(
            pedagogy.CoachRequest(
                problem_code="FIXTURE",
                diagnosis="concept",
                student_attempt="A subset.",
            )
        )


@pytest.mark.parametrize(
    "error,status",
    [
        (pedagogy.UnknownLearningEntity("Missing"), 404),
        (ServiceUnavailable("Offline"), 503),
    ],
)
def test_read_errors_are_not_success_shaped(monkeypatch, error, status):
    def fail(code):
        raise error

    monkeypatch.setattr(pedagogy, "learning_context", fail)
    assert client.get("/v1/tutor/learning-context/FIXTURE").status_code == status


@pytest.mark.parametrize(
    "url",
    [
        "/v1/tutor/prerequisites/select?max_depth=9",
        "/v1/tutor/prerequisites/select?max_depth=0",
        "/v1/tutor/practice/FIXTURE?limit=21",
        "/v1/tutor/practice/FIXTURE?limit=0",
    ],
)
def test_query_bounds(url):
    assert client.get(url).status_code == 422


def test_refusal_returns_502(monkeypatch):
    def fail(body):
        raise pedagogy.CoachingUnavailable("Refused")

    monkeypatch.setattr(pedagogy, "coach", fail)
    response = client.post(
        "/v1/tutor/coach",
        json={
            "problem_code": "FIXTURE",
            "diagnosis": "concept",
            "student_attempt": "A subset.",
        },
    )
    assert response.status_code == 502 and response.json()["detail"] == "Refused"
