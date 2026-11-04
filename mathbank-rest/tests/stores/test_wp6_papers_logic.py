"""quiz_logic (requirement 71 WP6): the database-free rules of the quiz subsystem, and the PostgreSQL path of ``quiz_runtime`` that now
shares them (generator loop, grading, disclosure of an exam-mode respond, status gate). No database: the SQL layer is a scripted fake."""
from __future__ import annotations

import contextlib
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from wp6_papers_support import FakeLLM

from mathbank_rest import quiz_logic as ql
from mathbank_rest import quiz_runtime
from mathbank_rest.config import settings
from mathbank_rest.quiz_logic import QuizError

# ------------------------------------------------------------------------------------------------- pure rules


def test_quiz_runtime_re_exports_what_it_always_had():
    for name in ("QuizError", "STYLES", "QUESTION_TYPES", "EVENT_TYPES", "MODEL_NAME", "_client", "_now", "_validate_exam_draft", "_grade_free_text",
                 "_generate_one_question", "_maybe_generate_diagram", "_sanitize_point_id", "_targets_from_state", "normalize_topic_key",
                 "_pool_content_hash", "_POOL_QUESTION_EXCLUDED_FIELDS", "_QUESTION_SCHEMA", "_DIAGRAM_SCHEMA", "_STYLE_COMPETITION"):
        assert hasattr(quiz_runtime, name), name
    assert quiz_runtime.QuizError is ql.QuizError


@pytest.mark.parametrize("band,expected", [(None, None), ("Easy", "easy"), (" VERY_HARD ", "very_hard")])
def test_difficulty_bands_are_lower_cased(band, expected):
    assert ql.normalize_band(band) == expected


def test_an_unknown_band_is_422():
    with pytest.raises(QuizError) as exc:
        ql.normalize_band("extreme")
    assert (exc.value.code, exc.value.status_code) == ("INVALID_DIFFICULTY_BAND", 422)


def test_event_timestamps_more_than_a_day_away_are_dropped():
    now = 1_790_000_000_000
    assert ql.validate_event("VIEW", None, now - 86_000_000, now_ms=now) == now - 86_000_000
    assert ql.validate_event("VIEW", None, now + 86_400_001, now_ms=now) is None
    assert ql.validate_event("VIEW", None, None, now_ms=now) is None


def test_generation_events_are_validated():
    ql.validate_generation_event("DONE", "FAILED", 999_999)
    for args in (("NOPE", "DONE", 1), ("DONE", "NOPE", 1), ("DONE", "DONE", 0), ("DONE", "DONE", 1_000_000)):
        with pytest.raises(QuizError) as exc:
            ql.validate_generation_event(*args)
        assert exc.value.status_code == 422


def test_mcq_is_an_exact_match_and_written_answers_go_to_the_llm():
    mcq = {"question_type": "MCQ", "prompt_text": "p", "correct_answer": {"correct_key": "B"}}
    assert ql.grade_answer(mcq, {"selected_key": "B"}) == (True, "EXACT_MATCH", 1.0, "Correct.")
    assert ql.grade_answer(mcq, {"selected_key": "A"}) == (False, "EXACT_MATCH", 1.0, "The correct answer was B.")
    llm = FakeLLM()
    written = {"question_type": "PROOF", "prompt_text": "p", "correct_answer": {"expected_answer": None, "grading_rubric": "steps"}}
    assert ql.grade_answer(written, {"response_text": "x"}, client_factory=lambda: llm.client) == (True, "LLM_GRADED", 0.9, "Well reasoned.")
    wild = ql.grade_answer(written, {"response_text": "x"}, grade_free_text=lambda *a: {"is_correct": False, "confidence": 7, "feedback": "f"})
    assert wild == (False, "LLM_GRADED", 1.0, "f")                                      # a confidence outside [0, 1] is clamped (the CHECK)


def test_complexity_signals_count_what_the_generator_gave():
    q = {"solution_steps": ["a", "b", "c"], "concept_slugs": ["x", "y"], "technique_slugs": ["y", "z"], "solution_text": "abcd"}
    assert ql.complexity_signals(q) == {"step_count": 3, "concept_count": 3, "technique_count": 2, "solution_length_chars": 4}


def test_the_strict_policy_flag_decides_what_an_exam_respond_discloses(monkeypatch):
    full = {"is_correct": True, "feedback": "Correct."}
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", True)
    assert ql.respond_view(full, answer_disclosure="AFTER_SUBMIT", question_id="q", answered_count=3) == {
        "saved": True, "question_id": "q", "answered_count": 3}
    assert ql.respond_view(full, answer_disclosure="IMMEDIATE", question_id="q", answered_count=3) is full
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", False)
    assert ql.respond_view(full, answer_disclosure="AFTER_SUBMIT", question_id="q", answered_count=3) is full


