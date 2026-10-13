"""requirements/53: AI-generated quiz subsystem tests.

Unit tests cover pure logic (validation, MCQ grading, schema shape) with a mocked OpenAI
client for determinism and zero API cost. One opt-in live test
(MATHBANK_LIVE_QUIZ_TEST=1) exercises the full real flow against Postgres + a mocked LLM
client, with explicit cleanup (quiz_runtime's functions open their own connections, so this
cannot use a single outer rollback transaction the way step_runtime's live tests do).
"""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_rest import quiz_runtime
from mathbank_rest.db.postgres import engine
from mathbank_rest.main import app

client = TestClient(app)
live = pytest.mark.skipif(os.getenv("MATHBANK_LIVE_QUIZ_TEST") != "1", reason="Live Postgres opt-in")


# --------------------------------------------------------------------------- pure/unit

def test_generate_rejects_unknown_style():
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.generate_quiz(
            uuid4(), style="NOT_A_STYLE", question_count=3, question_types=["MCQ"],
        )
    assert exc.value.code == "INVALID_STYLE"


def test_generate_rejects_bad_question_count():
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.generate_quiz(
            uuid4(), style="AIME", question_count=0, question_types=["MCQ"],
        )
    assert exc.value.code == "INVALID_QUESTION_COUNT"


def test_generate_rejects_bad_question_type():
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.generate_quiz(
            uuid4(), style="AIME", question_count=3, question_types=["ESSAY"],
        )
    assert exc.value.code == "INVALID_QUESTION_TYPE"


def test_sanitize_point_id_handles_bad_llm_output():
    assert quiz_runtime._sanitize_point_id("A", "P0") == "A"
    assert quiz_runtime._sanitize_point_id("1x", "P0") == "P1x"
    assert quiz_runtime._sanitize_point_id("", "P0") == "P0"
    assert quiz_runtime._sanitize_point_id("point A!", "P0") == "pointA"


def test_routes_require_auth():
    qid = "00000000-0000-0000-0000-000000000000"
    assert client.post("/v1/quiz/generate", json={"style": "AIME"}).status_code == 401
    assert client.get(f"/v1/quiz/{qid}").status_code == 401
    assert client.get("/v1/quiz/mine").status_code == 401
    assert client.get(f"/v1/quiz/{qid}/review").status_code == 401
    assert client.post(f"/v1/quiz/{qid}/questions/{qid}/respond", json={}).status_code == 401


# --------------------------------------------------------------------------- live flow

def _fake_mcq_choice(content: dict):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(content)))])


@pytest.fixture
def mock_llm(monkeypatch):
    """Deterministic, zero-cost stand-in for every chat.completions.create call this
    module makes (generation, diagram planning, free-text grading)."""
    calls: list[dict] = []

    def create(*, messages, response_format, **_kwargs):
        schema_name = response_format["json_schema"]["name"]
        calls.append({"schema": schema_name, "messages": messages})
        if schema_name == "quiz_question":
            if "MCQ" in messages[0]["content"]:
                content = {
                    "prompt_text": "What is 2+2?", "prompt_latex": None,
                    "options": [{"key": "A", "text": "3"}, {"key": "B", "text": "4"},
                               {"key": "C", "text": "5"}, {"key": "D", "text": "6"}],
                    "correct_answer_key": "B", "expected_answer": None,
                    "grading_rubric": None, "solution_text": "2+2=4 by direct addition.",
                    "key_insight": "Basic arithmetic.",
                }
            else:
                content = {
                    "prompt_text": "Prove that the sum of two even integers is even.",
                    "prompt_latex": None, "options": None, "correct_answer_key": None,
                    "expected_answer": None,
                    "grading_rubric": "Must express both integers as 2k forms and show the sum is 2(k1+k2).",
                    "solution_text": "Let a=2m, b=2n. Then a+b=2(m+n), which is even.",
                    "key_insight": "Even numbers are exactly the multiples of 2.",
                }
        elif schema_name == "diagram_plan":
            content = {"needs_diagram": False, "title": "", "elements": []}
        elif schema_name == "grading_result":
            content = {"is_correct": True, "confidence": 0.9, "feedback": "Well reasoned."}
        else:
            raise AssertionError(f"unexpected schema {schema_name}")
        return _fake_mcq_choice(content)

    fake_client = MagicMock()
    fake_client.with_options.return_value = fake_client
    fake_client.chat.completions.create.side_effect = create
    monkeypatch.setattr(quiz_runtime, "_client", lambda: fake_client)
    monkeypatch.setattr(
        "mathbank_rest.db.hybrid_search.search_problems",
        lambda *a, **k: {"results": [], "warnings": [], "retrieval": {}},
    )
    return calls


