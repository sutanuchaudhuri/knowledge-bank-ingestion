"""Admin authentication, bounded mutation contracts, and bulk review ordering."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mathbank_rest.config import settings
from mathbank_rest.db import pedagogy_admin as db
from mathbank_rest.main import app

client = TestClient(app)
HEADERS = {"X-Admin-Api-Key": settings.admin_api_key}
KEY = {"skill_id": str(uuid4())}
REVISION = "a" * 64
BODY = {
    "kind": "skill",
    "key": KEY,
    "expected_revision": REVISION,
    "review_status": "REVIEWED",
    "note": "Approved by operator.",
}


def test_queue_remains_available_without_complete_starter_metadata(monkeypatch):
    connection = MagicMock()
    result = connection.execute.return_value
    result.mappings.return_value.all.return_value = [
        {"metadata": {**KEY, "review_status": "PENDING"}, "title": "Independent skill"}
    ]
    result.mappings.return_value.first.return_value = None
    result.scalar_one.return_value = 1
    result.all.return_value = [("PENDING", 1)]
    result.scalars.return_value = []
    fixture_engine = MagicMock()
    fixture_engine.connect.return_value.__enter__.return_value = connection
    monkeypatch.setattr(db, "engine", fixture_engine)

    def missing_starter(conn):
        raise db.MissingMetadata("Starter metadata is incomplete; import it before bulk review.")

    monkeypatch.setattr(db, "starter_items", missing_starter)
    response = db.queue("skill", "ALL", 25, 0)
    assert len(response["items"]) == 1
    assert response["starter_pending"] == 0
    assert "incomplete" in response["starter_warning"]


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("get", "/queue", None),
        ("post", "/review", BODY),
        ("post", "/history", {"kind": "skill", "key": KEY}),
        ("post", "/publish", {"expected_fingerprint": REVISION}),
        ("post", "/bulk-review", {"items": [], "review_status": "REVIEWED", "note": "A rationale"}),
        ("post", "/approve-starter", {"expected_fingerprint": REVISION, "note": "A rationale"}),
    ],
)
def test_every_admin_pedagogy_endpoint_requires_auth(method, path, body):
    kwargs = {"json": body} if body is not None else {}
    response = getattr(client, method)(f"/v1/admin/pedagogy{path}", **kwargs)
    assert response.status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "core.problem"),
        ("note", " " * 20),
        ("note", "short"),
        ("expected_revision", "stale"),
        ("review_status", "APPROVED"),
        ("reviewer", "spoofed-user"),
    ],
)
def test_invalid_review_does_not_reach_storage(monkeypatch, field, value):
    operation = MagicMock()
    monkeypatch.setattr(db, "decide", operation)
    response = client.post(
        "/v1/admin/pedagogy/review", json={**BODY, field: value}, headers=HEADERS
    )
    assert response.status_code == 422
    operation.assert_not_called()


def test_review_forwards_snapshot_and_note_to_postgres(monkeypatch):
    operation = MagicMock(return_value={"review_status": "REVIEWED"})
    monkeypatch.setattr(db, "decide", operation)
    response = client.post("/v1/admin/pedagogy/review", json=BODY, headers=HEADERS)
    assert response.status_code == 200
    operation.assert_called_once_with("skill", KEY, REVISION, "REVIEWED", BODY["note"])


@pytest.mark.parametrize(
    "error,status",
    [
        (db.ReviewConflict("Reload changed assertion"), 409),
        (db.MissingMetadata("No assertion"), 404),
        (ValueError("Invalid key"), 422),
        (RuntimeError("Projection failed"), 503),
    ],
)
def test_failures_are_explicit(monkeypatch, error, status):
    def fail(*args):
        raise error

    monkeypatch.setattr(db, "decide", fail)
    response = client.post("/v1/admin/pedagogy/review", json=BODY, headers=HEADERS)
    assert response.status_code == status


@pytest.mark.parametrize(
    "url",
    [
        "/queue?limit=0",
        "/queue?limit=101",
        "/queue?offset=-1",
        "/queue?kind=problem",
        "/queue?status=APPROVED",
    ],
)
def test_queue_bounds(url):
    assert client.get("/v1/admin/pedagogy" + url, headers=HEADERS).status_code == 422


def test_bulk_size_and_empty_bounds(monkeypatch):
    operation = MagicMock()
    monkeypatch.setattr(db, "bulk_decide", operation)
    item = {"kind": "skill", "key": KEY, "expected_revision": REVISION}
    for items in ([], [item] * 101):
        response = client.post(
            "/v1/admin/pedagogy/bulk-review",
            headers=HEADERS,
            json={
                "items": items,
                "review_status": "REVIEWED",
                "note": BODY["note"],
            },
        )
        assert response.status_code == 422
    operation.assert_not_called()


def test_bulk_skills_precede_dependent_mappings(monkeypatch):
    skill_item = {"kind": "skill", "key": KEY, "expected_revision": REVISION}
    mapping = {
        "kind": "skill_concept",
        "key": {**KEY, "concept_id": str(uuid4())},
        "expected_revision": REVISION,
    }
    changes = MagicMock()
    validation = MagicMock()
    monkeypatch.setattr(db, "change_decision", changes)
    monkeypatch.setattr(db, "validate_graph", validation)
    conn = MagicMock()
    result = db.apply_bulk(conn, [mapping, skill_item], "REVIEWED", BODY["note"])
    assert result["updated"] == 2
    assert changes.call_args_list[0].args[1] == "skill"
    assert changes.call_args_list[1].args[1] == "skill_concept"
    validation.assert_called_once_with(conn)


def test_bulk_duplicate_keys_rejected_before_writes(monkeypatch):
    changes = MagicMock()
    monkeypatch.setattr(db, "change_decision", changes)
    item = {"kind": "skill", "key": KEY, "expected_revision": REVISION}
    with pytest.raises(ValueError, match="Duplicate"):
        db.apply_bulk(MagicMock(), [item, item], "REVIEWED", BODY["note"])
    changes.assert_not_called()


def test_natural_keys_are_whitelisted_and_uuid_validated():
    assert db.validate_key("skill", KEY) == KEY
    for kind, key in [
        ("skill", {"skill_id": "invalid"}),
        ("skill", {**KEY, "source": "extra"}),
        ("core.problem", KEY),
        (
            "skill_relation",
            {
                "from_skill_id": KEY["skill_id"],
                "to_skill_id": str(uuid4()),
                "relation_type": "MALICIOUS",
            },
        ),
    ]:
        with pytest.raises(ValueError):
            db.validate_key(kind, key)


def test_revision_detects_changes_but_ignores_dictionary_order():
    assert db.revision({"a": 1, "b": 2}) == db.revision({"b": 2, "a": 1})
    assert db.revision({"status": "PENDING"}) != db.revision({"status": "REVIEWED"})
