"""WP3 jobs store and SQS wrapper on moto: enqueue ordering, conditional claims, leases, retries and DLQ, idempotent
redelivery, cancellation, promotion, listing, S3 offload, frozen cutover. Real-AWS threaded claim race is marked
``ddb_integration``."""
from __future__ import annotations

import datetime as dt
import json
import threading
import uuid

import pytest
from wp3_support import wp3_fixture  # noqa: F401  (fixture 'wp3')

from mathbank_rest import jobs_queue
from mathbank_rest.jobs_queue import JobMessage, JobsQueue, process_sqs_event, queue_name
from mathbank_rest.models.manual.jobs import JobsRenderjob, JobsResearchjob
from mathbank_rest.stores import FrozenProxy, typed
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores.errors import (
    ConditionFailed,
    InvalidToken,
    ItemSchemaError,
    NotFound,
    StoreFrozen,
    StoreUnavailable,
    ValidationFailed,
)
from mathbank_rest.stores.jobs import DynamoDBJobsStore, LeaseLost
from mathbank_rest.stores.jobs import dynamodb as jobs_mod

SPEC = {"scene_key": "x", "scene_version": 1, "objects": [], "timeline": []}


@pytest.fixture()
def store(wp3):
    return DynamoDBJobsStore()


def drain(kind: str, n: int = 10) -> list[JobMessage]:
    """Consume (receive and delete) the visible messages of a queue."""
    q = JobsQueue()
    got = q.receive(kind, max_messages=n, wait_seconds=0, visibility_timeout=30)
    q.delete_batch(kind, [r.receipt_handle for r in got])
    return [r.message for r in got]


def delayed(kind: str) -> int:
    attrs = toolkit.client("sqs").get_queue_attributes(QueueUrl=JobsQueue().url(kind), AttributeNames=["All"])["Attributes"]
    return int(attrs["ApproximateNumberOfMessagesDelayed"])


def research(store, topic="Vieta") -> str:
    return store.create_research_job(topic, {"concept_code": "VIETA"}, requested_by="staff:1")["scene_research_job_id"]


def item(kind, jid):
    model, prefix = (JobsResearchjob, "RESEARCH") if kind == "research" else (JobsRenderjob, "RENDER")
    return typed.require(model, f"{prefix}#{jid}", "META")


def age(kind, jid, **changes):
    it = item(kind, jid)
    typed.update(type(it), it.PK, it.SK, it.version, changes)


# ------------------------------------------------------------------ create and enqueue

def test_create_writes_a_validated_item_then_one_message(store):
    row = store.create_research_job("Vieta", {"a": 1}, requested_by="staff:1")
    jid = row["scene_research_job_id"]
    assert row["status"] == "PENDING" and row["context_json"] == {"a": 1} and row["attempts"] == 0
    it = item("research", jid)
    assert it.version == 1 and it.GSI1PK == "RESEARCH#STATUS#PENDING" and it.requested_by == "staff:1"
    assert it.expires_at - it.created_at == dt.timedelta(days=1) and it.ttl == int(it.expires_at.timestamp())
    msgs = drain("research")
    assert [(str(m.job_id), m.kind, m.version) for m in msgs] == [(jid, "research", 1)]
    assert drain("render") == []


def test_item_is_written_before_the_message_and_a_lost_send_is_recovered(store, monkeypatch):
    sent = []

    def lost(message, **_):
        assert typed.get(JobsResearchjob, f"RESEARCH#{message.job_id}", "META") is not None  # item first
        sent.append(message)
        raise StoreUnavailable("sqs down")

    with monkeypatch.context() as m:
        m.setattr(store.queue, "send", lost)
        jid = research(store)  # creation still succeeds
    assert len(sent) == 1 and store.get_research_job(jid)["status"] == "PENDING"
    assert drain("research") == []  # nothing was queued
    assert store.republish_pending("research", older_than_seconds=-5) == 1
    assert [str(m.job_id) for m in drain("research")] == [jid]


def test_republish_skips_fresh_running_and_finished_jobs(store):
    pending, running, done = research(store, "a"), research(store, "b"), research(store, "c")
    drain("research")
    claim = store.claim("research", running, "w")
    d = store.claim("research", done, "w")
    store.complete_research_job(done, d.claim_token, SPEC, "e")
    assert claim and store.republish_pending("research", older_than_seconds=-5) == 1  # only the PENDING one
    assert [str(m.job_id) for m in drain("research")] == [pending]


