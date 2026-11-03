"""Connectivity for local development: doctor, credential hints, startup fail-fast, deep health."""
from __future__ import annotations

import json

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi.testclient import TestClient

from mathbank_rest import profiles, stores
from mathbank_rest.config import settings
from mathbank_rest.stores import ddb, doctor
from mathbank_rest.stores import ddb as ddb_module


@pytest.fixture
def tables_and_buckets(ddb, monkeypatch):
    """moto tables for learner and exam plus both buckets the check expects."""
    ddb_module.client("s3").create_bucket(Bucket="mathbank-content-ut-123456789012",
                                          CreateBucketConfiguration={"LocationConstraint": "us-east-2"})
    return ddb


def test_connectivity_reports_identity_tables_buckets_and_write_roundtrip(tables_and_buckets):
    r = ddb.check_connectivity(["learner", "exam"], write_check=True)
    assert r["ok"] and r["errors"] == [] and r["identity"]["account"] == "123456789012"
    assert set(r["tables"]) == {"mb-learner-ut", "mb-exam-ut"}
    t = r["tables"]["mb-learner-ut"]
    assert t["status"] == "ACTIVE" and t["gsis"] == ["GSI1", "GSI2"] and t["write_roundtrip"] is True
    assert set(r["buckets"]) == {"mathbank-data-ut-123456789012", "mathbank-content-ut-123456789012"}


def test_write_check_leaves_nothing_behind(tables_and_buckets):
    ddb.check_connectivity(["learner"], write_check=True)
    items = ddb_module.client().scan(TableName="mb-learner-ut")["Items"]  # moto-only inspection
    assert items == []


def test_missing_table_is_reported_with_the_provision_command(tables_and_buckets):
    r = ddb.check_connectivity(["jobs"])
    assert not r["ok"]
    e = next(x for x in r["errors"] if x["where"] == "mb-jobs-ut")
    assert e["code"] == "missing" and "aws-provision AWS_ENV=ut" in e["message"]


def test_missing_credentials_give_the_login_command_for_the_configured_profile(monkeypatch):
    monkeypatch.setattr(settings, "aws_profile", "aws-sutanu-admin")

    class NoCreds:
        def get_caller_identity(self):
            raise NoCredentialsError()

    monkeypatch.setattr(ddb, "client", lambda service="dynamodb": NoCreds())
    r = ddb.check_connectivity(["learner"])
    assert not r["ok"] and r["errors"][0]["code"] == "credentials"
    assert "aws login --profile aws-sutanu-admin" in r["hint"]
    assert r["tables"] == {}  # nothing else is attempted without credentials


@pytest.mark.parametrize("code", ["ExpiredToken", "ExpiredTokenException", "InvalidClientTokenId", "UnrecognizedClientException"])
def test_expired_or_invalid_tokens_are_classified_as_credentials(monkeypatch, code):
    monkeypatch.setattr(settings, "aws_profile", "")
    exc = ClientError({"Error": {"Code": code, "Message": "x"}}, "GetCallerIdentity")
    assert ddb._classify(exc)[0] == "credentials"
    assert "aws login --profile <your-profile>" in ddb.credential_hint()


def test_access_denied_is_not_mistaken_for_credentials():
    exc = ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "DescribeTable")
    assert ddb._classify(exc)[0] == "access"


def test_profile_setting_selects_the_boto3_profile(monkeypatch):
    seen = {}

    class FakeSession:
        def __init__(self, profile_name=None, region_name=None):
            seen.update(profile=profile_name, region=region_name)

        def client(self, service, **kw):
            return object()

    import boto3

    monkeypatch.setattr(boto3.session, "Session", FakeSession)
    monkeypatch.setattr(settings, "aws_profile", "dev-profile")
    ddb.reset_clients()
    ddb.client("dynamodb")
    assert seen == {"profile": "dev-profile", "region": "us-east-2"}
    monkeypatch.setattr(settings, "aws_profile", "")
    ddb.client("dynamodb")
    assert seen["profile"] is None  # empty means the default chain (env, shared config, Lambda role)
    ddb.reset_clients()


# ---------------------------------------------------------------- doctor CLI