@pytest.fixture
def live_student():
    with engine.begin() as conn:
        student_id = conn.execute(
            text("INSERT INTO learner.student_profile (email, password_hash, first_name, "
                 "last_name, display_name) VALUES (:e, 'x', 'Quiz', 'Test', 'Quiz Test') "
                 "RETURNING student_id"),
            {"e": f"quiz-live-{uuid4()}@example.com"},
        ).scalar_one()
    try:
        yield student_id
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM quiz.response WHERE student_id=:s"), {"s": str(student_id)})
            conn.execute(text("DELETE FROM quiz.question WHERE quiz_id IN "
                              "(SELECT quiz_id FROM quiz.paper WHERE student_id=:s)"),
                        {"s": str(student_id)})
            conn.execute(text("DELETE FROM quiz.paper WHERE student_id=:s"), {"s": str(student_id)})
            conn.execute(text("DELETE FROM learner.concept_mastery WHERE student_id=:s"), {"s": str(student_id)})
            conn.execute(text("DELETE FROM learner.technique_mastery WHERE student_id=:s"), {"s": str(student_id)})
            conn.execute(text("DELETE FROM learner.student_profile WHERE student_id=:s"), {"s": str(student_id)})


@live
def test_live_generate_respond_grade_mastery_absorption(mock_llm, live_student):
    student_id = live_student
    paper = quiz_runtime.generate_quiz(
        student_id, style="MIXED", question_count=2,
        question_types=["MCQ", "FREE_TEXT"],
    )
    assert paper["status"] == "READY"
    assert len(paper["questions"]) == 2
    mcq_q = next(q for q in paper["questions"] if q["question_type"] == "MCQ")
    free_q = next(q for q in paper["questions"] if q["question_type"] == "FREE_TEXT")
    assert mcq_q["options"] is not None and len(mcq_q["options"]) == 4
    assert free_q["options"] is None
    # solutions must not leak before any response exists
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT question_id FROM quiz.question WHERE quiz_id=:q"),
                            {"q": paper["quiz_id"]}).scalars().all()
    assert len(rows) == 2

    # MCQ: deterministic exact-match grading, correct answer
    result = quiz_runtime.submit_response(
        paper["quiz_id"], mcq_q["question_id"], student_id,
        raw_response={"selected_key": "B"},
    )
    assert result["is_correct"] is True
    assert result["grading_method"] == "EXACT_MATCH"
    assert result["solution"] is not None

    # Duplicate submission to the same question is rejected
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.submit_response(
            paper["quiz_id"], mcq_q["question_id"], student_id,
            raw_response={"selected_key": "A"},
        )
    assert exc.value.code == "ALREADY_ANSWERED"

    # FREE_TEXT: LLM-graded via the mocked client
    result2 = quiz_runtime.submit_response(
        paper["quiz_id"], free_q["question_id"], student_id,
        raw_response={"response_text": "a=2m, b=2n, a+b=2(m+n)"},
    )
    assert result2["grading_method"] == "LLM_GRADED"
    assert result2["is_correct"] is True

    review = quiz_runtime.get_review(paper["quiz_id"], student_id)
    assert review["answered_count"] == 2
    assert review["score"] == 2

    with engine.connect() as conn:
        paper_status = conn.execute(
            text("SELECT status FROM quiz.paper WHERE quiz_id=:q"), {"q": paper["quiz_id"]}
        ).scalar_one()
    assert paper_status == "GRADED"