def test_the_review_gate():
    assert ql.review_open(answer_disclosure="IMMEDIATE", status="READY")
    assert not ql.review_open(answer_disclosure="AFTER_SUBMIT", status="IN_PROGRESS")
    assert ql.review_open(answer_disclosure="AFTER_SUBMIT", status="GRADED") and ql.review_open(answer_disclosure="AFTER_SUBMIT", status="SUBMITTED")


def test_the_learner_question_is_an_allow_list():
    q = {"question_id": "1", "ordinal": 1, "question_type": "MCQ", "prompt_text": "p", "prompt_latex": None, "options": [{"key": "A", "text": "x"}],
         "points": 1, "diagram_object_key": "d", "correct_answer": {"correct_key": "A"}, "solution_text": "secret"}
    out = ql.learner_question(q, student_response=None, draft_response=None, answered=False)
    assert set(out) == {"question_id", "ordinal", "question_type", "prompt_text", "prompt_latex", "options", "points", "has_diagram",
                        "student_response", "draft_response", "answered"} and out["has_diagram"] is True
    assert "secret" not in json.dumps(out)


# ----------------------------------------------------------------------------------- the PostgreSQL path, scripted


class FakeResult:
    def __init__(self, rows=None, scalar=None):
        self.rows, self.scalar = rows or [], scalar

    def mappings(self):
        return SimpleNamespace(first=lambda: self.rows[0] if self.rows else None, all=lambda: self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar_one(self):
        return self.scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: self.rows)


class FakeSql:
    """Answers each statement by a substring of its text; records every statement."""

    def __init__(self, answers: dict[str, FakeResult]):
        self.answers, self.statements = answers, []

    def execute(self, stmt, params=None):
        text = " ".join(str(stmt).split())
        self.statements.append((text, params))
        for needle, result in self.answers.items():
            if needle in text:
                return result
        return FakeResult()

    def connect(self):
        return contextlib.nullcontext(self)

    begin = connect


def pg_paper(**over):
    return {"quiz_id": str(uuid4()), "student_id": str(uuid4()), "status": "IN_PROGRESS", "exam_mode": False, "style": "AIME", "title": "t", **over}


def run_respond(monkeypatch, paper, *, answers=None, question=None):
    question = question or {"question_id": str(uuid4()), "question_type": "MCQ", "prompt_text": "p", "correct_answer": {"correct_key": "B"}}
    sql = FakeSql({"FROM quiz.question WHERE": FakeResult([question]), "FROM quiz.solution": FakeResult([{"solution_text": "s", "key_insight": "k"}]),
                   "count(*)": FakeResult(scalar=2), "FROM quiz.response WHERE": FakeResult(), **(answers or {})})
    monkeypatch.setattr(quiz_runtime, "engine", sql)
    monkeypatch.setattr(quiz_runtime, "_require_owned_paper", lambda *_a: paper)
    monkeypatch.setattr(quiz_runtime, "_absorb_mastery_feedback", lambda *_a: None)
    monkeypatch.setattr(quiz_runtime.object_store, "put_bytes", lambda *a, **k: {"object_key": "k", "sha256": "s"})
    return quiz_runtime.submit_response(uuid4(), uuid4(), uuid4(), raw_response={"selected_key": "B"}), sql


def test_pg_practice_respond_keeps_its_full_body(monkeypatch):
    body, _ = run_respond(monkeypatch, pg_paper(exam_mode=False))
    assert body == {"is_correct": True, "grading_method": "EXACT_MATCH", "confidence": 1.0, "feedback": "Correct.",
                    "solution": {"solution_text": "s", "key_insight": "k"}}


def test_pg_exam_respond_withholds_the_grading_under_the_strict_policy(monkeypatch):
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", True)
    paper = pg_paper(exam_mode=True)
    body, sql = run_respond(monkeypatch, paper)
    assert set(body) == {"saved", "question_id", "answered_count"} and body["answered_count"] == 2
    assert any("count(*)" in text for text, _ in sql.statements)
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", False)
    full, sql = run_respond(monkeypatch, paper)
    assert full["is_correct"] is True and not any("count(*)" in text for text, _ in sql.statements)


@pytest.mark.parametrize("status", ["GENERATING", "FAILED", "SUBMITTED", "GRADED"])
def test_pg_respond_needs_an_open_paper_under_the_strict_policy(monkeypatch, status):
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", True)
    with pytest.raises(QuizError) as exc:
        run_respond(monkeypatch, pg_paper(status=status))
    assert (exc.value.code, exc.value.status_code) == ("EXAM_NOT_EDITABLE", 409)
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", False)
    body, _ = run_respond(monkeypatch, pg_paper(status=status))                    # the old unchecked behaviour is one flag away
    assert body["is_correct"] is True


