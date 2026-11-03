"""Typed store access (stores/typed.py) on moto: models in, models out, strict writes, validated updates, offload."""
from __future__ import annotations

import datetime as dt
import json
import uuid

import pytest
from pydantic import ValidationError

from mathbank_rest.models.ddb.learner import LearnerOutcome, LearnerProfile
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    ItemSchemaError,
    NotFound,
    RevisionConflict,
    StoreError,
)

WHEN = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)


def make_profile(sid: str, **over) -> LearnerProfile:
    base = {
        "PK": toolkit.student_pk(sid), "SK": "PROFILE", "student_id": sid, "email": "a@x.org", "email_lc": "a@x.org",
        "first_name": "A", "last_name": "B", "display_name": "A B", "password_hash": "h", "search_blob": "a b",
        "status": "ACTIVE", "is_anonymous": False, "token_version": 1, "version": 1, "created_at": WHEN, "updated_at": WHEN,
    }
    base.update(over)
    return LearnerProfile(**base)


def test_put_new_then_get_returns_the_same_typed_item(ddb, sid):
    typed.put_new(make_profile(sid))
    got = typed.require(LearnerProfile, ddb_pk(sid), "PROFILE")
    assert isinstance(got, LearnerProfile) and str(got.student_id) == sid and got.created_at.tzinfo is not None
    raw = ddb_raw(sid)
    assert raw["type"] == "PROFILE" and raw["created_at"] == "2026-01-02T03:04:05.000000Z" and "grade" not in raw


def ddb_pk(sid: str) -> str:
    return toolkit.student_pk(sid)


def ddb_raw(sid: str) -> dict:
    return toolkit.get_item("learner", ddb_pk(sid), "PROFILE")


def test_put_new_refuses_to_overwrite(ddb, sid):
    typed.put_new(make_profile(sid))
    with pytest.raises(ConditionFailed):
        typed.put_new(make_profile(sid, first_name="Other"))


def test_get_missing_is_none_and_require_is_not_found(ddb, sid):
    assert typed.get(LearnerProfile, ddb_pk(sid), "PROFILE") is None
    with pytest.raises(NotFound):
        typed.require(LearnerProfile, ddb_pk(sid), "PROFILE")


def test_writes_reject_undeclared_attributes_and_invalid_keys(ddb, sid):
    p = LearnerProfile.from_item({**make_profile(sid).to_item(), "sneaky": 1})
    with pytest.raises(ItemSchemaError, match="undeclared"):
        typed.put(p)
    with pytest.raises(ValidationError):
        make_profile(sid, PK="USER#1")                      # key pattern is checked at construction


def test_reading_drifted_data_raises_a_500_not_garbage(ddb, sid):
    ddb.put_item(TableName="mb-learner-ut", Item=toolkit._ser_map({**make_profile(sid).to_item(), "token_version": "oops"}))
    with pytest.raises(ItemSchemaError) as e:
        typed.require(LearnerProfile, ddb_pk(sid), "PROFILE")
    assert e.value.status_code == 500 and e.value.detail["errors"][0]["loc"] == "token_version"


def test_update_validates_each_attribute_then_applies_a_cas(ddb, sid):
    typed.put_new(make_profile(sid))
    new = typed.update(LearnerProfile, ddb_pk(sid), "PROFILE", 1, {"status": "DISABLED", "token_version": 2})
    assert new.status == "DISABLED" and new.token_version == 2 and new.version == 2
    with pytest.raises(RevisionConflict):
        typed.update(LearnerProfile, ddb_pk(sid), "PROFILE", 1, {"status": "ACTIVE"})
    with pytest.raises(ItemSchemaError):
        typed.update(LearnerProfile, ddb_pk(sid), "PROFILE", 2, {"token_version": "3"})        # strict int
    with pytest.raises(ItemSchemaError, match="no attribute"):
        typed.update(LearnerProfile, ddb_pk(sid), "PROFILE", 2, {"nope": 1})
    assert typed.require(LearnerProfile, ddb_pk(sid), "PROFILE").version == 2                  # rejected updates changed nothing


def test_update_accepts_python_values_and_stores_json_forms(ddb, sid):
    typed.put_new(make_profile(sid))
    when = dt.datetime(2026, 5, 6, 7, 8, 9, tzinfo=dt.UTC)
    new = typed.update(LearnerProfile, ddb_pk(sid), "PROFILE", 1, {"last_login_at": when})
    assert new.last_login_at == when and ddb_raw(sid)["last_login_at"] == "2026-05-06T07:08:09.000000Z"


