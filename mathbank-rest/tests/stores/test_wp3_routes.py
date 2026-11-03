"""WP3 routes on moto + TestClient: owner scoping over HTTP, admin credential and actor, frozen cutover, no Postgres on the
DynamoDB path (Neon may suspend while idle), and dual-backend parity of the student list/read routes with the Postgres side
answered from canned rows."""
from __future__ import annotations

import datetime as dt
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from wp3_support import seed_learner, wp3_fixture  # noqa: F401  (fixture 'wp3')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))
from parity_harness import ParityCase, assert_parity

from mathbank_rest import security
from mathbank_rest.config import settings
from mathbank_rest.main import app
from mathbank_rest.notifications import NotificationCreate
from mathbank_rest.security import Actor
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores.notify import DynamoDBNotifyStore

KEY = {"X-Admin-Api-Key": settings.admin_api_key}
STAFF = Actor("staff", "staff:42", "Alice", frozenset({"publish"}))


@pytest.fixture(autouse=True)
def _flags(monkeypatch):
    monkeypatch.setattr(settings, "notify_store", "dynamodb")
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
def client(wp3):
    return TestClient(app)


def as_student(sid: str) -> None:
    app.dependency_overrides[security.get_current_student_id] = lambda: uuid.UUID(sid)


def note(sid: str, title: str = "graded", **kw) -> NotificationCreate:
    return NotificationCreate(recipient_type="STUDENT", recipient_id=sid, notification_type="QUIZ_GRADED", severity="SUCCESS",
                              title=title, payload_json={"quiz_id": "q1"}, **kw)


def admin_note() -> NotificationCreate:
    return NotificationCreate(recipient_type="ADMIN", recipient_id="admin-1", notification_type="ADMIN_REVIEW_NEEDED",
                              severity="ACTION_NEEDED", title="review", payload_json={"release_id": "r1"})


# ------------------------------------------------------------------ student routes

def test_list_and_mark_read_for_the_authenticated_student(client):
    sid = seed_learner()
    store = DynamoDBNotifyStore()
    a, b = store.record_notification(note(sid, "a")), store.record_notification(note(sid, "b"))
    as_student(sid)
    body = client.get("/v1/notifications/me").json()
    assert [n["notification_id"] for n in body["notifications"]] == [b, a] and body["unread_count"] == 2
    assert client.post(f"/v1/notifications/{a}/read").json() == {"notification_id": a, "read": True}
    assert client.post(f"/v1/notifications/{a}/read").status_code == 200  # idempotent
    body = client.get("/v1/notifications/me", params={"unread": True}).json()
    assert [n["notification_id"] for n in body["notifications"]] == [b] and body["unread_count"] == 1
    assert client.post("/v1/notifications/me/read-all").json() == {"updated": 1}
    assert client.get("/v1/notifications/me").json()["unread_count"] == 0


def test_another_students_notification_id_is_404_not_403(client):
    mine, theirs = seed_learner(), seed_learner()
    nid = DynamoDBNotifyStore().record_notification(note(theirs))
    as_student(mine)
    r = client.post(f"/v1/notifications/{nid}/read")
    assert r.status_code == 404 and r.json() == {"detail": "not_found"}
    assert client.post(f"/v1/notifications/{uuid.uuid4()}/read").json() == r.json()  # indistinguishable from "unknown"
    assert client.get("/v1/notifications/me").json()["notifications"] == []
    as_student(theirs)
    assert client.get("/v1/notifications/me").json()["unread_count"] == 1  # untouched


def test_student_routes_need_a_valid_bearer_token(client):
    assert client.get("/v1/notifications/me").status_code == 401
    assert client.post(f"/v1/notifications/{uuid.uuid4()}/read", headers={"Authorization": "Bearer nope"}).status_code == 401


def test_tampered_next_token_is_400_and_offset_is_422(client):
    sid = seed_learner()
    store = DynamoDBNotifyStore()
    for i in range(3):
        store.record_notification(note(sid, str(i)))
    as_student(sid)
    first = client.get("/v1/notifications/me", params={"limit": 2}).json()
    assert len(first["notifications"]) == 2 and first["next_token"]
    rest = client.get("/v1/notifications/me", params={"limit": 2, "next_token": first["next_token"]}).json()
    assert len(rest["notifications"]) == 1 and rest["next_token"] is None
    bad = client.get("/v1/notifications/me", params={"limit": 2, "next_token": first["next_token"][:-2] + "xx"})
    assert bad.status_code == 400 and bad.json() == {"detail": "invalid_next_token"}
    assert client.get("/v1/notifications/me", params={"offset": 1}).status_code == 422
    assert client.get("/v1/notifications/me", params={"limit": 500}).status_code == 422


