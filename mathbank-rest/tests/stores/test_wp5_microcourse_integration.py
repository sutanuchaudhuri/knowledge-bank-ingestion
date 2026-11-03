"""Micro-course learner store on the REAL `test` data-plane environment: true concurrency (requirement 71 WP5 gate).

Skipped unless MB_DDB_ENV=test (`make test-ddb-integration`). moto is not atomic across threads, so the races of the design live here:
concurrent enrolls end with ONE enrollment, concurrent duplicates of one Idempotency-Key write once, concurrent responses to different
items lose no ``last_responses`` pointer, and concurrent advances with the same ``state_version`` let exactly one win.
Published content is served by an in-memory stand-in (the `test` environment has no content); every learner item and offloaded object a
test creates is removed afterwards. Never point this at `dev`.
"""
from __future__ import annotations

import copy
import threading
import uuid
from collections import Counter

import pytest
import test_wp4_learning as wp4

from mathbank_rest import micro_course_service as courses
from mathbank_rest import stores
from mathbank_rest.models.ddb.learner import LearnerProfile
from mathbank_rest.models.manual import learner_microcourse as mc
from mathbank_rest.stores import ddb as t
from mathbank_rest.stores import typed
from mathbank_rest.stores.content.learning import reader_payload
from mathbank_rest.stores.learner.microcourse import MicroCourseDynamoDB

pytestmark = pytest.mark.ddb_integration
CTX = "learner"
CODE = "MC-1"
THREADS = 8


class StandInContent:
    """The published course of the WP4 logical release, served from memory (grading keys included, server side only)."""

    def __init__(self):
        self.snapshot = wp4.learner_snapshot()
        self.keys = {wp4.LI1: ("b", "why-b"), wp4.LI2: ("d", None)}

    def get_micro_course_reader(self, conn, code):
        if code != CODE:
            raise courses.MicroCourseNotFound("published micro-course not found")
        return reader_payload(copy.deepcopy(self.snapshot))

    def get_pinned_micro_course_reader(self, conn, release_id):
        return reader_payload(copy.deepcopy(self.snapshot))

    def get_grading_item(self, conn, release_id, state_id, learning_item_id):
        state = next(s for s in self.snapshot["states"] if s["state_id"] == str(state_id))
        item = next((i for i in state["learning_items"] if i["learning_item_id"] == learning_item_id), None)
        if item is None:
            return None
        correct, seed = self.keys[learning_item_id]
        return {"learning_item_id": learning_item_id, "choices": item["choices"], "correct_answer": correct,
                "answer_or_solution_seed": seed}

    def get_learning_item_key(self, conn, learning_item_id):
        correct, seed = self.keys[learning_item_id]
        return {"learning_item_id": learning_item_id, "correct_answer": correct, "answer_or_solution_seed": seed}

    def get_activity_key(self, conn, activity_id):
        return {"activity_id": activity_id, "correctness_policy": {"correct_index": 0, "explanation": "because"}}

    def get_grading_activity(self, conn, release_id, activity_id):
        if activity_id != wp4.ACT1:
            return None
        return {"state_id": wp4.STATE1, "activity_type": "MCQ", "options": ["x = 1", "x = 2"],
                "correctness_policy": {"correct_index": 0, "explanation": "because"}}


@pytest.fixture()
def student(real_env):
    sid = str(uuid.uuid4())
    typed.put_new(LearnerProfile(
        PK=t.student_pk(sid), SK="PROFILE", student_id=sid, email=f"{sid}@example.test", email_lc=f"{sid}@example.test",
        first_name="T", last_name="T", display_name="T T", password_hash="h", search_blob="t", status="ACTIVE", is_anonymous=False,
        token_version=1, version=1, created_at=t.now_iso()))
    with stores.override_store("content", StandInContent()):
        yield sid
    pk, ddb, token = t.student_pk(sid), t.client(), None
    delete = lambda p, s: ddb.delete_item(TableName=t.table_name(CTX), Key={"PK": {"S": p}, "SK": {"S": s}})
    while True:
        page = t.query_page(CTX, pk, limit=100, next_token=token)
        for item in page["items"]:
            if item["type"] == "ENROLL":
                delete(f"ENROLL#{item['enrollment_id']}", "OWNER")
            delete(item["PK"], item["SK"])
        token = page["next_token"]
        if not token:
            break
    s3 = t.client("s3")
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=t.data_bucket(), Prefix=f"offload/learner/students/{sid}/"):
        for o in pg.get("Contents", []):
            s3.delete_object(Bucket=t.data_bucket(), Key=o["Key"])