def test_doctor_ok_exit_code_and_output(tables_and_buckets, capsys, monkeypatch):
    monkeypatch.setattr(settings, "learner_store", "dynamodb")
    assert doctor.main(["--write-check"]) == 0          # defaults to the contexts whose flag is dynamodb
    out = capsys.readouterr().out
    assert "table mb-learner-ut: ACTIVE" in out and "write-roundtrip=ok" in out and out.strip().endswith("OK")


def test_doctor_fails_with_exit_1_when_something_is_missing(ddb, capsys):
    assert doctor.main(["--contexts", "jobs"]) == 1
    assert "NOT READY" in capsys.readouterr().out


def test_doctor_json_and_unknown_context(tables_and_buckets, capsys):
    assert doctor.main(["--contexts", "exam", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["tables"]["mb-exam-ut"]["status"] == "ACTIVE"
    assert doctor.main(["--contexts", "nope"]) == 2


def test_doctor_without_any_dynamodb_flag_checks_credentials_only(ddb, capsys):
    assert doctor.main([]) == 0
    assert "no store is set to dynamodb" in capsys.readouterr().out


def test_doctor_warns_about_prod(ddb, capsys, monkeypatch):
    monkeypatch.setattr(settings, "ddb_env", "prod")
    doctor.main([])
    assert "env=prod" in capsys.readouterr().out


# ---------------------------------------------------------------- startup fail-fast and deep health

def test_startup_check_is_a_no_op_while_every_store_is_on_postgres(monkeypatch):
    monkeypatch.setattr(ddb, "client", lambda *a, **k: pytest.fail("no AWS call expected"))
    profiles.startup_aws_check()


def test_startup_refuses_to_start_when_a_dynamodb_store_cannot_reach_aws(monkeypatch):
    monkeypatch.setattr(settings, "learner_store", "dynamodb")
    monkeypatch.setattr(settings, "aws_profile", "aws-sutanu-admin")

    class NoCreds:
        def get_caller_identity(self):
            raise NoCredentialsError()

    monkeypatch.setattr(ddb, "client", lambda service="dynamodb": NoCreds())
    with pytest.raises(RuntimeError) as e:
        profiles.startup_aws_check()
    msg = str(e.value)
    assert "AWS data plane not reachable" in msg and "aws login --profile aws-sutanu-admin" in msg and "make aws-check" in msg


def test_startup_check_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "learner_store", "dynamodb")
    monkeypatch.setattr(settings, "ddb_startup_check", False)
    monkeypatch.setattr(ddb, "client", lambda *a, **k: pytest.fail("no AWS call expected"))
    profiles.startup_aws_check()


def test_startup_passes_when_everything_is_reachable(tables_and_buckets, monkeypatch):
    monkeypatch.setattr(settings, "learner_store", "dynamodb")
    profiles.startup_aws_check()


def _client_for_health():
    app = profiles.create_app("admin")
    return TestClient(app)


def test_deep_health_is_503_with_details_when_aws_is_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "learner_store", "dynamodb")

    class NoCreds:
        def get_caller_identity(self):
            raise NoCredentialsError()

    monkeypatch.setattr(ddb, "client", lambda service="dynamodb": NoCreds())
    r = _client_for_health().get("/health/stores", params={"deep": "true"})
    assert r.status_code == 503 and r.json()["aws"]["errors"][0]["code"] == "credentials"


def test_deep_health_ok_and_shallow_health_never_calls_aws(tables_and_buckets, monkeypatch):
    monkeypatch.setattr(settings, "learner_store", "dynamodb")
    c = _client_for_health()
    r = c.get("/health/stores", params={"deep": "true"})
    assert r.status_code == 200 and r.json()["aws"]["ok"] and r.json()["stores"]["learner"]["backend"] == "dynamodb"
    monkeypatch.setattr(ddb, "client", lambda *a, **k: pytest.fail("shallow health must not call AWS"))
    assert c.get("/health/stores").status_code == 200


def test_store_flags_are_read_from_settings_not_cached_across_tests():
    assert stores.store_mode("learner") == ("postgres", "postgres")