def test_no_postgres_is_touched_on_the_dynamodb_path(client, monkeypatch):
    class Boom:
        def __getattr__(self, name):
            raise AssertionError(f"PostgreSQL used: engine.{name}")

    monkeypatch.setattr("mathbank_rest.db.postgres.engine", Boom())
    sid = seed_learner()
    nid = DynamoDBNotifyStore().record_notification(note(sid))
    as_student(sid)
    assert client.get("/v1/notifications/me").status_code == 200
    assert client.post(f"/v1/notifications/{nid}/read").status_code == 200
    assert client.post("/v1/notifications/me/read-all").status_code == 200


def test_frozen_notify_store_serves_reads_and_503s_writes(client, monkeypatch):
    sid = seed_learner()
    nid = DynamoDBNotifyStore().record_notification(note(sid))
    monkeypatch.setattr(settings, "notify_store", "frozen:dynamodb")
    as_student(sid)
    assert client.get("/v1/notifications/me").json()["unread_count"] == 1
    r = client.post(f"/v1/notifications/{nid}/read")
    assert r.status_code == 503 and r.headers["Retry-After"] == "30"
    assert client.get("/v1/notifications/me").json()["unread_count"] == 1


# ------------------------------------------------------------------ admin routes

def test_admin_routes_need_the_admin_credential(client):
    nid = DynamoDBNotifyStore().record_notification(admin_note())
    for method, path in (("GET", "/v1/admin/notifications"), ("POST", f"/v1/admin/notifications/{nid}/ack")):
        assert client.request(method, path).status_code == 401
        assert client.request(method, path, headers={"X-Admin-Api-Key": "wrong"}).status_code == 401
    sid = seed_learner()
    as_student(sid)  # a learner token is not an admin credential
    assert client.get("/v1/admin/notifications", headers={"Authorization": "Bearer x"}).status_code == 401


def test_admin_lists_and_acks_with_the_service_actor(client):
    store = DynamoDBNotifyStore()
    a, b = store.record_notification(admin_note()), store.record_notification(admin_note())
    body = client.get("/v1/admin/notifications", headers=KEY).json()
    assert [n["notification_id"] for n in body["notifications"]] == [b, a] and body["unread_count"] == 2
    r = client.post(f"/v1/admin/notifications/{a}/ack", headers=KEY)
    assert r.status_code == 200 and r.json() == {"notification_id": a, "acknowledged": True,
                                                   "acknowledged_by": "service:admin-key", "newly_acknowledged": True}
    listing = client.get("/v1/admin/notifications", headers=KEY, params={"unread": True}).json()
    assert [n["notification_id"] for n in listing["notifications"]] == [b] and listing["unread_count"] == 1
    assert client.post(f"/v1/admin/notifications/{uuid.uuid4()}/ack", headers=KEY).status_code == 404


def test_admin_ack_records_the_staff_actor_never_a_client_supplied_name(client):
    nid = DynamoDBNotifyStore().record_notification(admin_note())
    app.dependency_overrides[security.require_admin_api_key] = lambda: STAFF
    r = client.post(f"/v1/admin/notifications/{nid}/ack", params={"actor": "mallory"}, headers={"X-Actor-Id": "mallory"})
    assert r.json()["acknowledged_by"] == "staff:42"
    item = next(n for n in client.get("/v1/admin/notifications").json()["notifications"] if n["notification_id"] == nid)
    assert item["acknowledged_by"] == "staff:42" and item["read_at"]


def test_admin_filter_by_type_and_student_inbox_isolation(client):
    store = DynamoDBNotifyStore()
    sid = seed_learner()
    store.record_notification(note(sid))
    keep = store.record_notification(admin_note())
    body = client.get("/v1/admin/notifications", headers=KEY, params={"notification_type": "ADMIN_REVIEW_NEEDED"}).json()
    assert [n["notification_id"] for n in body["notifications"]] == [keep]
    assert client.get("/v1/admin/notifications", headers=KEY, params={"notification_type": "QUIZ_GRADED"}).json()["notifications"] == []


# ------------------------------------------------------------------ parity (student list / read)