def test_pg_a_retry_of_an_answer_on_a_closed_paper_is_already_answered(monkeypatch):
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", True)
    with pytest.raises(QuizError) as exc:
        run_respond(monkeypatch, pg_paper(status="GRADED"), answers={"FROM quiz.response WHERE": FakeResult([(1,)])})
    assert exc.value.code == "ALREADY_ANSWERED"


def test_pg_submit_exam_refuses_a_generating_paper_under_the_strict_policy(monkeypatch):
    monkeypatch.setattr(settings, "quiz_strict_exam_policy", True)
    monkeypatch.setattr(quiz_runtime, "engine", FakeSql({}))
    monkeypatch.setattr(quiz_runtime, "_require_owned_paper", lambda *_a: pg_paper(status="GENERATING"))
    with pytest.raises(QuizError) as exc:
        quiz_runtime.submit_exam(uuid4(), uuid4())
    assert (exc.value.code, exc.value.status_code) == ("EXAM_NOT_EDITABLE", 409)


def test_pg_generate_quiz_runs_the_shared_generator_loop(monkeypatch):
    sql = FakeSql({})
    llm = FakeLLM()
    persisted = []
    monkeypatch.setattr(quiz_runtime, "engine", sql)
    monkeypatch.setattr(quiz_runtime, "_client", lambda: llm.client)
    monkeypatch.setattr(quiz_runtime, "_targets_from_state", lambda sid, max_targets: [])
    monkeypatch.setattr("mathbank_rest.db.hybrid_search.search_problems", lambda *a, **k: {"results": []})
    monkeypatch.setattr(quiz_runtime, "_persist_questions", lambda quiz_id, questions: persisted.append(questions))
    monkeypatch.setattr(quiz_runtime, "get_quiz", lambda quiz_id, student_id: {"quiz_id": str(quiz_id), "status": "READY"})
    view = quiz_runtime.generate_quiz(uuid4(), style="PROOF_BASED", question_count=3, question_types=["MCQ", "FREE_TEXT"])
    assert view["status"] == "READY" and [q["question_type"] for q in persisted[0]] == ["MCQ", "FREE_TEXT", "MCQ"]
    assert [q["ordinal"] for q in persisted[0]] == [1, 2, 3] and persisted[0][0]["target"]["kind"] == "topic"
    assert "diagram_plan" not in llm.calls                                           # PROOF_BASED asks for no diagram
    assert any("INSERT INTO quiz.paper" in text for text, _ in sql.statements)


def test_pg_generate_quiz_marks_the_paper_failed_when_the_llm_does(monkeypatch):
    sql = FakeSql({})
    monkeypatch.setattr(quiz_runtime, "engine", sql)
    monkeypatch.setattr(quiz_runtime, "_client", lambda: FakeLLM(fail_on="quiz_question").client)
    monkeypatch.setattr(quiz_runtime, "_targets_from_state", lambda sid, max_targets: [])
    monkeypatch.setattr("mathbank_rest.db.hybrid_search.search_problems", lambda *a, **k: {"results": []})
    with pytest.raises(QuizError) as exc:
        quiz_runtime.generate_quiz(uuid4(), style="AIME", question_count=1, question_types=["MCQ"])
    assert (exc.value.code, exc.value.status_code) == ("GENERATION_FAILED", 502)
    assert any("status='FAILED'" in text and "llm down" in str(params) for text, params in sql.statements)


def test_pg_quiz_evidence_rows_are_the_quiz_branch_of_the_attempts(monkeypatch):
    sql = FakeSql({"FROM quiz.response r": FakeResult([{"is_correct": True, "attempted_at": 1, "hint_count": 0, "difficulty_band": "easy"}])})
    monkeypatch.setattr(quiz_runtime, "engine", sql)
    rows = quiz_runtime.get_quiz_evidence_rows(uuid4(), "T", uuid4())
    assert rows == [{"is_correct": True, "attempted_at": 1, "hint_count": 0, "difficulty_band": "easy"}]
    assert "quiz.question_technique j" in sql.statements[0][0] and "coalesce(q.difficulty_band, qp.difficulty_band)" in sql.statements[0][0]
    with pytest.raises(KeyError):
        quiz_runtime.get_quiz_evidence_rows(uuid4(), "X", uuid4())


def test_the_postgres_store_delegates_to_quiz_runtime_at_call_time(monkeypatch):
    from mathbank_rest.stores.exam import PostgresExamStore

    seen = {}
    monkeypatch.setattr(quiz_runtime, "get_quiz", lambda quiz_id, student_id: seen.setdefault("quiz", (quiz_id, student_id)) and {"ok": 1})
    monkeypatch.setattr(quiz_runtime, "get_quiz_evidence_rows", lambda *a: ["rows"])
    store = PostgresExamStore()
    assert store.get_quiz("q", "s") == {"ok": 1} and seen["quiz"] == ("q", "s")
    assert store.get_quiz_evidence("s", "C", "t") == ["rows"]
