"""WP3 notify store on moto: producer idempotency, atomic unread counter, owner scoping, pagination, admin inbox,
frozen cutover, and the DynamoDB-only rules (no scan, no Postgres). A threaded variant for the real `test` environment is
marked ``ddb_integration``."""
from __future__ import annotations

import ast
import threading
import uuid
from pathlib import Path

import pytest
from wp3_support import seed_learner, wp3_fixture  # noqa: F401  (fixture 'wp3')

from mathbank_rest import notifications
from mathbank_rest.models.manual.notify import NotifyDedupe, NotifyInboxCounter, NotifyNotification
from mathbank_rest.notifications import NotificationCreate
from mathbank_rest.stores import FrozenProxy, typed
from mathbank_rest.stores.errors import InvalidToken, NotFound, StoreFrozen, ValidationFailed
from mathbank_rest.stores.notify import DynamoDBNotifyStore

STORES = Path(__file__).resolve().parents[2] / "src" / "mathbank_rest" / "stores"


def student_note(sid: str, **kw) -> NotificationCreate:
    return NotificationCreate(recipient_type="STUDENT", recipient_id=sid, notification_type=kw.pop("notification_type", "QUIZ_GRADED"),
                              severity="SUCCESS", title=kw.pop("title", "graded"), payload_json=kw.pop("payload_json", {"quiz_id": "q1"}),
                              **kw)


def admin_note(**kw) -> NotificationCreate:
    return NotificationCreate(recipient_type="ADMIN", recipient_id="admin-1", severity="ACTION_NEEDED",
                              notification_type=kw.pop("notification_type", "ADMIN_REVIEW_NEEDED"), title="review",
                              payload_json={"release_id": "r1"})


@pytest.fixture()
def store(wp3):
    return DynamoDBNotifyStore()


def unread(store, sid) -> int:
    return store.count_unread(recipient_type="STUDENT", recipient_id=sid)


def test_record_lists_newest_first_with_payload_and_counter(store):
    sid = seed_learner()
    ids = [store.record_notification(student_note(sid, title=f"n{i}")) for i in range(3)]
    page = store.list_notifications(recipient_type="STUDENT", recipient_id=sid)
    assert [str(n.notification_id) for n in page.notifications] == ids[::-1]
    assert page.unread_count == 3 and page.next_token is None
    first = page.notifications[-1]
    assert first.payload_json == {"quiz_id": "q1"} and first.read_at is None and first.recipient_id == sid
    assert first.created_at.endswith("Z")


def test_redelivery_with_same_dedupe_key_is_a_noop(store):
    sid = seed_learner()
    first = store.record_notification(student_note(sid), dedupe_key="mb-quiz#QUIZ#1#RESP#1#3")
    again = store.record_notification(student_note(sid), dedupe_key="mb-quiz#QUIZ#1#RESP#1#3")
    other = store.record_notification(student_note(sid), dedupe_key="mb-quiz#QUIZ#1#RESP#1#4")
    assert again == first and other != first
    assert unread(store, sid) == 2
    assert len(store.list_notifications(recipient_type="STUDENT", recipient_id=sid).notifications) == 2
    sentinel = typed.require(NotifyDedupe, f"RCPT#STUDENT#{sid}", "DEDUPE#mb-quiz#QUIZ#1#RESP#1#3")
    assert str(sentinel.notification_id) == first


def test_dedupe_is_per_recipient(store):
    a, b = seed_learner(), seed_learner()
    ia = store.record_notification(student_note(a), dedupe_key="k")
    ib = store.record_notification(student_note(b), dedupe_key="k")
    assert ia != ib and unread(store, a) == unread(store, b) == 1


def test_unknown_recipient_writes_nothing(store):
    ghost = str(uuid.uuid4())
    with pytest.raises(NotFound):
        store.record_notification(student_note(ghost), dedupe_key="k")
    assert store.list_notifications(recipient_type="STUDENT", recipient_id=ghost).notifications == []
    assert unread(store, ghost) == 0


def test_bad_recipient_id_and_bad_payload_are_validation_errors(store):
    with pytest.raises(ValidationFailed):
        store.record_notification(student_note("not-a-uuid"))
    with pytest.raises(ValidationFailed):
        store.record_notification(student_note(seed_learner(), payload_json={"quiz_id": 12}))


def test_mark_read_is_owner_scoped_and_idempotent(store):
    mine, theirs = seed_learner(), seed_learner()
    nid = store.record_notification(student_note(mine))
    with pytest.raises(NotFound):  # another student's id is "not found", never "forbidden"
        store.mark_read(notification_id=nid, recipient_id=theirs)
    assert unread(store, mine) == 1 and unread(store, theirs) == 0
    assert store.mark_read(notification_id=nid, recipient_id=mine) is True
    assert store.mark_read(notification_id=nid, recipient_id=mine) is False  # already read: 200 idempotent
    assert unread(store, mine) == 0
    with pytest.raises(NotFound):
        store.mark_read(notification_id=str(uuid.uuid4()), recipient_id=mine)