def test_render_job_from_a_research_job_needs_it_done(store):
    rid = research(store)
    with pytest.raises(ConditionFailed):
        store.create_render_job(source_research_job_id=rid)
    with pytest.raises(NotFound):
        store.create_render_job(source_research_job_id=str(uuid.uuid4()))
    with pytest.raises(ValidationFailed):
        store.create_render_job()
    c = store.claim("research", rid, "w")
    store.complete_research_job(rid, c.claim_token, SPEC, "e")
    render = store.create_render_job(source_research_job_id=rid)
    assert render["scene_spec_json"] == SPEC and render["source_research_job_id"] == rid and render["status"] == "PENDING"
    assert [m.kind for m in drain("render")] == ["render"]


# ------------------------------------------------------------------ claims, leases, idempotency

def test_claim_sets_a_lease_and_only_one_claimant_wins(store):
    jid = research(store)
    first = store.claim("research", jid, "w1")
    assert first and first.attempts == 1 and first.payload == {"topic": "Vieta", "context_json": {"concept_code": "VIETA"}}
    assert first.lease_until > dt.datetime.now(dt.UTC) + dt.timedelta(seconds=300)
    assert store.claim("research", jid, "w2") is None  # live lease: duplicate / stale delivery
    it = item("research", jid)
    assert it.status == "RUNNING" and it.claim_token == first.claim_token and it.claimed_by == "w1" and it.GSI1PK.endswith("#RUNNING")
    assert it.expires_at >= it.lease_until + dt.timedelta(days=1) - dt.timedelta(seconds=1)  # never reaped under the worker


def test_losing_the_optimistic_race_is_a_none_not_an_error(store, monkeypatch):
    jid = research(store)
    real = jobs_mod.DynamoDBJobsStore._load
    calls = {"n": 0}

    def stale_then_fresh(self, spec, job_id, **kw):
        got = real(self, spec, job_id, **kw)
        if calls["n"] == 0:  # the other worker claims between our read and our write
            calls["n"] += 1
            assert store.claim("research", jid, "winner")
        return got

    monkeypatch.setattr(jobs_mod.DynamoDBJobsStore, "_load", stale_then_fresh)
    assert store.claim("research", jid, "loser") is None
    assert item("research", jid).claimed_by == "winner"


def test_duplicate_delivery_of_claimed_or_finished_jobs_is_a_noop(store):
    jid = research(store)
    c = store.claim("research", jid, "w1")
    assert store.claim("research", jid, "w1") is None
    store.complete_research_job(jid, c.claim_token, SPEC, "e")
    before = item("research", jid)
    assert store.claim("research", jid, "w2") is None
    assert item("research", jid).version == before.version
    assert store.claim("research", str(uuid.uuid4()), "w") is None and store.claim("research", "nonsense", "w") is None


def test_complete_stores_the_result_and_is_idempotent_for_the_holder(store):
    jid = research(store)
    c = store.claim("research", jid, "w")
    done = store.complete_research_job(jid, c.claim_token, SPEC, "because")
    again = store.complete_research_job(jid, c.claim_token, {"different": True}, "ignored")
    assert done["status"] == again["status"] == "DONE"
    assert again["result_scene_spec"] == SPEC and again["result_explanation"] == "because"
    it = item("research", jid)
    assert it.lease_until is None and it.GSI1PK == "RESEARCH#STATUS#DONE" and it.version == 3
    with pytest.raises(LeaseLost):
        store.complete_research_job(jid, "someone-else", SPEC, "x")


def test_an_expired_lease_is_reclaimed_and_the_old_worker_loses_everything(store):
    jid = research(store)
    stale = store.claim("research", jid, "w1", lease_seconds=-1)
    fresh = store.claim("research", jid, "w2")
    assert fresh and fresh.attempts == 2 and fresh.claim_token != stale.claim_token
    with pytest.raises(LeaseLost):
        store.complete_research_job(jid, stale.claim_token, SPEC, "late")
    with pytest.raises(LeaseLost):
        store.heartbeat("research", jid, stale.claim_token)
    with pytest.raises(LeaseLost):
        store.fail("research", jid, stale.claim_token, "late")
    assert store.complete_research_job(jid, fresh.claim_token, SPEC, "ok")["status"] == "DONE"