def test_query_parses_each_item_by_type_and_pages(ddb, sid):
    typed.put_new(make_profile(sid))
    for i in range(3):
        typed.put_new(outcome(sid, i))
    page = typed.query("learner", ddb_pk(sid), limit=2)
    assert len(page.items) == 2 and page.next_token
    rest = typed.query("learner", ddb_pk(sid), limit=10, next_token=page.next_token)
    kinds = [type(i).__name__ for i in page.items + rest.items]
    assert sorted(kinds) == ["LearnerOutcome"] * 3 + ["LearnerProfile"]
    only = typed.query(LearnerOutcome, ddb_pk(sid), sk_begins="OUTCOME#")
    assert [type(i) for i in only.items] == [LearnerOutcome] * 3
    with pytest.raises(ItemSchemaError, match="unexpected item type"):
        typed.query("learner", ddb_pk(sid), models=[LearnerProfile])           # partition holds other types


def outcome(sid: str, i: int, answer: str = "42") -> LearnerOutcome:
    return LearnerOutcome(PK=ddb_pk(sid), SK=f"OUTCOME#web#{uuid.uuid4()}", attempt_id=uuid.uuid4(), attempted_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                          hint_count=i, is_correct=True, legacy_source="x", problem_id=uuid.uuid4(), source="web", student_id=sid,
                          time_spent_seconds=3, submitted_answer=answer)


def test_large_offloadable_attribute_goes_to_s3_and_resolves_typed(ddb, sid):
    big = "x" * 40_000
    o = outcome(sid, 0, answer=big)
    typed.put_new(o)
    raw = toolkit.get_item("learner", o.PK, o.SK)
    assert "submitted_answer" not in raw and raw["submitted_answer_ref"]["bytes"] > 16 * 1024
    assert f"/students/{sid}/" in raw["submitted_answer_ref"]["key"]               # erasure is one prefix delete
    got = typed.require(LearnerOutcome, o.PK, o.SK)
    assert got.submitted_answer is None and got.ref("submitted_answer").sha256 == raw["submitted_answer_ref"]["sha256"]
    assert got.resolve("submitted_answer") == big


def test_small_attribute_stays_inline(ddb, sid):
    o = outcome(sid, 0, answer="42")
    typed.put_new(o)
    raw = toolkit.get_item("learner", o.PK, o.SK)
    assert raw["submitted_answer"] == "42" and "submitted_answer_ref" not in raw
    assert typed.require(LearnerOutcome, o.PK, o.SK).resolve("submitted_answer") == "42"


def test_resolve_verifies_checksum_and_type(ddb, sid):
    big = "y" * 40_000
    o = outcome(sid, 0, answer=big)
    typed.put_new(o)
    got = typed.require(LearnerOutcome, o.PK, o.SK)
    assert got.resolve("submitted_answer", model=str) == big
    with pytest.raises(ItemSchemaError):
        got.resolve("submitted_answer", model=int)                                 # typed: wrong shape is a schema error
    ref = got.ref("submitted_answer")
    toolkit.client("s3").put_object(Bucket=ref.bucket, Key=ref.key, Body=json.dumps("tampered").encode())
    with pytest.raises(StoreError, match="size mismatch|checksum"):
        got.resolve("submitted_answer")


def test_tx_put_builds_a_transactional_put_from_a_model(ddb, sid):
    p = make_profile(sid)
    sentinel = toolkit.sentinel_put("learner", "email", "a@x.org", {"student_id": sid})
    toolkit.transact([typed.tx_put(p, toolkit.NOT_EXISTS), sentinel])
    assert typed.get(LearnerProfile, p.PK, "PROFILE") is not None
    with pytest.raises(StoreError):
        toolkit.transact([typed.tx_put(p, toolkit.NOT_EXISTS)])


def test_batch_get_returns_models(ddb, sid):
    typed.put_new(make_profile(sid))
    got = typed.batch_get(LearnerProfile, [(ddb_pk(sid), "PROFILE"), (ddb_pk(sid), "MISSING")])
    assert [type(g) for g in got] == [LearnerProfile]
