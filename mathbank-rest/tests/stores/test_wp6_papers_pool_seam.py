"""WP6 seam between the papers and pool areas on the composed ``DynamoDBExamStore`` (requirement 70 C2: pool write-back and serve ops of finalize).

The pool area (stores/exam/pool.py) provides ``link_or_insert_pool_questions`` and ``build_pool_serve_ops``; the papers area calls them from
``finalize_paper``: the write-back runs BEFORE the paper's transaction, the serve ops join it. Vectors are the in-memory store; the
embedder is a deterministic bag-of-words hash.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from uuid import UUID

import pytest
from wp6_papers_support import NoPostgres, mcq, profile, seed_content

from mathbank_rest import embeddings, stores, vector_sync
from mathbank_rest import vector_store as vs
from mathbank_rest.config import settings
from mathbank_rest.models.manual import exam_papers as ep
from mathbank_rest.models.manual.exam_pool import PoolQuestion, PoolServed, pool_pk, served_sk
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.exam import DynamoDBExamStore
from mathbank_rest.stores.exam import pool as pool_module
from mathbank_rest.vector_store import MemoryVectorStore


def fake_vec(text: str) -> list[float]:
    v = [0.0] * 1536
    for w in re.findall(r"\w+", text.lower()) or ["empty"]:
        v[int(hashlib.sha1(w.encode()).hexdigest(), 16) % 1536] += 1.0
    return v


@pytest.fixture()
def world(content_table, monkeypatch):
    from mathbank_rest.db import postgres

    seed_content()
    vs.set_vector_store_for_tests(MemoryVectorStore())
    embeddings.reset_for_tests()
    monkeypatch.setattr(embeddings, "EMBEDDER", fake_vec)
    monkeypatch.setattr(vector_sync, "BATCH_EMBEDDER", lambda texts: [fake_vec(t) for t in texts])
    monkeypatch.setattr(postgres, "engine", NoPostgres())
    monkeypatch.setattr(settings, "quiz_mastery_inline", False)
    pool_module._SEEN.clear()
    store = DynamoDBExamStore()
    with stores.override_store("content", DynamoDBContentStore()):
        yield store
    vs.set_vector_store_for_tests(None)
    embeddings.reset_for_tests()
    pool_module._SEEN.clear()


def paper(store, sid: str, questions: list[dict], **finalize) -> tuple[UUID, dict]:
    typed.put(profile(sid))
    qid = store.start_paper(UUID(sid), style="AIME", title="t", requested_question_count=len(questions), requested_question_types=["MCQ"],
                            generated_by="agent", difficulty_band="medium")
    return qid, store.finalize_paper(qid, UUID(sid), questions=questions, **finalize)


def test_a_written_back_question_is_linked_and_its_serve_ops_ride_the_paper_transaction(world):
    sid = str(uuid.uuid4())
    qid, view = paper(world, sid, [mcq(1, add_to_pool=True, concepts=("counting",)), mcq(2)], pool_topic="Counting", pool_concept_slugs=["counting"])
    assert view["status"] == "READY"
    q1 = typed.require(ep.ExamQuestionItem, toolkit.student_pk(sid), ep.question_sk(qid, view["questions"][0]["question_id"]))
    q2 = typed.require(ep.ExamQuestionItem, toolkit.student_pk(sid), ep.question_sk(qid, view["questions"][1]["question_id"]))
    assert q1.pool_question_id is not None and q2.pool_question_id is None
    pool = typed.require(PoolQuestion, pool_pk(q1.pool_question_id), "POOL")
    assert (pool.style, pool.difficulty_band, pool.times_served, str(pool.source_quiz_id)) == ("AIME", "medium", 0, str(qid))   # a write-back is not a serve
    served = typed.require(PoolServed, toolkit.student_pk(sid), served_sk(q1.pool_question_id))
    assert str(served.first_quiz_id) == str(qid)


def test_a_question_served_from_the_pool_bumps_its_usage_and_is_not_matched_again(world):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    _, first = paper(world, a, [mcq(1, add_to_pool=True, concepts=("counting",))], pool_topic="Counting", pool_concept_slugs=["counting"])
    q = typed.require(ep.ExamQuestionItem, toolkit.student_pk(a), ep.question_sk(first["quiz_id"], first["questions"][0]["question_id"]))
    pid = str(q.pool_question_id)
    hits = world.match_pool_questions(UUID(b), style="AIME", question_types=["MCQ"], difficulty_band="medium", topic="Counting",
                                      concept_slugs=["counting"], limit=5)
    assert [h["pool_question_id"] for h in hits] == [pid]
    assert world.match_pool_questions(UUID(a), style="AIME", question_types=["MCQ"], difficulty_band="medium", topic="Counting",
                                      concept_slugs=["counting"], limit=5) == []                       # a's own history excludes it
    _, second = paper(world, b, [mcq(1, pool_question_id=uuid.UUID(pid))])
    assert second["status"] == "READY"
    assert typed.require(PoolQuestion, pool_pk(pid), "POOL").times_served == 1
    assert typed.get(PoolServed, toolkit.student_pk(b), served_sk(pid)) is not None
    assert world.match_pool_questions(UUID(b), style="AIME", question_types=["MCQ"], difficulty_band="medium", topic="Counting",
                                      concept_slugs=["counting"], limit=5) == []


def test_a_missing_pool_entry_does_not_fail_the_paper(world):
    sid = str(uuid.uuid4())
    _, view = paper(world, sid, [mcq(1, pool_question_id=uuid.uuid4())])
    assert view["status"] == "READY"
    q = typed.require(ep.ExamQuestionItem, toolkit.student_pk(sid), ep.question_sk(view["quiz_id"], view["questions"][0]["question_id"]))
    assert q.pool_question_id is None
