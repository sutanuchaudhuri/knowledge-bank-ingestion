"""Explicit selected-target integration; every fixture rolls back all its synthetic writes."""
import os
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from mathbank_rest import socratic_service as service
from mathbank_rest.db.postgres import engine
from mathbank_rest.socratic_auth import StaffActor
from mathbank_rest.socratic_contracts import CreateWorkflow, Source, UpdateWorkflow

pytestmark = pytest.mark.skipif(os.getenv("SOCRATIC_DB_TESTS") != "1",
                                reason="Set SOCRATIC_DB_TESTS=1 for the explicitly authorized REST-configured target")


@pytest.fixture
def db(monkeypatch):
    with engine.connect() as conn:
        transaction = conn.begin()

        class BoundEngine:
            @contextmanager
            def connect(self):
                yield conn

            @contextmanager
            def begin(self):
                with conn.begin_nested():
                    yield conn

        monkeypatch.setattr(service, "engine", BoundEngine())
        yield conn
        transaction.rollback()


@pytest.fixture
def actor():
    return StaffActor(actor_id="synthetic:socratic-test:" + str(uuid4()),
                      username="Synthetic schema acceptance", capabilities=["author"])


def create(actor, key="create-one"):
    return service.create_workflow(CreateWorkflow(title="Synthetic Socratic acceptance", domain="Algebra"), actor, key)


def test_create_replay_owner_scope_and_audit_outbox_atomicity(db, actor):
    workflow = create(actor)
    assert create(actor) == workflow
    assert service.get_workflow(workflow.workflow_id, actor) == workflow
    assert service.list_workflows(actor, 25, 0)["workflows"][0].workflow_id == workflow.workflow_id
    other = actor.model_copy(update={"actor_id": "synthetic:other"})
    with pytest.raises(HTTPException) as denied:
        service.get_workflow(workflow.workflow_id, other)
    assert denied.value.status_code == 404
    assert not service.list_workflows(other, 25, 0)["workflows"]
    for table, where in (
        ("audit.action_log", "entity_id=:id AND action='SOCRATIC_DRAFT_SAVED'"),
        ("pipeline.outbox_event", "aggregate_id=:id AND event_type='SOCRATIC_DRAFT_SAVED'"),
    ):
        assert db.execute(text(f"SELECT count(*) FROM {table} WHERE {where}"),
                          {"id": str(workflow.workflow_id)}).scalar_one() == 1
    with pytest.raises(HTTPException) as conflict:
        service.create_workflow(CreateWorkflow(title="Changed request", domain="Algebra"), actor, "create-one")
    assert conflict.value.status_code == 409


def test_hash_cas_replay_and_immutable_revision(db, actor):
    workflow = create(actor)
    program = workflow.program.model_copy(deep=True)
    program.nodes[0].prompt = "Explain why this representation is useful."
    body = UpdateWorkflow(expected_hash=workflow.content_hash, program=program)
    updated = service.update_workflow(workflow.workflow_id, body, actor, "update-one")
    assert updated.revision == 2 and updated.content_hash != workflow.content_hash
    assert service.update_workflow(workflow.workflow_id, body, actor, "update-one") == updated
    assert service.get_workflow(workflow.workflow_id, actor, 1) == workflow
    with pytest.raises(HTTPException) as stale:
        service.update_workflow(workflow.workflow_id, body, actor, "update-two")
    assert stale.value.status_code == 409
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE orchestration.socratic_revision SET author_id='changed' WHERE workflow_id=:id"),
                   {"id": workflow.workflow_id})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("""
            INSERT INTO orchestration.socratic_revision
                (workflow_id,revision,content_hash,author_id,strategy_code,program,dependencies)
            SELECT workflow_id,99,content_hash,author_id,strategy_code,CAST(:invalid AS jsonb),dependencies
            FROM orchestration.socratic_revision WHERE workflow_id=:id AND revision=1
        """), {"id": workflow.workflow_id, "invalid": "{}"})


