"""``notify`` store on DynamoDB (``mb-notify``), requirement 70 C5 and requirement 71 WP3.

Items, all under the recipient's partition ``RCPT#STUDENT#<sid>`` (or the shared ``RCPT#ADMIN``):

* ``N#<uuidv7>``        NOTIFICATION. Time-ordered key; ``GSI1PK=UNREAD#<recipient>`` while unread (sparse index, removed on read).
* ``DEDUPE#<key>``      UNIQUE(recipient, dedupe_key) sentinel, written in the **same transaction** as the notification.
* ``COUNTER``           INBOX_COUNTER; ``unread_count`` changes only in the transaction that changes an unread flag, so it
                        cannot drift under concurrency and never goes below zero (``nightly reconcile`` repairs TTL drift).

Ownership: the partition key is built from the authenticated recipient, never from the request, so another student's
notification id is simply not found (404). Idempotency: a redelivered ``record_notification`` with the same dedupe key
writes nothing and returns the id of the first delivery. Nothing here scans or touches PostgreSQL.
"""
from __future__ import annotations

import datetime as dt
import logging
import uuid
from typing import Any

from pydantic import ValidationError

from mathbank_rest import notifications
from mathbank_rest.models.manual.notify import (
    NotifyDedupe,
    NotifyInboxCounter,
    NotifyNotification,
    NotifyNotificationPayload,
)
from mathbank_rest.notifications import (
    NotificationCreate,
    NotificationEvent,
    NotificationListResponse,
    RecipientType,
)
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import ConditionFailed, NotFound, UniqueViolation, ValidationFailed

LOG = logging.getLogger("mathbank_rest.stores.notify")

TTL_DAYS = 90
CHUNK = 98  # 98 notifications + the counter fit one transaction with room to spare (limit 100)
MAX_LIMIT = 200
ADMIN_PK = "RCPT#ADMIN"
_FILTER_PAGES = 20  # pages read at most when filtering the admin inbox by notification_type


class _NotUnread(ConditionFailed):
    """The notification is absent or already read (decided by a follow-up read)."""


class _CounterFloor(ConditionFailed):
    """The unread counter is already zero (drift); the notification is still marked read."""


def _pk(recipient_type: str, recipient_id: str | None) -> str:
    if recipient_type == "ADMIN":
        return ADMIN_PK
    try:
        return f"RCPT#STUDENT#{uuid.UUID(str(recipient_id))}"
    except ValueError:
        raise ValidationFailed("recipient_id must be a student UUID") from None


def _unread_pk(pk: str) -> str:
    return "UNREAD#" + pk.removeprefix("RCPT#")


def _nid(notification_id: Any) -> str:
    try:
        return str(uuid.UUID(str(notification_id)))
    except ValueError:
        raise NotFound("notification not found") from None


def _event(item: NotifyNotification) -> NotificationEvent:
    payload = item.resolve("payload")
    rtype = item.recipient_type or ("ADMIN" if item.PK == ADMIN_PK else "STUDENT")
    return NotificationEvent(
        notification_id=item.notification_id or item.SK.removeprefix("N#"), recipient_type=rtype,
        recipient_id=item.recipient_id or ("ADMIN" if rtype == "ADMIN" else item.PK.rsplit("#", 1)[1]),
        notification_type=item.notification_type, severity=item.severity, title=item.title, body=item.resolve("body"),
        payload_json=payload.model_dump(mode="json", exclude_unset=True) if payload is not None else {},
        read_at=None if item.read_at is None else ddb.encode(item.read_at), created_at=ddb.encode(item.created_at),
        acknowledged_by=item.acknowledged_by)


def _counter_op(pk: str, delta: int, *, floor: bool = False):
    """One ``COUNTER`` update op. ``delta > 0`` creates the item on first use; ``delta < 0`` requires enough unread."""
    now = ddb.now_iso()
    if delta > 0:
        return ddb.Update("notify", pk, "COUNTER",
                          "SET #t = if_not_exists(#t, :t), #v = if_not_exists(#v, :z) + :one, #u = :now ADD unread_count :d",
                          names={"#t": "type", "#v": "version", "#u": "updated_at"},
                          values={":t": "INBOX_COUNTER", ":z": 0, ":one": 1, ":now": now, ":d": delta}, label="counter")
    return ddb.Update("notify", pk, "COUNTER", "SET unread_count = unread_count - :d, #v = #v + :one, #u = :now",
                      names={"#v": "version", "#u": "updated_at"}, values={":d": -delta, ":one": 1, ":now": now},
                      cond=ddb.Cond("unread_count >= :d"), conflict=_CounterFloor("unread counter below zero") if floor else None,
                      label="counter")


