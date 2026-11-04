"""WP6 seam with the learner area (requirement 70 C2 A18): quiz evidence in the mastery of a tag.

With the exam store on DynamoDB the learner store reads the quiz part of a tag's attempts from ``QUIZ_EVIDENCE``
(``exam.get_quiz_evidence``) and leaves out the learner's migrated copy of the same responses (``MEVID`` ``src_kind=QZ``); with the exam
store on PostgreSQL nothing changes. A respond recomputes the mastery of its tags after the commit (``quiz_mastery_inline``).
"""
from __future__ import annotations

import datetime as dt
import uuid
from uuid import UUID

import pytest
from wp6_papers_support import FakeLLM, NoPostgres, free_text, mcq, profile, seed_content, uid

from mathbank_rest import quiz_logic as ql
from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models.manual.learner_outcomes import MasteryItem, MevidItem
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.exam import DynamoDBExamStore, PostgresExamStore
from mathbank_rest.stores.learner import DynamoDBLearnerStore

CONCEPT = uid("concept:counting")
WHEN = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


@pytest.fixture()
def world(content_table, monkeypatch, sid):
    from mathbank_rest.db import postgres

    seed_content()
    typed.put(profile(sid))
    monkeypatch.setattr(postgres, "engine", NoPostgres())
    monkeypatch.setattr(settings, "quiz_mastery_inline", True)
    llm = FakeLLM()
    monkeypatch.setattr(ql, "_client", lambda: llm.client)
    exam, learner = DynamoDBExamStore(), DynamoDBLearnerStore()
    with stores.override_store("content", DynamoDBContentStore()), stores.override_store("exam", exam), \
            stores.override_store("learner", learner):
        yield exam, learner, sid


def mevid(sid: str, kind: str, correct: bool, src: str, when: dt.datetime) -> MevidItem:
    src_id = uuid.uuid4()
    return MevidItem(PK=toolkit.student_pk(sid), SK=f"MEVID#C#{CONCEPT}#{toolkit.encode(when)}#{src}#{src_id}", student_id=sid, tag_kind="C",
                     tag_id=CONCEPT, is_correct=correct, hint_count=0, difficulty_band="medium", difficulty_weight=1.0, attempted_at=when,
                     src_kind=src, src_id=src_id)


def test_the_quiz_branch_of_the_attempts_comes_from_the_exam_store_without_double_counting(world):
    exam, learner, sid = world
    typed.put(mevid(sid, "C", True, "OUT", WHEN))                                              # a real-corpus attempt
    typed.put(mevid(sid, "C", False, "QZ", WHEN + dt.timedelta(days=1)))                         # the migrated copy of a quiz response
    qid = exam.start_paper(UUID(sid), style="MIXED", title="t", requested_question_count=1, requested_question_types=["MCQ"], generated_by="x",
                           exam_mode=False)
    view = exam.finalize_paper(qid, UUID(sid), questions=[mcq(1, concepts=("counting",), band="hard")])
    exam.submit_response(qid, UUID(view["questions"][0]["question_id"]), UUID(sid), raw_response={"selected_key": "B"})
    rows = learner.get_attempts_for_concept(UUID(sid), UUID(CONCEPT))
    assert [(r["is_correct"], r["difficulty_band"], r["hint_count"]) for r in rows] == [(True, "medium", 0), (True, "hard", 0)]
    assert rows[0]["attempted_at"] < rows[1]["attempted_at"]
    assert learner.get_attempts_for_technique(UUID(sid), UUID(uid("technique:pigeonhole"))) == []


def test_a_respond_updates_the_mastery_of_the_tags_it_is_tagged_with(world):
    exam, _, sid = world
    qid = exam.start_paper(UUID(sid), style="MIXED", title="t", requested_question_count=2, requested_question_types=["MCQ", "FREE_TEXT"],
                           generated_by="x", exam_mode=False)
    view = exam.finalize_paper(qid, UUID(sid), questions=[mcq(1, concepts=("counting",)), free_text(2, concept_slugs=["counting"])])
    q1, q2 = (UUID(q["question_id"]) for q in view["questions"])
    exam.submit_response(qid, q1, UUID(sid), raw_response={"selected_key": "A"})
    exam.submit_response(qid, q2, UUID(sid), raw_response={"response_text": "4"})
    item = typed.require(MasteryItem, toolkit.student_pk(sid), f"MASTERY#C#{CONCEPT}")
    assert (item.attempts_count, item.correct_count) == (2, 1)


def test_with_the_exam_store_on_postgres_the_learner_evidence_is_unchanged(world):
    _, learner, sid = world
    typed.put(mevid(sid, "C", True, "OUT", WHEN))
    typed.put(mevid(sid, "C", False, "QZ", WHEN + dt.timedelta(days=1)))
    with stores.override_store("exam", PostgresExamStore()):
        rows = learner.get_attempts_for_concept(UUID(sid), UUID(CONCEPT))
    assert [r["is_correct"] for r in rows] == [True, False]
