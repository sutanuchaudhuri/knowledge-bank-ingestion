"""Question pool (migration 052) pure helpers and request models — no database."""
from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from mathbank_rest import quiz_runtime
from mathbank_rest.routers.exam_integration import FailPaperRequest, FinalizePaperRequest, MatchPoolRequest


def test_normalize_topic_key_collapses_case_and_whitespace():
    assert quiz_runtime.normalize_topic_key("  Counting   WITH\tBijections ") == "counting with bijections"
    assert quiz_runtime.normalize_topic_key(None) == ""
    assert len(quiz_runtime.normalize_topic_key("x" * 500)) == 200


def test_pool_content_hash_ignores_case_and_whitespace_only():
    h = quiz_runtime._pool_content_hash
    assert h("What is 2 + 2?") == h("  what IS 2 +  2? ")
    assert h("What is 2 + 2?") != h("What is 2 + 3?")


def test_match_pool_questions_without_topic_or_concepts_skips_db():
    assert quiz_runtime.match_pool_questions(
        uuid4(), style="AIME", question_types=["MCQ"], difficulty_band=None, topic="  ", concept_slugs=[],
    ) == []


def test_finalize_request_accepts_pool_fields():
    body = FinalizePaperRequest.model_validate({
        "student_id": str(uuid4()), "pool_topic": "combinatorics", "pool_concept_slugs": ["count"],
        "questions": [{
            "question_type": "MCQ", "prompt_text": "2+2?", "options": [{"key": "A", "text": "4"}],
            "correct_answer": {"correct_key": "A"}, "solution_text": "4", "key_insight": "add",
            "pool_question_id": str(uuid4()), "add_to_pool": False,
        }],
    })
    assert body.pool_concept_slugs == ["count"]
    assert body.questions[0].pool_question_id is not None


def test_match_pool_request_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        MatchPoolRequest.model_validate({"student_id": str(uuid4()), "style": "AIME", "bogus": 1})


def test_fail_paper_request_requires_a_bounded_message():
    body = FailPaperRequest.model_validate({
        "student_id": str(uuid4()),
        "error_message": "critic rejected question 2",
    })
    assert body.error_message == "critic rejected question 2"
    with pytest.raises(ValidationError):
        FailPaperRequest.model_validate({"student_id": str(uuid4()), "error_message": ""})
