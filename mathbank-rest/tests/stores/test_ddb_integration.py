"""The toolkit against the REAL `test` data-plane environment (requirement 71 §5).

Skipped unless MB_DDB_ENV=test (`make test-ddb-integration`). Needs the `test` environment:
    make -C ../mathbank-db aws-provision AWS_ENV=test
Each test uses a fresh student id and removes everything it created (DynamoDB partition + S3 prefix).
Never point this at `dev`: that environment holds the migrated copy of real data.
"""
from __future__ import annotations

import uuid

import httpx
import pytest

from mathbank_rest.stores import ddb as t
from mathbank_rest.stores.errors import (
    ConditionFailed,
    IdempotencyKeyReused,
    InvalidToken,
    RevisionConflict,
    UniqueViolation,
)

pytestmark = pytest.mark.ddb_integration
CTX = "learner"


def _delete(ddb, pk: str, sk: str) -> None:
    ddb.delete_item(TableName=t.table_name(CTX), Key={"PK": {"S": pk}, "SK": {"S": sk}})


@pytest.fixture()
def student(real_env):
    sid = str(uuid.uuid4())
    yield sid
    # cleanup: the whole partition, its uniqueness sentinel, and its offloaded objects
    pk, ddb, token = t.student_pk(sid), t.client(), None
    while True:
        page = t.query_page(CTX, pk, limit=100, next_token=token)
        for it in page["items"]:
            _delete(ddb, it["PK"], it["SK"])
        token = page["next_token"]
        if not token:
            break
    _delete(ddb, f"UNIQUE#email#{sid}@example.test", "UNIQUE")
    s3 = t.client("s3")
    for pg in s3.get_paginator("list_objects_v2").paginate(Bucket=t.data_bucket(), Prefix=f"offload/learner/students/{sid}/"):
        for o in pg.get("Contents", []):
            s3.delete_object(Bucket=t.data_bucket(), Key=o["Key"])


def test_test_environment_is_the_real_one(real_env):
    assert t.table_name(CTX) == "mb-learner-test" and "test" in t.data_bucket()
    d = t.client().describe_table(TableName=t.table_name(CTX))["Table"]
    assert d["BillingModeSummary"]["BillingMode"] == "PAY_PER_REQUEST" and d["DeletionProtectionEnabled"]
    assert {g["IndexName"] for g in d["GlobalSecondaryIndexes"]} == {"GSI1", "GSI2"}
    assert d["StreamSpecification"]["StreamViewType"] == "NEW_AND_OLD_IMAGES"


def test_cas_update_conflict_reports_current_revision_on_real_dynamodb(student):
    pk = t.student_pk(student)
    t.put_item(CTX, {"PK": pk, "SK": "X", "type": "T", "version": 1, "n": 0})
    assert t.cas_update(CTX, pk, "X", 1, {"n": 1})["version"] == 2
    with pytest.raises(RevisionConflict) as e:
        t.cas_update(CTX, pk, "X", 1, {"n": 2})
    assert e.value.current_revision == 2


def test_transaction_cancellation_reasons_map_to_domain_errors(student):
    pk, email = t.student_pk(student), f"{student}@example.test"
    t.transact([t.sentinel_put(CTX, "email", email, {"student_id": student}),
                t.Put(CTX, {"PK": pk, "SK": "PROFILE", "type": "PROFILE", "version": 1})])
    other = str(uuid.uuid4())
    with pytest.raises(UniqueViolation) as e:
        t.transact([t.Put(CTX, {"PK": t.student_pk(other), "SK": "PROFILE", "type": "PROFILE", "version": 1}),
                    t.sentinel_put(CTX, "email", email, {"student_id": other})])
    assert e.value.field == "email"
    assert t.get_item(CTX, t.student_pk(other), "PROFILE") is None  # atomic: the first op rolled back too
    stale = t.Cond("#v = :v", {"#v": "version"}, {":v": 99})
    with pytest.raises(ConditionFailed):
        t.transact([t.Check(CTX, pk, "PROFILE", stale, label="stale")])


def test_pagination_and_gsi_on_real_dynamodb(student):
    pk = t.student_pk(student)
    for i in range(7):
        t.put_item(CTX, {"PK": pk, "SK": f"EVENT#{i:03d}", "type": "EVENT", "GSI1PK": f"ATT#{student}", "GSI1SK": f"{i:03d}"})
    seen, token = [], None
    while True:
        page = t.query_page(CTX, pk, sk_begins="EVENT#", limit=3, next_token=token)
        seen += [i["SK"] for i in page["items"]]
        token = page["next_token"]
        if not token:
            break
    assert seen == [f"EVENT#{i:03d}" for i in range(7)]
    first = t.query_page(CTX, f"ATT#{student}", index="GSI1", forward=False, limit=2)
    assert [i["GSI1SK"] for i in first["items"]] == ["006", "005"] and first["next_token"]
    with pytest.raises(InvalidToken):  # a GSI token is not valid for another partition
        t.query_page(CTX, f"ATT#{uuid.uuid4()}", index="GSI1", forward=False, limit=2, next_token=first["next_token"])


def test_offload_to_real_s3_with_integrity_and_presigned_download(student):
    pk, big = t.student_pk(student), "answer " * 4000
    item = {"PK": pk, "SK": "RESP#1", "type": "RESPONSE", "version": 1, "answer": big}
    t.offload(CTX, item, ("answer",))
    t.put_item(CTX, item)
    got = t.get_item(CTX, pk, "RESP#1")
    ref = got["answer_ref"]
    assert ref["key"].startswith(f"offload/learner/students/{student}/RESPONSE/") and ref["bucket"] == t.data_bucket()
    assert t.load_attr(got, "answer") == big
    head = t.client("s3").head_object(Bucket=ref["bucket"], Key=ref["key"])
    assert head["Metadata"]["sha256"] == ref["sha256"] and head["ContentLength"] == ref["bytes"]
    assert httpx.get(t.presign(ref, 60), timeout=30).content == t._json_bytes(big)


def test_idempotent_write_with_offloaded_receipt_on_real_aws(student):
    pk, calls = t.student_pk(student), []
    big = {"data": "z" * (t.OFFLOAD_THRESHOLD + 50)}

    def build():
        calls.append(1)
        return [t.Put(CTX, {"PK": pk, "SK": "EFFECT#1", "type": "EFFECT"})], big

    kw = {"owner_pk": pk, "key": "k1", "req_hash": t.request_hash({"a": 1})}
    assert t.run_idempotent(CTX, build=build, **kw) == (big, False)
    assert t.run_idempotent(CTX, build=build, **kw) == (big, True) and len(calls) == 1
    assert t.get_item(CTX, pk, "IDEM#k1").get("response_ref")
    with pytest.raises(IdempotencyKeyReused):
        t.run_idempotent(CTX, owner_pk=pk, key="k1", req_hash="different", build=build)
    assert len(t.query_page(CTX, pk, sk_begins="EFFECT#")["items"]) == 1
