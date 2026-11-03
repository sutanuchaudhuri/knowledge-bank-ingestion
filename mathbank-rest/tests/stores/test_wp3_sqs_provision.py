"""The mathbank-db SQS provisioning module against moto: idempotent, converges attributes, never deletes, and agrees with the
queue names and redrive policy that ``mathbank_rest.jobs_queue`` expects."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from mathbank_rest import jobs_queue

DB = Path(__file__).resolve().parents[3] / "mathbank-db"
pytestmark = pytest.mark.skipif(not (DB / "aws" / "sqs" / "provision.py").exists(), reason="mathbank-db not checked out")


@pytest.fixture()
def provision(monkeypatch):
    from moto import mock_aws

    for k, v in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_SESSION_TOKEN": "testing",
                 "AWS_DEFAULT_REGION": "us-east-2", "AWS_REGION": "us-east-2"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.syspath_prepend(str(DB))
    for m in [m for m in sys.modules if m == "aws" or m.startswith("aws.")]:
        monkeypatch.delitem(sys.modules, m)
    with mock_aws():
        from aws import common
        from aws.sqs import provision as mod

        monkeypatch.setattr(common, "_SESSION", None)
        monkeypatch.setattr(common, "PROFILE", "")
        yield mod, common.client("sqs")


def test_creates_every_queue_with_its_dlq_and_matches_the_rest_side(provision):
    mod, sqs = provision
    for spec in mod.QUEUES:
        mod.ensure(mod.Env("ut"), spec)
    urls = sqs.list_queues()["QueueUrls"]
    assert len(urls) == 2 * len(mod.QUEUES)
    for kind in jobs_queue.KINDS:
        main = sqs.get_queue_url(QueueName=jobs_queue.queue_name(kind, env="ut"))["QueueUrl"]
        dlq = sqs.get_queue_url(QueueName=jobs_queue.queue_name(kind, dlq=True, env="ut"))["QueueUrl"]
        attrs = sqs.get_queue_attributes(QueueUrl=main, AttributeNames=["All"])["Attributes"]
        arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        assert attrs["VisibilityTimeout"] == str(jobs_queue.DEFAULT_VISIBILITY_SECONDS)
        assert json.loads(attrs["RedrivePolicy"]) == {"deadLetterTargetArn": arn, "maxReceiveCount": jobs_queue.MAX_RECEIVE_COUNT}
        assert attrs["ReceiveMessageWaitTimeSeconds"] == "20"


def test_is_idempotent_converges_attributes_and_never_deletes(provision):
    mod, sqs = provision
    spec = mod.QUEUES[0]
    mod.ensure(mod.Env("ut"), spec)
    url = sqs.get_queue_url(QueueName=mod.queue_name(spec, mod.Env("ut")))["QueueUrl"]
    sqs.send_message(QueueUrl=url, MessageBody="keep me")
    sqs.set_queue_attributes(QueueUrl=url, Attributes={"VisibilityTimeout": "5"})  # drift
    mod.ensure(mod.Env("ut"), spec)
    mod.ensure(mod.Env("ut"), spec)
    assert sqs.get_queue_attributes(QueueUrl=url, AttributeNames=["VisibilityTimeout"])["Attributes"]["VisibilityTimeout"] == "360"
    assert sqs.receive_message(QueueUrl=url, VisibilityTimeout=0)["Messages"][0]["Body"] == "keep me"
    assert len(sqs.list_queues()["QueueUrls"]) == 2


def test_dry_run_creates_nothing(provision):
    mod, sqs = provision
    mod.ensure(mod.Env("ut"), mod.QUEUES[0], dry=True)
    assert "QueueUrls" not in sqs.list_queues()
