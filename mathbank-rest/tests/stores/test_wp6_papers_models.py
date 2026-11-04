"""The refined ``mb-exam`` models accept every shape the migration writes (requirement 71 WP6 gate, ``python -m mathbank_rest.models.validate``).

Samples come from the real transforms of ``mathbank-db/aws/dynamo/specs/exam.py`` fed with synthetic source rows (post-processed like the
engine does and decoded like a DynamoDB read), so a refinement that rejects a migrated item fails here before it fails on ``dev``.
"""
from __future__ import annotations

import datetime as dt
import sys
import uuid
from pathlib import Path

import pytest

from mathbank_rest.models import base
from mathbank_rest.models.validate import same
from mathbank_rest.stores import ddb

DB_ROOT = Path(__file__).resolve().parents[3] / "mathbank-db"


def _load():
    sys.path.insert(0, str(DB_ROOT))
    try:
        from aws import common
        from aws.dynamo.specs import exam
    except ImportError:
        return None
    finally:
        sys.path.remove(str(DB_ROOT))
    return common, exam


SPECS = _load()
pytestmark = pytest.mark.skipif(SPECS is None, reason="mathbank-db is not importable")


def u() -> str:
    return str(uuid.uuid4())


def ts(day: int = 1, hour: int = 10) -> dt.datetime:
    return dt.datetime(2026, 10, day, hour, 30, 15, 123456, tzinfo=dt.UTC)


def emit(transform, row: dict) -> list[dict]:
    common = SPECS[0]
    out = []
    for raw in transform(row) or ():
        item = common.clean_item(raw)
        for k in [k for k in item if k.startswith("GSI") and k.endswith(("PK", "SK"))]:
            if item[k] in ("", None):
                del item[k]
        out.append(ddb.decode(item))
    return out


SID, QID = u(), u()


def paper_row(**over) -> dict:
    return {"quiz_id": QID, "student_id": SID, "style": "MIXED", "title": "Mock", "instructions": "", "requested_question_count": 2,
            "requested_question_types": ["MCQ", "FREE_TEXT"], "target_skill_slugs": [], "target_concept_slugs": ["counting"],
            "difficulty_band": "Hard", "generated_by": "bedrock:x", "object_key": None, "object_sha256": None, "status": "GRADED",
            "error_message": None, "created_at": ts(1), "started_at": ts(1, 11), "submitted_at": ts(1, 12), "graded_at": ts(1, 12),
            "exam_mode": True, "time_limit_seconds": 5400, "agent_framework": "STRANDS_BEDROCK", "resume_question_ordinal": 2,
            "question_count": 2, "answered_count": 1, "correct_count": 1, "diagnosis_version": 1, **over}


def question_row(ordinal: int, qtype: str, **over) -> dict:
    mcq = qtype == "MCQ"
    return {"question_id": u(), "quiz_id": QID, "student_id": SID, "ordinal": ordinal, "question_type": qtype, "prompt_text": f"Q{ordinal}",
            "prompt_latex": None, "options": [{"key": "A", "text": "1"}, {"key": "B", "text": "2"}] if mcq else None,
            "correct_answer": {"correct_key": "B"} if mcq else {"expected_answer": "2", "grading_rubric": None}, "points": 1,
            "inspired_by_problem_id": u() if mcq else None, "diagram_object_key": None, "diagram_sha256": None, "created_at": ts(1),
            "revision_log": [{"round": 1, "verdict": "APPROVE", "feedback": "ok"}] if mcq else [], "difficulty_band": "Medium",
            "option_explanations": {"A": "no", "B": "yes"} if mcq else {}, "complexity_signals": {"step_count": 2, "concept_count": 1},
            "pool_question_id": None, "has_solution": True, "solution_text": "because", "solution_latex": None, "key_insight": "insight",
            "solution_object_key": None, "solution_object_sha256": None, "solution_created_at": ts(1), "solution_steps": ["a", "b"],
            "step_count": 2, "inspiration_sources": [{"rank": 1, "problem_id": u(), "canonical_code": "AMC10_2005B_Q18", "note": "n"}] if mcq else [],
            "concept_ids": [u()] if mcq else [], "concept_slugs": ["counting"] if mcq else [], "technique_ids": [u()] if mcq else [],
            "technique_slugs": ["pigeonhole"] if mcq else [], "skill_ids": [u()] if mcq else [], "skill_slugs": ["case-analysis"] if mcq else [], **over}


