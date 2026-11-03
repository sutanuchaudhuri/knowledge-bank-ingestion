"""Store-layer DynamoDB toolkit on moto (requirement 71 §2.3)."""
from __future__ import annotations

import threading
import time
import uuid

import pytest

from mathbank_rest.stores import ddb as t
from mathbank_rest.stores.errors import (
    ConditionFailed,
    IdempotencyKeyReused,
    InvalidToken,
    NotFound,
    RevisionConflict,
    StoreError,
    UniqueViolation,
)

CTX = "learner"


def put(sid, sk, **extra):
    item = {"PK": t.student_pk(sid), "SK": sk, "type": "T", "version": 1, **extra}
    t.put_item(CTX, item)
    return item


# ---------------------------------------------------------------- conversion

def test_encode_decode_round_trip(ddb):
    import datetime as dt
    import decimal

    value = {"f": 0.1, "i": 3, "neg": -2.5, "u": uuid.UUID(int=1), "d": dt.date(2026, 1, 2), "none": None,
             "ts": dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.timezone(dt.timedelta(hours=-5))),
             "nested": {"a": [1, 2.5, None, {"b": True}]}, "s": {"x", "y"}}
    enc = t.encode_item(value)
    assert "none" not in enc and isinstance(enc["f"], decimal.Decimal)
    assert enc["ts"] == "2026-01-02T08:04:05.000000Z" and enc["s"] == ["x", "y"]
    assert t.decode(enc)["f"] == 0.1 and t.decode(enc)["i"] == 3 and isinstance(t.decode(enc)["i"], int)


def test_table_names_use_env_and_dashes(ddb):
    assert t.table_name("agent_sessions") == "mb-agent-sessions-ut"
    assert t.table_name("learner") == "mb-learner-ut"


# ---------------------------------------------------------------- single items and cas_update

def test_get_put_round_trip_and_missing(ddb, sid):
    put(sid, "PROFILE", email="a@example.test", score=0.75)
    got = t.get_item(CTX, t.student_pk(sid), "PROFILE")
    assert got["email"] == "a@example.test" and got["score"] == 0.75
    assert t.get_item(CTX, t.student_pk(sid), "NOPE") is None


def test_put_condition_not_exists(ddb, sid):
    put(sid, "A")
    with pytest.raises(UniqueViolation) as e:
        t.put_item(CTX, {"PK": t.student_pk(sid), "SK": "A", "type": "T"}, t.NOT_EXISTS, UniqueViolation("sk", "A"))
    assert e.value.field == "sk"


def test_cas_update_bumps_version_and_sets_fields(ddb, sid):
    put(sid, "X", name="old", gone="y")
    new = t.cas_update(CTX, t.student_pk(sid), "X", 1, {"name": "new"}, remove=["gone"])
    assert new["version"] == 2 and new["name"] == "new" and "gone" not in new and new["updated_at"].endswith("Z")
    assert t.get_item(CTX, t.student_pk(sid), "X")["version"] == 2


def test_cas_update_stale_version_reports_current_revision(ddb, sid):
    put(sid, "X")
    t.cas_update(CTX, t.student_pk(sid), "X", 1, {"a": 1})
    with pytest.raises(RevisionConflict) as e:
        t.cas_update(CTX, t.student_pk(sid), "X", 1, {"a": 2})
    assert e.value.current_revision == 2 and e.value.body() == {"detail": "revision_conflict", "current_revision": 2}


def test_cas_update_missing_item_is_not_found(ddb, sid):
    with pytest.raises(NotFound):
        t.cas_update(CTX, t.student_pk(sid), "MISSING", 1, {"a": 1})


def test_cas_update_extra_condition_failure(ddb, sid):
    put(sid, "X", status="CLOSED")
    cond = t.Cond("#st = :open", {"#st": "status"}, {":open": "OPEN"})
    with pytest.raises(ConditionFailed):
        t.cas_update(CTX, t.student_pk(sid), "X", 1, {"a": 1}, cond=cond)
    assert t.get_item(CTX, t.student_pk(sid), "X")["version"] == 1


@pytest.mark.parametrize("field", ["PK", "SK", "version", "updated_at"])
def test_cas_update_refuses_reserved_fields(ddb, sid, field):
    put(sid, "X")
    with pytest.raises(ValueError):
        t.cas_update(CTX, t.student_pk(sid), "X", 1, {field: "x"})