def test_source_revision_pinning_and_no_private_solution_body_in_catalog(db, actor):
    row = db.execute(text("""
        SELECT p.canonical_code,s.solution_id,s.revision
        FROM core.problem p JOIN core.solution s USING(problem_id)
        ORDER BY p.canonical_code,s.solution_id LIMIT 1
    """)).mappings().one()
    workflow = create(actor)
    program = workflow.program.model_copy(deep=True)
    program.source = Source(problem_code=row["canonical_code"], solution_id=row["solution_id"],
                            solution_revision=row["revision"])
    updated = service.update_workflow(workflow.workflow_id, UpdateWorkflow(
        expected_hash=workflow.content_hash, program=program), actor, "bind-source")
    assert updated.program.source.solution_revision == row["revision"]
    assert service.validate_workflow(updated.workflow_id, updated.content_hash, actor).valid
    results = service.resources(row["canonical_code"], 25, 0)
    assert results["resources"]
    assert "body_markdown" not in str(results) and "correctness_policy" not in str(results)
    program.source.solution_revision += 1
    with pytest.raises(HTTPException) as stale:
        service.update_workflow(updated.workflow_id, UpdateWorkflow(
            expected_hash=updated.content_hash, program=program), actor, "stale-source")
    assert stale.value.status_code == 409
    assert service.get_workflow(updated.workflow_id, actor).revision == 2


def test_invalid_route_and_strategy_fail_without_revision_or_receipt(db, actor):
    workflow = create(actor)
    program = workflow.program.model_copy(deep=True)
    program.strategy_code = "NT_MODULAR"
    with pytest.raises(HTTPException) as error:
        service.update_workflow(workflow.workflow_id, UpdateWorkflow(
            expected_hash=workflow.content_hash, program=program), actor, "bad-strategy")
    assert error.value.status_code == 422
    assert db.execute(text("""
        SELECT count(*) FROM orchestration.socratic_revision WHERE workflow_id=:id
    """), {"id": workflow.workflow_id}).scalar_one() == 1
    assert db.execute(text("""
        SELECT count(*) FROM orchestration.socratic_command WHERE owner_id=:owner
    """), {"owner": actor.actor_id}).scalar_one() == 1
    findings = service.validate_workflow(workflow.workflow_id, workflow.content_hash, actor)
    assert not findings.valid and "explicit canonical solution" in findings.findings[0]


def test_registry_domains_and_pagination(db, actor):
    registry = service.strategies()
    assert len(registry) >= 20 and len({item.domain for item in registry}) == 8
    create(actor, "create-first")
    create(actor, "create-second")
    page = service.list_workflows(actor, 1, 0)
    assert len(page["workflows"]) == 1 and page["has_more"]
    assert service.list_workflows(actor, 1, 1)["workflows"][0] != page["workflows"][0]


def test_outbox_failure_rolls_back_draft_revision_command_and_audit(db, actor, monkeypatch):
    execute = db.execute

    def fail_outbox(statement, *args, **kwargs):
        if "INSERT INTO pipeline.outbox_event" in str(statement):
            raise SQLAlchemyError("synthetic private failure")
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", fail_outbox)
    with pytest.raises(HTTPException) as unavailable:
        create(actor)
    assert unavailable.value.status_code == 503
    assert "synthetic private" not in str(unavailable.value.detail)
    for table, field in (
        ("orchestration.socratic_workflow", "owner_id"),
        ("orchestration.socratic_revision", "author_id"),
        ("orchestration.socratic_command", "owner_id"),
        ("audit.action_log", "actor_id"),
    ):
        assert db.execute(text(f"SELECT count(*) FROM {table} WHERE {field}=:owner"),
                          {"owner": actor.actor_id}).scalar_one() == 0


