"""Jobs store through REAL SQS and DynamoDB (``make test-ddb-integration``, environment ``test``): enqueue sends a wake-up, a worker
receives it, claims the job by conditional update, completes it, deletes the message; a duplicate delivery is a no-op.
Run ``make -C ../mathbank-db aws-sqs AWS_ENV=test`` once first (creates ``mb-studio-*-test`` queues and DLQs)."""
from __future__ import annotations

import time

import pytest

from mathbank_rest.jobs_queue import JobsQueue
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores.jobs import DynamoDBJobsStore


def _drain(q: JobsQueue, kind: str) -> None:
    for _ in range(3):
        got = q.receive(kind, max_messages=10, wait_seconds=1, visibility_timeout=1)
        for r in got:
            q.delete(kind, r.receipt_handle)


def _delete_item(kind: str, job_id: str) -> None:
    pk = f"{'RESEARCH' if kind == 'research' else 'RENDER'}#{job_id}"
    toolkit.client("dynamodb").delete_item(TableName=toolkit.table_name("jobs"), Key={"PK": {"S": pk}, "SK": {"S": "META"}})


@pytest.mark.ddb_integration
def test_enqueue_receive_claim_complete_over_real_sqs(real_env):
    q = JobsQueue()
    _drain(q, "research")
    store = DynamoDBJobsStore(queue=q)
    job = store.create_research_job("integration test topic", {"purpose": "wp3 real-aws test"}, requested_by="test")
    jid = str(job["scene_research_job_id"])
    try:
        got = []
        for _ in range(10):                       # SQS is eventually consistent; poll for up to ~20 s
            got = [r for r in q.receive("research", max_messages=10, wait_seconds=2, visibility_timeout=30)
                   if r.message and str(r.message.job_id) == jid]
            if got:
                break
        assert got, "the wake-up message never arrived on mb-studio-research-test"
        claim = store.claim("research", jid, "worker-1")
        assert claim is not None
        assert store.claim("research", jid, "worker-2") is None                 # a second worker loses
        done = store.complete_research_job(jid, claim.claim_token, {"ok": True}, "explanation")
        assert done["status"] == "DONE"
        q.delete("research", got[0].receipt_handle)
        assert store.claim("research", jid, "worker-3") is None                 # redelivery of a finished job is a no-op
        time.sleep(1)
        assert not [r for r in q.receive("research", max_messages=10, wait_seconds=1, visibility_timeout=1)
                    if r.message and str(r.message.job_id) == jid]
    finally:
        _delete_item("research", jid)
        _drain(q, "research")