STUDENT = "5c1a0e4e-62a8-4d0c-9b83-8f4f0a1e7d11"
ID1, ID2 = "01990000-0000-7000-8000-000000000001", "01990000-0000-7000-8000-000000000002"


class PgRows:
    """Canned ``notification.event`` rows answering the SQL of ``notifications.list_notifications`` / ``mark_read``."""

    def __init__(self):
        t = dt.datetime(2026, 11, 3, 12, 0, tzinfo=dt.UTC)
        self.rows = [
            {"notification_id": uuid.UUID(i), "recipient_type": "STUDENT", "recipient_id": STUDENT,
             "notification_type": "QUIZ_GRADED", "severity": "SUCCESS", "title": title, "body": None,
             "payload_json": {"quiz_id": "q1"}, "read_at": None, "created_at": t + dt.timedelta(minutes=n)}
            for n, (i, title) in enumerate(((ID2, "second"), (ID1, "first")))]

    def execute(self, stmt, params=None):
        sql, params = str(stmt), params or {}
        mine = [r for r in self.rows if r["recipient_id"] == params.get("rid") and r["recipient_type"] == params.get("rt")]
        if "count(*)" in sql:
            return SimpleNamespace(scalar_one=lambda: sum(r["read_at"] is None for r in mine))
        if sql.lstrip().startswith("SELECT"):
            window = mine[params["offset"]:params["offset"] + params["limit"]]
            return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: window))
        hit = next((r for r in mine if str(r["notification_id"]) == params["id"]), None)
        if hit is None:
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: None))
        was_unread = hit["read_at"] is None
        hit["read_at"] = hit["read_at"] or dt.datetime(2026, 11, 3, 13, 0, tzinfo=dt.UTC)
        return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: {"was_unread": was_unread}))


class PgEngine:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def connect(self):
        yield self.conn

    begin = connect


class BackendClient:
    """A TestClient whose requests run with the notify flag set to one backend (the harness compares two of these)."""

    def __init__(self, backend: str):
        self.backend, self.http = backend, TestClient(app)

    def request(self, *args, **kwargs):
        previous, settings.notify_store = settings.notify_store, self.backend
        try:
            return self.http.request(*args, **kwargs)
        finally:
            settings.notify_store = previous


@pytest.fixture()
def backends(wp3, monkeypatch):
    from mathbank_rest.stores.notify import postgres as pg

    monkeypatch.setattr(pg, "engine", PgEngine(PgRows()))
    seed_learner(STUDENT)
    ids = iter([ID1, ID2])
    monkeypatch.setattr(toolkit, "uuid7", lambda: next(ids))
    store = DynamoDBNotifyStore()
    for title in ("first", "second"):
        store.record_notification(NotificationCreate(
            recipient_type="STUDENT", recipient_id=STUDENT, notification_type="QUIZ_GRADED", severity="SUCCESS", title=title,
            payload_json={"quiz_id": "q1"}))
    as_student(STUDENT)
    return {"postgres": BackendClient("postgres"), "dynamodb": BackendClient("dynamodb")}


TIMES = ["$.notifications[*].read_at"]  # PostgreSQL timestamps are isoformat(), DynamoDB's end in Z: same instant, own format


def test_parity_list_pages_and_unread_count(backends):
    assert_parity(backends, ParityCase("list", "GET", "/v1/notifications/me", expect_status=200), allowed=TIMES)
    assert_parity(backends, ParityCase("list page 1", "GET", "/v1/notifications/me", params={"limit": 1}, expect_status=200),
                  allowed=TIMES)


def test_parity_mark_read_then_list(backends):
    assert_parity(backends, ParityCase("read own", "POST", f"/v1/notifications/{ID1}/read", expect_status=200))
    assert_parity(backends, ParityCase("read again", "POST", f"/v1/notifications/{ID1}/read", expect_status=200))
    for backend, client in backends.items():
        body = client.request("GET", "/v1/notifications/me").json()
        assert body["unread_count"] == 1, backend
        assert [n["read_at"] is not None for n in body["notifications"]] == [False, True], backend
    assert_parity(backends, ParityCase("list after", "GET", "/v1/notifications/me", expect_status=200), allowed=TIMES)


def test_parity_not_found_is_a_404_on_both(backends):
    assert_parity(backends, ParityCase("unknown id", "POST", f"/v1/notifications/{uuid.uuid4()}/read", expect_status=404))
