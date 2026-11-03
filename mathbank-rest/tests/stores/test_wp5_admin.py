"""WP5 admin area (requirement 71 WP5; requirement 70 C1 A5, A17, A41, A43, T4, T35, T36, section 5 stream consumers) on moto.

Store level: directory paging with signed tokens, account status and token version, erasure (idempotent, resumable after a failed
batch, sentinels freed, S3 prefix emptied, tombstone), rebuilds, interaction-event listing. Consumers: ``learner-integrity``,
``mastery-repair``, ``mastery-cohort``, ``learner-abandon-stale``, the erasure worker, with synthetic stream records in raw
attribute-value and deserialised form. Routes: admin credential required on every new route, a learner token is refused, the actor is
the credential's identity, and no PostgreSQL is touched.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
import test_wp4_catalog as cat
from boto3.dynamodb.types import TypeSerializer
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_wp5_microcourse import (  # noqa: F401  (world is a fixture)
    eid_of,
    enroll,
    finish_assessment,
    items_of,
    seed_profile,
    world,
)
from test_wp5_microcourse import wp4 as mcw

from mathbank_rest import learner_consumers as lc
from mathbank_rest import security, stores
from mathbank_rest.config import settings
from mathbank_rest.db import postgres
from mathbank_rest.models.ddb.learner import LearnerEvent
from mathbank_rest.models.manual import learner_microcourse as mc
from mathbank_rest.models.manual.learner_admin import LearnerTombstone
from mathbank_rest.models.manual.learner_idem import LearnerIdem
from mathbank_rest.models.manual.learner_outcomes import (
    CohortItem,
    DailyItem,
    MasteryItem,
    MevidItem,
    OutcomeItem,
)
from mathbank_rest.routers import admin_learner
from mathbank_rest.routers import micro_courses as mc_router
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore, catalog
from mathbank_rest.stores.errors import (
    ConditionFailed,
    InvalidToken,
    NotFound,
    StoreError,
    StoreNotImplemented,
    UniqueViolation,
    ValidationFailed,
    install_error_handlers,
)
from mathbank_rest.stores.learner import AdminPostgres, DynamoDBLearnerStore, PostgresLearnerStore
from mathbank_rest.stores.learner.admin import AdminDynamoDB, register_erasure_hook
from mathbank_rest.stores.learner.identity import IdentityDynamoDB
from mathbank_rest.stores.learner.outcomes import OutcomesDynamoDB
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork

KEY = "unit-test-admin-key"
H = {"X-Admin-Api-Key": KEY}
HASH = security.hash_password("a-long-password")
CTX = "learner"
PID = cat.pid
Q1 = "AIME_2005_I_Q01"
SER = TypeSerializer()


class Boom:
    def connect(self, *a, **k):
        raise AssertionError("the DynamoDB learner store touched Postgres")

    begin = connect


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
def store(ddb, monkeypatch):
    _create_audit_table(ddb)
    monkeypatch.setattr(settings, "admin_api_key", KEY)
    monkeypatch.setattr(postgres, "engine", Boom())
    monkeypatch.setattr(mc_router, "engine", Boom())
    learner = DynamoDBLearnerStore()
    with stores.override_store("learner", learner):
        yield learner


@pytest.fixture()
def corpus(store, content_table):
    catalog._CATALOGUES.clear()
    OutcomesDynamoDB._themes.clear()
    cat.seed()
    with stores.override_store("content", DynamoDBContentStore()):
        yield store
    catalog._CATALOGUES.clear()
    OutcomesDynamoDB._themes.clear()


def register(store, email, first="Ada", last="Lovelace") -> str:
    return str(store.create_student(email=email, password_hash=HASH, first_name=first, last_name=last)["student_id"])


def audit(ddb_client, kind: str, sid: str) -> list[dict]:
    return [i for i in toolkit.query_page("audit", f"ENTITY#{kind}#{sid}")["items"]]


def keys_of(ddb_client, table="mb-learner-ut") -> set[tuple[str, str]]:
    return {(i["PK"]["S"], i["SK"]["S"]) for i in ddb_client.scan(TableName=table)["Items"]}


def partition_keys(sid: str) -> list[str]:
    return [i["SK"] for i in toolkit.query_page(CTX, toolkit.student_pk(sid), limit=200)["items"]]


def raw_put(item: dict) -> None:
    toolkit.put_item(CTX, item)


# ------------------------------------------------------------------------------------------------ A5 directory

def test_directory_pages_in_email_order_with_signed_tokens_and_never_returns_secrets(store):
    ids = {e: register(store, f"{e}@example.org", first=e.upper(), last="Student") for e in "abcde"}
    token, seen = None, []
    while True:
        page = store.list_admin_students(limit=2, next_token=token)
        assert len(page["items"]) <= 2
        seen += [r["email"] for r in page["items"]]
        token = page["next_token"]
        if not token:
            break
    assert seen == [f"{e}@example.org" for e in "abcde"]
    row = store.list_admin_students(limit=1)["items"][0]
    assert set(row) == {"student_id", "email", "first_name", "last_name", "display_name", "status", "created_at", "is_anonymous"}
    assert "password_hash" not in json.dumps(store.list_admin_students(limit=50), default=str)
    assert ids["a"] == row["student_id"]


def test_directory_filters_by_text_status_and_exact_id_and_continues_after_a_thin_page(store):
    a = register(store, "grace@example.org", "Grace", "Hopper")
    b = register(store, "alan@example.org", "Alan", "Turing")
    c = register(store, "ada@example.org", "Ada", "Lovelace")
    store.set_account_status(b, "DISABLED", "service:admin-key")
    assert [r["student_id"] for r in store.list_admin_students(q="HOPPER")["items"]] == [a]
    assert [r["student_id"] for r in store.list_admin_students(q="example.org", status="DISABLED")["items"]] == [b]
    assert [r["student_id"] for r in store.list_admin_students(q=c)["items"]] == [c]
    assert store.list_admin_students(q=c, status="DISABLED")["items"] == []
    page = store.list_admin_students(q="example", limit=2)
    assert len(page["items"]) == 2 and page["next_token"]
    rest = store.list_admin_students(q="example", limit=2, next_token=page["next_token"])
    assert {r["student_id"] for r in page["items"] + rest["items"]} == {a, b, c} and rest["next_token"] is None
    with pytest.raises(ValidationFailed):
        store.list_admin_students(status="BOGUS")


def test_a_tampered_or_foreign_directory_token_is_rejected(store):
    for e in "abc":
        register(store, f"{e}@example.org")
    token = store.list_admin_students(limit=1)["next_token"]
    bad = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(InvalidToken):
        store.list_admin_students(limit=1, next_token=bad)
    foreign = toolkit.sign_token({"t": "mb-learner-ut", "i": "GSI2", "p": "STUDENT#other", "f": True, "k": {}})
    with pytest.raises(InvalidToken):
        store.list_admin_students(limit=1, next_token=foreign)


def test_admin_student_view_has_status_and_token_version_but_no_secrets(store):
    sid = register(store, "ada@example.org")
    view = store.get_admin_student(sid)
    assert view["status"] == "ACTIVE" and view["token_version"] == 0 and view["auth"] == "password"
    assert "password_hash" not in view and "search_blob" not in view
    assert store.get_admin_student(uuid.uuid4()) is None


# ------------------------------------------------------------------------------------------------ T4 / auth

@pytest.fixture()
def real_status(store, monkeypatch):
    monkeypatch.setattr(security, "_load_student_status", store.get_student_status)
    monkeypatch.setattr(security, "_load_student_token_version", store.get_student_token_version)
    security._status_cache.clear()


def rejected(sid: str, tv: int) -> bool:
    from fastapi import HTTPException

    security._status_cache.clear()
    try:
        security.assert_student_active(UUID(sid), tv)
    except HTTPException as exc:
        return exc.status_code == 401
    return False


def test_disable_bumps_the_token_version_audits_the_actor_and_enable_keeps_old_tokens_dead(ddb, store, real_status):
    sid = register(store, "ada@example.org")
    assert not rejected(sid, 0)
    out = store.set_account_status(sid, "DISABLED", "staff:alice", "abuse")
    assert out["status"] == "DISABLED" and rejected(sid, 0) and store.get_student_token_version(sid) == 1
    view = store.get_admin_student(sid)
    assert view["token_version"] == 1 and view["disabled_at"] is not None
    store.set_account_status(sid, "ACTIVE", "staff:alice")
    assert rejected(sid, 0) and not rejected(sid, 1)                       # the pre-disable token stays revoked
    entries = audit(ddb, "STUDENT", sid)
    assert sorted(e["action"] for e in entries) == ["STUDENT_DISABLED", "STUDENT_ENABLED"]
    assert {e["actor_id"] for e in entries} == {"staff:alice"}
    assert store.set_account_status(uuid.uuid4(), "DISABLED", "staff:alice") is None


def test_revoke_tokens_bumps_the_version_without_a_status_change(ddb, store, real_status):
    sid = register(store, "ada@example.org")
    assert store.revoke_student_tokens(sid, "service:admin-key")["token_version"] == 1
    assert rejected(sid, 0) and not rejected(sid, 1) and store.get_student_status(sid) == "ACTIVE"
    assert [e["action"] for e in audit(ddb, "STUDENT", sid)] == ["STUDENT_TOKENS_REVOKED"]
    assert store.revoke_student_tokens(uuid.uuid4(), "x") is None


# ------------------------------------------------------------------------------------------------ T36 erasure

def seed_partition(store, ddb_client, sid: str, cognito: str) -> dict:
    """Everything an active learner leaves: items of every pointer-bearing type, 230 fillers, S3 offload objects, sentinels."""
    pk = toolkit.student_pk(sid)
    aid, plan, eid, fid = (str(uuid.uuid4()) for _ in range(4))
    for kind, sk, owner_pk in (("SOLVE", f"SOLVE#{aid}", f"SOLVE#{aid}"), ("PLAN", f"PLAN#{plan}", f"PLAN#{plan}"),
                               ("ENROLL", f"ENROLL#{eid}", f"ENROLL#{eid}"), ("FEEDBACK", f"FEEDBACK#{fid}", f"FEEDBACK#{fid}")):
        raw_put({"PK": pk, "SK": sk, "type": kind, "student_id": sid})
        raw_put({"PK": owner_pk, "SK": "OWNER", "type": f"{kind}_OWNER", "student_id": sid})
    raw_put({"PK": pk, "SK": "AGENT#mathbank_tutor#sess-1", "type": "AGENTLINK", "student_id": sid})
    raw_put({"PK": "UNIQUE#agent_session#mathbank_tutor#sess-1", "SK": "UNIQUE", "type": "UNIQUE_AGENT_SESSION", "student_id": sid})
    for n in range(230):
        raw_put({"PK": pk, "SK": f"OUTCOME#2026-01-01T00:00:{n:02d}.000000Z#{uuid.uuid4()}", "type": "OUTCOME", "student_id": sid})
    s3, bucket = toolkit.client("s3"), toolkit.data_bucket()
    for key in (f"offload/learner/students/{sid}/IDEM/ab/response.json", f"offload/learner/students/{sid}/EVENT/cd/payload.json",
                "offload/learner/students/someone-else/EVENT/cd/payload.json"):
        s3.put_object(Bucket=bucket, Key=key, Body=b"{}")
    return {"solve": aid, "plan": plan, "enroll": eid, "feedback": fid}


def test_erasure_leaves_nothing_frees_the_email_removes_the_files_and_is_idempotent(ddb, store, real_status):
    cognito = str(uuid.uuid4())
    sid = str(store.create_student_for_cognito(cognito_sub=cognito, first_name="Ada", last_name="L", email="Ada@Example.org",
                                              email_verified=True)["student_id"])
    other = register(store, "grace@example.org")
    ptr = seed_partition(store, ddb, sid, cognito)
    raw_put({"PK": toolkit.student_pk(other), "SK": "OUTCOME#2026-01-01T00:00:00.000000Z#" + str(uuid.uuid4()), "type": "OUTCOME"})

    job = store.request_erasure(sid, "staff:alice", "gdpr request")
    assert job["status"] == "REQUESTED" and job["already_requested"] is False
    assert store.get_student_status(sid) == "ERASING" and rejected(sid, 0) and rejected(sid, 1)
    assert store.request_erasure(sid, "staff:bob")["job_id"] == job["job_id"]
    assert store.list_pending_erasures() == [sid]
    with pytest.raises(UniqueViolation):
        register(store, "ada@example.org")                                  # the address stays reserved until the erasure ran

    report = store.erase_partition(sid)
    assert report["done"] is True and report["items"] == 230 + 5 and report["s3_objects"] == 2
    assert toolkit.query_page(CTX, toolkit.student_pk(sid), limit=200)["items"] == []
    left = keys_of(ddb)
    for pk in (f"SOLVE#{ptr['solve']}", f"PLAN#{ptr['plan']}", f"ENROLL#{ptr['enroll']}", f"FEEDBACK#{ptr['feedback']}",
               "UNIQUE#agent_session#mathbank_tutor#sess-1", "UNIQUE#email#ada@example.org", f"UNIQUE#cognito_sub#{cognito}"):
        assert not any(k[0] == pk for k in left), pk
    s3 = toolkit.client("s3")
    keys = [o["Key"] for o in s3.list_objects_v2(Bucket=toolkit.data_bucket()).get("Contents", [])]
    assert keys == ["offload/learner/students/someone-else/EVENT/cd/payload.json"]
    tomb = typed.require(LearnerTombstone, f"ERASED#{sid}", "TOMBSTONE")
    assert tomb.status == "DONE" and tomb.erased_at is not None and tomb.job_id == job["job_id"] and tomb.GSI1PK is None
    assert store.list_pending_erasures() == []
    assert store.get_student_status(sid) is None and rejected(sid, 0)       # old tokens: no such account
    assert {e["action"] for e in audit(ddb, "STUDENT", sid)} == {"STUDENT_ERASURE_REQUESTED", "STUDENT_ERASED"}
    assert any(k[0] == toolkit.student_pk(other) for k in left)             # somebody else's data is untouched
    assert register(store, "ada@example.org")                               # the e-mail can register again
    assert store.erase_partition(sid)["status"] == "DONE"                   # idempotent
    again = store.request_erasure(sid, "staff:alice")
    assert again["status"] == "DONE" and again["already_requested"] is True


def test_erasure_resumes_after_a_failed_batch_and_never_strands_a_pointer(ddb, store, monkeypatch):
    sid = register(store, "ada@example.org")
    ptr = seed_partition(store, ddb, sid, str(uuid.uuid4()))
    store.request_erasure(sid, "service:admin-key")
    real, calls = toolkit.transact, {"n": 0}

    def flaky(ops, **kw):
        calls["n"] += 1
        if calls["n"] == 4:
            raise StoreError("boom: batch failed")
        return real(ops, **kw)

    monkeypatch.setattr(toolkit, "transact", flaky)
    with pytest.raises(StoreError, match="boom"):
        store.erase_partition(sid)
    monkeypatch.setattr(toolkit, "transact", real)
    mid = partition_keys(sid)
    assert "PROFILE" in mid and store.get_student_status(sid) == "ERASING"      # not finished: still blocked, still resumable
    assert store.get_erasure_job(sid)["status"] == "REQUESTED"
    done = store.erase_partition(sid)
    assert done["done"] is True and partition_keys(sid) == []
    assert not any(k[0] == f"SOLVE#{ptr['solve']}" for k in keys_of(ddb))


def test_erasure_refuses_an_account_that_was_not_requested_and_unknown_ids(store):
    sid = register(store, "ada@example.org")
    with pytest.raises(ConditionFailed):
        store.erase_partition(sid)
    with pytest.raises(NotFound):
        store.erase_partition(uuid.uuid4())
    with pytest.raises(NotFound):
        store.request_erasure(uuid.uuid4(), "x")
    assert partition_keys(sid) == ["PROFILE"]


def test_a_resumed_erasure_does_not_delete_a_sentinel_somebody_else_now_owns(ddb, store):
    mine, theirs = register(store, "a@example.org"), str(uuid.uuid4())
    raw_put({"PK": "SOLVE#x", "SK": "OWNER", "type": "SOLVE_OWNER", "student_id": theirs})
    raw_put({"PK": "SOLVE#mine", "SK": "OWNER", "type": "SOLVE_OWNER", "student_id": mine})
    AdminDynamoDB._adm_delete_owned([("SOLVE#x", "OWNER"), ("SOLVE#missing", "OWNER"), ("SOLVE#mine", "OWNER")], mine)
    left = keys_of(ddb)
    assert ("SOLVE#x", "OWNER") in left and ("SOLVE#mine", "OWNER") not in left


def test_erasure_calls_registered_hooks_before_deleting_and_a_failing_hook_blocks_it(store):
    sid = register(store, "ada@example.org")
    store.request_erasure(sid, "service:admin-key")
    register_erasure_hook("exam", lambda s: (_ for _ in ()).throw(StoreError("exam erase failed")))
    try:
        with pytest.raises(StoreError):
            store.erase_partition(sid)
        assert partition_keys(sid) == ["PROFILE"]
        register_erasure_hook("exam", lambda s: 3)
        assert store.erase_partition(sid)["hooks"]["exam"] == 3
    finally:
        register_erasure_hook("exam", None)


def test_erasure_worker_handler_runs_one_student_or_sweeps_pending_requests(store):
    a, b = register(store, "a@example.org"), register(store, "b@example.org")
    register(store, "keep@example.org")
    store.request_erasure(a, "x")
    store.request_erasure(b, "x")
    out = lc.erasure_handler({"student_id": a}, store=store)
    assert [r["status"] for r in out["results"]] == ["DONE"] and store.list_pending_erasures() == [b]
    out = lc.erasure_handler({}, store=store)
    assert [r["student_id"] for r in out["results"]] == [b] and store.list_pending_erasures() == []
    assert lc.erasure_handler({}, store=store)["results"] == []
    body = json.dumps({"student_id": b})
    assert lc.erasure_handler({"Records": [{"messageId": "m1", "body": body}]}, store=store)["failed"] == []


# ------------------------------------------------------------------------------------------------ T35 rebuilds

def commit(store, sid, code, correct, when):
    problem = stores.get_store("content").get_problem_by_id(PID(code))
    uow = LearnerUnitOfWork(sid)
    staged = OutcomesDynamoDB().stage_outcome(
        uow, problem_id=UUID(PID(code)), attempt_id=uuid.uuid4(), attempted_at=when, is_correct=correct, submitted_answer=None,
        time_spent_seconds=30, hint_count=0, source="web", difficulty_band=problem["difficulty_band"],
        tags=stores.get_store("content").get_problem_tags(problem_id=PID(code)))
    uow.commit()
    return staged


def mastery_scores(sid) -> dict:
    page = typed.query(MasteryItem, toolkit.student_pk(sid), sk_begins="MASTERY#", limit=200)
    return {(i.tag_kind, str(i.tag_id)): i.mastery_score for i in page.items}


def test_mastery_rebuild_restores_corrupted_scores_from_the_evidence_and_audits(ddb, corpus):
    sid = register(corpus, "ada@example.org")
    now = datetime.now(UTC)
    commit(corpus, sid, Q1, True, now - dt.timedelta(days=3))
    commit(corpus, sid, Q1, False, now - dt.timedelta(days=1))
    good = mastery_scores(sid)
    assert good
    for (kind, tag) in good:
        out = OutcomesDynamoDB()
        (out.upsert_concept_mastery if kind == "C" else out.upsert_technique_mastery)(
            **{"student_id": UUID(sid), "concept_id" if kind == "C" else "technique_id": UUID(tag), "mastery_score": 0.01,
               "attempts_count": 99, "correct_count": 1, "last_attempt_at": now})
    assert mastery_scores(sid) != good
    result = corpus.rebuild_mastery(sid, "staff:alice")
    assert result["concepts"] + result["techniques"] == len(good)
    assert mastery_scores(sid) == pytest.approx(good)
    assert [e["action"] for e in audit(ddb, "STUDENT", sid)] == ["STUDENT_MASTERY_REBUILT"]
    assert audit(ddb, "STUDENT", sid)[0]["actor_id"] == "staff:alice"
    with pytest.raises(NotFound):
        corpus.rebuild_mastery(uuid.uuid4())


def put_event(sid, when: datetime, event_type: str, payload=None) -> None:
    typed.put(LearnerEvent(
        PK=toolkit.student_pk(sid), SK=f"EVT#{toolkit.encode(when)}#{uuid.uuid4()}", event_id=uuid.uuid4(), event_time=when,
        event_type=event_type, actor_type="STUDENT", solve_attempt_id=uuid.uuid4(), student_id=sid, payload=payload or {}))


def test_daily_activity_rebuild_counts_events_per_utc_day_and_drops_stale_days(ddb, store):
    sid = register(store, "ada@example.org")
    d1, d2 = datetime(2026, 10, 1, 23, 59, tzinfo=UTC), datetime(2026, 10, 2, 0, 1, tzinfo=UTC)
    for when, kind, payload in ((d1, "ATTEMPT_STARTED", None), (d1, "STEP_EVALUATED", {"result": "SUCCESS"}),
                                (d1, "STEP_EVALUATED", {"result": "FAIL"}), (d2, "ATTEMPT_COMPLETED", None),
                                (d2, "GAP_HYPOTHESIS_CREATED", None), (d2, "HINT_REQUESTED", None)):
        put_event(sid, when, kind, payload)
    typed.put(DailyItem(PK=toolkit.student_pk(sid), SK="DAILY#2026-01-01", student_id=UUID(sid), activity_date=date(2026, 1, 1),
                        updated_at=d1, **dict.fromkeys(lc_counters(), 5)))
    out = store.rebuild_daily_activity(sid, "staff:alice")
    assert out == {"student_id": sid, "days": 2, "removed": 1}
    rows = {r["activity_date"]: r for r in store.list_daily_activity(UUID(sid), date(2026, 9, 1), date(2026, 11, 1))}
    assert set(rows) == {date(2026, 10, 1), date(2026, 10, 2)}
    assert (rows[date(2026, 10, 1)]["attempts_started"], rows[date(2026, 10, 1)]["steps_evaluated"],
            rows[date(2026, 10, 1)]["steps_succeeded"]) == (1, 2, 1)
    assert (rows[date(2026, 10, 2)]["attempts_completed"], rows[date(2026, 10, 2)]["knowledge_gaps_created"]) == (1, 1)
    assert store.rebuild_daily_activity(sid)["days"] == 2                  # idempotent
    assert [e["action"] for e in audit(ddb, "STUDENT", sid)] == ["STUDENT_DAILY_REBUILT"]


def lc_counters():
    from mathbank_rest.models.manual.learner_outcomes import DAILY_COUNTERS

    return DAILY_COUNTERS


def test_admin_daily_activity_one_student_and_across_a_directory_page(store):
    a, b = register(store, "a@example.org"), register(store, "b@example.org")
    for sid, kind in ((a, "ATTEMPT_STARTED"), (b, "ATTEMPT_STARTED"), (b, "ATTEMPT_COMPLETED")):
        put_event(sid, datetime(2026, 10, 1, 12, tzinfo=UTC), kind)
    store.rebuild_daily_activity(a)
    store.rebuild_daily_activity(b)
    one = store.list_admin_daily_activity(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), student_id=a)
    assert one["scope"] == "student" and [r["student_id"] for r in one["items"]] == [a]
    both = store.list_admin_daily_activity(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31))
    assert {r["student_id"] for r in both["items"]} == {a, b} and both["scope"] == "page"
    summed = store.list_admin_daily_activity(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), group_by="day")
    assert summed["items"][0]["students"] == 2 and summed["items"][0]["attempts_started"] == 2
    paged = store.list_admin_daily_activity(date_from=date(2026, 10, 1), date_to=date(2026, 10, 31), limit=1)
    assert len(paged["items"]) <= 1 and paged["next_token"]
    with pytest.raises(ValidationFailed):
        store.list_admin_daily_activity(date_from=date(2025, 1, 1), date_to=date(2026, 12, 31))


def test_expired_idempotency_receipts_are_purged_and_live_ones_kept(ddb, store):
    sid, now = register(store, "ada@example.org"), int(dt.datetime.now(UTC).timestamp())
    for key, ttl in (("old", now - 10), ("live", now + 3600)):
        typed.put(LearnerIdem(PK=toolkit.student_pk(sid), SK=f"IDEM#{key}", request_hash="a" * 64, response={"ok": True},
                              created_at=datetime.now(UTC), ttl=ttl))
    assert store.purge_idempotency(sid, "staff:alice") == {"student_id": sid, "scanned": 2, "deleted": 1}
    assert [k for k in partition_keys(sid) if k.startswith("IDEM#")] == ["IDEM#live"]
    assert [e["action"] for e in audit(ddb, "STUDENT", sid)] == ["STUDENT_IDEMPOTENCY_PURGED"]


# ------------------------------------------------------------------------------------------------ stream consumers

def image(item: dict | None, raw: bool) -> dict | None:
    if item is None:
        return None
    return {k: SER.serialize(toolkit.encode(v)) for k, v in item.items()} if raw else item


def record(name, old=None, new=None, *, raw=False, ident=None, eid=None) -> dict:
    src = old or new
    body = {"Keys": image({"PK": src["PK"], "SK": src["SK"]}, raw), "SequenceNumber": eid or str(uuid.uuid4().int)}
    if old is not None:
        body["OldImage"] = image(old, raw)
    if new is not None:
        body["NewImage"] = image(new, raw)
    rec = {"eventID": eid or uuid.uuid4().hex, "eventName": name, "dynamodb": body}
    if ident:
        rec["userIdentity"] = ident
    return rec


OUT = {"PK": f"STUDENT#{uuid.uuid4()}", "SK": "OUTCOME#2026-01-01T00:00:00.000000Z#" + str(uuid.uuid4()), "type": "OUTCOME",
       "is_correct": True, "hint_count": 0}
TTL = {"type": "Service", "principalId": "dynamodb.amazonaws.com"}


@pytest.mark.parametrize("raw", [False, True])
def test_integrity_alarm_fires_on_modify_and_remove_of_append_only_types_only(store, raw, capsys):
    lc.COUNTERS.clear()
    for kind in ("OUTCOME", "MEVID", "EVENT", "MCEVENT", "IXEVENT", "MISCEVID", "DIAG"):
        item = {**OUT, "type": kind}
        out = lc.integrity_handler({"Records": [record("MODIFY", item, {**item, "is_correct": False}, raw=raw)]}, store=store)
        assert [v["reason"] for v in out["violations"]] == [f"MODIFY of {kind}"], kind
    out = lc.integrity_handler({"Records": [record("REMOVE", OUT, raw=raw)]}, store=store)
    assert [v["reason"] for v in out["violations"]] == ["REMOVE of OUTCOME"]
    assert lc.COUNTERS[lc.VIOLATION_METRIC] == 8
    assert lc.VIOLATION_METRIC in capsys.readouterr().out                      # the EMF line reaches CloudWatch


@pytest.mark.parametrize("raw", [False, True])
def test_integrity_ignores_inserts_ttl_expiry_other_types_and_the_repair_edit(store, raw):
    lc.COUNTERS.clear()
    pending = {**OUT, "mastery_pending": True}
    cases = [
        record("INSERT", None, OUT, raw=raw),
        record("REMOVE", OUT, raw=raw, ident=TTL),
        record("MODIFY", {**OUT, "type": "MASTERY"}, {**OUT, "type": "MASTERY", "mastery_score": 0.3}, raw=raw),
        record("REMOVE", {**OUT, "type": "IDEM"}, raw=raw),
        record("MODIFY", pending, OUT, raw=raw),                                # mastery-repair clearing its flag
    ]
    out = lc.integrity_handler({"Records": cases}, store=store)
    assert out["violations"] == [] and lc.COUNTERS[lc.VIOLATION_METRIC] == 0
    # ... but changing anything else while clearing the flag, or setting the flag, is a violation
    sneaky = lc.integrity_handler({"Records": [record("MODIFY", pending, {**OUT, "is_correct": False}, raw=raw),
                                               record("MODIFY", OUT, pending, raw=raw)]}, store=store)
    assert len(sneaky["violations"]) == 2


def test_integrity_allows_removals_inside_a_partition_being_erased_but_not_elsewhere(store):
    sid = register(store, "ada@example.org")
    mine = {**OUT, "PK": toolkit.student_pk(sid)}
    assert len(lc.integrity_handler({"Records": [record("REMOVE", mine)]}, store=store)["violations"]) == 1
    store.request_erasure(sid, "x")
    assert lc.integrity_handler({"Records": [record("REMOVE", mine)]}, store=store)["violations"] == []
    other = {**OUT, "PK": toolkit.student_pk(uuid.uuid4())}
    assert len(lc.integrity_handler({"Records": [record("REMOVE", other)]}, store=store)["violations"]) == 1


@pytest.mark.parametrize("raw", [False, True])
def test_mastery_repair_restores_missing_evidence_equals_recompute_and_clears_the_flag(ddb, corpus, raw):
    sid = register(corpus, "ada@example.org")
    now = datetime.now(UTC)
    commit(corpus, sid, Q1, True, now - dt.timedelta(days=2))
    staged = commit(corpus, sid, Q1, False, now - dt.timedelta(days=1))
    expected = mastery_scores(sid)
    pk = toolkit.student_pk(sid)
    outcome = next(i for i in toolkit.query_page(CTX, pk, sk_begins="OUTCOME#", forward=False)["items"] if i["is_correct"] is False)
    for ev in toolkit.query_page(CTX, pk, sk_begins="MEVID#", limit=200)["items"]:
        if str(staged.attempt["attempt_id"]) in ev["SK"]:
            toolkit.transact([toolkit.Delete(CTX, ev["PK"], ev["SK"])])
    toolkit.transact([toolkit.Update(CTX, pk, outcome["SK"], "SET #m = :t", names={"#m": "mastery_pending"}, values={":t": True})])
    for tag in mastery_scores(sid):                                          # stale scores: only the first outcome counted
        OutcomesDynamoDB()._rebuild(UUID(sid), tag[0], UUID(tag[1]))
    assert mastery_scores(sid) != expected
    pending = toolkit.get_item(CTX, pk, outcome["SK"])
    out = lc.mastery_repair_handler({"Records": [record("INSERT", None, pending, raw=raw)]}, store=corpus)
    assert out == {"batchItemFailures": []}
    assert mastery_scores(sid) == pytest.approx(expected)
    assert "mastery_pending" not in toolkit.get_item(CTX, pk, outcome["SK"])
    assert typed.require(OutcomeItem, pk, outcome["SK"]).is_correct is False
    assert len(typed.query(MevidItem, pk, sk_begins="MEVID#", limit=200).items) == 2 * len(expected)
    assert corpus.repair_pending_outcome(sid, outcome["SK"]) == {"status": "clear"}     # idempotent
    # the same edit seen by learner-integrity is not an alarm
    cleared = toolkit.get_item(CTX, pk, outcome["SK"])
    assert lc.integrity_handler({"Records": [record("MODIFY", pending, cleared, raw=raw)]}, store=corpus)["violations"] == []


def test_mastery_repair_ignores_everything_but_pending_inserts_and_reports_failures(store):
    ok = lc.mastery_repair_handler({"Records": [record("INSERT", None, OUT), record("MODIFY", OUT, {**OUT, "mastery_pending": True})]},
                                   store=store)
    assert ok == {"batchItemFailures": []}
    pend = {**OUT, "mastery_pending": True}
    second = {**pend, "PK": pend["PK"], "SK": pend["SK"] + "x"}

    class Failing:
        def repair_pending_outcome(self, *a):
            raise RuntimeError("down")

    out = lc.mastery_repair_handler({"Records": [record("INSERT", None, pend, eid="1"), record("INSERT", None, second, eid="2")]},
                                    store=Failing())
    assert [f["itemIdentifier"] for f in out["batchItemFailures"]] == ["1", "2"]          # later records of the item keep order


@pytest.mark.parametrize("raw", [False, True])
def test_mastery_cohort_counts_students_scores_and_attempts_exactly_once(store, raw):
    cid = str(uuid.uuid4())

    def mast(sid, score, attempts, kind="C"):
        return {"PK": toolkit.student_pk(sid), "SK": f"MASTERY#{kind}#{cid}", "type": "MASTERY", "mastery_score": score,
                "attempts_count": attempts}

    s1, s2 = str(uuid.uuid4()), str(uuid.uuid4())
    batch = [record("INSERT", None, mast(s1, 0.5, 2), raw=raw, eid="e1"), record("INSERT", None, mast(s2, 0.3, 1), raw=raw, eid="e2"),
             record("MODIFY", mast(s1, 0.5, 2), mast(s1, 0.7, 3), raw=raw, eid="e3"),
             record("INSERT", None, mast(s1, 0.9, 9, kind="T"), raw=raw, eid="e4")]
    assert lc.mastery_cohort_handler({"Records": batch}, store=store) == {"batchItemFailures": []}
    row = typed.require(CohortItem, "COHORT#CONCEPT", cid)
    assert (row.n_students, row.sum_attempts) == (2, 4) and row.sum_score == pytest.approx(1.0)
    lc.mastery_cohort_handler({"Records": batch}, store=store)                              # redelivered batch: no double count
    assert typed.require(CohortItem, "COHORT#CONCEPT", cid).n_students == 2
    lc.mastery_cohort_handler({"Records": [record("REMOVE", mast(s2, 0.3, 1), raw=raw, eid="e5"),
                                           record("MODIFY", mast(s1, 0.7, 3), mast(s1, 0.7, 3), raw=raw, eid="e6")]}, store=store)
    row = typed.require(CohortItem, "COHORT#CONCEPT", cid)
    assert (row.n_students, row.sum_attempts) == (1, 3) and row.sum_score == pytest.approx(0.7)


def test_cohort_delta_is_exact_in_decimal_arithmetic():
    rec = lc.StreamRecord.model_validate(record("MODIFY", {"PK": "STUDENT#a", "SK": "MASTERY#C#c1", "type": "MASTERY",
                                                          "mastery_score": Decimal("0.1"), "attempts_count": 1},
                                                {"PK": "STUDENT#a", "SK": "MASTERY#C#c1", "type": "MASTERY",
                                                 "mastery_score": Decimal("0.3"), "attempts_count": 2}))
    delta = lc.cohort_delta(rec)
    assert delta.d_score == Decimal("0.2") and delta.d_students == 0 and delta.d_attempts == 1


def test_abandon_stale_handler_loops_batches_and_defaults_to_the_configured_idle_days(monkeypatch):
    class Fake:
        def __init__(self):
            self.calls = []
            self.queue = [["a"] * 3, ["b"] * 3, ["c"]]

        def abandon_stale_attempts(self, idle_days, limit):
            self.calls.append((idle_days, limit))
            return self.queue.pop(0)

    monkeypatch.setattr(settings, "abandon_idle_days", 21)
    fake = Fake()
    assert lc.abandon_stale_handler({"limit": 3}, store=fake) == {"abandoned": 7, "idle_days": 21}
    assert fake.calls == [(21, 3)] * 3
    fake2 = Fake()
    assert lc.abandon_stale_handler({"idle_days": 5, "limit": 3}, store=fake2)["idle_days"] == 5


def test_abandon_stale_handler_uses_the_learner_store_without_postgres(store):
    assert lc.abandon_stale_handler({}) == {"abandoned": 0, "idle_days": settings.abandon_idle_days}


def test_rebuild_handler_walks_the_directory_and_resumes_by_token(store):
    ids = [register(store, f"{e}@example.org") for e in "abc"]
    out = lc.rebuild_handler({"kind": "daily", "max_seconds": 0}, store=store)
    assert out["processed"] == 3 and out["next_token"] is None and out["failed"] == []
    one = lc.rebuild_handler({"kind": "mastery", "student_id": ids[0]}, store=store)
    assert one["processed"] == 1 and one["result"]["student_id"] == ids[0]
    with pytest.raises(ValueError):
        lc.rebuild_handler({"kind": "nope"}, store=store)


# ------------------------------------------------------------------------------------------------ interaction events

def put_ix(sid, eid, instance, n, created):
    typed.put(mc.LearnerIxevent(
        PK=toolkit.student_pk(sid), SK=mc.ixevent_sk(eid, instance, toolkit.encode(created), (ixid := str(uuid.uuid4()))),
        student_id=sid, enrollment_id=eid, interaction_event_id=ixid, interaction_instance_id=instance,
        course_state_id=str(uuid.uuid4()), created_at=created, event_type="CHANGE", semantic_action=f"A{n}", control_key="c",
        action_payload={"value": float(n)}))


def test_interaction_events_list_per_enrollment_after_a_time_with_signed_paging(store):
    sid, e1, e2, inst = register(store, "ada@example.org"), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    t0 = datetime(2026, 10, 1, tzinfo=UTC)
    for n in range(5):
        put_ix(sid, e1, inst, n, t0 + dt.timedelta(minutes=n))
    put_ix(sid, e2, inst, 9, t0)
    first = store.list_admin_interaction_events(student_id=sid, enrollment_id=e1, limit=2)
    assert [r["semantic_action"] for r in first["items"]] == ["A0", "A1"] and first["next_token"]
    assert "action_payload" not in first["items"][0]
    rest = store.list_admin_interaction_events(student_id=sid, enrollment_id=e1, limit=10, next_token=first["next_token"],
                                               include_payload=True)
    assert [r["semantic_action"] for r in rest["items"]] == ["A2", "A3", "A4"] and rest["items"][0]["action_payload"] == {"value": 2.0}
    late = store.list_admin_interaction_events(student_id=sid, enrollment_id=e1, after=(t0 + dt.timedelta(minutes=2)).isoformat())
    assert [r["semantic_action"] for r in late["items"]] == ["A3", "A4"]
    every = store.list_admin_interaction_events(student_id=sid, limit=50)
    assert len(every["items"]) == 6
    with pytest.raises(InvalidToken):
        store.list_admin_interaction_events(student_id=sid, enrollment_id=e1, next_token="x.y")
    with pytest.raises(ValidationFailed):
        store.list_admin_interaction_events(student_id=sid, after="not a time")


# ------------------------------------------------------------------------------------------------ composition / postgres

def test_postgres_admin_answers_501_for_what_only_dynamodb_has_and_delegates_the_rest(monkeypatch):
    pg = PostgresLearnerStore()
    for call in (lambda: pg.request_erasure("s", "a"), lambda: pg.erase_partition("s"), lambda: pg.rebuild_mastery("s"),
                 lambda: pg.revoke_student_tokens("s", "a"), lambda: pg.purge_idempotency("s"),
                 lambda: pg.list_admin_interaction_events(student_id="s"),
                 lambda: pg.list_admin_daily_activity(date_from=date(2026, 1, 1), date_to=date(2026, 1, 2))):
        with pytest.raises(StoreNotImplemented):
            call()
    from mathbank_rest.db import learner as learner_db

    seen = []
    monkeypatch.setattr(learner_db, "set_student_status", lambda sid, status, actor: seen.append((str(sid), status, actor)) or {"ok": 1})
    sid = str(uuid.uuid4())
    assert pg.set_account_status(sid, "DISABLED", "service:admin-key") == {"ok": 1} and seen == [(sid, "DISABLED", "service:admin-key")]
    monkeypatch.setattr(learner_db, "list_daily_activity", lambda s, a, b: [{"activity_date": a, **dict.fromkeys(lc_counters(), 1)}])
    out = pg.list_admin_daily_activity(date_from=date(2026, 1, 1), date_to=date(2026, 1, 2), student_id=sid)
    assert out["items"][0]["student_id"] == sid and AdminPostgres


def test_admin_methods_follow_the_read_prefix_rule():
    reads = {"list_admin_students", "get_admin_student", "list_admin_daily_activity", "list_admin_interaction_events",
             "get_enrollment_reset_info", "get_erasure_job", "list_pending_erasures"}
    writes = {"set_account_status", "revoke_student_tokens", "request_erasure", "erase_partition", "rebuild_mastery",
              "rebuild_daily_activity", "purge_idempotency", "record_admin_audit", "apply_cohort_change", "repair_pending_outcome"}
    assert all(n.startswith(stores.READ_PREFIXES) for n in reads)
    assert not any(n.startswith(stores.READ_PREFIXES) for n in writes)
    assert all(hasattr(DynamoDBLearnerStore, n) and hasattr(PostgresLearnerStore, n) for n in reads | writes)
    assert IdentityDynamoDB and AdminDynamoDB


# ------------------------------------------------------------------------------------------------ routes

@pytest.fixture()
def client(store):
    app = FastAPI()
    install_error_handlers(app)
    app.include_router(admin_learner.router)
    app.include_router(mc_router.admin_router)
    return TestClient(app, raise_server_exceptions=False)


def new_routes():
    return [(m, r.path) for r in admin_learner.router.routes for m in sorted(r.methods)]


def fill(path: str) -> str:
    return path.replace("{student_id}", str(uuid.uuid4())).replace("{enrollment_id}", str(uuid.uuid4()))


def test_every_new_admin_route_needs_the_admin_credential_and_refuses_a_learner_token(client):
    token = security.create_access_token(uuid.uuid4(), token_version=0)
    routes = new_routes() + [("GET", "/v1/admin/micro-courses/enrollments/{enrollment_id}"),
                             ("POST", "/v1/admin/micro-courses/enrollments/{enrollment_id}/reset")]
    assert len(routes) >= 25
    for method, path in routes:
        none = client.request(method, fill(path), json={} if method == "POST" else None)
        assert none.status_code == 401, (method, path, none.status_code)
        student = client.request(method, fill(path), headers={"Authorization": f"Bearer {token}"}, json={} if method == "POST" else None)
        assert student.status_code in (401, 403), (method, path, student.status_code)


def test_route_directory_detail_and_tampered_token(client, store):
    a = register(store, "a@example.org")
    register(store, "b@example.org")
    page = client.get("/v1/admin/learner/students", headers=H, params={"limit": 1}).json()
    assert page["items"][0]["student_id"] == a and page["next_token"]
    nxt = client.get("/v1/admin/learner/students", headers=H, params={"limit": 1, "next_token": page["next_token"]}).json()
    assert nxt["items"][0]["email"] == "b@example.org"
    bad = client.get("/v1/admin/learner/students", headers=H, params={"next_token": page["next_token"][:-3] + "AAA"})
    assert bad.status_code == 400 and bad.json()["detail"] == "invalid_next_token"
    detail = client.get(f"/v1/admin/learner/students/{a}", headers=H).json()
    assert detail["status"] == "ACTIVE" and "password_hash" not in detail and "search_blob" not in detail
    assert client.get(f"/v1/admin/learner/students/{uuid.uuid4()}", headers=H).status_code == 404
    assert client.get("/v1/admin/learner/students", headers=H, params={"status": "NOPE"}).status_code == 422


def test_route_disable_revoke_reactivate_record_the_credential_actor(ddb, client, store):
    sid = register(store, "a@example.org")
    r = client.post(f"/v1/admin/learner/students/{sid}/disable", headers=H, json={"reason": "spam"})
    assert r.status_code == 200 and r.json()["status"] == "DISABLED"
    assert client.post(f"/v1/admin/learner/students/{sid}/reactivate", headers=H).json()["status"] == "ACTIVE"
    assert client.post(f"/v1/admin/learner/students/{sid}/revoke-tokens", headers=H).json()["token_version"] == 2
    assert {e["actor_id"] for e in audit(ddb, "STUDENT", sid)} == {"service:admin-key"}
    assert client.post(f"/v1/admin/learner/students/{uuid.uuid4()}/disable", headers=H).status_code == 404
    spoof = client.post(f"/v1/admin/learner/students/{sid}/disable", headers=H, json={"actor": "staff:mallory"})
    assert spoof.status_code == 422                                          # an actor name is never accepted from the client


def test_route_erase_returns_202_flags_erasing_and_the_worker_finishes_it(ddb, client, store, real_status):
    sid = register(store, "ada@example.org")
    r = client.post(f"/v1/admin/learner/students/{sid}/erase", headers=H, json={"reason": "gdpr"})
    assert r.status_code == 202 and r.json()["status"] == "ERASING" and r.json()["job_id"]
    assert rejected(sid, 0) and store.get_admin_student(sid)["status"] == "ERASING"
    assert client.get(f"/v1/admin/learner/students/{sid}/erasure", headers=H).json()["status"] == "ERASING"
    assert client.post(f"/v1/admin/learner/students/{sid}/erase", headers=H).json()["job_id"] == r.json()["job_id"]
    assert client.post(f"/v1/admin/learner/students/{sid}/disable", headers=H).status_code == 409
    lc.erasure_handler({"student_id": sid})
    again = client.post(f"/v1/admin/learner/students/{sid}/erase", headers=H)
    assert again.status_code == 200 and again.json()["status"] == "ERASED"
    assert client.get(f"/v1/admin/learner/students/{sid}", headers=H).status_code == 404
    assert client.post(f"/v1/admin/learner/students/{uuid.uuid4()}/erase", headers=H).status_code == 404
    assert {e["actor_id"] for e in audit(ddb, "STUDENT", sid)} == {"service:admin-key"}


def test_route_per_student_views_and_events_carry_the_full_payload(client, store):
    sid = register(store, "a@example.org")
    put_event(sid, datetime(2026, 10, 1, tzinfo=UTC), "STEP_EVALUATED", {"result": "SUCCESS", "evaluation": {"confidence": 0.9}})
    events = client.get(f"/v1/admin/learner/students/{sid}/events", headers=H).json()
    assert events["items"][0]["payload"]["evaluation"] == {"confidence": 0.9}
    for tail in ("attempts", "mastery", "solve-attempts", "misconceptions"):
        assert client.get(f"/v1/admin/learner/students/{sid}/{tail}", headers=H).status_code == 200, tail
    assert client.get(f"/v1/admin/learner/students/{uuid.uuid4()}/events", headers=H).status_code == 404


def test_route_gaps_and_plans_are_501_until_the_store_provides_them(client, store):
    sid = register(store, "a@example.org")
    for tail in ("knowledge-gaps", "recovery-plans"):
        r = client.get(f"/v1/admin/learner/students/{sid}/{tail}", headers=H)
        if hasattr(store, "list_student_gaps" if tail == "knowledge-gaps" else "admin_plans"):
            assert r.status_code in (200, 404, 422, 500)
        else:
            assert r.status_code == 501 and r.json()["detail"] == "store_not_implemented"


def test_route_rebuilds_purge_and_bulk_guards(ddb, client, store):
    sid = register(store, "a@example.org")
    assert client.post(f"/v1/admin/learner/students/{sid}/mastery/rebuild", headers=H).json()["student_id"] == sid
    assert client.post("/v1/admin/learner/mastery/rebuild", headers=H, params={"student_id": sid}).status_code == 200
    assert client.post("/v1/admin/learner/mastery/rebuild", headers=H).status_code == 422
    assert client.post("/v1/admin/analytics/learner-daily-activity/rebuild", headers=H, json={"student_id": sid}).json()["days"] == 0
    assert client.post("/v1/admin/learner/idempotency-records/purge", headers=H, params={"student_id": sid}).json()["deleted"] == 0
    assert client.post("/v1/admin/learner/idempotency-records/purge", headers=H).status_code == 422
    assert {e["actor_id"] for e in audit(ddb, "STUDENT", sid)} == {"service:admin-key"}


def test_route_daily_activity_and_weak_concepts_floor(client, store, monkeypatch):
    sid = register(store, "a@example.org")
    put_event(sid, datetime.now(UTC), "ATTEMPT_STARTED")
    client.post("/v1/admin/analytics/learner-daily-activity/rebuild", headers=H, json={"student_id": sid})
    one = client.get("/v1/admin/analytics/learner-daily-activity", headers=H, params={"student_id": sid}).json()
    assert one["items"][0]["attempts_started"] == 1
    assert client.get("/v1/admin/analytics/learner-daily-activity", headers=H, params={"group_by": "day"}).json()["scope"] == "page"
    assert client.get("/v1/admin/analytics/learner-daily-activity", headers=H, params={"from": "2026-12-01", "to": "2026-01-01"}).status_code == 422
    cid = str(uuid.uuid4())
    typed.put(CohortItem(PK="COHORT#CONCEPT", SK=cid, concept_id=cid, n_students=3, sum_score=1.5, updated_at=datetime.now(UTC)))
    body = client.get("/v1/admin/analytics/weak-concepts", headers=H, params={"min_students": 1}).json()
    assert body["suppressed"] is True and body["cohort_min_students"] == settings.cohort_min_students and body["results"] == []


def test_route_import_attempt_records_an_import_outcome_for_the_student_and_audits(ddb, client, corpus):
    sid = register(corpus, "ada@example.org")
    r = client.post(f"/v1/admin/learner/students/{sid}/attempts:import", headers={**H, "Idempotency-Key": "k1"},
                    json={"problem_code": Q1, "is_correct": True, "hint_count": 1})
    assert r.status_code == 201 and set(r.json()) == {"attempt", "updated_mastery"}
    again = client.post(f"/v1/admin/learner/students/{sid}/attempts:import", headers={**H, "Idempotency-Key": "k1"},
                        json={"problem_code": Q1, "is_correct": True, "hint_count": 1})
    assert again.json()["attempt"]["attempt_id"] == r.json()["attempt"]["attempt_id"]
    outcomes = typed.query(OutcomeItem, toolkit.student_pk(sid), sk_begins="OUTCOME#").items
    assert len(outcomes) == 1 and outcomes[0].source == "import"
    assert client.post(f"/v1/admin/learner/students/{sid}/attempts:import", headers=H,
                       json={"problem_code": "NOPE", "is_correct": True}).status_code == 404
    assert client.post(f"/v1/admin/learner/students/{sid}/attempts:import", headers=H,
                       json={"problem_code": Q1, "is_correct": True, "source": "web"}).status_code == 422
    assert any(e["action"] == "STUDENT_ATTEMPT_IMPORTED" and e["actor_id"] == "service:admin-key" for e in audit(ddb, "STUDENT", sid))


# ------------------------------------------------------------------------------------------------ micro-course admin routes

@pytest.fixture()
def course(world, store, ddb):                                      # noqa: F811  (world is the imported fixture)
    return world


def test_micro_course_admin_drill_down_reset_and_activity_run_on_the_learner_store(ddb, client, course):
    student = course
    eid = eid_of(enroll(student))
    drill = client.get(f"/v1/admin/micro-courses/enrollments/{eid}", headers=H)
    assert drill.status_code == 200 and drill.json()["student_id"] == student and drill.json()["state_version"] == 1
    assert client.get(f"/v1/admin/micro-courses/enrollments/{uuid.uuid4()}", headers=H).status_code == 404
    finish_assessment(eid, student)
    stores.get_store("learner").advance_enrollment(None, eid, student, 1, "CONTINUE")
    version = client.get(f"/v1/admin/micro-courses/enrollments/{eid}", headers=H).json()["state_version"]
    stale = client.post(f"/v1/admin/micro-courses/enrollments/{eid}/reset", headers=H, json={"expected_state_version": version - 1})
    assert stale.status_code == 409
    wrong = client.post(f"/v1/admin/micro-courses/enrollments/{eid}/reset", headers=H,
                        json={"expected_state_version": version, "to_state_id": mcw.uid(555)})
    assert wrong.status_code == 422
    ok = client.post(f"/v1/admin/micro-courses/enrollments/{eid}/reset", headers=H, json={"expected_state_version": version})
    assert ok.status_code == 200 and ok.json()["current_state"]["state_id"] == mcw.STATE1 and ok.json()["state_version"] == version + 1
    reset = next(e for e in items_of(student, mc.LearnerMcevent) if e.event_type == "RESET")
    assert reset.actor_type == "ADMIN" and reset.payload["actor"] == "service:admin-key"
    entries = audit(ddb, "MICRO_COURSE_ENROLLMENT", eid)
    assert [e["action"] for e in entries] == ["ENROLLMENT_RESET"] and entries[0]["actor_id"] == "service:admin-key"
    assert client.post(f"/v1/admin/micro-courses/enrollments/{uuid.uuid4()}/reset", headers=H,
                       json={"expected_state_version": 1}).status_code == 404
    activity = client.get("/v1/admin/micro-courses/MC-1/activity", headers=H)
    assert activity.status_code == 200 and activity.json()["total_enrollments"] == 1
    ix = client.get("/v1/admin/learner/interaction-events", headers=H, params={"enrollment_id": eid})
    assert ix.status_code == 200 and ix.json()["items"] == []
    assert client.get("/v1/admin/learner/interaction-events", headers=H).status_code == 422
    assert client.get("/v1/admin/learner/interaction-events", headers=H,
                      params={"enrollment_id": eid, "student_id": str(uuid.uuid4())}).status_code == 404
