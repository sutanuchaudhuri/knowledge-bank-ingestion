"""WP5 routes area of the learner store: route attempts, feedback and agent links on moto (no Postgres, no AWS).

Content comes from the moto ``mb-content`` read model seeded with the WP4 helpers; the agent-session store (``agent_sessions``
schema, WP9) is replaced by an in-memory fake behind its single seam. The DynamoDB store is compared with an in-memory oracle of
today's PostgreSQL behaviour through the real routes (``tests/parity``).
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from parity_harness import ParityCase, assert_parity
from test_wp4_pedagogy import (
    CODE,
    EXPECTED,
    PROBLEM_ID,
    problem_item,
    seed_dag,
    seed_route,
    taxnode,
    uid,
)

from mathbank_rest import agent_transcripts as at
from mathbank_rest import route_runtime, security, stores
from mathbank_rest.db import postgres, topic_pedagogy
from mathbank_rest.main import app
from mathbank_rest.models.ddb.learner import LearnerGap, LearnerProblem
from mathbank_rest.models.manual.learner_routes import (
    AgentLinkItem,
    FeedbackItem,
    FeedbackOwner,
    RetrievalExclusion,
    RouteItem,
    UniqueAgentSession,
    UniqueFeedback,
    UniqueOpenRoute,
)
from mathbank_rest.security import Actor
from mathbank_rest.step_runtime import InvalidTransition, NotFound, StateVersionConflict
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.errors import (
    ConditionFailed,
    IdempotencyKeyReused,
    InvalidToken,
    StoreFrozen,
    ValidationFailed,
)
from mathbank_rest.stores.learner import DynamoDBLearnerStore, PostgresLearnerStore

A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
RID = uid(1)
RCODE = "PRASOLOV_PGV1_11"          # the route start body only accepts [A-Z0-9_] codes
RRID = uid(9)
NODE = {"taxonomy_node_id": "SK1", "node_type": "SKILL", "name": "Angle chase"}
WHEN = dt.datetime(2026, 3, 1, 12, 0, tzinfo=dt.UTC)
REASON = "The statement is about another theorem."


class Boom:
    def connect(self, *a, **k):
        raise AssertionError("the DynamoDB learner store touched Postgres")

    begin = connect


class FakeAdk:
    """The ADK session store behind ``agent_transcripts.adk_sessions`` (PostgreSQL ``agent_sessions`` until WP9)."""

    def __init__(self):
        self.sessions: dict[tuple[str, str, str], list[dict]] = {}

    def add(self, user: str, session: str, *texts: str, app: str = "mathbank_tutor") -> None:
        self.sessions[(app, user, session)] = [
            {"timestamp": f"2026-03-01T12:00:0{i}", "event_data": {"author": "user" if i % 2 == 0 else app,
                                                                   "content": {"parts": [{"text": t}]}}}
            for i, t in enumerate(texts)]

    def available(self) -> bool:
        return True

    def session_exists(self, app, user, session) -> bool:
        return (app, user, session) in self.sessions

    def facts(self, keys):
        return {k: {"session_updated_at": WHEN.replace(tzinfo=None) + dt.timedelta(minutes=len(self.sessions[k])),
                    "event_count": len(self.sessions[k]),
                    "first_message": self.sessions[k][0]["event_data"]["content"]["parts"][0]["text"] if self.sessions[k] else None}
                for k in keys if k in self.sessions}

    def unlinked_count(self, linked) -> int:
        return sum(1 for k in self.sessions if k not in linked)

    def owners(self, app, session):
        return [u for (a, u, s) in self.sessions if a == app and s == session]

    def body(self, app, user, session):
        events = self.sessions.get((app, user, session))
        return ({"create_time": WHEN.replace(tzinfo=None), "update_time": WHEN.replace(tzinfo=None)} if events is not None else None,
                events or [])


@pytest.fixture()
def adk(monkeypatch):
    fake = FakeAdk()
    monkeypatch.setattr(at, "adk_sessions", fake)
    return fake


@pytest.fixture()
def no_postgres(monkeypatch):
    for module in (postgres, route_runtime, topic_pedagogy):
        monkeypatch.setattr(module, "engine", Boom())


def _create_audit_table(client) -> None:
    client.create_table(
        TableName="mb-audit-ut",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in
                              ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK", "GSI3PK", "GSI3SK")],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[{"IndexName": g, "KeySchema": [{"AttributeName": f"{g}PK", "KeyType": "HASH"},
                                                               {"AttributeName": f"{g}SK", "KeyType": "RANGE"}],
                                 "Projection": {"ProjectionType": "ALL"}} for g in ("GSI1", "GSI2", "GSI3")],
        BillingMode="PAY_PER_REQUEST")


@pytest.fixture()
def env(content_table, no_postgres, adk):
    """The DynamoDB learner store over moto with a published route, a problem with its solution DAG and one taxonomy skill."""
    _create_audit_table(content_table)
    seed_route(RID, leak=True)
    typed.put(problem_item())
    seed_route(RRID, code=RCODE)
    seed_dag()
    typed.put(taxnode("SK1", "Angle chase", "SKILL"))
    store = DynamoDBLearnerStore()
    with stores.override_store("content", DynamoDBContentStore()), stores.override_store("learner", store):
        yield store


def pk(sid: str) -> str:
    return toolkit.student_pk(sid)


def route_item(sid: str, view: dict) -> RouteItem:
    return typed.require(RouteItem, pk(sid), f"ROUTE#{view['route_attempt_id']}")


# ---------------------------------------------------------------------------------------------------- route attempts

def test_start_creates_attempt_and_sentinel_then_resumes(env):
    first = env.start_route_attempt(A, CODE)
    view = first.view
    assert first.created and not first.replayed
    assert view == {"route_attempt_id": view["route_attempt_id"], "route_release_id": RID, "version": 1, "current_step": 1,
                    "status": "active", "goal": "GOAL1", "student_prompt": "PROMPT1", "tutor_explained_steps": [],
                    "mastery_recorded": False}
    assert EXPECTED not in json.dumps(view)                                 # WP1: never in a learner payload
    item = route_item(A, view)
    assert item.status == "IN_PROGRESS" and item.version == 1 and item.problem_code == CODE and item.finished_at is None
    assert str(typed.require(UniqueOpenRoute, pk(A), f"UNIQUE#open_route#{RID}").route_attempt_id) == view["route_attempt_id"]

    again = env.start_route_attempt(A, CODE)
    assert not again.created and again.view == view                        # resumed, not a second cursor (LRN-F21)
    assert not env.start_route_attempt(A, CODE, RID).created               # pinned to the same release: same attempt
    other = env.start_route_attempt(B, CODE)
    assert other.created and other.view["route_attempt_id"] != view["route_attempt_id"]
    with pytest.raises(NotFound, match="No reviewed published route"):
        env.start_route_attempt(A, "NO_SUCH_PROBLEM")
    with pytest.raises(NotFound):
        env.start_route_attempt(A, CODE, uid(77))                          # not a release of this problem


def test_assist_hints_advances_and_finishes_the_attempt(env):
    view = env.start_route_attempt(A, CODE).view
    attempt = view["route_attempt_id"]
    hint = env.assist_route_attempt(A, attempt, 1, 2, False)
    assert hint["hint"] == "H1.2" and hint["version"] == 2 and hint["current_step"] == 1
    assert hint["hint_level"] == 2 and hint["source"] == "published-hint-library" and hint["tutor_explained_steps"] == []
    assert EXPECTED not in json.dumps(hint)
    with pytest.raises(StateVersionConflict):
        env.assist_route_attempt(A, attempt, 1, 2, False)                  # stale client version
    with pytest.raises(InvalidTransition):
        env.assist_route_attempt(A, attempt, 2, 3, True)                   # advance only at level 5
    advanced = env.assist_route_attempt(A, attempt, 2, 5, True)
    assert advanced["current_step"] == 2 and advanced["tutor_explained_steps"] == [1] and advanced["version"] == 3
    assert advanced["goal"] == "GOAL2" and advanced["status"] == "active"
    done = env.assist_route_attempt(A, attempt, 3, 5, True)
    assert done["status"] == "finished" and done["goal"] is None and done["student_prompt"] is None
    assert done["tutor_explained_steps"] == [1, 2] and done["version"] == 4
    item = route_item(A, view)
    assert item.status == "FINISHED" and item.finished_at is not None and item.version == 4
    assert typed.get(UniqueOpenRoute, pk(A), f"UNIQUE#open_route#{RID}") is None   # a new attempt may start
    with pytest.raises(NotFound, match="No reviewed asset"):
        env.assist_route_attempt(A, attempt, 4, 1, False)                  # nothing left to hint
    assert env.get_route_attempt_view(A, attempt)["status"] == "finished"
    fresh = env.start_route_attempt(A, CODE)
    assert fresh.created and fresh.view["route_attempt_id"] != attempt


def test_route_attempts_belong_to_their_learner(env):
    attempt = env.start_route_attempt(A, CODE).view["route_attempt_id"]
    assert env.get_route_attempt(B, attempt) is None and env.get_route_attempt(A, "not-a-uuid") is None
    for call in (lambda: env.get_route_attempt_view(B, attempt), lambda: env.get_owned_route_attempt(B, attempt),
                 lambda: env.assist_route_attempt(B, attempt, 1, 1, False), lambda: env.get_route_attempt_view(A, str(uuid.uuid4()))):
        with pytest.raises(NotFound):
            call()
    assert env.get_owned_route_attempt(A, attempt)["version"] == 1
    assert route_item(A, {"route_attempt_id": attempt}).version == 1       # B's assist changed nothing


def test_open_route_race_resumes_instead_of_duplicating(env, monkeypatch):
    winner = env.start_route_attempt(A, CODE).view
    real, calls = env._route_open, []

    def blind_once(student_id, release_id):          # the loser read before the winner committed
        calls.append(1)
        return (None, None) if len(calls) == 1 else real(student_id, release_id)

    monkeypatch.setattr(env, "_route_open", blind_once)
    loser = env.start_route_attempt(A, CODE)
    assert len(calls) == 2 and not loser.created and loser.view == winner
    assert len(list(typed.query(RouteItem, pk(A), sk_begins="ROUTE#").items)) == 1


def test_stale_sentinel_is_taken_over(env):
    view = env.start_route_attempt(A, CODE).view
    toolkit.client().delete_item(TableName=toolkit.table_name("learner"),
                                 Key={"PK": {"S": pk(A)}, "SK": {"S": f"ROUTE#{view['route_attempt_id']}"}})
    fresh = env.start_route_attempt(A, CODE)
    assert fresh.created and fresh.view["route_attempt_id"] != view["route_attempt_id"]
    marker = typed.require(UniqueOpenRoute, pk(A), f"UNIQUE#open_route#{RID}")
    assert str(marker.route_attempt_id) == fresh.view["route_attempt_id"]


def test_start_and_assist_are_idempotent_per_key(env):
    first = env.start_route_attempt(A, CODE, idempotency_key="start-1")
    replay = env.start_route_attempt(A, CODE, idempotency_key="start-1")
    assert replay.replayed and replay.created == first.created and replay.view == first.view
    attempt = first.view["route_attempt_id"]
    one = env.assist_route_attempt(A, attempt, 1, 2, False, idempotency_key="assist-1")
    two = env.assist_route_attempt(A, attempt, 1, 2, False, idempotency_key="assist-1")      # redelivery, not a 409
    assert two == one and route_item(A, first.view).version == 2
    with pytest.raises(IdempotencyKeyReused):
        env.assist_route_attempt(A, attempt, 1, 3, False, idempotency_key="assist-1")
    done = env.assist_route_attempt(A, attempt, 2, 5, True, idempotency_key="assist-2")
    assert done["current_step"] == 2
    again = env.assist_route_attempt(A, attempt, 2, 5, True, idempotency_key="assist-2")
    assert again == done and route_item(A, first.view).tutor_explained_steps == [1]   # the step was not advanced twice
    finished = env.assist_route_attempt(A, attempt, 3, 5, True, idempotency_key="assist-3")
    assert env.assist_route_attempt(A, attempt, 3, 5, True, idempotency_key="assist-3") == finished
    assert finished["goal"] is None and finished["student_prompt"] is None          # nullable keys survive the receipt


def test_list_route_attempts_filters_pages_and_rejects_foreign_tokens(env):
    seed_route(uid(2))
    seed_route(uid(3))
    ids = [env.start_route_attempt(A, CODE, release).view["route_attempt_id"] for release in (RID, uid(2), uid(3))]
    env.start_route_attempt(B, CODE)
    env.assist_route_attempt(A, ids[0], 1, 5, True)
    env.assist_route_attempt(A, ids[0], 2, 5, True)                                  # first attempt finished
    first = env.list_route_attempts(A, limit=2)
    assert [i["route_attempt_id"] for i in first["items"]] == [ids[2], ids[1]] and first["next_token"]
    second = env.list_route_attempts(A, limit=2, next_token=first["next_token"])
    assert [i["route_attempt_id"] for i in second["items"]] == [ids[0]] and second["next_token"] is None
    assert set(first["items"][0]) == {"route_attempt_id", "route_release_id", "problem_code", "status", "current_step",
                                      "tutor_explained_steps", "version", "created_at", "updated_at", "finished_at"}
    assert second["items"][0]["status"] == "FINISHED" and second["items"][0]["finished_at"] is not None
    assert [i["route_attempt_id"] for i in env.list_route_attempts(A, status="FINISHED")["items"]] == [ids[0]]
    assert [i["route_attempt_id"] for i in env.list_route_attempts(A, route_release_id=uid(2))["items"]] == [ids[1]]
    assert len(env.list_route_attempts(B)["items"]) == 1
    for token, user in ((first["next_token"], B), (first["next_token"][:-3] + "abc", A)):
        with pytest.raises(InvalidToken):
            env.list_route_attempts(user, limit=2, next_token=token)
    with pytest.raises(InvalidToken):
        env.list_route_attempts(A, status="FINISHED", limit=2, next_token=first["next_token"])   # token bound to its filters


def test_a_frozen_store_serves_reads_and_rejects_writes(env):
    attempt = env.start_route_attempt(A, CODE).view["route_attempt_id"]
    frozen = stores.FrozenProxy("learner", env)
    assert frozen.get_route_attempt_view(A, attempt)["current_step"] == 1
    assert frozen.list_route_attempts(A)["items"] and frozen.list_my_feedback(A)["items"] == []
    for call in (lambda: frozen.start_route_attempt(A, CODE), lambda: frozen.assist_route_attempt(A, attempt, 1, 1, False),
                 lambda: frozen.submit_feedback(A, CODE, "t", REASON), lambda: frozen.resolve_feedback(uid(1), "RESOLVED", "x" * 12),
                 lambda: frozen.withdraw_feedback(A, uid(1)), lambda: frozen.register_agent_link(A, "s"),
                 lambda: frozen.unlink_agent_session(A, "s")):
        with pytest.raises(StoreFrozen):
            call()


# ---------------------------------------------------------------------------------------------------- feedback

def submit(store, sid=A, reason=REASON, topic="Angle chase", **kw):
    return store.submit_feedback(sid, CODE, topic, reason, node=NODE, **kw)


def test_submit_feedback_writes_report_sentinel_owner_and_audit_snapshot(env):
    out = submit(env)
    fid = out["feedback_id"]
    assert set(out) == {"feedback_id", "status", "created_at", "audit"} and out["status"] == "PENDING"
    assert out["audit"]["problem_code"] == CODE and out["audit"]["requested_node_id"] == "SK1"
    assert out["audit"]["published_step_count"] == 3 and out["audit"]["supporting_step_ids"] == ["st1"]
    assert out["audit"]["structural_validation"] is None and out["audit"]["retrieval_score"] is None   # PG jsonb keeps the nulls
    item = typed.require(FeedbackItem, pk(A), f"FEEDBACK#{fid}")
    assert (item.status, item.version, item.GSI1PK, str(item.problem_id), item.requested_node_id) == (
        "PENDING", 1, "FEEDBACK#PENDING", PROBLEM_ID, "SK1")
    assert item.GSI1SK.endswith(f"#{fid}") and item.reviewed_by is None and item.review_note is None
    assert str(typed.require(FeedbackOwner, f"FEEDBACK#{fid}", "OWNER").student_id) == A
    assert typed.query(UniqueFeedback, pk(A), sk_begins="UNIQUE#feedback#").items[0].feedback_id.hex == fid.replace("-", "")


def test_duplicate_report_is_the_existing_report_and_a_new_reason_is_a_new_one(env):
    first = submit(env)
    again = submit(env, reason=f"  {REASON}  ")             # trimmed like the PostgreSQL UNIQUE key
    assert again["feedback_id"] == first["feedback_id"] and again["audit"] == first["audit"]
    other = submit(env, reason="A different wording of the problem.")
    assert other["feedback_id"] != first["feedback_id"]
    assert submit(env, sid=B)["feedback_id"] not in {first["feedback_id"], other["feedback_id"]}
    assert len(typed.query(FeedbackItem, pk(A), sk_begins="FEEDBACK#").items) == 2
    assert env.submit_feedback(A, "NO_SUCH", "Angle chase", REASON, node=NODE) is None


def test_feedback_is_idempotent_per_key_and_a_concurrent_duplicate_converges(env, monkeypatch):
    one = submit(env, idempotency_key="fb-1")
    assert submit(env, idempotency_key="fb-1") == one
    with pytest.raises(IdempotencyKeyReused):
        submit(env, reason="Something else entirely here.", idempotency_key="fb-1")
    real = typed.get
    seen = []

    def blind_once(model, *a, **k):                 # the loser looked before the winner committed
        if model is UniqueFeedback and not seen:
            seen.append(1)
            return None
        return real(model, *a, **k)

    monkeypatch.setattr(typed, "get", blind_once)
    race = submit(env)
    assert race["feedback_id"] == one["feedback_id"] and len(typed.query(FeedbackItem, pk(A), sk_begins="FEEDBACK#").items) == 1


def test_list_my_feedback_is_owner_scoped_newest_first_and_paged(env):
    ids = [submit(env, reason=f"Report number {n} about the topic.")["feedback_id"] for n in range(3)]
    submit(env, sid=B)
    page = env.list_my_feedback(A, limit=2)
    assert [i["feedback_id"] for i in page["items"]] == [ids[2], ids[1]] and page["next_token"]
    assert set(page["items"][0]) == {"feedback_id", "problem_code", "topic", "reason", "status", "created_at", "review_note",
                                     "reviewed_at", "retrieval_verdict", "error_kind"}      # no audit snapshot for the learner
    assert page["items"][0]["problem_code"] == CODE
    rest = env.list_my_feedback(A, limit=2, next_token=page["next_token"])
    assert [i["feedback_id"] for i in rest["items"]] == [ids[0]] and rest["next_token"] is None
    with pytest.raises(InvalidToken):
        env.list_my_feedback(B, limit=2, next_token=page["next_token"])
    assert len(env.list_my_feedback(B)["items"]) == 1


def test_withdraw_dismisses_an_own_pending_report_once(env):
    fid = submit(env)["feedback_id"]
    with pytest.raises(NotFound):
        env.withdraw_feedback(B, fid)
    assert env.withdraw_feedback(A, fid) == {"feedback_id": fid, "status": "DISMISSED"}
    item = typed.require(FeedbackItem, pk(A), f"FEEDBACK#{fid}")
    assert item.status == "DISMISSED" and item.review_note == "withdrawn by learner" and item.reviewed_at and item.GSI1PK == "FEEDBACK#DISMISSED"
    with pytest.raises(InvalidTransition):
        env.withdraw_feedback(A, fid)
    with pytest.raises(NotFound):
        env.withdraw_feedback(A, str(uuid.uuid4()))
    assert env.resolve_feedback(fid, "RESOLVED", "Reviewing a withdrawn report.") is None       # no longer reviewable
    assert [i["feedback_id"] for i in env.list_feedback_queue(10, 0)["items"]] == [fid]


def audit_items(fid: str) -> list[dict]:
    return toolkit.query_page("audit", f"ENTITY#FEEDBACK#{fid}")["items"]


def test_review_records_reviewer_audit_and_exclusion_in_one_transaction(env):
    fid = submit(env)["feedback_id"]
    out = env.resolve_feedback(fid, "RESOLVED", "  Reviewed the source evidence.  ", "IRRELEVANT", "RETRIEVAL", actor="staff:42")
    assert out == {"feedback_id": fid, "status": "RESOLVED", "review_note": "Reviewed the source evidence.",
                   "retrieval_verdict": "IRRELEVANT", "error_kind": "RETRIEVAL"}
    item = typed.require(FeedbackItem, pk(A), f"FEEDBACK#{fid}")
    assert (item.status, item.version, item.reviewed_by, item.GSI1PK) == ("RESOLVED", 2, "staff:42", "FEEDBACK#RESOLVED")
    assert item.reviewed_at is not None and item.retrieval_verdict == "IRRELEVANT"
    [record] = audit_items(fid)                                                     # LRN-F22 / LRN-S10
    assert (record["action"], record["actor_id"], record["actor_type"], record["entity_type"]) == (
        "FEEDBACK_REVIEWED", "staff:42", "ADMIN", "FEEDBACK")
    assert record["GSI1PK"] == "ACTOR#ADMIN#staff:42" and record["after_state"]["status"] == "RESOLVED" and record["ttl"] > 0
    exclusion = typed.require(RetrievalExclusion, "RETRIEVAL_EXCLUSION#SK1", f"PROBLEM#{PROBLEM_ID}")
    assert exclusion.feedback_ids == [fid] and exclusion.problem_code == CODE
    assert env.list_excluded_problem_codes("SK1") == [CODE] and env.list_excluded_problem_codes("SK2") == []
    assert env.resolve_feedback(fid, "RESOLVED", "A second review is not permitted.") is None     # already reviewed
    assert env.resolve_feedback(str(uuid.uuid4()), "RESOLVED", "Reviewing an unknown report.") is None
    assert env.resolve_feedback("not-a-uuid", "RESOLVED", "Reviewing an unknown report.") is None
    second = submit(env, sid=B)["feedback_id"]
    env.resolve_feedback(second, "RESOLVED", "Same verdict from another learner.", "IRRELEVANT", actor="staff:42")
    assert sorted(typed.require(RetrievalExclusion, "RETRIEVAL_EXCLUSION#SK1", f"PROBLEM#{PROBLEM_ID}").feedback_ids) == sorted([fid, second])


def test_dismissal_and_relevant_verdicts_do_not_exclude_the_problem(env):
    dismissed = submit(env)["feedback_id"]
    relevant = submit(env, reason="Another sufficiently long reason.")["feedback_id"]
    assert env.resolve_feedback(dismissed, "DISMISSED", "Not actionable, no change.", actor=None)["status"] == "DISMISSED"
    env.resolve_feedback(relevant, "RESOLVED", "The problem is relevant after all.", "RELEVANT", "INSUFFICIENT_EVIDENCE", actor="staff:1")
    assert env.list_excluded_problem_codes("SK1") == []
    assert audit_items(dismissed)[0]["actor_type"] == "SYSTEM" and audit_items(dismissed)[0]["actor_id"] == "system"


def test_a_failing_audit_write_rolls_the_whole_review_back(env, monkeypatch):
    fid = submit(env)["feedback_id"]
    owner = typed.require(FeedbackOwner, f"FEEDBACK#{fid}", "OWNER")
    monkeypatch.setattr(type(env), "_feedback_audit_op", staticmethod(lambda *a, **k: toolkit.Check(
        "learner", pk(str(owner.student_id)), "NO-SUCH-ITEM", toolkit.EXISTS, ConditionFailed("audit unavailable"))))
    assert env.resolve_feedback(fid, "RESOLVED", "Reviewed the source evidence.", "IRRELEVANT", actor="staff:42") is None
    item = typed.require(FeedbackItem, pk(A), f"FEEDBACK#{fid}")
    assert item.status == "PENDING" and item.version == 1 and item.reviewed_by is None
    assert typed.get(RetrievalExclusion, "RETRIEVAL_EXCLUSION#SK1", f"PROBLEM#{PROBLEM_ID}") is None and audit_items(fid) == []


def test_two_reviewers_cannot_both_win(env, monkeypatch):
    fid = submit(env)["feedback_id"]
    stale = typed.require(FeedbackItem, pk(A), f"FEEDBACK#{fid}")
    assert env.resolve_feedback(fid, "RESOLVED", "First reviewer decides now.", "IRRELEVANT", actor="staff:1")["status"] == "RESOLVED"
    real = typed.get
    with monkeypatch.context() as patch:
        patch.setattr(typed, "get", lambda model, *a, **k: stale if model is FeedbackItem else real(model, *a, **k))
        assert env.resolve_feedback(fid, "DISMISSED", "Second reviewer too late.", actor="staff:2") is None   # version CAS -> 409
    assert typed.require(FeedbackItem, pk(A), f"FEEDBACK#{fid}").reviewed_by == "staff:1" and len(audit_items(fid)) == 1


def test_admin_queue_puts_pending_first_counts_related_reports_and_filters(env):
    r1 = submit(env, reason="First report about this topic.")["feedback_id"]
    r2 = submit(env, reason="Second report about this topic.")["feedback_id"]
    r3 = submit(env, sid=B, reason="Third report from another learner.")["feedback_id"]
    env.resolve_feedback(r1, "RESOLVED", "Reviewed and classified.", "IRRELEVANT", "RETRIEVAL", actor="staff:1")
    queue = env.list_feedback_queue(25, 0)
    assert [i["feedback_id"] for i in queue["items"]] == [r3, r2, r1] and queue["total"] == 3 and (queue["limit"], queue["offset"]) == (25, 0)
    assert {i["related_report_count"] for i in queue["items"]} == {3}
    assert set(queue["items"][0]) == {"feedback_id", "canonical_code", "topic", "reason", "status", "created_at", "review_note",
                                      "reviewed_at", "audit", "retrieval_verdict", "error_kind", "related_report_count"}
    assert queue["items"][2]["review_note"] == "Reviewed and classified." and queue["items"][0]["canonical_code"] == CODE
    assert [i["feedback_id"] for i in env.list_feedback_queue(1, 1)["items"]] == [r2]
    assert [i["feedback_id"] for i in env.list_feedback_queue(25, 0, status="RESOLVED")["items"]] == [r1]
    assert [i["feedback_id"] for i in env.list_feedback_queue(25, 0, student_id=B)["items"]] == [r3]
    assert [i["feedback_id"] for i in env.list_feedback_queue(25, 0, q="SECOND REPORT")["items"]] == [r2]
    assert env.list_feedback_queue(25, 0, q="nothing like it")["total"] == 0


def test_retrieval_examples_are_reviewed_classified_reports_newest_first(env):
    a = submit(env, reason="First report about this topic.")["feedback_id"]
    b = submit(env, reason="Second report about this topic.")["feedback_id"]
    c = submit(env, reason="Third report about this topic.")["feedback_id"]
    env.resolve_feedback(a, "RESOLVED", "Evidence says irrelevant.", "IRRELEVANT", "METADATA", actor="staff:1")
    env.resolve_feedback(b, "RESOLVED", "Evidence says relevant.", "RELEVANT", "UNCLASSIFIED", actor="staff:1")
    env.resolve_feedback(c, "RESOLVED", "Resolved but not classified.", actor="staff:1")      # UNCLASSIFIED: not an example
    examples = env.list_retrieval_examples(10)
    assert [e["review_reference"] for e in examples] == [b, a]
    assert set(examples[0]) == {"query", "canonical_code", "retrieval_verdict", "error_kind", "reason", "reviewed_at", "review_reference"}
    assert examples[0]["query"] == "Angle chase" and examples[0]["reason"] == "Evidence says relevant."
    assert len(env.list_retrieval_examples(1)) == 1


def test_topic_practice_state_and_exclusion_come_from_mb_learner(env, monkeypatch):
    typed.put(LearnerProblem(PK=pk(A), SK=f"PROBLEM#{PROBLEM_ID}", first_attempted_at=WHEN, outcome_count=1, problem_id=PROBLEM_ID,
                             student_id=A))
    gap = {"confidence": 0.5, "created_at": WHEN, "failure_location": "L", "failure_mode": "M", "gap_diagnosis_id": uid(5), "rank": 1,
           "solution_step_id": "st1", "solve_attempt_id": uid(6), "student_id": A, "target_concept_id": "C1", "target_label": "x",
           "target_skill_node_id": uid(7), "target_subconcept_id": "SC1"}
    typed.put(LearnerGap(PK=pk(A), SK=f"GAP#{uid(10)}", knowledge_gap_id=uid(10), status="UNRESOLVED", target_skill_id="SK1", **gap))
    typed.put(LearnerGap(PK=pk(A), SK=f"GAP#{uid(11)}", knowledge_gap_id=uid(11), status="RESOLVED", target_skill_id="SK9", **gap))
    assert env.get_topic_learner_state(A) == {"exposed_codes": [CODE], "gap_skill_ids": ["SK1"]}
    assert env.get_topic_learner_state(B) == {"exposed_codes": [], "gap_skill_ids": []}

    fid = submit(env)["feedback_id"]
    env.resolve_feedback(fid, "RESOLVED", "Evidence says irrelevant.", "IRRELEVANT", actor="staff:1")
    monkeypatch.setattr(topic_pedagogy, "load_profile", lambda version: {"minimum_confidence": 0.0})
    monkeypatch.setattr(topic_pedagogy, "rank_candidates", lambda cands, **kw: cands)

    class Content:
        def list_taxonomy_nodes(self, types):
            return [{"taxonomy_node_id": "SK1", "name": "Angle chase", "node_type": "SKILL"}]

        def get_taxonomy_nodes(self, ids):
            return {"SK1": NODE}

        def get_problem_by_id(self, problem_id):
            return {"canonical_code": CODE} if str(problem_id) == PROBLEM_ID else None

        def list_topic_candidates(self, node_id, *, limit=100):
            return [{"canonical_code": c, "confidence": 0.5, "difficulty": 2, "skill_ids": [], "structure_key": c}
                    for c in (CODE, "OTHER_1")]

    with stores.override_store("content", Content()):
        result = topic_pedagogy.topic_candidates("angle chase", student_id=uuid.UUID(A))
    assert [c["canonical_code"] for c in result["candidates"]] == ["OTHER_1"]        # the reviewed-irrelevant problem is gone
    assert result["candidates"][0]["gap_skill_ids"] == ["SK1"] and result["candidates"][0]["exposure_known"] is True


def test_feedback_models_enforce_the_review_pairing_rules():
    from mathbank_rest.stores.errors import ItemSchemaError

    base = {"PK": pk(A), "SK": f"FEEDBACK#{uid(1)}", "student_id": A, "feedback_id": uid(1), "problem_id": uid(2), "topic": "t",
            "reason": REASON, "created_at": WHEN, "version": 1, "audit_snapshot": {}}
    assert FeedbackItem(**base, status="PENDING").status == "PENDING"
    bad = ({"status": "PENDING", "review_note": "A review note here."}, {"status": "PENDING", "retrieval_verdict": "IRRELEVANT"},
           {"status": "RESOLVED"}, {"status": "RESOLVED", "review_note": "A review note here."},
           {"status": "DISMISSED", "reviewed_at": WHEN}, {"status": "DONE"}, {"status": "PENDING", "error_kind": "OTHER"})
    for extra in bad:
        with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError or ItemSchemaError, both mean "refused"
            FeedbackItem(**base, **extra)
    ok = FeedbackItem(**base, status="RESOLVED", review_note="A review note here.", reviewed_at=WHEN, retrieval_verdict="IRRELEVANT")
    assert ok.to_item()["status"] == "RESOLVED"
    assert ItemSchemaError  # the typed layer raises it on stored drift


# ---------------------------------------------------------------------------------------------------- agent links

def test_register_link_is_idempotent_merges_context_and_guards_the_owner(env, adk):
    adk.add(A, "s1", "What is the power of a point?", "PA * PB")
    adk.add(B, "s1", "someone else's session with the same id")
    first = env.register_agent_link(A, "s1", surface="SOLVE_WORKSPACE", context={"problem_code": CODE})
    assert first["created"] is True and first["agent_session_id"] == "s1" and first["surface"] == "SOLVE_WORKSPACE"
    assert first["agent_app_name"] == "mathbank_tutor" and set(first) == {"agent_session_link_id", "created", "agent_session_id",
                                                                       "agent_app_name", "surface"}
    again = env.register_agent_link(A, "s1", context={"solve_attempt_id": uid(3)})
    assert again["created"] is False and again["agent_session_link_id"] == first["agent_session_link_id"]
    link = typed.require(AgentLinkItem, pk(A), "AGENT#mathbank_tutor#s1")
    assert link.context == {"problem_code": CODE, "solve_attempt_id": uid(3)} and link.GSI1PK == "AGENTLINKS"
    assert str(typed.require(UniqueAgentSession, "UNIQUE#agent_session#mathbank_tutor#s1", "UNIQUE").student_id) == A
    with pytest.raises(at.Conflict):                    # the ADK session exists for B too, but A owns the link
        env.register_agent_link(B, "s1")
    with pytest.raises(at.NotFound):                    # a session nobody created under this identity
        env.register_agent_link(B, "missing")
    with pytest.raises(at.TranscriptError):
        env.register_agent_link(A, "s1", surface="EMAIL")
    with pytest.raises(ValidationFailed):
        env.register_agent_link(A, "bad#id")


def test_link_registration_race_converges(env, adk, monkeypatch):
    adk.add(A, "s1", "hello")
    real = typed.get
    seen = []

    def blind_once(model, *a, **k):                      # a concurrent registration commits between our read and write
        if model is UniqueAgentSession and not seen:
            seen.append(1)
            env.register_agent_link(A, "s1")
            return None
        return real(model, *a, **k)

    monkeypatch.setattr(typed, "get", blind_once)
    out = env.register_agent_link(A, "s1")
    assert out["created"] is False and len(typed.query(AgentLinkItem, pk(A), sk_begins="AGENT#").items) == 1


def test_owner_lookup_and_unlink(env, adk):
    adk.add(A, "s1", "hello")
    env.register_agent_link(A, "s1", context={"problem_code": CODE})
    link = env.get_agent_link("mathbank_tutor", "s1")
    assert link["student_id"] == A and link["agent_user_id"] == A and link["surface"] == "HOME_CHAT" and link["context"] == {"problem_code": CODE}
    assert env.get_link_owner("mathbank_tutor", "s1") == A and env.get_link_owner("mathbank_tutor", "nope") is None
    assert env.get_agent_link("mathbank_tutor", "nope") is None and env.get_agent_link("mathbank_tutor", "a#b") is None
    assert env.unlink_agent_session(B, "s1") is False and env.get_link_owner("mathbank_tutor", "s1") == A      # not theirs
    assert env.unlink_agent_session(A, "s1") is True and env.unlink_agent_session(A, "s1") is False
    assert env.get_link_owner("mathbank_tutor", "s1") is None and env.list_student_sessions(A) == []
    adk.add(B, "s1", "now B's session")
    assert env.register_agent_link(B, "s1")["created"] is True                 # the sentinel went with the link


def test_session_lists_are_owner_scoped_ordered_and_shaped_like_the_sql(env, adk):
    adk.add(A, "s1", "first conversation")
    adk.add(A, "s2", "second conversation", "answer", "follow up")
    adk.add(B, "s3", "b's conversation")
    adk.add(B, "unlinked", "never linked")
    for student, session in ((A, "s1"), (A, "s2"), (B, "s3")):
        env.register_agent_link(student, session)
    mine = env.list_student_sessions(A)
    assert [m["agent_session_id"] for m in mine] == ["s2", "s1"]                # most recent ADK activity first
    assert set(mine[0]) == {"agent_session_link_id", "agent_app_name", "agent_session_id", "agent_user_id", "student_id", "email",
                            "surface", "context", "created_at", "last_seen_at", "session_updated_at", "event_count", "preview",
                            "session_missing"}
    assert mine[0]["event_count"] == 3 and mine[0]["preview"] == "second conversation" and mine[0]["session_missing"] is False
    assert mine[0]["session_updated_at"].endswith("+00:00") and len(env.list_student_sessions(A, 1)) == 1
    assert env.list_student_sessions(uuid.uuid4()) == []
    everyone = env.list_all_sessions()
    assert len(everyone["linked"]) == 3 and everyone["unlinked_count"] == 1 and "next_token" not in everyone
    assert [m["agent_session_id"] for m in env.list_all_sessions(A)["linked"]] == ["s2", "s1"]       # by student uuid
    first = env.list_all_sessions(limit=2)
    assert len(first["linked"]) == 2 and first["next_token"]
    rest = env.list_all_sessions(limit=2, next_token=first["next_token"])
    assert len(rest["linked"]) == 1 and "next_token" not in rest
    with pytest.raises(InvalidToken):
        env.list_all_sessions(A, limit=2, next_token=first["next_token"])         # bound to its filter
    with pytest.raises(InvalidToken):
        env.list_all_sessions(limit=2, next_token=first["next_token"][:-2] + "zz")


def test_transcripts_are_read_through_the_link_ownership(env, adk):
    adk.add(A, "s1", "What is the power of a point?", "PA times PB.")
    env.register_agent_link(A, "s1", context={"problem_code": CODE})
    mine = at.read_transcript("s1", student_id=uuid.UUID(A), include_tools=False)
    assert [m["role"] for m in mine["messages"]] == ["student", "tutor"] and mine["student_id"] == A
    assert mine["context"] == {"problem_code": CODE} and "email" not in mine
    with pytest.raises(at.NotFound):
        at.read_transcript("s1", student_id=uuid.UUID(B), include_tools=False)    # someone else's conversation
    with pytest.raises(at.NotFound):
        at.read_transcript("nope", student_id=uuid.UUID(A), include_tools=False)
    admin = at.read_transcript("s1", student_id=None, include_tools=True)
    assert admin["linked"] is True and admin["agent_user_id"] == A and admin["student_id"] == A
    adk.add(B, "loose", "an unlinked conversation")
    loose = at.read_transcript("loose", student_id=None, include_tools=True)       # admin may read an unlinked session
    assert loose["linked"] is False and loose["student_id"] is None
    adk.add(A, "dup", "x")
    adk.add(B, "dup", "y")
    with pytest.raises(at.TranscriptError, match="ambiguous"):
        at.read_transcript("dup", student_id=None, include_tools=True)


# ---------------------------------------------------------------------------------------------------- Postgres oracle


class Rows(list):
    def one(self):
        return self[0]

    def first(self):
        return self[0] if self else None

    def all(self):
        return list(self)


class Res:
    def __init__(self, rows=()):
        self.rows = Rows(rows)

    def mappings(self):
        return self.rows

    def scalars(self):
        return Rows([next(iter(r.values())) for r in self.rows])

    def scalar(self):
        return next(iter(self.rows[0].values())) if self.rows else None

    scalar_one = scalar

    def first(self):
        return self.rows.first()


class PgOracle:
    """An in-memory stand-in of the PostgreSQL rows behind today's route-attempt and feedback SQL (matched by statement fragment):
    the same scripted scenario runs against it (``PostgresLearnerStore``) and against moto (``DynamoDBLearnerStore``)."""

    STEPS = 2

    def __init__(self):
        self.routes: list[dict] = []
        self.feedback: list[dict] = []
        self.audit: list[dict] = []
        self.tick = 0

    def now(self) -> dt.datetime:
        self.tick += 1
        return WHEN + dt.timedelta(seconds=self.tick)

    @contextmanager
    def begin(self):
        yield self

    connect = begin

    def execute(self, statement, params=None):
        sql, p = " ".join(str(statement).split()), params or {}
        for fragment, handler in self.handlers:
            if fragment in sql:
                return handler(self, p)
        raise AssertionError(f"oracle does not know: {sql[:100]}")

    # ---- routes
    def route_insert(self, p):
        row = {"route_attempt_id": uuid.uuid4(), "student_id": p["s"], "route_release_id": uuid.UUID(str(p["r"])), "current_step": 1,
               "version": 1, "tutor_explained_steps": [], "created_at": self.now(), "updated_at": self.now()}
        self.routes.append(row)
        return Res([row])

    def route_by_id(self, p):
        return Res([dict(r) for r in self.routes if r["route_attempt_id"] == p["id"] and str(r["student_id"]) == str(p["s"])])

    def route_update(self, p):
        for r in self.routes:
            if r["route_attempt_id"] == p["id"]:
                r["version"] += 1
                r["updated_at"] = self.now()
                if p["advance"]:
                    r["tutor_explained_steps"] = [*r["tutor_explained_steps"], r["current_step"]]
                    r["current_step"] += 1
        return Res()

    def route_list(self, p):
        rows = [{**r, "problem_code": RCODE if r["route_release_id"] == uuid.UUID(RRID) else CODE, "has_instruction": r["current_step"] <= self.STEPS}
                for r in self.routes if str(r["student_id"]) == str(p["s"]) and ("r" not in p or str(r["route_release_id"]) == str(p["r"]))]
        return Res(sorted(rows, key=lambda r: (-r["created_at"].timestamp(), str(r["route_attempt_id"]))))

    # ---- feedback
    def feedback_insert(self, p):
        for f in self.feedback:
            if (str(f["student_id"]), f["code"], f["topic"], f["reason"]) == (str(p["student_id"]), p["code"], p["topic"], p["reason"]):
                return Res([self.out(f)])
        f = {"feedback_id": uuid.uuid4(), "student_id": p["student_id"], "code": p["code"], "topic": p["topic"], "reason": p["reason"],
             "status": "PENDING", "created_at": self.now(), "review_note": None, "reviewed_at": None, "audit": json.loads(p["audit"]),
             "retrieval_verdict": "UNCLASSIFIED", "error_kind": "UNCLASSIFIED"}
        self.feedback.append(f)
        return Res([self.out(f)])

    @staticmethod
    def out(f):
        return {k: f[k] for k in ("feedback_id", "status", "created_at", "audit")}

    def feedback_resolve(self, p):
        for f in self.feedback:
            if f["feedback_id"] == p["id"] and f["status"] == "PENDING":
                f.update(status=p["status"], review_note=p["note"], reviewed_at=self.now(), retrieval_verdict=p["verdict"],
                         error_kind=p["error_kind"])
                return Res([{k: f[k] for k in ("feedback_id", "status", "review_note", "retrieval_verdict", "error_kind")}])
        return Res()

    def feedback_withdraw(self, p):
        for f in self.feedback:
            if f["feedback_id"] == p["id"] and str(f["student_id"]) == str(p["s"]) and f["status"] == "PENDING":
                f.update(status="DISMISSED", review_note=p["note"], reviewed_at=self.now())
                return Res([{"feedback_id": f["feedback_id"], "status": "DISMISSED"}])
        return Res()

    def feedback_owned(self, p):
        return Res([{"x": 1}] if any(f["feedback_id"] == p["id"] and str(f["student_id"]) == str(p["s"]) for f in self.feedback) else [])

    def feedback_mine(self, p):
        rows = [{**{k: f[k] for k in ("feedback_id", "topic", "reason", "status", "created_at", "review_note", "reviewed_at",
                                      "retrieval_verdict", "error_kind")}, "problem_code": f["code"]}
                for f in self.feedback if str(f["student_id"]) == str(p["s"])]
        return Res(sorted(rows, key=lambda r: (-r["created_at"].timestamp(), str(r["feedback_id"]))))

    def queue_rows(self):
        order = sorted(self.feedback, key=lambda f: -f["created_at"].timestamp())
        return sorted(order, key=lambda f: f["status"] != "PENDING")

    def feedback_queue(self, p):
        rows = self.queue_rows()
        related = {(f["code"], f["topic"]): sum(1 for g in rows if (g["code"], g["topic"]) == (f["code"], f["topic"])) for f in rows}
        return Res([{"feedback_id": f["feedback_id"], "canonical_code": f["code"], "topic": f["topic"], "reason": f["reason"],
                     "status": f["status"], "created_at": f["created_at"], "review_note": f["review_note"],
                     "reviewed_at": f["reviewed_at"], "audit": f["audit"], "retrieval_verdict": f["retrieval_verdict"],
                     "error_kind": f["error_kind"], "related_report_count": related[(f["code"], f["topic"])]}
                    for f in rows[p["offset"]:p["offset"] + p["limit"]]])

    def feedback_count(self, p):
        return Res([{"count": len(self.feedback)}])

    def feedback_examples(self, p):
        rows = [f for f in self.feedback if f["status"] == "RESOLVED" and f["retrieval_verdict"] != "UNCLASSIFIED"]
        rows.sort(key=lambda f: -f["reviewed_at"].timestamp())
        return Res([{"query": f["topic"], "canonical_code": f["code"], "retrieval_verdict": f["retrieval_verdict"],
                     "error_kind": f["error_kind"], "reason": f["review_note"], "reviewed_at": f["reviewed_at"],
                     "review_reference": f["feedback_id"]} for f in rows[:p["limit"]]])

    def audit_insert(self, p):
        self.audit.append(p)
        return Res()


PgOracle.handlers = [
    ("INSERT INTO learner.route_attempt", PgOracle.route_insert),
    ("SELECT * FROM learner.route_attempt WHERE route_attempt_id=:id", PgOracle.route_by_id),
    ("UPDATE learner.route_attempt", PgOracle.route_update),
    ("FROM learner.route_attempt ra", PgOracle.route_list),
    ("INSERT INTO learner.pedagogy_feedback", PgOracle.feedback_insert),
    ("UPDATE learner.pedagogy_feedback SET status='DISMISSED'", PgOracle.feedback_withdraw),
    ("UPDATE learner.pedagogy_feedback SET status=:status", PgOracle.feedback_resolve),
    ("SELECT 1 FROM learner.pedagogy_feedback", PgOracle.feedback_owned),
    ("WHERE f.student_id=:s ORDER BY", PgOracle.feedback_mine),
    ("count(*) OVER (PARTITION BY", PgOracle.feedback_queue),
    ("SELECT count(*) FROM learner.pedagogy_feedback", PgOracle.feedback_count),
    ("f.retrieval_verdict <> 'UNCLASSIFIED'", PgOracle.feedback_examples),
    ("INSERT INTO audit.action_log", PgOracle.audit_insert),
]


class PgAgentLinks:
    """Oracle of ``agent_transcripts`` link SQL (register / list / link lookup) over the same fake ADK store."""

    def __init__(self, adk: FakeAdk):
        self.adk, self.links = adk, {}

    def register_link(self, conn, student_id, session_id, *, app_name="mathbank_tutor", surface="HOME_CHAT", context=None):
        if surface not in at.SURFACES:
            raise at.TranscriptError(f"surface must be one of {at.SURFACES}")
        if not self.adk.session_exists(app_name, str(student_id), session_id):
            raise at.NotFound("agent session not found for this student")
        key = (app_name, session_id)
        if key in self.links:
            if self.links[key]["student_id"] != str(student_id):
                raise at.Conflict("agent session is linked to another student")
            self.links[key]["context"] = {**self.links[key]["context"], **(context or {})}
            return {"agent_session_link_id": self.links[key]["agent_session_link_id"], "created": False,
                    "agent_session_id": session_id, "agent_app_name": app_name, "surface": surface}
        link = {"agent_session_link_id": str(uuid.uuid4()), "agent_app_name": app_name, "agent_session_id": session_id,
                "agent_user_id": str(student_id), "student_id": str(student_id), "email": f"{student_id}@example.org",
                "surface": surface, "context": dict(context or {}), "created_at": WHEN, "last_seen_at": WHEN}
        self.links[key] = link
        return {"agent_session_link_id": link["agent_session_link_id"], "created": True, "agent_session_id": session_id,
                "agent_app_name": app_name, "surface": surface}

    def rows(self, links):
        facts = self.adk.facts([(link["agent_app_name"], link["agent_user_id"], link["agent_session_id"]) for link in links])
        out = []
        for link in links:
            fact = facts.get((link["agent_app_name"], link["agent_user_id"], link["agent_session_id"]), {})
            out.append({**link, "session_updated_at": fact.get("session_updated_at"), "event_count": fact.get("event_count", 0),
                        "first_message": fact.get("first_message")})
        out.sort(key=lambda r: (r["session_updated_at"] or r["last_seen_at"].replace(tzinfo=None)), reverse=True)
        return [at._shape(r) for r in out]

    def list_student_sessions(self, conn, student_id, limit=50):
        return self.rows([link for link in self.links.values() if link["student_id"] == str(student_id)])[:limit]

    def list_all_sessions(self, conn, student=None, limit=100):
        links = [link for link in self.links.values() if not student or student == link["student_id"] or student.lower() in link["email"]]
        keys = {(link["agent_app_name"], link["agent_user_id"], link["agent_session_id"]) for link in self.links.values()}
        return {"linked": self.rows(links)[:limit], "unlinked_count": self.adk.unlinked_count(keys)}

    def _agent_schema_present(self, conn):
        return True

    def _pg_link(self, conn, app_name, session_id):
        return self.links.get((app_name, session_id))


# ---------------------------------------------------------------------------------------------------- parity


class Backend:
    """A TestClient of one backend: its learner store, current learner (``X-Test-Student``) and the generated ids by name."""

    def __init__(self, client: TestClient, store, users: dict[str, str]):
        self.client, self.store, self.users, self.ids = client, store, users, {}

    def request(self, method, path, json=None, params=None, headers=None):
        headers = dict(headers or {})
        user = self.users[headers.pop("X-Test-Student", "A")]
        app.dependency_overrides[security.get_current_student_id] = lambda: uuid.UUID(user)
        with stores.override_store("learner", self.store):
            body = {k: v.format(**self.ids) if isinstance(v, str) else v for k, v in json.items()} if isinstance(json, dict) else json
            res = self.client.request(method, path.format(**self.ids), json=body, params=params, headers=headers)
        if res.headers.get("content-type", "").startswith("application/json") and isinstance(res.json(), dict):
            for key in ("route_attempt_id", "feedback_id"):
                if key in res.json():
                    self.ids[key] = res.json()[key]
        return res


STAFF = Actor("staff", "staff:42", "Alice", frozenset({"review"}))


@pytest.fixture()
def parity(env, adk, monkeypatch):
    oracle = PgOracle()
    for module in (postgres, route_runtime, topic_pedagogy):
        monkeypatch.setattr(module, "engine", oracle)
    monkeypatch.setattr(topic_pedagogy, "audit_problem",
                        lambda conn, code, topic, node: topic_pedagogy.audit_problem_content(stores.get_store("content"), code, topic, node))
    links = PgAgentLinks(adk)
    for name in ("register_link", "list_student_sessions", "list_all_sessions", "_agent_schema_present", "_pg_link"):
        monkeypatch.setattr(at, name, getattr(links, name))
    app.dependency_overrides[security.require_admin_api_key] = lambda: STAFF
    users = {"A": A, "B": B}
    client = TestClient(app)
    clients = {"postgres": Backend(client, PostgresLearnerStore(), users), "dynamodb": Backend(client, env, users)}
    yield clients
    app.dependency_overrides.clear()


def run(clients, name, method, path, *, expect=200, allowed=(), **kw):
    generated = ("$.route_attempt_id", "$.feedback_id")           # each backend mints its own ids
    return assert_parity(clients, ParityCase(name, method, path, expect_status=expect, **kw), allowed=[*generated, *allowed])


def test_route_attempt_routes_have_the_same_responses_on_both_backends(parity):
    started = run(parity, "start", "POST", "/v1/tutor/route-attempts", expect=201, json={"problem_code": RCODE})
    assert started["dynamodb"][1]["student_prompt"] == "PROMPT1" and EXPECTED not in json.dumps(started)
    run(parity, "current", "GET", "/v1/tutor/route-attempts/{route_attempt_id}")
    run(parity, "foreign learner", "GET", "/v1/tutor/route-attempts/{route_attempt_id}", expect=404, headers={"X-Test-Student": "B"})
    run(parity, "foreign assist", "POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", expect=404,
        json={"expected_version": 1, "hint_level": 1}, headers={"X-Test-Student": "B"})
    run(parity, "hint", "POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", json={"expected_version": 1, "hint_level": 2})
    run(parity, "stale version", "POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", expect=409,
        json={"expected_version": 1, "hint_level": 2})
    run(parity, "advance below level 5", "POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", expect=409,
        json={"expected_version": 2, "hint_level": 3, "advance": True})
    run(parity, "advance", "POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist",
        json={"expected_version": 2, "hint_level": 5, "advance": True})
    finished = run(parity, "finish", "POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist",
                   json={"expected_version": 3, "hint_level": 5, "advance": True})
    assert finished["dynamodb"][1]["status"] == "finished" and finished["dynamodb"][1]["goal"] is None
    run(parity, "finished view", "GET", "/v1/tutor/route-attempts/{route_attempt_id}")
    run(parity, "no hint left", "POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", expect=404,
        json={"expected_version": 4, "hint_level": 1})
    run(parity, "unknown problem", "POST", "/v1/tutor/route-attempts", expect=404, json={"problem_code": "NO_SUCH_CODE"})


def test_route_attempt_list_has_the_same_shape_on_both_backends(parity):
    run(parity, "start", "POST", "/v1/tutor/route-attempts", expect=201, json={"problem_code": RCODE})
    run(parity, "list", "GET", "/v1/learner/route-attempts", allowed=["$.items[*].route_attempt_id"])
    run(parity, "list of another learner", "GET", "/v1/learner/route-attempts", headers={"X-Test-Student": "B"})
    run(parity, "bad token", "GET", "/v1/learner/route-attempts", expect=400, params={"next_token": "garbage"})


def test_resume_and_idempotent_redelivery_are_dynamodb_behaviour_changes(parity):
    ddb_client = parity["dynamodb"]
    first = ddb_client.request("POST", "/v1/tutor/route-attempts", json={"problem_code": RCODE}, headers={"Idempotency-Key": "k1"})
    replay = ddb_client.request("POST", "/v1/tutor/route-attempts", json={"problem_code": RCODE}, headers={"Idempotency-Key": "k1"})
    resumed = ddb_client.request("POST", "/v1/tutor/route-attempts", json={"problem_code": RCODE})
    assert (first.status_code, replay.status_code, resumed.status_code) == (201, 201, 200)
    assert replay.headers.get("Idempotent-Replayed") == "true" and "Idempotent-Replayed" not in first.headers
    assert first.json() == replay.json() == resumed.json()
    hint = {"expected_version": 1, "hint_level": 2}
    one = ddb_client.request("POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", json=hint, headers={"Idempotency-Key": "a1"})
    two = ddb_client.request("POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", json=hint, headers={"Idempotency-Key": "a1"})
    assert one.status_code == two.status_code == 200 and one.json() == two.json()
    reused = ddb_client.request("POST", "/v1/tutor/route-attempts/{route_attempt_id}/assist", json={**hint, "hint_level": 3},
                                headers={"Idempotency-Key": "a1"})
    assert reused.status_code == 422


def test_feedback_routes_have_the_same_responses_on_both_backends(parity):
    body = {"problem_code": CODE, "topic": "Angle chase", "reason": REASON}
    created = run(parity, "submit", "POST", "/v1/tutor/feedback", expect=201, json=body)
    assert created["dynamodb"][1]["status"] == "PENDING" and "no annotation" in created["dynamodb"][1]["message"]
    run(parity, "duplicate", "POST", "/v1/tutor/feedback", expect=201, json=body)
    run(parity, "unknown problem", "POST", "/v1/tutor/feedback", expect=404, json={**body, "problem_code": "NO_SUCH"})
    run(parity, "second report", "POST", "/v1/tutor/feedback", expect=201, json={**body, "reason": "A different explanation of why."},
        headers={"X-Test-Student": "B"})
    run(parity, "own list", "GET", "/v1/learner/feedback", allowed=["$.items[*].feedback_id"], unordered=("$.items",))
    run(parity, "queue", "GET", "/v1/admin/pedagogy/feedback", allowed=["$.items[*].feedback_id"])
    review = {"feedback_id": "{feedback_id}", "status": "RESOLVED", "note": "Reviewed the source evidence.",
              "retrieval_verdict": "IRRELEVANT", "error_kind": "RETRIEVAL"}
    for backend in parity.values():
        backend.ids["feedback_id"] = backend.store.list_my_feedback(backend.users["B"])["items"][0]["feedback_id"]
    resolved = run(parity, "review", "POST", "/v1/admin/pedagogy/feedback-review", json=review, allowed=["$.feedback_id"])
    assert resolved["dynamodb"][1]["status"] == "RESOLVED"
    run(parity, "review again", "POST", "/v1/admin/pedagogy/feedback-review", expect=409, json=review)
    run(parity, "queue after review", "GET", "/v1/admin/pedagogy/feedback",
        allowed=["$.items[*].feedback_id", "$.items[*].reviewed_at"])
    run(parity, "examples", "GET", "/v1/admin/pedagogy/retrieval-examples",
        allowed=["$.examples[*].review_reference", "$.examples[*].reviewed_at"])
    run(parity, "withdraw foreign", "POST", "/v1/learner/feedback/{feedback_id}/withdraw", expect=404)


def test_the_reviewer_is_audited_on_both_backends(parity, monkeypatch):
    run(parity, "submit", "POST", "/v1/tutor/feedback", expect=201,
        json={"problem_code": CODE, "topic": "Angle chase", "reason": REASON})
    for backend in parity.values():
        backend.ids["feedback_id"] = backend.store.list_my_feedback(backend.users["A"])["items"][0]["feedback_id"]
    run(parity, "review", "POST", "/v1/admin/pedagogy/feedback-review", allowed=["$.feedback_id"],
        json={"feedback_id": "{feedback_id}", "status": "DISMISSED", "note": "Reviewed, nothing to change."})
    oracle = topic_pedagogy.engine
    assert [r["actor_id"] for r in oracle.audit] == ["staff:42"] and oracle.audit[0]["action"] == "FEEDBACK_REVIEWED"
    ddb_id = parity["dynamodb"].ids["feedback_id"]
    assert [r["actor_id"] for r in audit_items(ddb_id)] == ["staff:42"]
    assert typed.require(FeedbackItem, pk(A), f"FEEDBACK#{ddb_id}").reviewed_by == "staff:42"


def test_learner_can_withdraw_an_own_report_on_both_backends(parity):
    run(parity, "submit", "POST", "/v1/tutor/feedback", expect=201,
        json={"problem_code": CODE, "topic": "Angle chase", "reason": REASON})
    for backend in parity.values():
        backend.ids["feedback_id"] = backend.store.list_my_feedback(backend.users["A"])["items"][0]["feedback_id"]
    run(parity, "withdraw", "POST", "/v1/learner/feedback/{feedback_id}/withdraw", allowed=["$.feedback_id"])
    run(parity, "withdraw twice", "POST", "/v1/learner/feedback/{feedback_id}/withdraw", expect=409)
    run(parity, "list after", "GET", "/v1/learner/feedback", allowed=["$.items[*].feedback_id", "$.items[*].reviewed_at"])


def test_agent_session_routes_have_the_same_responses_on_both_backends(parity, adk):
    adk.add(A, "s1", "What is the power of a point?", "PA times PB.")
    adk.add(B, "s2", "another learner's chat")
    adk.add(B, "loose", "never linked")
    link = {"agent_session_id": "s1", "surface": "SOLVE_WORKSPACE", "context": {"problem_code": CODE}}
    run(parity, "link", "POST", "/v1/learner/agent-sessions", json=link, allowed=["$.agent_session_link_id"])
    run(parity, "link again", "POST", "/v1/learner/agent-sessions", json={"agent_session_id": "s1"},
        allowed=["$.agent_session_link_id"])
    run(parity, "foreign session", "POST", "/v1/learner/agent-sessions", expect=404, json={"agent_session_id": "s2"})
    run(parity, "link B", "POST", "/v1/learner/agent-sessions", json={"agent_session_id": "s2"}, headers={"X-Test-Student": "B"},
        allowed=["$.agent_session_link_id"])
    run(parity, "my sessions", "GET", "/v1/learner/agent-sessions",
        allowed=["$[*].agent_session_link_id", "$[*].email", "$[*].created_at", "$[*].last_seen_at"])
    run(parity, "my transcript", "GET", "/v1/learner/agent-sessions/s1/transcript",
        allowed=["$.created_at", "$.updated_at"])
    run(parity, "foreign transcript", "GET", "/v1/learner/agent-sessions/s2/transcript", expect=404)
    run(parity, "admin list", "GET", "/v1/admin/agent-sessions",
        allowed=["$.linked[*].agent_session_link_id", "$.linked[*].email", "$.linked[*].created_at", "$.linked[*].last_seen_at"])
    run(parity, "admin transcript", "GET", "/v1/admin/agent-sessions/s1/transcript", allowed=["$.email", "$.created_at", "$.updated_at"])
    run(parity, "admin unlinked transcript", "GET", "/v1/admin/agent-sessions/loose/transcript", allowed=["$.created_at", "$.updated_at"])
    run(parity, "admin unknown", "GET", "/v1/admin/agent-sessions/missing/transcript", expect=404)


def test_unlink_is_a_dynamodb_endpoint_change(parity, adk):
    adk.add(A, "s1", "hello")
    client = parity["dynamodb"]
    client.request("POST", "/v1/learner/agent-sessions", json={"agent_session_id": "s1"})
    assert client.request("GET", "/v1/learner/agent-sessions/s1").json()["agent_session_id"] == "s1"
    assert client.request("DELETE", "/v1/learner/agent-sessions/s1", headers={"X-Test-Student": "B"}).status_code == 404
    assert client.request("DELETE", "/v1/learner/agent-sessions/s1").status_code == 204
    assert client.request("GET", "/v1/learner/agent-sessions/s1").status_code == 404
    assert client.request("GET", "/v1/learner/agent-sessions").json() == []


def test_route_runtime_get_is_lock_free_and_assist_still_locks(monkeypatch):
    """LRN-F09: a GET no longer takes ``FOR UPDATE``; ``assist`` still does."""
    seen: list[str] = []

    class Conn:
        def execute(self, statement, params=None):
            seen.append(" ".join(str(statement).split()))
            return Res([{"route_attempt_id": uuid.uuid4(), "route_release_id": uuid.uuid4(), "version": 1, "current_step": 1,
                         "tutor_explained_steps": []}])

    route_runtime.owned_attempt(Conn(), uuid.uuid4(), uuid.uuid4(), lock=False)
    route_runtime.owned_attempt(Conn(), uuid.uuid4(), uuid.uuid4())
    assert "FOR UPDATE" not in seen[0] and seen[1].endswith("FOR UPDATE")


# ---------------------------------------------------------------------------------------------------- PostgreSQL flag unchanged


class ScriptedEngine:
    """Answers the SQL of the PostgreSQL implementation by statement fragment (the first fragment that matches wins)."""

    def __init__(self, answers: dict[str, list[dict]]):
        self.answers, self.statements = answers, []

    @contextmanager
    def connect(self):
        yield self

    begin = connect

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.statements.append(sql)
        for fragment, rows in self.answers.items():
            if fragment in sql:
                return Res(rows)
        raise AssertionError(f"unexpected SQL: {sql[:100]}")


def test_topic_practice_state_runs_the_same_two_queries_on_postgres_and_skips_the_exclusion_read(monkeypatch):
    engine = ScriptedEngine({"FROM learner.solve_attempt": [{"canonical_code": CODE}],
                             "FROM pedagogy.knowledge_gap": [{"target_skill_id": "SK1"}]})
    monkeypatch.setattr(topic_pedagogy, "engine", engine)
    monkeypatch.setattr(topic_pedagogy, "load_profile", lambda version: {"minimum_confidence": 0.0})
    monkeypatch.setattr(topic_pedagogy, "rank_candidates", lambda cands, **kw: cands)

    class Content:
        backend = "postgres"

        def list_taxonomy_nodes(self, types):
            return [{"taxonomy_node_id": "SK1", "name": "Angle chase", "node_type": "SKILL"}]

        def get_taxonomy_nodes(self, ids):
            return {"SK1": NODE}

        def list_topic_candidates(self, node_id, *, limit=100):
            return [{"canonical_code": CODE, "confidence": 0.5, "difficulty": 2, "skill_ids": [], "structure_key": CODE}]

    with stores.override_store("content", Content()), stores.override_store("learner", PostgresLearnerStore()):
        result = topic_pedagogy.topic_candidates("angle chase", student_id=uuid.UUID(A))
    assert result["candidates"][0]["gap_skill_ids"] == ["SK1"] and result["candidates"][0]["exposure_known"] is True
    assert len(engine.statements) == 2 and not any("pedagogy_feedback" in s for s in engine.statements)   # SQL excludes in the candidate query


def test_transcript_reads_the_same_conversation_through_the_store_and_through_the_sql_function(monkeypatch):
    """``read_transcript`` (link from the learner store, body from the ADK seam) equals the one-connection ``transcript``."""
    user, session = A, "s1"
    link = {"agent_user_id": user, "student_id": user, "email": "a@example.org", "surface": "HOME_CHAT",
            "context": {"problem_code": CODE}, "created_at": WHEN}
    events = [{"timestamp": WHEN.replace(tzinfo=None), "event_data": {"author": "user", "content": {"parts": [{"text": "Hi"}]}}},
              {"timestamp": WHEN.replace(tzinfo=None), "event_data": json.dumps(
                  {"author": "mathbank_tutor", "content": {"parts": [{"text": "Hello"}]}})}]
    engine = ScriptedEngine({
        "to_regclass": [{"present": True}],
        "FROM learner.agent_session_link l JOIN learner.student_profile sp": [link],
        "SELECT user_id FROM agent_sessions.sessions": [{"user_id": user}],
        "SELECT create_time, update_time FROM agent_sessions.sessions": [{"create_time": WHEN.replace(tzinfo=None),
                                                                          "update_time": WHEN.replace(tzinfo=None)}],
        "FROM agent_sessions.events": events})
    monkeypatch.setattr(postgres, "engine", engine)
    with stores.override_store("learner", PostgresLearnerStore()):
        for student, tools in ((uuid.UUID(A), False), (None, True)):
            via_store = at.read_transcript(session, student_id=student, include_tools=tools)
            assert via_store == at.transcript(engine, session, student_id=student, include_tools=tools)
        with pytest.raises(at.NotFound):
            at.read_transcript(session, student_id=uuid.UUID(B), include_tools=False)
    assert [m["text"] for m in via_store["messages"]] == ["Hi", "Hello"] and via_store["linked"] is True