@live
def test_live_mastery_blends_quiz_and_real_attempts(mock_llm, live_student):
    student_id = live_student
    with engine.connect() as conn:
        concept = conn.execute(text("SELECT concept_id FROM knowledge.concept LIMIT 1")).first()
    if concept is None:
        pytest.skip("no concept rows available in this environment")
    concept_id = str(concept[0])

    quiz_runtime.generate_quiz(
        student_id, style="TOPIC_BASED", question_count=1, question_types=["MCQ"],
    )
    with engine.connect() as conn:
        question_id, quiz_id = conn.execute(
            text("SELECT q.question_id, q.quiz_id FROM quiz.question q JOIN quiz.paper p USING(quiz_id) "
                 "WHERE p.student_id=:s ORDER BY q.created_at DESC LIMIT 1"),
            {"s": str(student_id)},
        ).one()
    # Force-tag this question to our known concept so mastery fan-out is observable.
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO quiz.question_concept (question_id, concept_id) "
                 "VALUES (:q, :c) ON CONFLICT DO NOTHING"),
            {"q": str(question_id), "c": concept_id},
        )
    quiz_runtime.submit_response(
        quiz_id, question_id, student_id, raw_response={"selected_key": "Z"},
    )
    with engine.connect() as conn:
        score = conn.execute(
            text("SELECT mastery_score, attempts_count FROM learner.concept_mastery "
                 "WHERE student_id=:s AND concept_id=:c"),
            {"s": str(student_id), "c": concept_id},
        ).mappings().first()
    assert score is not None
    assert score["attempts_count"] == 1


# --------------------------------------------------------------------------- requirements/64:
# mathbank-exam-agent integration (import, exam-mode gate, submit, diagnosis)

def _sample_import_question(ordinal: int) -> dict:
    return {
        "question_type": "MCQ",
        "prompt_text": f"Sample question {ordinal}: what is 3+3?",
        "prompt_latex": None,
        "options": [{"key": "A", "text": "5"}, {"key": "B", "text": "6"},
                   {"key": "C", "text": "7"}, {"key": "D", "text": "8"}],
        "correct_answer": {"correct_key": "B"},
        "solution_text": "3+3=6 by direct addition.",
        "key_insight": "Basic arithmetic.",
        "difficulty_band": "easy",
        "revision_log": [{"round": 1, "verdict": "APPROVE", "feedback": "Clear and correct."}],
        "concept_slugs": [], "technique_slugs": [], "skill_slugs": [],
    }


def test_import_paper_rejects_unknown_style():
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.import_paper(
            uuid4(), style="NOT_A_STYLE", title="t", requested_question_count=1,
            requested_question_types=["MCQ"], generated_by="test", questions=[_sample_import_question(1)],
        )
    assert exc.value.code == "INVALID_STYLE"


def test_import_paper_rejects_no_questions():
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.import_paper(
            uuid4(), style="AIME", title="t", requested_question_count=1,
            requested_question_types=["MCQ"], generated_by="test", questions=[],
        )
    assert exc.value.code == "NO_QUESTIONS"


def test_exam_integration_routes_require_admin_key():
    qid = "00000000-0000-0000-0000-000000000000"
    assert client.post("/v1/quiz-integration/papers", json={}).status_code == 401
    assert client.post(f"/v1/quiz-integration/papers/{qid}/submit",
                       params={"student_id": qid}).status_code == 401
    assert client.get(f"/v1/quiz-integration/papers/{qid}/diagnosis",
                      params={"student_id": qid}).status_code == 401