def test_cas_update_only_one_of_concurrent_writers_wins(ddb, sid):
    put(sid, "X", n=0)
    wins, losses = [], []

    def worker(i):
        try:
            t.cas_update(CTX, t.student_pk(sid), "X", 1, {"n": i})
            wins.append(i)
        except RevisionConflict:
            losses.append(i)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    [x.start() for x in threads]
    [x.join() for x in threads]
    assert len(wins) == 1 and len(losses) == 7 and t.get_item(CTX, t.student_pk(sid), "X")["version"] == 2


# ---------------------------------------------------------------- transactions and sentinels

def test_transaction_is_all_or_nothing(ddb, sid):
    put(sid, "EXISTS")
    ops = [t.Put(CTX, {"PK": t.student_pk(sid), "SK": "NEW", "type": "T"}),
           t.Put(CTX, {"PK": t.student_pk(sid), "SK": "EXISTS", "type": "T"}, t.NOT_EXISTS,
                 ConditionFailed("exists", op="second"), label="second")]
    with pytest.raises(ConditionFailed) as e:
        t.transact(ops)
    assert e.value.detail == {"op": "second"}
    assert t.get_item(CTX, t.student_pk(sid), "NEW") is None


def test_sentinel_blocks_duplicate_and_writes_nothing_else(ddb, sid):
    email = f"{sid}@example.test"
    t.transact([t.sentinel_put(CTX, "email", email, {"student_id": sid}),
                t.Put(CTX, {"PK": t.student_pk(sid), "SK": "PROFILE", "type": "PROFILE", "version": 1})])
    other = str(uuid.uuid4())
    with pytest.raises(UniqueViolation) as e:
        t.transact([t.sentinel_put(CTX, "email", email, {"student_id": other}),
                    t.Put(CTX, {"PK": t.student_pk(other), "SK": "PROFILE", "type": "PROFILE", "version": 1})])
    assert e.value.field == "email" and e.value.body() == {"detail": "unique_violation", "field": "email"}
    assert t.get_item(CTX, t.student_pk(other), "PROFILE") is None


def test_transaction_version_check_and_update(ddb, sid):
    put(sid, "ATTEMPT", n=0)
    # The version condition belongs on the Update itself (DynamoDB forbids Check + Update on one item).
    bump = lambda expected, label: t.Update(
        CTX, t.student_pk(sid), "ATTEMPT", "SET #n = :n, #v = #v + :one", names={"#n": "n", "#v": "version"},
        values={":n": 5, ":one": 1}, cond=t.version_is(expected), conflict=RevisionConflict(None), label=label)
    t.transact([bump(1, "first"), t.Put(CTX, {"PK": t.student_pk(sid), "SK": "EVENT#1", "type": "EVENT"})])
    got = t.get_item(CTX, t.student_pk(sid), "ATTEMPT")
    assert got["n"] == 5 and got["version"] == 2
    with pytest.raises(RevisionConflict):
        t.transact([bump(1, "stale"), t.Put(CTX, {"PK": t.student_pk(sid), "SK": "EVENT#2", "type": "EVENT"})])
    assert t.get_item(CTX, t.student_pk(sid), "EVENT#2") is None


def test_condition_check_guards_a_different_item(ddb, sid):
    put(sid, "PARENT", status="OPEN")
    ops = lambda status: [t.Check(CTX, t.student_pk(sid), "PARENT", t.Cond("#s = :s", {"#s": "status"}, {":s": status}),
                                  label="parent-state"),
                          t.Put(CTX, {"PK": t.student_pk(sid), "SK": f"CHILD#{status}", "type": "CHILD"})]
    t.transact(ops("OPEN"))
    with pytest.raises(ConditionFailed):
        t.transact(ops("CLOSED"))
    assert t.get_item(CTX, t.student_pk(sid), "CHILD#CLOSED") is None


def test_transaction_limit_is_enforced_client_side(ddb, sid):
    ops = [t.Put(CTX, {"PK": t.student_pk(sid), "SK": f"S{i}", "type": "T"}) for i in range(101)]
    with pytest.raises(StoreError):
        t.transact(ops)


# ---------------------------------------------------------------- queries and pagination tokens

def _seed(sid, n=7):
    for i in range(n):
        put(sid, f"EVENT#{i:03d}", GSI1PK=f"ATT#{sid}", GSI1SK=f"{i:03d}")


def test_query_page_walks_partition_with_tokens(ddb, sid):
    _seed(sid)
    seen, token, pages = [], None, 0
    while True:
        page = t.query_page(CTX, t.student_pk(sid), sk_begins="EVENT#", limit=3, next_token=token)
        seen += [i["SK"] for i in page["items"]]
        pages += 1
        token = page["next_token"]
        if not token:
            break
    assert seen == [f"EVENT#{i:03d}" for i in range(7)] and pages == 3


