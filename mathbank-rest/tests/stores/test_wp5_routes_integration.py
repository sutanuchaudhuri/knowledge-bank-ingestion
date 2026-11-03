"""Concurrency of the WP5 routes area against the REAL `test` data-plane environment (requirement 71 WP5 gate).

Skipped unless MB_DDB_ENV=test (`make test-ddb-integration`). Never point this at `dev`. The content store is a small in-memory fake
(the `test` environment holds no content); every item the tests create is removed afterwards. Threads race for real:

* N learners' requests start the same route release at once -> exactly one open attempt, everybody else resumes it;
* N identical feedback submissions -> one report, one sentinel, every caller gets the same report;
* two reviewers resolve the same report at once -> exactly one wins, with one audit record (skipped without `mb-audit-test`);
* N registrations of the same agent session -> one link, one sentinel.
"""
from __future__ import annotations

import threading
import uuid

import pytest

from mathbank_rest import agent_transcripts as at
from mathbank_rest import stores
from mathbank_rest.models.manual.learner_routes import (
    AgentLinkItem,
    FeedbackItem,
    FeedbackOwner,
    RouteItem,
)
from mathbank_rest.stores import ddb as t
from mathbank_rest.stores import typed
from mathbank_rest.stores.learner.routes import RoutesDynamoDB

pytestmark = pytest.mark.ddb_integration
CTX = "learner"
THREADS = 8
RELEASE = str(uuid.uuid4())
PROBLEM = str(uuid.uuid4())
CODE = "ITEST_ROUTE_1"
NODE = {"taxonomy_node_id": "ITEST.NODE", "node_type": "SKILL", "name": "Integration"}


class FakeContent:
    """The content reads the routes area makes: one published route of two steps and one problem."""

    def find_published_route(self, code, *, conn=None):
        return {"route_release_id": RELEASE} if code == CODE else None

    def get_published_route(self, code, release_id, *, conn=None):
        return {"route_release_id": RELEASE} if code == CODE and str(release_id) == RELEASE else None

    def get_route_step_instruction(self, release_id, step, *, conn=None):
        return {"goal_text": f"GOAL{step}", "student_prompt": f"PROMPT{step}"} if step in (1, 2) else None

    def get_route_step_hint(self, release_id, step, level, *, conn=None):
        return f"H{step}.{level}" if step in (1, 2) else None

    def get_problem_by_code(self, code):
        return {"canonical_code": CODE, "statement_text": "statement"} if code == CODE else None

    def get_solution_dag(self, code):
        return {"problem_id": PROBLEM, "steps": [], "step_techniques": []}

    def get_problem_by_id(self, problem_id):
        return {"canonical_code": CODE} if str(problem_id) == PROBLEM else None


class OneSession:
    def __init__(self, user: str, session: str):
        self.key = ("mathbank_tutor", user, session)

    def available(self):
        return True

    def session_exists(self, app, user, session):
        return (app, user, session) == self.key


def _delete(ddb, pk: str, sk: str) -> None:
    ddb.delete_item(TableName=t.table_name(CTX), Key={"PK": {"S": pk}, "SK": {"S": sk}})


@pytest.fixture()
def student(real_env):
    sid, extra = str(uuid.uuid4()), []
    with stores.override_store("content", FakeContent()):
        yield sid, extra
    ddb, token, pk = t.client(), None, t.student_pk(sid)
    while True:
        page = t.query_page(CTX, pk, limit=100, next_token=token)
        for it in page["items"]:
            _delete(ddb, it["PK"], it["SK"])
            if it["type"] == "FEEDBACK":
                _delete(ddb, f"FEEDBACK#{it['feedback_id']}", "OWNER")
        token = page["next_token"]
        if not token:
            break
    for key in extra:
        _delete(ddb, *key)
    s3 = t.client("s3")
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=t.data_bucket(), Prefix=f"offload/learner/students/{sid}/"):
        for o in pg.get("Contents", []):
            s3.delete_object(Bucket=t.data_bucket(), Key=o["Key"])