def run_threads(fn, count: int = THREADS) -> list:
    """Run ``fn(i)`` on ``count`` threads released together; returns each result or the exception it raised."""
    barrier, out = threading.Barrier(count), [None] * count

    def work(i):
        barrier.wait()
        try:
            out[i] = fn(i)
        except Exception as exc:  # noqa: BLE001 - the test inspects the outcome of each racer
            out[i] = exc

    threads = [threading.Thread(target=work, args=(i,)) for i in range(count)]
    [th.start() for th in threads]
    [th.join(60) for th in threads]
    return out


def enrollments(student: str) -> list:
    return [i for i in typed.query(CTX, t.student_pk(student), limit=200, models=[mc.LearnerEnroll, mc.LearnerMcevent, mc.LearnerUniqueOpenEnroll,
                                                                             mc.LearnerEnrollOwner, LearnerProfile]).items
            if isinstance(i, mc.LearnerEnroll)]


def test_concurrent_enrolls_end_with_one_enrollment(student):
    store = MicroCourseDynamoDB()
    results = run_threads(lambda i: store.start_enrollment(None, CODE, student))
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, errors
    assert len({r["enrollment_id"] for r in results}) == 1
    assert len(enrollments(student)) == 1
    assert store.list_enrollments(None, student)["total"] == 1


def test_concurrent_duplicates_of_one_idempotency_key_write_once(student):
    store = MicroCourseDynamoDB()
    eid = store.start_enrollment(None, CODE, student)["enrollment_id"]
    results = run_threads(lambda i: store.submit_learning_item_response(None, eid, student, wp4.LI1, 1, idempotency_key="dup"))
    assert not [r for r in results if isinstance(r, Exception)], results
    assert Counter(bool(r.get("replayed")) for r in results)[False] == 1
    assert len({(r["is_correct"], r["learning_item_id"]) for r in results}) == 1
    events = [i for i in typed.query(CTX, t.student_pk(student), limit=200, sk_begins=f"ENROLL#{eid}#EVT#", models=[mc.LearnerMcevent]).items
              if i.event_type == "QUIZ_RESPONSE"]
    assert len(events) == 1


def test_concurrent_responses_to_different_items_lose_no_pointer(student):
    store = MicroCourseDynamoDB()
    eid = store.start_enrollment(None, CODE, student)["enrollment_id"]
    calls = [lambda: store.submit_learning_item_response(None, eid, student, wp4.LI1, 1),
             lambda: store.submit_learning_item_response(None, eid, student, wp4.LI2, 0),
             lambda: store.submit_activity_response(None, eid, student, wp4.ACT1, choice_index=0)]
    results = run_threads(lambda i: calls[i](), count=len(calls))
    assert not [r for r in results if isinstance(r, Exception)], results
    assert set(enrollments(student)[0].last_responses) == {wp4.LI1, wp4.LI2, wp4.ACT1}
    assert enrollments(student)[0].state_version == 1


def test_concurrent_advances_with_the_same_version_let_exactly_one_win(student):
    store = MicroCourseDynamoDB()
    eid = store.start_enrollment(None, CODE, student)["enrollment_id"]
    store.submit_learning_item_response(None, eid, student, wp4.LI1, 1)
    results = run_threads(lambda i: store.advance_enrollment(None, eid, student, 1, "CONTINUE"))
    winners = [r for r in results if isinstance(r, dict)]
    losers = [r for r in results if isinstance(r, courses.MicroCourseConflict)]
    assert len(winners) == 1 and len(losers) == THREADS - 1, results
    assert enrollments(student)[0].state_version == 2