def test_query_page_backwards_and_gsi(ddb, sid):
    _seed(sid)
    page = t.query_page(CTX, f"ATT#{sid}", index="GSI1", forward=False, limit=2)
    assert [i["GSI1SK"] for i in page["items"]] == ["006", "005"] and page["next_token"]


def test_query_limit_is_capped(ddb, sid):
    _seed(sid, 3)
    assert len(t.query_page(CTX, t.student_pk(sid), limit=100000)["items"]) == 3


def test_token_cannot_be_used_on_another_partition_or_tampered(ddb, sid):
    _seed(sid)
    token = t.query_page(CTX, t.student_pk(sid), sk_begins="EVENT#", limit=2)["next_token"]
    with pytest.raises(InvalidToken):
        t.query_page(CTX, t.student_pk(str(uuid.uuid4())), sk_begins="EVENT#", limit=2, next_token=token)
    with pytest.raises(InvalidToken):
        t.query_page(CTX, t.student_pk(sid), sk_begins="EVENT#", limit=2, next_token=token[:-3] + "AAA")
    with pytest.raises(InvalidToken):
        t.query_page(CTX, t.student_pk(sid), sk_begins="EVENT#", limit=2, next_token="garbage")


def test_expired_token_is_rejected(ddb):
    token = t.sign_token({"x": 1}, ttl_seconds=-1)
    with pytest.raises(InvalidToken):
        t.verify_token(token)
    assert t.verify_token(t.sign_token({"x": 1}))["x"] == 1


def test_batch_get_returns_present_items(ddb, sid):
    for i in range(3):
        put(sid, f"K{i}")
    got = t.batch_get(CTX, [(t.student_pk(sid), f"K{i}") for i in range(5)])
    assert sorted(i["SK"] for i in got) == ["K0", "K1", "K2"]


# ---------------------------------------------------------------- S3 offload

def test_offload_policy_moves_only_listed_large_attributes(ddb, sid):
    small, big = "s" * 100, "x" * (t.OFFLOAD_THRESHOLD + 5)
    item = {"PK": t.student_pk(sid), "SK": "RESP#1", "type": "RESPONSE", "answer": big, "note": small}
    t.offload(CTX, item, ("answer", "note"))
    assert "answer" not in item and item["note"] == small
    ref = item["answer_ref"]
    assert ref["key"].startswith(f"offload/learner/students/{sid}/RESPONSE/") and ref["key"].endswith("/answer.json")
    assert t.load_attr(item, "answer") == big and t.load_attr(item, "note") == small


def test_offload_key_layout_matches_the_migration(ddb, sid):
    item = {"PK": "PROBLEM#p1", "SK": "META", "type": "PROBLEM"}
    key = t.offload_key("content", item, "statement")
    assert key.startswith("offload/content/PROBLEM/") and key.endswith("/statement.json")
    owned = {"PK": "SESSION#s1", "SK": "RESP#a", "type": "RESP", "student_id": sid}
    assert t.offload_key("live", owned, "response").startswith(f"offload/live/students/{sid}/RESP/")


def test_safety_net_offloads_largest_attribute_of_oversize_item(ddb, sid):
    item = {"PK": t.student_pk(sid), "SK": "BIG", "type": "T", "a": "a" * 200_000, "b": "b" * 200_000, "c": "c"}
    t.offload(CTX, item, ())
    assert len(t._json_bytes(item)) < t.MAX_ITEM_BYTES and ("a_ref" in item or "b_ref" in item)


def test_resolve_ref_detects_tampering(ddb, sid):
    item = {"PK": t.student_pk(sid), "SK": "R", "type": "T", "answer": "x" * (t.OFFLOAD_THRESHOLD + 1)}
    t.offload(CTX, item, ("answer",))
    ref = item["answer_ref"]
    t.client("s3").put_object(Bucket=ref["bucket"], Key=ref["key"], Body=b'"y"' + b" " * (ref["bytes"] - 3))
    with pytest.raises(StoreError, match="checksum"):
        t.resolve_ref(ref)
    t.client("s3").put_object(Bucket=ref["bucket"], Key=ref["key"], Body=b"short")
    with pytest.raises(StoreError, match="size"):
        t.resolve_ref(ref)


