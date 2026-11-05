"""MB_AWS_READONLY: a run against a real environment can read but never mutate."""
import pytest

from mathbank_rest.config import settings
from mathbank_rest.stores import ddb as toolkit


@pytest.fixture
def readonly(ddb, monkeypatch):
    monkeypatch.setattr(settings, "aws_readonly", True)
    toolkit.reset_clients()
    toolkit.BLOCKED_WRITES.clear()
    yield
    toolkit.reset_clients()


def test_reads_pass_and_writes_are_refused(readonly):
    c = toolkit.client("dynamodb")
    t = toolkit.table_name("learner")
    c.get_item(TableName=t, Key={"PK": {"S": "x"}, "SK": {"S": "y"}})
    for call in (
        lambda: c.put_item(TableName=t, Item={"PK": {"S": "x"}, "SK": {"S": "y"}}),
        lambda: c.delete_item(TableName=t, Key={"PK": {"S": "x"}, "SK": {"S": "y"}}),
        lambda: c.transact_write_items(TransactItems=[{"Put": {"TableName": t, "Item": {"PK": {"S": "a"}, "SK": {"S": "b"}}}}]),
    ):
        with pytest.raises(toolkit.ReadOnlyViolation):
            call()
    assert {"dynamodb.PutItem", "dynamodb.DeleteItem", "dynamodb.TransactWriteItems"} <= set(toolkit.BLOCKED_WRITES)
    assert c.get_item(TableName=t, Key={"PK": {"S": "x"}, "SK": {"S": "y"}}).get("Item") is None


def test_s3_writes_refused(readonly):
    s3 = toolkit.client("s3")
    with pytest.raises(toolkit.ReadOnlyViolation):
        s3.put_object(Bucket="b", Key="k", Body=b"x")


def test_write_envs_allow_only_matching_resources(ddb, monkeypatch):
    monkeypatch.setattr(settings, "aws_write_envs", "test")
    toolkit.reset_clients()
    toolkit.BLOCKED_WRITES.clear()
    c = toolkit.client("dynamodb")
    for target, ok in (("mb-learner-test", True), ("mb-learner-dev", False), ("mb-learner-prod", False)):
        try:
            c.put_item(TableName=target, Item={"PK": {"S": "x"}, "SK": {"S": "y"}})
            reached = True
        except toolkit.ReadOnlyViolation:
            reached = False
        except Exception:  # the call passed the guard and failed later (no such table in moto)
            reached = True
        assert reached is ok, target
    with pytest.raises(toolkit.ReadOnlyViolation):  # one forbidden table poisons the whole transaction
        c.transact_write_items(TransactItems=[
            {"Put": {"TableName": "mb-learner-test", "Item": {"PK": {"S": "a"}, "SK": {"S": "b"}}}},
            {"Put": {"TableName": "mb-exam-dev", "Item": {"PK": {"S": "a"}, "SK": {"S": "b"}}}}])
    toolkit.reset_clients()


def test_env_overrides_route_planes_to_other_environments(monkeypatch):
    monkeypatch.setattr(settings, "ddb_env", "test")
    monkeypatch.setattr(settings, "ddb_env_overrides", "content=dev, vectors=dev")
    assert toolkit.table_name("content") == "mb-content-dev"
    assert toolkit.table_name("learner") == "mb-learner-test"
    assert toolkit.env_for("vectors") == "dev" and toolkit.env_for("data") == "test"