def test_heartbeat_extends_the_lease_and_the_expiry(store):
    jid = research(store)
    c = store.claim("research", jid, "w", lease_seconds=10)
    new = store.heartbeat("research", jid, c.claim_token, lease_seconds=600)
    it = item("research", jid)
    assert it.lease_until == new and new > c.lease_until + dt.timedelta(seconds=500)
    assert it.expires_at >= new + dt.timedelta(days=1) - dt.timedelta(seconds=1)
    store.complete_research_job(jid, c.claim_token, SPEC, "e")
    with pytest.raises(LeaseLost):
        store.heartbeat("research", jid, c.claim_token)


def test_expired_job_cannot_be_claimed(store):
    jid = research(store)
    age("research", jid, expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1))
    assert store.claim("research", jid, "w") is None and store.get_research_job(jid) is None


# ------------------------------------------------------------------ failure, retries, DLQ

def test_attempts_are_bounded_then_the_job_fails_with_delivery_exhausted(store):
    jid = research(store)
    for n in range(1, jobs_mod.MAX_ATTEMPTS + 1):
        assert store.claim("research", jid, f"w{n}", lease_seconds=-1).attempts == n  # each worker dies without finishing
    assert store.claim("research", jid, "w-late") is None
    row = store.get_research_job(jid)
    assert row["status"] == "FAILED" and row["error_message"].startswith("DELIVERY_EXHAUSTED")
    assert item("research", jid).GSI1PK == "RESEARCH#STATUS#FAILED"


def test_fail_records_a_capped_error_and_is_idempotent(store):
    jid = research(store)
    c = store.claim("research", jid, "w")
    row = store.fail("research", jid, c.claim_token, "x" * 10_000)
    assert row["status"] == "FAILED" and len(row["error_message"]) == jobs_mod.ERROR_MAX
    assert store.fail("research", jid, c.claim_token, "again")["error_message"] == row["error_message"]
    assert store.claim("research", jid, "w2") is None


def test_retryable_failure_goes_back_to_pending_with_a_new_message_until_attempts_run_out(store):
    jid = research(store)
    drain("research")
    c = store.claim("research", jid, "w")
    assert store.fail("research", jid, c.claim_token, "flaky", retryable=True)["status"] == "PENDING"
    assert delayed("research") == 1  # the retry is queued with a backoff delay
    c2 = store.claim("research", jid, "w")
    assert c2.attempts == 2 and item("research", jid).error_message == "flaky"
    store.fail("research", jid, c2.claim_token, "flaky", retryable=True)
    c3 = store.claim("research", jid, "w")
    assert store.fail("research", jid, c3.claim_token, "flaky", retryable=True)["status"] == "FAILED"  # attempts used up


def test_dlq_handler_fails_stuck_jobs_but_leaves_finished_ones(store):
    stuck, finished = research(store, "s"), research(store, "f")
    c = store.claim("research", finished, "w")
    store.complete_research_job(finished, c.claim_token, SPEC, "e")
    row = store.fail_exhausted("research", stuck)
    assert row["status"] == "FAILED" and row["error_message"] == "DELIVERY_EXHAUSTED"
    assert store.fail_exhausted("research", finished) is None and store.get_research_job(finished)["status"] == "DONE"
    assert store.fail_exhausted("research", stuck) is None  # already terminal
    assert store.fail_exhausted("research", str(uuid.uuid4())) is None


def test_cancel_only_pending_jobs_and_a_cancelled_job_cannot_be_claimed(store):
    jid, running = research(store), research(store, "r")
    assert store.cancel("research", jid)["status"] == "CANCELLED"
    assert store.cancel("research", jid)["status"] == "CANCELLED"  # idempotent
    assert store.claim("research", jid, "w") is None
    store.claim("research", running, "w")
    with pytest.raises(ConditionFailed):
        store.cancel("research", running)
    with pytest.raises(NotFound):
        store.cancel("research", str(uuid.uuid4()))