def test_presigned_url_is_regional_short_lived_and_capped(ddb, sid):
    item = {"PK": t.student_pk(sid), "SK": "R", "type": "T", "answer": "x" * (t.OFFLOAD_THRESHOLD + 1)}
    t.offload(CTX, item, ("answer",))
    url = t.presign(item["answer_ref"], expires=99999)
    assert ".s3.us-east-2.amazonaws.com/" in url, "must presign against the regional host, not the global endpoint"
    assert "X-Amz-Expires=900" in url and "X-Amz-Signature=" in url  # SigV4, capped at 15 minutes


# ---------------------------------------------------------------- idempotency

def _build_counter(sid, calls):
    def build():
        calls.append(1)
        return ([t.Put(CTX, {"PK": t.student_pk(sid), "SK": f"EFFECT#{len(calls)}", "type": "EFFECT"})],
                {"ok": True, "n": len(calls)})

    return build


def test_idempotent_effect_and_replay(ddb, sid):
    calls = []
    kw = {"owner_pk": t.student_pk(sid), "key": "k-1", "req_hash": t.request_hash({"a": 1})}
    r1 = t.run_idempotent(CTX, build=_build_counter(sid, calls), **kw)
    r2 = t.run_idempotent(CTX, build=_build_counter(sid, calls), **kw)
    assert r1 == ({"ok": True, "n": 1}, False) and r2 == ({"ok": True, "n": 1}, True)
    assert len(calls) == 1
    effects = t.query_page(CTX, t.student_pk(sid), sk_begins="EFFECT#")["items"]
    assert len(effects) == 1


def test_idempotency_key_reuse_with_other_body_is_rejected(ddb, sid):
    calls = []
    t.run_idempotent(CTX, owner_pk=t.student_pk(sid), key="k", req_hash="h1", build=_build_counter(sid, calls))
    with pytest.raises(IdempotencyKeyReused):
        t.run_idempotent(CTX, owner_pk=t.student_pk(sid), key="k", req_hash="h2", build=_build_counter(sid, calls))
    assert len(calls) == 1


def test_idempotency_receipt_commits_atomically_with_a_failing_effect(ddb, sid):
    put(sid, "TAKEN")
    bad = lambda: ([t.Put(CTX, {"PK": t.student_pk(sid), "SK": "TAKEN", "type": "T"}, t.NOT_EXISTS,
                          ConditionFailed("taken"))], {"ok": 1})
    with pytest.raises(ConditionFailed):
        t.run_idempotent(CTX, owner_pk=t.student_pk(sid), key="k", req_hash="h", build=bad)
    assert t.get_item(CTX, t.student_pk(sid), "IDEM#k") is None  # no receipt without the effect


def test_idempotency_concurrent_requests_apply_effect_once(ddb, sid):
    calls, results = [], []
    lock = threading.Lock()

    def worker():
        def build():
            with lock:
                calls.append(1)
            return ([t.Put(CTX, {"PK": t.student_pk(sid), "SK": f"EFFECT#{uuid.uuid4()}", "type": "EFFECT"})], {"ok": True})

        results.append(t.run_idempotent(CTX, owner_pk=t.student_pk(sid), key="race", req_hash="h", build=build))

    threads = [threading.Thread(target=worker) for _ in range(6)]
    [x.start() for x in threads]
    [x.join() for x in threads]
    assert len(results) == 6 and all(r[0] == {"ok": True} for r in results)
    assert sum(1 for _, replayed in results if not replayed) == 1
    assert len(t.query_page(CTX, t.student_pk(sid), sk_begins="EFFECT#")["items"]) == 1


def test_expired_receipt_allows_the_key_to_be_reused(ddb, sid, monkeypatch):
    calls = []
    kw = {"owner_pk": t.student_pk(sid), "key": "old", "req_hash": "h"}
    t.run_idempotent(CTX, build=_build_counter(sid, calls), **kw)
    t.cas_update(CTX, t.student_pk(sid), "IDEM#old", 1, {"ttl": int(time.time()) - 10})
    _, replayed = t.run_idempotent(CTX, build=_build_counter(sid, calls), **kw)
    assert replayed is False and len(calls) == 2


def test_large_idempotent_response_is_offloaded_and_replayed(ddb, sid):
    big = {"data": "z" * (t.OFFLOAD_THRESHOLD + 10)}
    calls = []

    def build():
        calls.append(1)
        return [], big

    kw = {"owner_pk": t.student_pk(sid), "key": "big", "req_hash": "h"}
    t.run_idempotent(CTX, build=build, **kw)
    assert t.get_item(CTX, t.student_pk(sid), "IDEM#big").get("response_ref")
    assert t.run_idempotent(CTX, build=build, **kw) == (big, True) and len(calls) == 1