def samples() -> list[dict]:
    exam = SPECS[1]
    out: list[dict] = []
    for over in ({}, {"status": "GENERATING", "started_at": None, "submitted_at": None, "graded_at": None, "answered_count": 0, "correct_count": 0,
                      "question_count": 0, "diagnosis_version": 0, "resume_question_ordinal": None, "difficulty_band": None, "time_limit_seconds": None,
                      "exam_mode": False, "agent_framework": "OPENAI_DIRECT", "object_key": "k", "object_sha256": "a" * 64},
                 {"status": "FAILED", "error_message": "boom"}):
        out += emit(exam.paper, paper_row(**over))
    questions = [question_row(1, "MCQ"), question_row(2, "FREE_TEXT")]
    for q in questions:
        out += emit(exam.question, q)
    mcq_q = questions[0]
    rid = u()
    out += emit(exam.response, {"response_id": rid, "question_id": mcq_q["question_id"], "quiz_id": QID, "student_id": SID, "ordinal": 1,
                                "response_type": "MCQ", "raw_response": {"selected_key": "B"}, "object_key": "o", "object_sha256": "b" * 64,
                                "is_correct": True, "grading_method": "EXACT_MATCH", "grading_confidence": 1.0, "grading_feedback": "Correct.",
                                "time_spent_seconds": 31, "submitted_at": ts(1, 11)})
    out += emit(exam._evidence("C", "concept_id"), {"question_id": mcq_q["question_id"], "tag_id": u(), "quiz_id": QID, "student_id": SID,
                                                     "response_id": rid, "is_correct": True, "submitted_at": ts(1, 11), "difficulty_band": "medium"})
    out += emit(exam._evidence("T", "technique_id"), {"question_id": mcq_q["question_id"], "tag_id": u(), "quiz_id": QID, "student_id": SID,
                                                       "response_id": rid, "is_correct": False, "submitted_at": ts(1, 11), "difficulty_band": "hard"})
    out += emit(exam.draft, {"quiz_id": QID, "question_id": questions[1]["question_id"], "student_id": SID, "draft_student_id": SID,
                             "raw_response": {"response_text": "draft"}, "updated_at": ts(1, 11)})
    out += emit(exam.response_event, {"event_id": u(), "quiz_id": QID, "question_id": mcq_q["question_id"], "student_id": SID, "ordinal": 1,
                                      "event_type": "SELECT_OPTION", "option_key": "B", "client_timestamp_ms": 1_790_000_000_000, "created_at": ts(1, 11)})
    out += emit(exam.generation_event, {"event_id": u(), "quiz_id": QID, "student_id": SID, "ordinal": 3, "phase": "DRAFT_QUESTION", "status": "DONE",
                                        "question_ordinal": 1, "detail": "q1", "created_at": ts(1, 9)})
    out += emit(exam.diagnosis, {"quiz_id": QID, "student_id": SID, "time_management_verdict": "ok", "pacing_notes": [{"question_ordinal": 1,
             "time_spent_seconds": 31, "difficulty_band": "easy", "note": "fast"}], "reasoning_guidance": [{"question_ordinal": 2, "guidance": "g"}],
             "improvement_areas": [{"concept_or_technique": "x", "current_mastery_tier": "weak", "evidence": "e"}], "generated_by": "agent",
             "created_at": ts(1, 13)})
    return out


@pytest.mark.parametrize("item", samples(), ids=lambda i: f"{i['type']}-{i['SK'][:40]}")
def test_a_migrated_item_parses_and_round_trips_through_the_refined_model(item):
    model = base.parse_item("exam", item)
    assert type(model).__module__.endswith("manual.exam_papers") or item["type"] in {"PAPER_OWNER", "RESPONSE_OWNER"}
    assert same(model.to_item(), item)


def test_the_refinements_reject_what_the_check_constraints_reject():
    from mathbank_rest.stores.errors import ItemSchemaError

    paper = next(i for i in samples() if i["type"] == "PAPER")
    for field, bad in (("status", "ARCHIVED"), ("requested_question_count", 21), ("time_limit_seconds", 59), ("difficulty_band", "Hard"),
                       ("answer_disclosure", "NEVER"), ("requested_question_types", ["ESSAY"]), ("resume_question_ordinal", 0)):
        with pytest.raises(ItemSchemaError):
            base.parse_item("exam", {**paper, field: bad})
    event = next(i for i in samples() if i["type"] == "RESPONSE_EVENT")
    for field, bad in (("event_type", "WINK"), ("option_key", "x" * 11)):
        with pytest.raises(ItemSchemaError):
            base.parse_item("exam", {**event, field: bad})
    gen = next(i for i in samples() if i["type"] == "GENERATION_EVENT")
    for field, bad in (("phase", "NOPE"), ("status", "NOPE")):
        with pytest.raises(ItemSchemaError):
            base.parse_item("exam", {**gen, field: bad})