def test_retry_resets_a_failed_job_and_queues_it_again(store):
    jid = research(store)
    c = store.claim("research", jid, "w")
    store.fail("research", jid, c.claim_token, "boom")
    drain("research")
    row = store.retry("research", jid)
    it = item("research", jid)
    assert row["status"] == "PENDING" and it.attempts == 0 and it.error_message is None and it.claim_token is None
    assert [str(m.job_id) for m in drain("research")] == [jid]
    assert store.claim("research", jid, "w2").attempts == 1
    with pytest.raises(ConditionFailed):
        store.retry("research", jid)  # RUNNING with a live lease


def test_retry_of_a_stale_running_job(store):
    jid = research(store)
    store.claim("research", jid, "w", lease_seconds=-1)
    assert store.retry("research", jid)["status"] == "PENDING"


# ------------------------------------------------------------------ render jobs, promotion

def render_done(store) -> str:
    rid = store.create_render_job(SPEC)["video_render_job_id"]
    c = store.claim("render", rid, "w")
    assert c.payload == {"scene_spec_json": SPEC}
    row = store.complete_render_job(rid, c.claim_token, "manim-studio/videos/a.mp4", 4200, "mathbank-runtime")
    assert row["video_object_key"] == "manim-studio/videos/a.mp4" and row["video_duration_ms"] == 4200
    return rid


def test_mark_promoted_is_write_once_and_idempotent(store):
    rid = render_done(store)
    sid = str(uuid.uuid4())
    assert store.mark_render_job_promoted(rid, sid)["promoted_scene_spec_id"] == sid
    assert store.mark_render_job_promoted(rid, sid)["promoted_scene_spec_id"] == sid
    with pytest.raises(ConditionFailed):
        store.mark_render_job_promoted(rid, str(uuid.uuid4()))
    with pytest.raises(ValidationFailed):
        store.mark_render_job_promoted(rid, "not-a-uuid")
    pending = store.create_render_job(SPEC)["video_render_job_id"]
    with pytest.raises(ConditionFailed):
        store.mark_render_job_promoted(pending, str(uuid.uuid4()))
    with pytest.raises(NotFound):
        store.mark_render_job_promoted(str(uuid.uuid4()), sid)


def test_list_render_jobs_filters_status_and_unpromoted(store):
    done_a, done_b = render_done(store), render_done(store)
    store.create_render_job(SPEC)
    store.mark_render_job_promoted(done_a, str(uuid.uuid4()))
    assert [j["video_render_job_id"] for j in store.list_render_jobs(status="DONE", unpromoted_only=True)] == [done_b]
    assert {j["video_render_job_id"] for j in store.list_render_jobs(status="DONE")} == {done_a, done_b}
    assert len(store.list_render_jobs()) == 3  # merged across status partitions
    assert len(store.list_render_jobs(status="PENDING")) == 1 and store.list_render_jobs(status="FAILED") == []


def test_list_jobs_pages_newest_first_and_rejects_a_tampered_token(store):
    ids = [research(store, f"t{i}") for i in range(5)]
    seen, token = [], None
    while True:
        page = store.list_jobs("research", status="PENDING", limit=2, next_token=token)
        seen += [j["scene_research_job_id"] for j in page["items"]]
        token = page["next_token"]
        if token is None:
            break
    assert seen == ids[::-1]
    page = store.list_jobs("research", status="PENDING", limit=2)
    with pytest.raises(InvalidToken):
        store.list_jobs("research", status="PENDING", limit=2, next_token=page["next_token"][:-3] + "abc")
    with pytest.raises(InvalidToken):  # bound to its status partition
        store.list_jobs("research", status="DONE", limit=2, next_token=page["next_token"])
    with pytest.raises(ValidationFailed):
        store.list_jobs("research", status="BOGUS")
    with pytest.raises(ValidationFailed):
        store.list_jobs("research", next_token=page["next_token"])


def test_list_filters_by_requester_and_hides_expired_jobs(store):
    mine = store.create_research_job("a", requested_by="staff:1")["scene_research_job_id"]
    theirs = store.create_research_job("b", requested_by="staff:2")["scene_research_job_id"]
    assert [j["scene_research_job_id"] for j in store.list_jobs("research", status="PENDING", requested_by="staff:1")["items"]] == [mine]
    age("research", theirs, expires_at=dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1))
    assert [j["scene_research_job_id"] for j in store.list_jobs("research")["items"]] == [mine]