def test_unread_counter_never_goes_below_zero(store):
    sid = seed_learner()
    nid = store.record_notification(student_note(sid))
    typed.put(NotifyInboxCounter(PK=f"RCPT#STUDENT#{sid}", SK="COUNTER", unread_count=0, version=9))  # drifted to zero
    assert store.mark_read(notification_id=nid, recipient_id=sid) is True
    assert unread(store, sid) == 0
    item = typed.require(NotifyNotification, f"RCPT#STUDENT#{sid}", f"N#{nid}")
    assert item.read_at is not None and item.GSI1PK is None


def test_mark_read_removes_the_notification_from_the_unread_index(store):
    sid = seed_learner()
    a, b = (store.record_notification(student_note(sid)) for _ in range(2))
    store.mark_read(notification_id=a, recipient_id=sid)
    unread_ids = [str(n.notification_id) for n in
                  store.list_notifications(recipient_type="STUDENT", recipient_id=sid, unread_only=True).notifications]
    assert unread_ids == [b]
    allof = store.list_notifications(recipient_type="STUDENT", recipient_id=sid).notifications
    assert len(allof) == 2 and {n.read_at is None for n in allof} == {True, False}


def test_pagination_walks_every_item_once_and_rejects_tampering(store):
    sid = seed_learner()
    ids = [store.record_notification(student_note(sid)) for _ in range(5)]
    seen, token = [], None
    while True:
        page = store.list_notifications(recipient_type="STUDENT", recipient_id=sid, limit=2, next_token=token)
        seen += [str(n.notification_id) for n in page.notifications]
        token = page.next_token
        if token is None:
            break
    assert seen == ids[::-1]
    page = store.list_notifications(recipient_type="STUDENT", recipient_id=sid, limit=2)
    body, sig = page.next_token.split(".")
    for bad in (f"{body}.{sig[::-1]}", f"x{body}.{sig}", "garbage"):
        with pytest.raises(InvalidToken):
            store.list_notifications(recipient_type="STUDENT", recipient_id=sid, limit=2, next_token=bad)
    other = seed_learner()
    with pytest.raises(InvalidToken):  # a token is bound to its partition: it cannot page someone else's inbox
        store.list_notifications(recipient_type="STUDENT", recipient_id=other, limit=2, next_token=page.next_token)


def test_offset_is_rejected_rather_than_silently_ignored(store):
    with pytest.raises(ValidationFailed):
        store.list_notifications(recipient_type="STUDENT", recipient_id=seed_learner(), offset=5)


def test_mark_all_read(store):
    sid, other = seed_learner(), seed_learner()
    for _ in range(5):
        store.record_notification(student_note(sid))
    keep = store.record_notification(student_note(other))
    assert store.mark_all_read(recipient_id=sid) == 5
    assert store.mark_all_read(recipient_id=sid) == 0
    assert unread(store, sid) == 0 and unread(store, other) == 1
    assert store.list_notifications(recipient_type="STUDENT", recipient_id=other, unread_only=True).notifications[0].notification_id == uuid.UUID(keep)


def test_mark_all_read_spans_several_transaction_chunks(store, monkeypatch):
    from mathbank_rest.stores.notify import dynamodb as mod

    monkeypatch.setattr(mod, "CHUNK", 2)
    sid = seed_learner()
    for _ in range(5):
        store.record_notification(student_note(sid))
    assert store.mark_all_read(recipient_id=sid) == 5 and unread(store, sid) == 0


def test_admin_inbox_lists_filters_and_acknowledges_with_actor(store):
    a = store.record_notification(admin_note())
    b = store.record_notification(admin_note(notification_type="ADMIN_DATA_GAP"))
    assert [str(n.notification_id) for n in store.list_admin_notifications().notifications] == [b, a]
    only = store.list_admin_notifications(notification_type="ADMIN_REVIEW_NEEDED")
    assert [str(n.notification_id) for n in only.notifications] == [a] and only.unread_count == 2
    res = store.admin_ack(notification_id=a, actor_id="staff:42")
    assert res == {"notification_id": a, "acknowledged": True, "acknowledged_by": "staff:42", "newly_acknowledged": True}
    again = store.admin_ack(notification_id=a, actor_id="staff:7")  # idempotent; the first actor is kept
    assert again["acknowledged_by"] == "staff:42" and again["newly_acknowledged"] is False
    assert [str(n.notification_id) for n in store.list_admin_notifications(unread_only=True).notifications] == [b]
    with pytest.raises(NotFound):
        store.admin_ack(notification_id=str(uuid.uuid4()), actor_id="staff:42")


def test_admin_cannot_ack_a_student_notification_and_student_cannot_touch_admin_ones(store):
    sid = seed_learner()
    student_nid = store.record_notification(student_note(sid))
    admin_nid = store.record_notification(admin_note())
    with pytest.raises(NotFound):
        store.admin_ack(notification_id=student_nid, actor_id="staff:1")
    with pytest.raises(NotFound):
        store.mark_read(notification_id=admin_nid, recipient_id=sid)


