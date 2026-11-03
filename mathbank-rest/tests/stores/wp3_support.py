"""Shared moto setup for the WP3 tests: the ``mb-jobs`` / ``mb-notify`` tables (as provisioned), the Studio SQS queues
with their DLQs, and a learner profile seeder."""
from __future__ import annotations

import json
import uuid

import pytest

from mathbank_rest import jobs_queue
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import reset_for_tests

GSI_ATTRS = ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")


def create_table(client, ctx: str, env: str = "ut") -> None:
    client.create_table(
        TableName=f"mb-{ctx}-{env}",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in GSI_ATTRS],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[
            {"IndexName": g, "KeySchema": [{"AttributeName": f"{g}PK", "KeyType": "HASH"},
                                           {"AttributeName": f"{g}SK", "KeyType": "RANGE"}],
             "Projection": {"ProjectionType": "ALL"}} for g in ("GSI1", "GSI2")],
        BillingMode="PAY_PER_REQUEST")


def create_queues(sqs, env: str = "ut") -> None:
    for kind in jobs_queue.KINDS:
        dlq = sqs.create_queue(QueueName=jobs_queue.queue_name(kind, dlq=True, env=env))["QueueUrl"]
        arn = sqs.get_queue_attributes(QueueUrl=dlq, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]
        sqs.create_queue(QueueName=jobs_queue.queue_name(kind, env=env), Attributes={
            "VisibilityTimeout": str(jobs_queue.DEFAULT_VISIBILITY_SECONDS),
            "RedrivePolicy": json.dumps({"deadLetterTargetArn": arn, "maxReceiveCount": str(jobs_queue.MAX_RECEIVE_COUNT)})})


@pytest.fixture(name="wp3")
def wp3_fixture(ddb):
    """``ddb`` (moto DynamoDB + S3) plus the jobs and notify tables and the Studio queues."""
    create_table(ddb, "jobs")
    create_table(ddb, "notify")
    create_queues(toolkit.client("sqs"))
    reset_for_tests()
    yield ddb


def seed_learner(student_id: str | None = None) -> str:
    """A minimal learner PROFILE so the notify producer's recipient check passes."""
    sid = student_id or str(uuid.uuid4())
    toolkit.client("dynamodb").put_item(TableName=toolkit.table_name("learner"), Item={
        "PK": {"S": f"STUDENT#{sid}"}, "SK": {"S": "PROFILE"}, "type": {"S": "PROFILE"}})
    return sid