def race(n: int, fn) -> list:
    barrier, out, errors = threading.Barrier(n), [None] * n, []

    def worker(i: int) -> None:
        try:
            barrier.wait(timeout=10)
            out[i] = fn(i)
        except Exception as exc:  # noqa: BLE001 - reported to the main thread
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=60)
    assert not errors, errors
    return out


def test_concurrent_starts_of_one_release_make_exactly_one_open_attempt(student):
    sid, _ = student
    store = RoutesDynamoDB()
    results = race(THREADS, lambda i: store.start_route_attempt(sid, CODE))
    assert len({r.view["route_attempt_id"] for r in results}) == 1
    assert sum(1 for r in results if r.created) == 1
    routes = typed.query(RouteItem, t.student_pk(sid), sk_begins="ROUTE#").items
    assert len(routes) == 1 and routes[0].status == "IN_PROGRESS"


def test_concurrent_identical_feedback_is_one_report(student):
    sid, _ = student
    store = RoutesDynamoDB()
    results = race(THREADS, lambda i: store.submit_feedback(sid, CODE, "Integration", "The same reason from every thread.", node=NODE))
    assert len({r["feedback_id"] for r in results}) == 1
    assert len(typed.query(FeedbackItem, t.student_pk(sid), sk_begins="FEEDBACK#").items) == 1


def test_concurrent_assist_with_one_version_has_one_winner(student):
    sid, _ = student
    store = RoutesDynamoDB()
    attempt = store.start_route_attempt(sid, CODE).view["route_attempt_id"]
    outcomes = race(THREADS, lambda i: _try(lambda: store.assist_route_attempt(sid, attempt, 1, 2, False)))
    assert sum(1 for o in outcomes if o == "ok") == 1 and sum(1 for o in outcomes if o == "conflict") == THREADS - 1
    assert store.get_owned_route_attempt(sid, attempt)["version"] == 2


def _try(fn) -> str:
    from mathbank_rest.step_runtime import StateVersionConflict

    try:
        fn()
        return "ok"
    except StateVersionConflict:
        return "conflict"


def test_two_reviewers_resolve_one_report_once(student):
    try:
        t.client().describe_table(TableName=t.table_name("audit"))
    except Exception:  # noqa: BLE001
        pytest.skip("mb-audit-test is not provisioned in this environment")
    sid, extra = student
    store = RoutesDynamoDB()
    fid = store.submit_feedback(sid, CODE, "Integration", "A report that two reviewers will race for.", node=NODE)["feedback_id"]
    owner = typed.require(FeedbackOwner, f"FEEDBACK#{fid}", "OWNER")
    assert str(owner.student_id) == sid
    results = race(2, lambda i: store.resolve_feedback(fid, "RESOLVED", f"Reviewer {i} decides this report.", "IRRELEVANT",
                                                       actor=f"staff:{i}"))
    assert sum(1 for r in results if r is not None) == 1
    audit = t.query_page("audit", f"ENTITY#FEEDBACK#{fid}")["items"]
    assert len(audit) == 1
    extra.append((audit[0]["PK"], audit[0]["SK"]))
    extra.append((f"RETRIEVAL_EXCLUSION#{NODE['taxonomy_node_id']}", f"PROBLEM#{PROBLEM}"))


def test_concurrent_link_registrations_make_one_link(student):
    sid, extra = student
    session = f"itest-{uuid.uuid4()}"
    saved = at.adk_sessions
    at.adk_sessions = OneSession(sid, session)
    try:
        store = RoutesDynamoDB()
        results = race(THREADS, lambda i: store.register_agent_link(sid, session, context={f"k{i}": i}))
        assert len({r["agent_session_link_id"] for r in results}) == 1 and sum(1 for r in results if r["created"]) == 1
        extra.append((f"UNIQUE#agent_session#mathbank_tutor#{session}", "UNIQUE"))
        link = typed.require(AgentLinkItem, t.student_pk(sid), f"AGENT#mathbank_tutor#{session}")
        assert link.GSI1PK == "AGENTLINKS"
        assert store.get_link_owner("mathbank_tutor", session) == sid
    finally:
        at.adk_sessions = saved