class DynamoDBNotifyStore:
    backend = "dynamodb"

    def __init__(self, *, check_recipient: bool = True):
        self._check_recipient = check_recipient

    # ------------------------------------------------------------------ produce

    def record_notification(self, notification: NotificationCreate, *, dedupe_key: str | None = None) -> str:
        pk = _pk(notification.recipient_type, notification.recipient_id)
        nid, now = ddb.uuid7(), dt.datetime.now(dt.UTC)
        ttl = int((now + dt.timedelta(days=TTL_DAYS)).timestamp())
        try:
            payload = NotifyNotificationPayload.model_validate(notification.payload_json)
        except ValidationError as exc:
            raise ValidationFailed("invalid notification payload", errors=[e["type"] for e in exc.errors()[:3]]) from None
        item = NotifyNotification(
            PK=pk, SK=f"N#{nid}", GSI1PK=_unread_pk(pk), GSI1SK=f"N#{nid}", created_at=now, notification_id=nid,
            notification_type=notification.notification_type, severity=notification.severity, title=notification.title,
            body=notification.body, payload=payload, dedupe_key=dedupe_key, recipient_id=notification.recipient_id,
            recipient_type=notification.recipient_type, ttl=ttl)
        ops = []
        if dedupe_key:
            ops.append(typed.tx_put(NotifyDedupe(PK=pk, SK=f"DEDUPE#{dedupe_key}", notification_id=nid, ttl=ttl), ddb.NOT_EXISTS,
                                    UniqueViolation("dedupe_key", dedupe_key), "dedupe"))
        ops.append(typed.tx_put(item, ddb.NOT_EXISTS, label="notification"))
        ops.append(_counter_op(pk, 1))
        if self._check_recipient and notification.recipient_type == "STUDENT":
            ops.append(ddb.Check("learner", f"STUDENT#{pk.rsplit('#', 1)[1]}", "PROFILE", ddb.EXISTS,
                                 NotFound("recipient not found"), "recipient"))
        try:
            ddb.transact(ops)
        except UniqueViolation:
            first = typed.get(NotifyDedupe, pk, f"DEDUPE#{dedupe_key}")
            if first is None:
                raise
            return str(first.notification_id)
        self._publish(_event(item))
        return nid

    @staticmethod
    def _publish(event: NotificationEvent) -> None:
        try:
            notifications._publish_realtime(event)
        except NotImplementedError:
            pass  # realtime delivery is deferred (requirements/59 §5)
        except Exception:
            LOG.warning("realtime publish failed for %s", event.notification_id, exc_info=True)

    # ------------------------------------------------------------------ read

    def count_unread(self, *, recipient_type: RecipientType, recipient_id: str) -> int:
        counter = typed.get(NotifyInboxCounter, _pk(recipient_type, recipient_id), "COUNTER")
        return counter.unread_count if counter else 0

    def list_notifications(self, *, recipient_type: RecipientType, recipient_id: str, limit: int = 25, offset: int = 0,
                           next_token: str | None = None, unread_only: bool = False) -> NotificationListResponse:
        if offset:
            raise ValidationFailed("offset is not supported on this backend; page with next_token")
        pk, limit = _pk(recipient_type, recipient_id), max(1, min(int(limit), MAX_LIMIT))
        kw: dict[str, Any] = {"sk_begins": "N#", "forward": False, "limit": limit, "next_token": next_token}
        page = (typed.query(NotifyNotification, _unread_pk(pk), index="GSI1", **kw) if unread_only
                else typed.query(NotifyNotification, pk, **kw))
        return NotificationListResponse(notifications=[_event(i) for i in page.items],
                                        unread_count=self.count_unread(recipient_type=recipient_type, recipient_id=recipient_id),
                                        next_token=page.next_token)

    def list_admin_notifications(self, *, limit: int = 25, offset: int = 0, next_token: str | None = None,
                                 unread_only: bool = False, notification_type: str | None = None) -> NotificationListResponse:
        if not notification_type:
            return self.list_notifications(recipient_type="ADMIN", recipient_id="", limit=limit, offset=offset,
                                           next_token=next_token, unread_only=unread_only)
        if offset:
            raise ValidationFailed("offset is not supported on this backend; page with next_token")
        limit, token, found = max(1, min(int(limit), MAX_LIMIT)), next_token, []
        for _ in range(_FILTER_PAGES):
            # a page never holds more than the still-missing count, so filtering cannot skip an item between pages
            page = (typed.query(NotifyNotification, _unread_pk(ADMIN_PK), index="GSI1", sk_begins="N#", forward=False,
                                limit=limit - len(found), next_token=token) if unread_only
                    else typed.query(NotifyNotification, ADMIN_PK, sk_begins="N#", forward=False, limit=limit - len(found),
                                     next_token=token))
            found += [i for i in page.items if i.notification_type == notification_type]
            token = page.next_token
            if token is None or len(found) >= limit:
                break
        return NotificationListResponse(notifications=[_event(i) for i in found],
                                        unread_count=self.count_unread(recipient_type="ADMIN", recipient_id=""), next_token=token)

    # ------------------------------------------------------------------ mark read

    def _mark(self, pk: str, notification_id: str, acknowledged_by: str | None) -> bool:
        sk = f"N#{_nid(notification_id)}"
        changes = {"read_at": dt.datetime.now(dt.UTC)}
        if acknowledged_by:
            changes["acknowledged_by"] = acknowledged_by
        new = typed.validate_changes(NotifyNotification, changes)
        sets = ["#u = :now", *(f"#a{i} = :a{i}" for i in range(len(new)))]
        names = {"#u": "updated_at", **{f"#a{i}": k for i, k in enumerate(new)}}
        values = {":now": ddb.now_iso(), **{f":a{i}": v for i, (_, v) in enumerate(new.items())}}
        unread = ddb.Cond("attribute_exists(PK) AND attribute_not_exists(read_at)")
        mark = ddb.Update("notify", pk, sk, "SET " + ", ".join(sets) + " REMOVE GSI1PK, GSI1SK", names=names, values=values,
                          cond=unread, conflict=_NotUnread("not unread"), label="notification")
        try:
            try:
                ddb.transact([mark, _counter_op(pk, -1, floor=True)])
            except _CounterFloor:
                ddb.transact([mark])  # counter already zero (TTL drift): still mark the notification read
            return True
        except _NotUnread:
            if typed.get(NotifyNotification, pk, sk) is None:
                raise NotFound("notification not found") from None
            return False  # already read: idempotent

    def mark_read(self, *, notification_id: str, recipient_id: str) -> bool:
        return self._mark(_pk("STUDENT", recipient_id), notification_id, None)

    def mark_all_read(self, *, recipient_id: str) -> int:
        pk, total = _pk("STUDENT", recipient_id), 0
        while True:
            items = typed.query(NotifyNotification, _unread_pk(pk), index="GSI1", sk_begins="N#", limit=CHUNK).items
            done = self._mark_chunk(pk, items) if items else 0
            total += done
            if done == 0:
                return total

    def _mark_chunk(self, pk: str, items: list[NotifyNotification]) -> int:
        now = ddb.now_iso()
        ops = [ddb.Update("notify", i.PK, i.SK, "SET read_at = :now, #u = :now REMOVE GSI1PK, GSI1SK", names={"#u": "updated_at"},
                          values={":now": now}, cond=ddb.Cond("attribute_exists(PK) AND attribute_not_exists(read_at)"),
                          conflict=_NotUnread("not unread")) for i in items]
        try:
            ddb.transact([*ops, _counter_op(pk, -len(items), floor=True)])
            return len(items)
        except ConditionFailed:  # read concurrently, or the counter drifted: settle the chunk one by one
            return sum(self._mark(pk, i.SK.removeprefix("N#"), None) for i in items)

    def admin_ack(self, *, notification_id: str, actor_id: str) -> dict:
        newly = self._mark(ADMIN_PK, notification_id, actor_id)
        item = typed.require(NotifyNotification, ADMIN_PK, f"N#{_nid(notification_id)}")
        return {"notification_id": str(_nid(notification_id)), "acknowledged": True,
                "acknowledged_by": item.acknowledged_by or actor_id, "newly_acknowledged": newly}

    # ------------------------------------------------------------------ maintenance

    def reconcile_unread_count(self, *, recipient_type: RecipientType, recipient_id: str) -> int:
        """Recompute ``unread_count`` from the sparse unread index (nightly job; repairs drift after TTL deletes)."""
        pk, count, token = _pk(recipient_type, recipient_id), 0, None
        while True:
            page = typed.query(NotifyNotification, _unread_pk(pk), index="GSI1", sk_begins="N#", limit=MAX_LIMIT, next_token=token)
            count, token = count + len(page.items), page.next_token
            if token is None:
                break
        current = typed.get(NotifyInboxCounter, pk, "COUNTER")
        typed.put(NotifyInboxCounter(PK=pk, SK="COUNTER", unread_count=count, version=(current.version or 0) + 1 if current else 1,
                                     updated_at=dt.datetime.now(dt.UTC)))
        return count

    def erase_student(self, student_id: str) -> int:
        """Privacy erasure: delete every item of the student's partition (notifications, dedupe sentinels, counter)."""
        pk, keys, token = _pk("STUDENT", student_id), [], None
        while True:
            page = typed.query("notify", pk, limit=MAX_LIMIT, next_token=token)
            keys += [(i.PK, i.SK) for i in page.items]
            token = page.next_token
            if token is None:
                break
        for n in range(0, len(keys), 100):
            ddb.transact([ddb.Delete("notify", p, s) for p, s in keys[n:n + 100]])
        return len(keys)
