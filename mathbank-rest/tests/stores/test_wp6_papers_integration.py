"""WP6 papers against the REAL ``test`` data-plane environment: concurrent duplicate responds and racing writers.

Skipped unless MB_DDB_ENV=test (``make test-ddb-integration``). Needs ``make -C ../mathbank-db aws-provision AWS_ENV=test``.
No content table is needed (the questions carry no tags or sources); the learner profile (the ConditionCheck target), the papers and every
item written here are removed afterwards. Never point this at ``dev``: that environment holds the migrated copy of real data.
"""
from __future__ import annotations

import threading
import uuid
from uuid import UUID

import pytest
from wp6_papers_support import mcq, profile

from mathbank_rest.config import settings
from mathbank_rest.models.manual import exam_papers as ep
from mathbank_rest.quiz_logic import QuizError
from mathbank_rest.stores import ddb as t
from mathbank_rest.stores import typed
from mathbank_rest.stores.exam.papers import PapersDynamoDB

pytestmark = pytest.mark.ddb_integration
THREADS = 8


def _delete(client, ctx: str, pk: str, sk: str) -> None:
    client.delete_item(TableName=t.table_name(ctx), Key={"PK": {"S": pk}, "SK": {"S": sk}})


def race(fn, n: int = THREADS) -> list:
    """Run ``fn(i)`` on ``n`` threads released together; returns each result or the exception it raised."""
    barrier, out = threading.Barrier(n), [None] * n

    def work(i: int) -> None:
        barrier.wait()
        try:
            out[i] = fn(i)
        except Exception as exc:  # noqa: BLE001
            out[i] = exc

    threads = [threading.Thread(target=work, args=(i,)) for i in range(n)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return out


@pytest.fixture()
def paper(real_env, monkeypatch):
    monkeypatch.setattr(settings, "quiz_mastery_inline", False)
    sid, store = str(uuid.uuid4()), PapersDynamoDB()
    typed.put(profile(sid))
    qid = store.start_paper(UUID(sid), style="MIXED", title="race", requested_question_count=THREADS,
                            requested_question_types=["MCQ"], generated_by="test", exam_mode=False)
    view = store.finalize_paper(qid, UUID(sid), questions=[mcq(i) for i in range(1, THREADS + 1)])
    yield store, sid, qid, [UUID(q["question_id"]) for q in view["questions"]]
    client, token = t.client(), None
    while True:
        page = t.query_page("exam", t.student_pk(sid), limit=100, next_token=token)
        for item in page["items"]:
            _delete(client, "exam", item["PK"], item["SK"])
            if item["type"] == "RESPONSE":
                _delete(client, "exam", f"RESPONSE#{item['response_id']}", "OWNER")
        token = page["next_token"]
        if not token:
            break
    _delete(client, "exam", f"QUIZ#{qid}", "OWNER")
    _delete(client, "learner", t.student_pk(sid), "PROFILE")


def test_concurrent_duplicate_responds_write_exactly_one_response(paper):
    store, sid, qid, questions = paper
    results = race(lambda i: store.submit_response(qid, questions[0], UUID(sid), raw_response={"selected_key": "B" if i % 2 else "A"}))
    won = [r for r in results if isinstance(r, dict)]
    lost = [r for r in results if isinstance(r, QuizError)]
    assert len(won) == 1 and len(lost) == THREADS - 1 and {e.code for e in lost} <= {"ALREADY_ANSWERED", "CONFLICT"}, results
    responses = t.query_page("exam", t.student_pk(sid), sk_begins=f"QUIZ#{qid}#P#RESP#", limit=50)["items"]
    assert len(responses) == 1
    assert typed.require(ep.ExamPaperItem, t.student_pk(sid), ep.paper_sk(qid)).answered_count == 1


def test_racing_answers_to_different_questions_all_count(paper):
    store, sid, qid, questions = paper
    results = race(lambda i: store.submit_response(qid, questions[i], UUID(sid), raw_response={"selected_key": "B"}))
    errors = [r for r in results if isinstance(r, Exception)]
    assert all(isinstance(e, QuizError) and e.code == "CONFLICT" for e in errors), errors          # only an exhausted retry budget may lose
    answered = typed.require(ep.ExamPaperItem, t.student_pk(sid), ep.paper_sk(qid))
    assert answered.answered_count == THREADS - len(errors) == len(t.query_page(
        "exam", t.student_pk(sid), sk_begins=f"QUIZ#{qid}#P#RESP#", limit=50)["items"])
    if not errors:
        assert (answered.status, answered.correct_count) == ("GRADED", THREADS)


def test_concurrent_finalize_creates_the_questions_once(real_env, monkeypatch):
    store, sid = PapersDynamoDB(), str(uuid.uuid4())
    typed.put(profile(sid))
    qid = store.start_paper(UUID(sid), style="MIXED", title="finalize", requested_question_count=2, requested_question_types=["MCQ"],
                            generated_by="test")
    try:
        results = race(lambda i: store.finalize_paper(qid, UUID(sid), questions=[mcq(1), mcq(2)]), n=4)
        assert sum(1 for r in results if isinstance(r, dict)) == 1
        assert all(isinstance(r, QuizError) and r.status_code in (404, 502) for r in results if not isinstance(r, dict)), results
        questions = t.query_page("exam", t.student_pk(sid), sk_begins=f"QUIZ#{qid}#P#Q#", limit=50)["items"]
        assert sorted(q["ordinal"] for q in questions) == [1, 2]
    finally:
        client, token = t.client(), None
        while True:
            page = t.query_page("exam", t.student_pk(sid), limit=100, next_token=token)
            for item in page["items"]:
                _delete(client, "exam", item["PK"], item["SK"])
            token = page["next_token"]
            if not token:
                break
        _delete(client, "exam", f"QUIZ#{qid}", "OWNER")
        _delete(client, "learner", t.student_pk(sid), "PROFILE")