def test_http_local_staff_to_real_persistence(db, monkeypatch):
    import bcrypt
    from fastapi.testclient import TestClient
    from pydantic import SecretStr
    from test_socratic_local_auth import ORIGIN, PASSWORD, PASSWORD_HASH

    from mathbank_rest import socratic_app, socratic_auth, socratic_local_auth
    from mathbank_rest.config import settings

    assert bcrypt.checkpw(PASSWORD.encode(), PASSWORD_HASH.encode())
    for key, value in {
        "socratic_auth_mode": "local", "socratic_local_username": "synthetic-" + str(uuid4()),
        "socratic_local_password_hash": SecretStr(PASSWORD_HASH),
        "socratic_local_capabilities": ["author"],
        "socratic_csrf_secret": SecretStr("synthetic-csrf-secret-at-least-32-characters"),
        "socratic_allowed_origins": [ORIGIN], "socratic_cookie_secure": False,
    }.items():
        monkeypatch.setattr(settings, key, value)
    monkeypatch.setattr(socratic_local_auth, "store", socratic_local_auth.LocalSessionStore())
    monkeypatch.setattr(socratic_auth, "client", lambda: pytest.fail("Local persistence must not call AWS"))
    monkeypatch.setattr(socratic_app, "engine", service.engine)
    base = "/v1/admin/socratic"
    with TestClient(socratic_app.app, base_url=ORIGIN, client=("127.0.0.1", 43210)) as client:
        assert client.get("/health").json()["model_jobs_available"] is False
        assert "font-src 'self' data:" in client.get("/health").headers["Content-Security-Policy"]
        assert client.get("/docs").status_code == 404
        assert client.get(base + "/workflows").status_code == 401
        login = client.post(base + "/session", headers={"Origin": ORIGIN},
                            json={"username": settings.socratic_local_username, "password": PASSWORD})
        assert login.status_code == 200
        assert client.get(base + "/resources?limit=1").status_code == 200
        headers = {"Origin": ORIGIN, "X-CSRF-Token": login.json()["csrf_token"],
                   "Idempotency-Key": "synthetic-http-create"}
        created = client.post(base + "/workflows", headers=headers,
                              json={"title": "Synthetic HTTP acceptance", "domain": "Algebra"})
        assert created.status_code == 201
        path = base + "/workflows/" + created.json()["workflow_id"]
        restored = client.get(path)
        assert restored.json() == created.json()
        assert restored.headers["Cache-Control"] == "no-store"
        program = restored.json()["program"]
        program["nodes"][0]["prompt"] = "Explain the representation."
        body = {"expected_hash": created.json()["content_hash"], "program": program}
        assert client.put(path, json=body).status_code == 403
        headers["Idempotency-Key"] = "synthetic-http-update"
        assert client.put(path, headers=headers, json=body).json()["revision"] == 2
        assert client.put(path, headers=headers, json=body).json()["revision"] == 2
        headers["Idempotency-Key"] = "synthetic-http-stale"
        assert client.put(path, headers=headers, json=body).status_code == 409
        assert client.delete(base + "/session", headers=headers).status_code == 204
        assert client.get(path).status_code == 401


@pytest.mark.skipif(os.getenv("SOCRATIC_CONCURRENCY_TESTS") != "1",
                    reason="Explicit opt-in: retains one labeled synthetic draft and immutable evidence")
def test_concurrent_create_replay_and_single_cas_winner(actor):
    """Two real connections; intentionally retain one isolated synthetic acceptance fixture."""
    barrier = Barrier(2)

    def duplicate():
        barrier.wait(timeout=15)
        return create(actor, "concurrent-create")

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(duplicate) for _ in range(2)]
        first, replay = [future.result(timeout=45) for future in futures]
    assert first == replay
    barrier.reset()

    def writer(index):
        program = first.program.model_copy(deep=True)
        program.nodes[0].prompt = f"Synthetic concurrent writer {index}"
        barrier.wait(timeout=15)
        try:
            return service.update_workflow(first.workflow_id, UpdateWorkflow(
                expected_hash=first.content_hash, program=program), actor, f"concurrent-update-{index}")
        except HTTPException as error:
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer, index) for index in range(2)]
        results = [future.result(timeout=45) for future in futures]
    winners = [result for result in results if not isinstance(result, HTTPException)]
    conflicts = [result for result in results if isinstance(result, HTTPException)]
    assert len(winners) == len(conflicts) == 1
    assert conflicts[0].status_code == 409
    assert winners[0].revision == 2
    with engine.connect() as conn:
        for table, field in (
            ("orchestration.socratic_revision", "workflow_id"),
            ("orchestration.socratic_command", "workflow_id"),
            ("audit.action_log", "entity_id"),
            ("pipeline.outbox_event", "aggregate_id"),
        ):
            assert conn.execute(text(f"SELECT count(*) FROM {table} WHERE {field}=:id"),
                                {"id": str(first.workflow_id)}).scalar_one() == 2