def test_stale_running_jobs_are_listed(store):
    live, stale = research(store, "a"), research(store, "b")
    store.claim("research", live, "w")
    store.claim("research", stale, "w", lease_seconds=-1)
    assert [j["scene_research_job_id"] for j in store.list_stale_jobs("research")] == [stale]


# ------------------------------------------------------------------ validation and offload

def test_large_results_are_offloaded_to_s3_and_read_back(store):
    jid = research(store)
    c = store.claim("research", jid, "w")
    big = {"scene_key": "x", "blob": "y" * 40_000}
    store.complete_research_job(jid, c.claim_token, big, "e")
    it = item("research", jid)
    assert it.result_scene_spec is None and it.result_scene_spec_ref is not None
    assert toolkit.client("s3").get_object(Bucket=it.result_scene_spec_ref.bucket, Key=it.result_scene_spec_ref.key)["Body"].read()
    assert store.get_research_job(jid)["result_scene_spec"] == big


def test_large_context_is_offloaded_at_creation(store):
    jid = store.create_research_job("t", {"blob": "z" * 40_000})["scene_research_job_id"]
    assert item("research", jid).context_json_ref is not None
    assert store.claim("research", jid, "w").payload["context_json"] == {"blob": "z" * 40_000}


def test_writes_are_validated_against_the_item_models(store):
    rid = store.create_render_job(SPEC)["video_render_job_id"]
    c = store.claim("render", rid, "w")
    with pytest.raises(ValidationFailed):
        store.complete("render", rid, c.claim_token, {"unknown_attribute": 1})
    with pytest.raises(ItemSchemaError):
        store.complete("render", rid, c.claim_token, {"video_duration_ms": "long"})
    assert item("render", rid).status == "RUNNING"  # nothing half-written
    with pytest.raises(ValidationFailed):
        store.get_job("bogus", rid)


# ------------------------------------------------------------------ frozen, queue

def test_frozen_store_serves_reads_and_blocks_every_write(store):
    jid = research(store)
    frozen = FrozenProxy("jobs", store)
    assert frozen.get_research_job(jid)["status"] == "PENDING"
    assert len(frozen.list_jobs("research", status="PENDING")["items"]) == 1
    for call in (lambda: frozen.create_research_job("x"), lambda: frozen.claim("research", jid, "w"),
                 lambda: frozen.cancel("research", jid), lambda: frozen.enqueue("research", jid),
                 lambda: frozen.republish_pending("research"), lambda: frozen.fail_exhausted("research", jid)):
        with pytest.raises(StoreFrozen):
            call()
    assert store.get_research_job(jid)["status"] == "PENDING"


def test_queue_round_trip_visibility_and_delete(wp3):
    q = JobsQueue()
    msg = JobMessage(job_id=uuid.uuid4(), kind="render", version=3)
    q.send(msg)
    [got] = q.receive("render", wait_seconds=0, visibility_timeout=60)
    assert got.message == msg and got.receive_count == 1
    assert q.receive("render", wait_seconds=0) == []  # in flight: invisible
    q.delete("render", got.receipt_handle)
    assert q.receive("render", wait_seconds=0, visibility_timeout=0) == []
    assert q.url("render").endswith(queue_name("render", env="ut"))
    assert q.url("render", dlq=True).endswith("mb-studio-render-dlq-ut")


def test_missing_queue_is_a_503_not_a_crash(ddb):
    with pytest.raises(StoreUnavailable):
        JobsQueue().send(JobMessage(job_id=uuid.uuid4(), kind="render"))


def test_poison_messages_are_flagged_and_left_for_the_dlq(wp3):
    q = JobsQueue()
    toolkit.client("sqs").send_message(QueueUrl=q.url("research"), MessageBody='{"job_id": "nope"}')
    [got] = q.receive("research", wait_seconds=0, visibility_timeout=0)
    assert got.message is None and got.error == "invalid_message"
    handled = []
    assert q.poll("research", handled.append, wait_seconds=0, visibility_timeout=0) == 0 and handled == []


def test_poll_deletes_only_messages_whose_handler_succeeded(wp3):
    q = JobsQueue()
    ok, bad = JobMessage(job_id=uuid.uuid4(), kind="research"), JobMessage(job_id=uuid.uuid4(), kind="research")
    q.send_batch([ok, bad])

    def handler(m):
        if m.job_id == bad.job_id:
            raise RuntimeError("boom")

    assert q.poll("research", handler, max_messages=10, wait_seconds=0, visibility_timeout=0) == 1
    left = q.receive("research", max_messages=10, wait_seconds=0, visibility_timeout=0)
    assert [r.message.job_id for r in left] == [bad.job_id]


