"""Admin import / reconciliation / semantic DAG review (runtime_extension/15).

Offline: auth + validation contract and error mapping. Live (MATHBANK_LIVE_STEP_RUNTIME_TEST=1): every data
function inside one transaction that always rolls back.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

import mathbank_rest.config as config_module
from mathbank_rest.db import import_admin as db
from mathbank_rest.main import app
from mathbank_rest.routers import admin_imports

client = TestClient(app)
ADMIN = {"X-Admin-Api-Key": config_module.settings.admin_api_key}
PKG = "00000000-0000-0000-0000-000000000000"

READS = ["/v1/admin/imports/packages", f"/v1/admin/imports/packages/{PKG}",
         f"/v1/admin/imports/packages/{PKG}/issues", f"/v1/admin/imports/packages/{PKG}/conflicts",
         "/v1/admin/imports/reconciliation", "/v1/admin/imports/projection-requests",
         "/v1/admin/imports/problems/X/dag", "/v1/admin/imports/actions"]
WRITES = [("post", "/v1/admin/imports/conflicts/1/decision"), ("post", "/v1/admin/imports/projection-requests"),
          ("post", "/v1/admin/imports/learning-items/x/review"), ("patch", "/v1/admin/imports/steps/S1"),
          ("put", "/v1/admin/imports/dependencies"), ("post", "/v1/admin/imports/dependencies/reject"),
          ("post", "/v1/admin/imports/problems/X/dag/review")]


@pytest.mark.parametrize("path", READS)
def test_reads_require_admin_key(path: str) -> None:
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Admin-Api-Key": "wrong"}).status_code == 401


@pytest.mark.parametrize("method,path", WRITES)
def test_writes_require_admin_key(method: str, path: str) -> None:
    assert getattr(client, method)(path, json={}).status_code == 401


def test_validation_rejects_bad_input() -> None:
    assert client.get("/v1/admin/imports/packages/not-a-uuid", headers=ADMIN).status_code == 422
    assert client.get("/v1/admin/imports/reconciliation?book=x;drop", headers=ADMIN).status_code == 422
    assert client.post("/v1/admin/imports/conflicts/1/decision", headers=ADMIN,
                       json={"decision": "DELETE_EVERYTHING"}).status_code == 422
    assert client.put("/v1/admin/imports/dependencies", headers=ADMIN, json={
        "from_step_id": "a", "to_step_id": "b", "relationship_type": "CAUSES"}).status_code == 422
    assert client.post("/v1/admin/imports/projection-requests", headers=ADMIN, json={
        "target": "RUN_CYPHER", "scope_id": "x"}).status_code == 422


@pytest.mark.parametrize("exc,status", [(db.NotFound("x"), 404), (db.Invalid("x"), 422), (db.Conflict("x"), 409)])
def test_domain_errors_map_to_http(monkeypatch, exc, status) -> None:
    def boom(*_a, **_k):
        raise exc

    monkeypatch.setattr(db, "problem_dag", boom)
    assert client.get("/v1/admin/imports/problems/X/dag", headers=ADMIN).status_code == status


def test_router_registered_in_openapi() -> None:
    spec = app.openapi()["paths"]
    for route in admin_imports.router.routes:
        path = route.path.replace(":path}", "}")
        assert path in spec and set(m.lower() for m in route.methods) <= set(spec[path])


# ---------------------------------------------------------------- live (rolled back)

live = pytest.mark.skipif(os.getenv("MATHBANK_LIVE_STEP_RUNTIME_TEST") != "1", reason="Live Postgres opt-in")


@pytest.fixture
def live_conn():
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        tx = conn.begin()
        try:
            yield conn
        finally:
            tx.rollback()


def _outbox(conn, event_type: str, aggregate_id: str) -> int:
    return conn.execute(text("SELECT count(*) FROM pipeline.outbox_event WHERE event_type = :t AND aggregate_id = :a"),
                        {"t": event_type, "a": aggregate_id}).scalar_one()


def _audit(conn, target_type: str, target_id: str) -> list[str]:
    return list(conn.execute(text(
        "SELECT action FROM ingest.admin_review_action WHERE target_type = :t AND target_id = :i ORDER BY created_at, action_id"),
        {"t": target_type, "i": target_id}).scalars())


@live
def test_live_packages_reconciliation_and_queue(live_conn):
    conn = live_conn
    packages = db.list_packages(conn, "PRASOLOV_PGV1")
    assert len(packages) >= 2 and all(p["status"] for p in packages)
    detail = db.package_detail(conn, packages[0]["content_package_id"])
    assert detail["reconciliation"] and detail["staging"] and detail["status_history"]
    issues = db.validation_issues(conn, packages[0]["content_package_id"], kind="ALL", limit=5)
    assert issues["total"] >= len(issues["items"])
    conflicts = db.list_conflicts(conn, packages[0]["content_package_id"], limit=5)
    assert conflicts["total"] >= len(conflicts["items"])
    if conflicts["items"]:
        cid = conflicts["items"][0]["conflict_id"]
        out = db.decide_conflict(conn, cid, "KEEP_EXISTING", "test")
        assert out["decision"] == "KEEP_EXISTING"
        assert _audit(conn, "IMPORT_CONFLICT", str(cid))[-1] == "KEEP_EXISTING"
        with pytest.raises(db.Invalid):
            db.decide_conflict(conn, cid, "BOGUS", None)

    rec = db.reconciliation(conn, "PRASOLOV_PGV1", include_graph=False)
    assert rec["embeddings"] and rec["metadata_profile_version"] and rec["active_embedding"]["model_name"]
    first = db.request_projection(conn, "GRAPH_TEXTBOOK_STEPS", "BOOK", "PRASOLOV_PGV1", "test")
    again = db.request_projection(conn, "GRAPH_TEXTBOOK_STEPS", "BOOK", "PRASOLOV_PGV1", "test")
    assert first["projection_request_id"] == again["projection_request_id"]  # coalesced
    assert any(r["projection_request_id"] == first["projection_request_id"]
               for r in db.list_projection_requests(conn, "PENDING"))


@live
def test_live_dag_edit_dependency_cycle_and_review(live_conn):
    conn = live_conn
    code = conn.execute(text("""
        SELECT p.canonical_code FROM pedagogy.solution_step s JOIN core.problem p USING (problem_id)
         WHERE s.publication_status = 'PUBLISHED' GROUP BY p.canonical_code HAVING count(*) >= 3
         ORDER BY p.canonical_code LIMIT 1""")).scalar_one()
    dag = db.problem_dag(conn, code)
    steps = [s["solution_step_id"] for s in dag["steps"]]
    assert len(steps) >= 3

    edited = db.edit_step(conn, steps[0], is_checkpoint=True, note="test")
    assert edited["is_checkpoint"] is True
    assert _outbox(conn, "SOLUTION_STEP_CHANGED", steps[0]) >= 1
    assert _audit(conn, "SOLUTION_STEP", f"{code}|{steps[0]}") == ["EDIT"]

    db.upsert_dependency(conn, steps[0], steps[2], "DEPENDS_ON", note="test")  # 2 depends on 0
    with pytest.raises(db.Conflict):
        db.upsert_dependency(conn, steps[2], steps[0], "DEPENDS_ON")  # would close a cycle
    changed = db.upsert_dependency(conn, steps[0], steps[2], "ALTERNATIVE_TO", previous_type="DEPENDS_ON")
    assert changed["relationship_type"] == "ALTERNATIVE_TO" and changed["approval_method"] == "human"
    rejected = db.reject_dependency(conn, steps[0], steps[2], "ALTERNATIVE_TO", "test")
    assert rejected["review_status"] == "REJECTED"
    with pytest.raises(db.NotFound):
        db.reject_dependency(conn, steps[2], steps[0], "JUSTIFIES", None)

    review = db.review_dag(conn, code, "APPROVED", "looks right")
    assert review["review"]["status"] == "APPROVED"
    after = db.problem_dag(conn, code)
    assert after["review"]["status"] == "APPROVED"
    assert {a["action"] for a in after["actions"]} >= {"EDIT", "CREATE", "CHANGE_TYPE", "REJECT", "APPROVED"}
    assert any(s["admin_edited_at"] for s in after["steps"])
    assert db.list_actions(conn, "STEP_DEPENDENCY", 10)

    with pytest.raises(db.NotFound):
        db.problem_dag(conn, "NO_SUCH_PROBLEM")


@live
def test_live_learning_item_review_emits_outbox(live_conn):
    conn = live_conn
    item = conn.execute(text("SELECT learning_item_id::text FROM pedagogy.learning_item "
                             "WHERE review_status = 'APPROVED' ORDER BY learning_item_id LIMIT 1")).scalar_one()
    out = db.review_learning_item(conn, item, "REJECT", "test")
    assert out["review_status"] == "REJECTED"
    assert _outbox(conn, "LEARNING_ITEM_WITHDRAWN", item) == 1
    db.review_learning_item(conn, item, "APPROVE", "test")
    assert _outbox(conn, "LEARNING_ITEM_PUBLISHED", item) >= 1
    assert _audit(conn, "LEARNING_ITEM", item)[-2:] == ["REJECT", "APPROVE"]