@live
def test_live_import_exam_mode_gate_submit_and_diagnosis(live_student):
    student_id = live_student
    paper = quiz_runtime.import_paper(
        student_id, style="MIXED", title="Mock Exam — Bedrock Generated",
        requested_question_count=2, requested_question_types=["MCQ"],
        generated_by="bedrock:anthropic.claude-3-5-haiku", exam_mode=True,
        time_limit_seconds=5400,
        questions=[_sample_import_question(1), _sample_import_question(2)],
    )
    assert paper["status"] == "READY"
    assert len(paper["questions"]) == 2

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT exam_mode, time_limit_seconds, agent_framework FROM quiz.paper WHERE quiz_id=:q"),
            {"q": paper["quiz_id"]},
        ).mappings().one()
    assert row["exam_mode"] is True
    assert row["time_limit_seconds"] == 5400
    assert row["agent_framework"] == "STRANDS_BEDROCK"

    question_ids = [q["question_id"] for q in paper["questions"]]

    # Exam-mode gate: review is rejected while the paper is still in progress, even
    # though requirements/53's own practice-mode flow would allow it as soon as any
    # response exists (requirements/64 §6).
    quiz_runtime.submit_response(
        paper["quiz_id"], question_ids[0], student_id, raw_response={"selected_key": "B"},
        time_spent_seconds=45,
    )
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.get_review(paper["quiz_id"], student_id)
    assert exc.value.code == "EXAM_IN_PROGRESS"

    # Explicit submission (e.g. a time-limit auto-submit) with one question left blank —
    # review must still succeed and transition to GRADED, unlike the "every question
    # answered" trigger requirements/53's practice flow relies on.
    submitted = quiz_runtime.submit_exam(paper["quiz_id"], student_id)
    assert submitted["answered_count"] == 1
    assert submitted["score"] == 1
    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM quiz.paper WHERE quiz_id=:q"), {"q": paper["quiz_id"]}
        ).scalar_one()
    assert status == "GRADED"

    # Diagnosis input assembly — pre-exam mastery + per-question timing/difficulty.
    diagnosis_input = quiz_runtime.get_paper_for_diagnosis(paper["quiz_id"], student_id)
    assert len(diagnosis_input["questions"]) == 2
    answered_q = next(q for q in diagnosis_input["questions"] if q["time_spent_seconds"] == 45)
    assert answered_q["is_correct"] is True
    assert answered_q["difficulty_band"] == "easy"

    # Writing and reading the diagnosis report.
    written = quiz_runtime.write_diagnosis(
        paper["quiz_id"], student_id,
        time_management_verdict="Well-paced on the answered question; one left blank at time-up.",
        pacing_notes=[{"question_ordinal": 1, "time_spent_seconds": 45, "difficulty_band": "easy"}],
        reasoning_guidance=[], improvement_areas=[{"concept_or_technique": "arithmetic",
                                                    "current_mastery_tier": "DEVELOPING",
                                                    "evidence": "answered correctly, no gap evidence yet"}],
        generated_by="bedrock:anthropic.claude-3-5-haiku",
    )
    assert written["quiz_id"] == paper["quiz_id"]
    fetched = quiz_runtime.get_diagnosis(paper["quiz_id"], student_id)
    assert fetched["time_management_verdict"].startswith("Well-paced")
    assert len(fetched["improvement_areas"]) == 1


@live
def test_live_diagnosis_rejected_before_grading(live_student):
    student_id = live_student
    paper = quiz_runtime.import_paper(
        student_id, style="MIXED", title="Ungraded Paper", requested_question_count=1,
        requested_question_types=["MCQ"], generated_by="test", exam_mode=True,
        questions=[_sample_import_question(1)],
    )
    with pytest.raises(quiz_runtime.QuizError) as exc:
        quiz_runtime.write_diagnosis(
            paper["quiz_id"], student_id, time_management_verdict="x", pacing_notes=[],
            reasoning_guidance=[], improvement_areas=[], generated_by="test",
        )
    assert exc.value.code == "NOT_GRADED"