def test_messages_move_to_the_dlq_after_max_receive_count(wp3):
    q = JobsQueue()
    jid = uuid.uuid4()
    q.send(JobMessage(job_id=jid, kind="research"))
    for _ in range(jobs_queue.MAX_RECEIVE_COUNT):
        assert len(q.receive("research", wait_seconds=0, visibility_timeout=0)) == 1
    assert q.receive("research", wait_seconds=0, visibility_timeout=0) == []
    dead = toolkit.client("sqs").receive_message(QueueUrl=q.url("research", dlq=True), MaxNumberOfMessages=1)["Messages"]
    assert json.loads(dead[0]["Body"])["job_id"] == str(jid)


class FakeSqs:
    """Answers batch calls with per-entry failures, as SQS may."""

    def __init__(self, fail_ids):
        self.fail_ids, self.entries = set(fail_ids), []

    def get_queue_url(self, QueueName):
        return {"QueueUrl": f"https://sqs/{QueueName}"}

    def send_message_batch(self, QueueUrl, Entries):
        self.entries += Entries
        return {"Failed": [{"Id": e["Id"]} for e in Entries if e["Id"] in self.fail_ids]}

    def delete_message_batch(self, QueueUrl, Entries):
        return {"Failed": [{"Id": e["Id"]} for e in Entries if e["Id"] in self.fail_ids]}


def test_batch_send_and_delete_report_partial_failures():
    q = JobsQueue(client=FakeSqs({"1"}), env="ut")
    msgs = [JobMessage(job_id=uuid.uuid4(), kind="research") for _ in range(3)]
    assert q.send_batch(msgs) == [msgs[1]]
    assert q.delete_batch("research", ["h0", "h1", "h2"]) == ["h1"]


def test_lambda_sqs_event_reports_only_the_failed_records():
    good, bad = JobMessage(job_id=uuid.uuid4(), kind="render"), JobMessage(job_id=uuid.uuid4(), kind="render")
    event = {"Records": [{"messageId": "m1", "body": good.model_dump_json()}, {"messageId": "m2", "body": bad.model_dump_json()},
                         {"messageId": "m3", "body": "not json"}]}

    def handler(m):
        if m.job_id == bad.job_id:
            raise RuntimeError("worker crashed")

    assert process_sqs_event(event, handler) == {"batchItemFailures": [{"itemIdentifier": "m2"}, {"itemIdentifier": "m3"}]}


def test_worker_loop_end_to_end_over_sqs(store):
    jid = research(store)
    done = []

    def handle(m):
        c = store.claim(m.kind, str(m.job_id), "w")
        if c is None:
            return  # duplicate or stale: just delete the message
        store.complete_research_job(c.job_id, c.claim_token, SPEC, "e")
        done.append(c.job_id)

    store.queue.send(JobMessage(job_id=jid, kind="research", version=1))  # a duplicate wake-up
    assert store.queue.poll("research", handle, max_messages=10, wait_seconds=0) == 2
    assert done == [jid] and store.get_research_job(jid)["status"] == "DONE"
    assert store.queue.receive("research", wait_seconds=0, visibility_timeout=0) == []


# ------------------------------------------------------------------ real AWS

@pytest.mark.ddb_integration
def test_concurrent_claims_have_exactly_one_winner_on_the_real_test_environment(real_env):
    store = DynamoDBJobsStore(queue=_NoQueue())
    jid = research(store)
    winners: list = []

    def go(n):
        c = store.claim("research", jid, f"w{n}")
        if c:
            winners.append(c)

    threads = [threading.Thread(target=go, args=(n,)) for n in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    try:
        assert len(winners) == 1 and item("research", jid).claim_token == winners[0].claim_token
    finally:
        toolkit.client("dynamodb").delete_item(TableName=toolkit.table_name("jobs"),
                                               Key={"PK": {"S": f"RESEARCH#{jid}"}, "SK": {"S": "META"}})


class _NoQueue:
    def send(self, *_a, **_k):
        return "none"