def test_type_filtered_admin_listing_pages_without_skipping(store):
    ids = []
    for i in range(6):
        ids.append(store.record_notification(admin_note(notification_type="ADMIN_REVIEW_NEEDED" if i % 2 == 0 else "ADMIN_DATA_GAP")))
    wanted = [ids[4], ids[2], ids[0]]
    got, token = [], None
    while True:
        page = store.list_admin_notifications(notification_type="ADMIN_REVIEW_NEEDED", limit=2, next_token=token)
        got += [str(n.notification_id) for n in page.notifications]
        token = page.next_token
        if token is None:
            break
    assert got == wanted


def test_a_failing_realtime_push_never_fails_the_write(store, monkeypatch):
    def boom(_event):
        raise RuntimeError("socket.io down")

    monkeypatch.setattr(notifications, "_publish_realtime", boom)
    sid = seed_learner()
    assert store.record_notification(student_note(sid))
    assert unread(store, sid) == 1


def test_realtime_hook_receives_the_new_event_once(store, monkeypatch):
    seen = []
    monkeypatch.setattr(notifications, "_publish_realtime", seen.append)
    sid = seed_learner()
    nid = store.record_notification(student_note(sid), dedupe_key="k")
    store.record_notification(student_note(sid), dedupe_key="k")  # duplicate delivery: no second push
    assert [str(e.notification_id) for e in seen] == [nid]


def test_reconcile_repairs_a_drifted_counter(store):
    sid = seed_learner()
    for _ in range(3):
        store.record_notification(student_note(sid))
    typed.put(NotifyInboxCounter(PK=f"RCPT#STUDENT#{sid}", SK="COUNTER", unread_count=0, version=5))
    assert store.reconcile_unread_count(recipient_type="STUDENT", recipient_id=sid) == 3
    assert unread(store, sid) == 3


def test_erase_student_empties_the_partition_only(store):
    sid, other = seed_learner(), seed_learner()
    for i in range(3):
        store.record_notification(student_note(sid), dedupe_key=f"k{i}")
    store.record_notification(student_note(other))
    assert store.erase_student(sid) == 3 * 2 + 1  # notifications + dedupe sentinels + counter
    assert store.list_notifications(recipient_type="STUDENT", recipient_id=sid).notifications == []
    assert unread(store, sid) == 0 and unread(store, other) == 1


def test_large_payload_body_round_trips_through_s3(store):
    sid = seed_learner()
    nid = store.record_notification(student_note(sid, body="x" * 40_000))
    item = typed.require(NotifyNotification, f"RCPT#STUDENT#{sid}", f"N#{nid}")
    assert item.body is None and item.body_ref is not None
    assert store.list_notifications(recipient_type="STUDENT", recipient_id=sid).notifications[0].body == "x" * 40_000


def test_frozen_store_serves_reads_and_rejects_writes(store):
    sid = seed_learner()
    nid = store.record_notification(student_note(sid))
    frozen = FrozenProxy("notify", store)
    assert frozen.count_unread(recipient_type="STUDENT", recipient_id=sid) == 1
    assert len(frozen.list_notifications(recipient_type="STUDENT", recipient_id=sid).notifications) == 1
    assert len(frozen.list_admin_notifications().notifications) == 0
    for call in (lambda: frozen.record_notification(student_note(sid)),
                 lambda: frozen.mark_read(notification_id=nid, recipient_id=sid),
                 lambda: frozen.mark_all_read(recipient_id=sid),
                 lambda: frozen.admin_ack(notification_id=nid, actor_id="x")):
        with pytest.raises(StoreFrozen):
            call()
    assert unread(store, sid) == 1


@pytest.mark.parametrize("module", ["notify", "jobs"])
def test_dynamodb_stores_never_scan_or_touch_postgres(module):
    tree = ast.parse((STORES / module / "dynamodb.py").read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any("postgres" in m or m.startswith("sqlalchemy") for m in imported), imported
    calls = {getattr(n.func, "attr", getattr(n.func, "id", "")) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not calls & {"scan", "batch_write_item", "execute"}


# ---------------------------------------------------------------------------------------------------------------
# Real-AWS variant: moto does not serialise concurrent transactions the way DynamoDB does.

@pytest.mark.ddb_integration
def test_concurrent_producers_and_readers_on_the_real_test_environment(real_env):
    store = DynamoDBNotifyStore(check_recipient=False)
    sid = str(uuid.uuid4())
    try:
        results: list[str] = []

        def produce():
            results.append(store.record_notification(student_note(sid), dedupe_key="same-event"))

        threads = [threading.Thread(target=produce) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert len(set(results)) == 1 and unread(store, sid) == 1

        ids = [store.record_notification(student_note(sid), dedupe_key=f"e{i}") for i in range(10)]
        done: list[bool] = []
        readers = [threading.Thread(target=lambda n=n: done.append(store.mark_read(notification_id=n, recipient_id=sid))) for n in ids * 2]
        [t.start() for t in readers]
        [t.join() for t in readers]
        assert done.count(True) == 10 and unread(store, sid) == 1  # each marked exactly once; the first event stays unread
    finally:
        store.erase_student(sid)
