"""Fixtures for the store-layer tests (requirement 71).

`ddb` runs every test on moto with context tables shaped like the real ones (string PK/SK, GSI1, GSI2, TTL on
`ttl`). `real_env` is for tests marked `ddb_integration`: they use the real `test` environment created by
`make -C ../mathbank-db aws-provision AWS_ENV=test` and are skipped unless MB_DDB_ENV=test.
"""
from __future__ import annotations

import os
import uuid

import pytest

from mathbank_rest.config import settings
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import reset_for_tests

ACCOUNT = "123456789012"  # moto's default account id
CTXS = ("learner", "exam")


def pytest_collection_modifyitems(config, items):
    if os.getenv("MB_DDB_ENV") == "test":
        return
    skip = pytest.mark.skip(reason="real-AWS integration test: set MB_DDB_ENV=test (see make test-ddb-integration)")
    for item in items:
        if "ddb_integration" in item.keywords:
            item.add_marker(skip)


# Production learner GSI2 projects only these attributes (+ keys and `type`): mathbank-db/aws/dynamo/specs/learner.py GSI2_INCLUDE.
# Mirroring it here makes a typed query through GSI2 fail in tests exactly like it does on the real table.
LEARNER_GSI2_INCLUDE = sorted({
    "student_id", "email", "first_name", "last_name", "display_name", "status", "created_at", "is_anonymous", "search_blob",
    "problem_id", "attempt_number", "current_mode", "solve_attempt_id", "solution_step_id", "state", "help_level_used",
    "attempt_count", "independent_success", "type"})


def _create_tables(client, env: str) -> None:
    for ctx in CTXS:
        gsis = []
        for g in ("GSI1", "GSI2"):
            projection = ({"ProjectionType": "INCLUDE", "NonKeyAttributes": LEARNER_GSI2_INCLUDE}
                          if (ctx, g) == ("learner", "GSI2") else {"ProjectionType": "ALL"})
            gsis.append({"IndexName": g, "KeySchema": [{"AttributeName": f"{g}PK", "KeyType": "HASH"},
                                                       {"AttributeName": f"{g}SK", "KeyType": "RANGE"}], "Projection": projection})
        client.create_table(
            TableName=f"mb-{ctx}-{env}",
            AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"}
                                  for a in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")],
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=gsis,
            BillingMode="PAY_PER_REQUEST",
        )


@pytest.fixture()
def ddb(monkeypatch):
    """moto DynamoDB + S3 with the learner and exam tables and the data bucket; no network."""
    from moto import mock_aws

    for k, v in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_SESSION_TOKEN": "testing",
                 "AWS_DEFAULT_REGION": "us-east-2"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setattr(settings, "ddb_env", "ut")
    monkeypatch.setattr(settings, "ddb_region", "us-east-2")
    monkeypatch.setattr(settings, "ddb_endpoint_url", "")
    monkeypatch.setattr(settings, "data_bucket", "")
    monkeypatch.setattr(settings, "idempotency_ttl_days", 7)
    toolkit.reset_clients()
    reset_for_tests()
    with mock_aws():
        client = toolkit.client("dynamodb")
        _create_tables(client, "ut")
        toolkit.client("s3").create_bucket(Bucket=toolkit.data_bucket(),
                                           CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
        yield client
    toolkit.reset_clients()


@pytest.fixture()
def sid() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def real_env(monkeypatch):
    """The real `test` environment. Only used by tests marked ddb_integration."""
    monkeypatch.setattr(settings, "ddb_env", "test")
    monkeypatch.setattr(settings, "ddb_region", "us-east-2")
    monkeypatch.setattr(settings, "ddb_endpoint_url", "")
    monkeypatch.setattr(settings, "data_bucket", "")
    toolkit.reset_clients()
    yield
    toolkit.reset_clients()


CONTENT_BUCKET = f"mathbank-content-ut-{ACCOUNT}"


@pytest.fixture()
def content_table(ddb):
    """moto: the ``mb-content-ut`` table with GSI1/GSI2 (as provisioned) and the content bucket, next to learner/exam.

    Use ``typed.put(<model>)`` to seed items and ``toolkit.client("s3").put_object(Bucket=CONTENT_BUCKET, ...)`` for snapshots."""
    ddb.create_table(
        TableName="mb-content-ut",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("PK", "SK", "GSI1PK", "GSI1SK", "GSI2PK", "GSI2SK")],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        GlobalSecondaryIndexes=[
            {"IndexName": g, "KeySchema": [{"AttributeName": f"{g}PK", "KeyType": "HASH"}, {"AttributeName": f"{g}SK", "KeyType": "RANGE"}],
             "Projection": {"ProjectionType": "ALL"}} for g in ("GSI1", "GSI2")],
        BillingMode="PAY_PER_REQUEST",
    )
    toolkit.client("s3").create_bucket(Bucket=toolkit.content_bucket(), CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
    from mathbank_rest.stores.content import snapshots

    snapshots.clear()
    yield ddb
    snapshots.clear()
