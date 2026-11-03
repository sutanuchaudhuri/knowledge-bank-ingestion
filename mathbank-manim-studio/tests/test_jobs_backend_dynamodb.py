"""The Studio on the DynamoDB + SQS job backend (requirement 71 WP3), against moto: workers claim through the jobs store and
never open a Postgres connection. Needs `mathbank_rest` importable and moto; otherwise skipped:

    PYTHONPATH=../mathbank-rest/src .venv/bin/python -m pytest tests/test_jobs_backend_dynamodb.py
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("moto")
pytest.importorskip("mathbank_rest")

from fastapi.testclient import TestClient  # noqa: E402
from mathbank_rest.config import settings as rest_settings  # noqa: E402
from mathbank_rest.jobs_queue import JobMessage, queue_name  # noqa: E402
from mathbank_rest.models.manual.jobs import JobsRenderjob  # noqa: E402
from mathbank_rest.stores import ddb as toolkit  # noqa: E402
from mathbank_rest.stores import typed  # noqa: E402
from moto import mock_aws  # noqa: E402

from mathbank_manim_studio import jobs_backend, main, worker  # noqa: E402

SPEC = {"scene_key": "x", "scene_version": 1, "objects": [], "timeline": []}


def _table(client, ctx: str) -> None:
    client.create_table(
        TableName=f"mb-{ctx}-ut",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("PK", "SK", "GSI1PK", "GSI1SK")],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[{"IndexName": "GSI1", "Projection": {"ProjectionType": "ALL"}, "KeySchema": [
            {"AttributeName": "GSI1PK", "KeyType": "HASH"}, {"AttributeName": "GSI1SK", "KeyType": "RANGE"}]}],
        BillingMode="PAY_PER_REQUEST")


@pytest.fixture()
def backend(monkeypatch):
    for k, v in {"AWS_ACCESS_KEY_ID": "t", "AWS_SECRET_ACCESS_KEY": "t", "AWS_SESSION_TOKEN": "t",
                 "AWS_DEFAULT_REGION": "us-east-2"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    for attr, value in {"ddb_env": "ut", "ddb_region": "us-east-2", "ddb_endpoint_url": "", "data_bucket": "",
                        "aws_profile": ""}.items():
        monkeypatch.setattr(rest_settings, attr, value)
    toolkit.reset_clients()
    with mock_aws():
        _table(toolkit.client("dynamodb"), "jobs")
        toolkit.client("s3").create_bucket(Bucket=toolkit.data_bucket(),
                                           CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
        sqs = toolkit.client("sqs")
        for kind in ("research", "render"):
            dlq = sqs.create_queue(QueueName=queue_name(kind, dlq=True))["QueueUrl"]
            arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
            sqs.create_queue(QueueName=queue_name(kind), Attributes={
                "RedrivePolicy": json.dumps({"deadLetterTargetArn": arn, "maxReceiveCount": "3"})})

        def no_postgres(*_a, **_k):
            raise AssertionError("PostgreSQL used on the dynamodb backend")

        monkeypatch.setattr(jobs_backend, "connection", no_postgres)
        monkeypatch.setattr("mathbank_manim_studio.db.get_engine", no_postgres)
        be = jobs_backend.DynamoJobsBackend(worker_id="test-worker")
        monkeypatch.setattr(worker, "get_backend", lambda: be)
        monkeypatch.setattr(main, "get_backend", lambda: be)
        yield be
    toolkit.reset_clients()


def _agent(monkeypatch, *, fail: bool = False):
    async def research(topic, context):
        if fail:
            raise RuntimeError("llm exploded")
        return SPEC, f"about {topic}"

    monkeypatch.setattr(worker, "run_research_agent", research)


async def test_research_job_runs_end_to_end_over_sqs(backend, monkeypatch):
    _agent(monkeypatch)
    jid = backend.create_research_job("Vieta", {"concept_code": "VIETA"})["scene_research_job_id"]
    assert await worker._process_one_research_job() is True
    job = backend.get_research_job(jid)
    assert job["status"] == "DONE" and job["result_scene_spec"] == SPEC and job["result_explanation"] == "about Vieta"
    assert await worker._process_one_research_job() is False  # queue drained, message deleted


async def test_duplicate_wakeup_for_a_finished_job_is_dropped(backend, monkeypatch):
    _agent(monkeypatch)
    jid = backend.create_research_job("Vieta", {})["scene_research_job_id"]
    backend.store.queue.send(JobMessage(job_id=jid, kind="research"))  # at-least-once delivery
    assert await worker._process_one_research_job() is True
    before = backend.get_research_job(jid)
    assert await worker._process_one_research_job() is False  # duplicate: claim refused, message deleted
    assert backend.get_research_job(jid) == before
    assert backend.store.queue.receive("research", wait_seconds=0, visibility_timeout=0) == []


async def test_agent_failure_is_recorded_and_the_message_is_settled(backend, monkeypatch):
    _agent(monkeypatch, fail=True)
    jid = backend.create_research_job("Vieta", {})["scene_research_job_id"]
    assert await worker._process_one_research_job() is True
    job = backend.get_research_job(jid)
    assert job["status"] == "FAILED" and "llm exploded" in job["error_message"]
    assert backend.store.queue.receive("research", wait_seconds=0, visibility_timeout=0) == []


async def test_render_job_completes_and_the_api_serves_it(backend, monkeypatch):
    _agent(monkeypatch)
    monkeypatch.setattr(worker, "render_and_store", lambda spec: ("manim-studio/videos/a.mp4", 4200))
    client = TestClient(main.app)  # no lifespan: the worker loop is driven by the test
    rid = client.post("/v1/research-jobs", json={"topic": "Vieta"}).json()["id"]
    assert client.post("/v1/render-jobs", json={"research_job_id": rid}).status_code == 409  # not DONE yet
    await worker._process_one_research_job()
    posted = client.post("/v1/render-jobs", json={"research_job_id": rid})
    assert posted.status_code == 200 and posted.json()["status"] == "PENDING"
    vid = posted.json()["id"]
    assert await worker._process_one_render_job() is True
    got = client.get(f"/v1/render-jobs/{vid}").json()
    assert got["status"] == "DONE" and got["video_duration_ms"] == 4200 and got["video_url"] == f"/v1/render-jobs/{vid}/video"
    listed = client.get("/v1/render-jobs", params={"status": "DONE", "unpromoted_only": True}).json()
    assert [j["id"] for j in listed] == [vid]
    assert client.get("/v1/research-jobs/00000000-0000-0000-0000-000000000000").status_code == 404


async def test_mark_promoted_through_the_api_is_idempotent_and_conflicts_are_409(backend, monkeypatch):
    monkeypatch.setattr(worker, "render_and_store", lambda spec: ("k.mp4", 1))
    monkeypatch.setattr(main.get_settings(), "admin_api_key", "secret")
    client = TestClient(main.app)
    vid = client.post("/v1/render-jobs", json={"scene_spec_json": SPEC}).json()["id"]
    await worker._process_one_render_job()
    sid, key = "11111111-1111-1111-1111-111111111111", {"x-admin-api-key": "secret"}
    assert client.post(f"/v1/render-jobs/{vid}/mark-promoted", json={"scene_spec_id": sid}, headers=key).status_code == 200
    assert client.post(f"/v1/render-jobs/{vid}/mark-promoted", json={"scene_spec_id": sid}, headers=key).status_code == 200
    other = {"scene_spec_id": "22222222-2222-2222-2222-222222222222"}
    assert client.post(f"/v1/render-jobs/{vid}/mark-promoted", json=other, headers=key).status_code == 409
    assert client.post(f"/v1/render-jobs/{vid}/mark-promoted", json={"scene_spec_id": sid}).status_code == 401
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post(f"/v1/render-jobs/{missing}/mark-promoted", json={"scene_spec_id": sid}, headers=key).status_code == 404


async def test_a_lost_lease_drops_the_result_and_deletes_the_uploaded_video(backend, monkeypatch):
    deleted = []
    monkeypatch.setattr(worker.object_store, "delete_object", deleted.append)

    def slow_render(spec):  # this worker stalls; its lease expires and another worker takes the job over
        jid = backend.store.list_render_jobs(status="RUNNING")[0]["video_render_job_id"]
        token = typed.require(JobsRenderjob, f"RENDER#{jid}", "META").claim_token
        backend.store.heartbeat("render", jid, token, lease_seconds=-1)
        assert backend.store.claim("render", jid, "other-worker")
        return "manim-studio/videos/late.mp4", 10

    monkeypatch.setattr(worker, "render_and_store", slow_render)
    vid = backend.create_render_job(SPEC, None)["video_render_job_id"]
    assert await worker._process_one_render_job() is True
    assert deleted == ["manim-studio/videos/late.mp4"]
    job = backend.get_render_job(vid)
    assert job["status"] == "RUNNING" and job["video_object_key"] is None  # the new owner's run is untouched


async def test_sqs_triggered_claim_names_the_job_and_ignores_duplicates(backend, monkeypatch):
    _agent(monkeypatch)
    jid = backend.create_research_job("Vieta", {})["scene_research_job_id"]
    assert await worker.process_message("research", jid) is True
    assert await worker.process_message("research", jid) is False
    assert backend.get_research_job(jid)["status"] == "DONE"


async def test_heartbeat_keeps_a_long_job_alive(backend, monkeypatch):
    beats = []
    monkeypatch.setattr(type(backend), "heartbeat_interval", property(lambda self: 0.05))
    monkeypatch.setattr(backend, "heartbeat", lambda c: beats.append(c.job_id))

    async def slow(topic, context):
        import asyncio

        await asyncio.sleep(0.3)
        return SPEC, "e"

    monkeypatch.setattr(worker, "run_research_agent", slow)
    backend.create_research_job("Vieta", {})
    await worker._process_one_research_job()
    assert len(beats) >= 2


def test_default_backend_is_postgres_and_opens_no_connection():
    jobs_backend.get_backend.cache_clear()
    try:
        assert isinstance(jobs_backend.get_backend(), jobs_backend.PostgresJobsBackend)
    finally:
        jobs_backend.get_backend.cache_clear()


def test_postgres_backend_still_claims_through_the_original_sql(monkeypatch):
    import contextlib

    @contextlib.contextmanager
    def fake_connection():
        yield object()

    row = {"scene_research_job_id": "abc", "topic": "t", "context_json": {"a": 1}}
    monkeypatch.setattr(jobs_backend, "connection", fake_connection)
    monkeypatch.setattr(jobs_backend.jobs, "claim_pending_research_job", lambda conn: row)
    monkeypatch.setattr(jobs_backend.jobs, "claim_pending_render_job", lambda conn: None)
    be = jobs_backend.PostgresJobsBackend()
    assert be.claim("research") == jobs_backend.Claimed("abc", "research", {"topic": "t", "context_json": {"a": 1}})
    assert be.claim("render") is None
