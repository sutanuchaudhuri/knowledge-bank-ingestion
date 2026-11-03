"""LearnerUnitOfWork and the WP5 hook contract (stores/learner/uow.py, hooks.py) on moto."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from mathbank_rest.models.ddb.learner import LearnerEvent, LearnerOutcome, LearnerProfile
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    IdempotencyKeyReused,
    RevisionConflict,
    StoreError,
    UniqueViolation,
    ValidationFailed,
)
from mathbank_rest.stores.learner import hooks
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork, run_idempotent, with_retries

WHEN = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)


def profile(sid: str, **over) -> LearnerProfile:
    base = {
        "PK": toolkit.student_pk(sid), "SK": "PROFILE", "student_id": sid, "email": "a@x.org", "email_lc": "a@x.org", "first_name": "A",
        "last_name": "B", "display_name": "A B", "password_hash": "h", "search_blob": "a b", "status": "ACTIVE", "is_anonymous": False,
        "token_version": 1, "version": 1, "created_at": WHEN, "updated_at": WHEN,
    }
    return LearnerProfile(**{**base, **over})


def event(sid: str, n: int = 0) -> LearnerEvent:
    return LearnerEvent(PK=toolkit.student_pk(sid), SK=f"EVT#{n:04d}#{uuid.uuid4()}", event_id=uuid.uuid4(), event_time=WHEN,
                        event_type="PROBLEM_VIEWED", actor_type="STUDENT", solve_attempt_id=uuid.uuid4(), student_id=sid,
                        payload={"n": n})


def outcome(sid: str) -> LearnerOutcome:
    return LearnerOutcome(PK=toolkit.student_pk(sid), SK=f"OUTCOME#web#{uuid.uuid4()}", attempt_id=uuid.uuid4(), attempted_at=WHEN,
                          hint_count=0, is_correct=True, legacy_source="x", problem_id=uuid.uuid4(), source="web", student_id=sid,
                          time_spent_seconds=3)


def test_commit_writes_everything_atomically_and_typed(ddb, sid):
    uow = LearnerUnitOfWork(sid)
    uow.put_new(profile(sid)).put_new(event(sid)).put_new(outcome(sid)).sentinel("email", "a@x.org", {"student_id": sid})
    assert len(uow) == 4 and uow.remaining() == 95
    uow.commit()
    assert len(uow) == 0
    assert typed.require(LearnerProfile, toolkit.student_pk(sid), "PROFILE").first_name == "A"
    assert toolkit.get_item("learner", *toolkit.unique_key("email", "a@x.org"))["student_id"] == sid


def test_a_failed_condition_rolls_back_every_item(ddb, sid):
    typed.put_new(profile(sid))
    uow = LearnerUnitOfWork(sid)
    uow.put_new(event(sid)).put_new(profile(sid))            # the profile already exists
    with pytest.raises(ConditionFailed):
        uow.commit()
    assert typed.query("learner", toolkit.student_pk(sid)).items[0].type == "PROFILE" and len(typed.query("learner", toolkit.student_pk(sid)).items) == 1


def test_sentinel_collision_is_a_unique_violation(ddb, sid):
    LearnerUnitOfWork(sid).sentinel("email", "x@x.org", {"student_id": sid}).commit()
    other = str(uuid.uuid4())
    with pytest.raises(UniqueViolation):
        LearnerUnitOfWork(other).put_new(profile(other)).sentinel("email", "x@x.org", {"student_id": other}).commit()
    assert typed.get(LearnerProfile, toolkit.student_pk(other), "PROFILE") is None          # nothing partially written


def test_update_is_conditional_on_expected_values_and_bumps_the_version(ddb, sid):
    typed.put_new(profile(sid))
    pk = toolkit.student_pk(sid)
    LearnerUnitOfWork(sid).update(LearnerProfile, pk, "PROFILE", {"status": "DISABLED"}, expected={"version": 1}).commit()
    got = typed.require(LearnerProfile, pk, "PROFILE")
    assert got.status == "DISABLED" and got.version == 2 and got.updated_at > WHEN
    with pytest.raises(ConditionFailed):
        LearnerUnitOfWork(sid).update(LearnerProfile, pk, "PROFILE", {"status": "ACTIVE"}, expected={"version": 1}).commit()
    assert typed.require(LearnerProfile, pk, "PROFILE").status == "DISABLED"


def test_update_can_raise_a_domain_error_for_the_client_version(ddb, sid):
    typed.put_new(profile(sid))
    with pytest.raises(RevisionConflict):
        LearnerUnitOfWork(sid).update(LearnerProfile, toolkit.student_pk(sid), "PROFILE", {"first_name": "Z"}, expected={"version": 9},
                                      conflict=RevisionConflict(1)).commit()


def test_update_increments_counters_removes_attributes_and_checks_an_extra_condition(ddb, sid):
    typed.put_new(profile(sid, grade="9"))
    pk = toolkit.student_pk(sid)
    LearnerUnitOfWork(sid).update(LearnerProfile, pk, "PROFILE", {}, increment={"token_version": 2}, remove=("grade",),
                                  cond=toolkit.Cond("#st = :st", {"#st": "status"}, {":st": "ACTIVE"})).commit()
    got = typed.require(LearnerProfile, pk, "PROFILE")
    assert got.token_version == 3 and got.grade is None
    with pytest.raises(ConditionFailed):
        LearnerUnitOfWork(sid).update(LearnerProfile, pk, "PROFILE", {}, cond=toolkit.Cond("#st = :st", {"#st": "status"}, {":st": "DISABLED"})).commit()


def test_update_validates_attributes_against_the_model(ddb, sid):
    typed.put_new(profile(sid))
    from mathbank_rest.stores.errors import ItemSchemaError

    with pytest.raises(ItemSchemaError):
        LearnerUnitOfWork(sid).update(LearnerProfile, toolkit.student_pk(sid), "PROFILE", {"token_version": "3"})
    with pytest.raises(ValidationFailed):
        LearnerUnitOfWork(sid).update(LearnerProfile, toolkit.student_pk(sid), "PROFILE", {"version": 5})      # the bump attribute


def test_append_only_types_can_only_be_created(ddb, sid):
    uow = LearnerUnitOfWork(sid)
    uow.put_new(event(sid))
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.put(event(sid))
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.update(LearnerEvent, toolkit.student_pk(sid), "EVT#x", {"payload": {}})
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.delete(LearnerOutcome, toolkit.student_pk(sid), "OUTCOME#x")
    e = event(sid)
    LearnerUnitOfWork(sid).put_new(e).commit()
    with pytest.raises(ConditionFailed):
        LearnerUnitOfWork(sid).put_new(e).commit()                                   # never overwritten


def test_a_student_cannot_write_into_another_students_partition(ddb, sid):
    other = str(uuid.uuid4())
    uow = LearnerUnitOfWork(sid)
    with pytest.raises(ValidationFailed, match="another student"):
        uow.put_new(profile(other))
    with pytest.raises(ValidationFailed, match="another student"):
        uow.update(LearnerProfile, toolkit.student_pk(other), "PROFILE", {"status": "DISABLED"})


def test_more_than_100_items_is_refused(ddb, sid):
    uow = LearnerUnitOfWork(sid)
    for i in range(101):
        uow.put_new(event(sid, i))
    assert uow.remaining() < 0 and not uow.fits(1)
    with pytest.raises(StoreError, match="limit is 100"):
        uow.commit()


# ------------------------------------------------------------------ idempotency

def test_idempotent_run_replays_the_stored_response_without_running_build_again(ddb, sid):
    calls = []

    def build(uow):
        calls.append(1)
        uow.put_new(event(sid))
        return {"ok": True, "n": len(calls)}

    first, replayed1 = run_idempotent(sid, key="k1", operation="op", body={"a": 1}, build=build)
    again, replayed2 = run_idempotent(sid, key="k1", operation="op", body={"a": 1}, build=build)
    assert (first, replayed1, again, replayed2) == ({"ok": True, "n": 1}, False, {"ok": True, "n": 1}, True) and len(calls) == 1
    assert len([i for i in typed.query("learner", toolkit.student_pk(sid)).items if i.type == "EVENT"]) == 1


def test_the_same_key_with_a_different_request_is_422(ddb, sid):
    run_idempotent(sid, key="k2", operation="op", body={"a": 1}, build=lambda uow: uow.put_new(event(sid)) and {"ok": 1})
    with pytest.raises(IdempotencyKeyReused):
        run_idempotent(sid, key="k2", operation="op", body={"a": 2}, build=lambda uow: {})
    with pytest.raises(IdempotencyKeyReused):
        run_idempotent(sid, key="k2", operation="other_op", body={"a": 1}, build=lambda uow: {})


def test_without_a_key_it_just_commits(ddb, sid):
    resp, replayed = run_idempotent(sid, key=None, operation="op", body={}, build=lambda uow: (uow.put_new(event(sid)), {"x": 1})[1])
    assert (resp, replayed) == ({"x": 1}, False) and len(typed.query("learner", toolkit.student_pk(sid)).items) == 1


def test_the_idempotency_receipt_is_a_typed_item(ddb, sid):
    from mathbank_rest.models.manual.learner_idem import LearnerIdem

    run_idempotent(sid, key="k9", operation="op", body={"a": 1}, build=lambda uow: {"big": "x" * 40_000})
    rec = typed.require(LearnerIdem, toolkit.student_pk(sid), "IDEM#k9")
    assert rec.response is None and rec.ref("response") is not None and rec.resolve("response") == {"big": "x" * 40_000}   # offloaded
    assert rec.ttl and rec.ttl > toolkit.epoch_after(6)


def test_the_receipt_is_written_in_the_same_transaction_so_a_failed_effect_leaves_no_receipt(ddb, sid):
    typed.put_new(profile(sid))
    with pytest.raises(ConditionFailed):
        run_idempotent(sid, key="k3", operation="op", body={}, build=lambda uow: (uow.put_new(profile(sid)), {})[1])
    assert toolkit.get_item("learner", toolkit.student_pk(sid), "IDEM#k3") is None


def test_build_over_the_receipt_budget_is_refused(ddb, sid):
    def build(uow):
        for i in range(100):
            uow.put_new(event(sid, i))
        return {}

    with pytest.raises(StoreError, match="limit"):
        run_idempotent(sid, key="k4", operation="op", body={}, build=build)


# ------------------------------------------------------------------ retries and hooks

def test_with_retries_retries_only_conflicts_and_gives_up(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    n = {"c": 0}

    def flaky():
        n["c"] += 1
        if n["c"] < 3:
            raise ConditionFailed("race")
        return "done"

    assert with_retries(flaky) == "done" and n["c"] == 3
    n["c"] = 0
    with pytest.raises(ConditionFailed):
        with_retries(lambda: (_ for _ in ()).throw(ConditionFailed("always")), attempts=2)
    with pytest.raises(ValidationFailed):                              # other errors are not retried
        with_retries(lambda: (_ for _ in ()).throw(ValidationFailed("bad")))


def test_auto_diagnose_hook_defaults_to_noop_and_is_isolated(ddb, sid):
    hooks.register_auto_diagnose(None)
    uow = LearnerUnitOfWork(sid)
    assert hooks.run_auto_diagnose(uow, {"student_id": sid}) is False
    seen = {}

    def hook(u, ctx):
        seen.update(ctx)
        u.put_new(event(sid))
        return True

    hooks.register_auto_diagnose(hook)
    try:
        assert hooks.run_auto_diagnose(uow, {"student_id": sid}) is True and seen["budget"] == 99 and len(uow) == 1
        hooks.register_auto_diagnose(lambda u, c: 1 / 0)
        assert hooks.run_auto_diagnose(uow, {}) is False                        # a failing diagnosis never breaks the outcome
    finally:
        hooks.register_auto_diagnose(None)
