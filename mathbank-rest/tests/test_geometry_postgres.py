"""Opt-in real PostgreSQL tests; explicit DSN only, isolated disposable schema.

GEOMETRY_TEST_POSTGRES_DSN must identify a test database where schema creation is
authorized. Never reads the application's DSN. Object bytes stay in memory unless
the explicit filesystem integration test selects a project-local private directory.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from importlib.resources import files
from uuid import uuid4

import pytest
from geometry_scene.errors import InvalidFrame, VersionConflict
from geometry_scene.repository import ReplayConflict, SceneNotFound
from geometry_scene.schemas import SceneInput, StateDelta
from geometry_scene.service import apply_delta, create_scene
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import DBAPIError
from test_geometry_storage import PAYLOAD, MemoryObjects

from mathbank_rest.geometry_storage import GeometryStorageError, PostgresGeometryRepository

DSN = os.environ.get("GEOMETRY_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="explicit GEOMETRY_TEST_POSTGRES_DSN required")


@pytest.fixture
def repository():
    db = create_engine(DSN, pool_pre_ping=True)
    schema = "geometry_test_" + uuid4().hex

    @event.listens_for(db, "before_cursor_execute", retval=True)
    def isolated(_conn, _cursor, statement, parameters, _context, _many):
        statement = statement.replace("geometry_scene.", schema + ".")
        statement = statement.replace("SCHEMA IF NOT EXISTS geometry_scene;",
                                      f"SCHEMA IF NOT EXISTS {schema};")
        return statement, parameters

    try:
        migration = files("mathbank_rest").joinpath("migrations/026_geometry_scenes.sql").read_text()
        with db.begin() as conn:
            conn.exec_driver_sql(migration)
        yield PostgresGeometryRepository(db, MemoryObjects())
    finally:
        with db.begin() as conn:
            conn.exec_driver_sql(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        db.dispose()


def initial(repo, key="create"):
    return repo.create(SceneInput.model_validate(PAYLOAD), "student:a", key)[0]


def test_roundtrip_restart_ownership_receipts_and_lineage(repository):
    repo = repository
    base = initial(repo)
    replay, repeated = repo.create(SceneInput.model_validate(PAYLOAD), "student:a", "create")
    assert repeated and replay == base
    changed = SceneInput.model_validate({**PAYLOAD, "seed": 19})
    with pytest.raises(ReplayConflict):
        repo.create(changed, "student:a", "create")
    candidate = apply_delta(base, StateDelta(expected_version=0))
    assert repo.commit_candidate(candidate, "student:a", 0, "accept",
                                 {"solution_step": "step-1"}) == (candidate, False)
    assert repo.commit_candidate(candidate, "student:a", 0, "accept",
                                 {"solution_step": "step-1"}) == (candidate, True)
    reopened = PostgresGeometryRepository(repo.engine, repo.objects)
    assert reopened.current("geometry_test", "student:a") == candidate
    assert reopened.read("geometry_test", 0, "student:a") == base
    assert [f["version"] for f in reopened.frames("geometry_test", "student:a")] == [0, 1]
    with pytest.raises(SceneNotFound):
        reopened.read("geometry_test", 0, "student:b")
    with pytest.raises(SceneNotFound):
        reopened.apply("geometry_test", StateDelta(expected_version=1), "student:b")
    with pytest.raises(VersionConflict):
        reopened.apply("geometry_test", StateDelta(expected_version=0), "student:a")
    with repo.engine.connect() as conn:
        assert conn.execute(text(
            "SELECT lineage FROM geometry_scene.versions WHERE version=1"
        )).scalar_one() == {"solution_step": "step-1"}
    with pytest.raises(DBAPIError), repo.engine.begin() as conn:
        conn.execute(text("UPDATE geometry_scene.versions SET lineage='{}'"))
    with pytest.raises(DBAPIError), repo.engine.begin() as conn:
        conn.execute(text("UPDATE geometry_scene.receipts SET request_hash='tampered'"))


def test_concurrent_cas_has_exactly_one_winner(repository):
    repo = repository
    initial(repo)

    def update(key):
        try:
            return repo.apply("geometry_test", StateDelta(expected_version=0), "student:a", key)[0].version
        except VersionConflict:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(update, ["one", "two"]))
    assert sorted(results, key=str) == [1, "conflict"]
    assert len(repo.objects.data) == 4


def test_concurrent_same_receipt_replays_once(repository):
    repo = repository
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(
            lambda _: repo.create(SceneInput.model_validate(PAYLOAD), "student:a", "same"),
            range(2)))
    assert sorted(replayed for _, replayed in results) == [False, True]
    assert results[0][0] == results[1][0] and len(repo.objects.data) == 2


def test_interpretation_preflight_matches_candidate_request_receipt(repository):
    repo = repository
    body = {"goal": "show points", "initial": PAYLOAD, "seed": 17}
    assert repo.lookup_receipt("learner", "interpret-once", "interpret", body) is None
    frame = create_scene(SceneInput.model_validate(PAYLOAD))
    assert repo.commit_candidate(frame, "learner", None, "interpret-once",
                                 {"run_id": "run"}, request_body=body) == (frame, False)
    reordered = dict(reversed(list(body.items())))
    assert repo.lookup_receipt("learner", "interpret-once", "interpret", reordered) == frame
    assert repo.lookup_receipt("another", "interpret-once", "interpret", body) is None
    assert repo.commit_candidate(frame, "learner", None, "interpret-once",
                                 {"run_id": "different"}, request_body=body) == (frame, True)
    with pytest.raises(ReplayConflict):
        repo.lookup_receipt("learner", "interpret-once", "interpret", {**body, "seed": 19})
    with pytest.raises(ReplayConflict):
        repo.lookup_receipt("learner", "interpret-once", "create", body)


def test_upload_failure_rolls_back_all_database_state(repository, monkeypatch):
    repo = repository
    original = repo.objects.put_bytes

    def fail_second(data, suffix):
        if suffix == "svg":
            raise OSError("write failed")
        return original(data, suffix)

    monkeypatch.setattr(repo.objects, "put_bytes", fail_second)
    with pytest.raises(GeometryStorageError):
        initial(repo)
    assert repo.objects.data == {}
    with repo.engine.connect() as conn:
        for table in ("scenes", "versions", "receipts"):
            assert conn.execute(text(f"SELECT count(*) FROM geometry_scene.{table}")).scalar_one() == 0


def test_database_failure_after_upload_rolls_back_receipts_and_assets(repository, monkeypatch):
    repo = repository
    original = repo._publish

    def fail_after_publish(conn, *args):
        original(conn, *args)
        conn.execute(text("SELECT 1/0"))

    monkeypatch.setattr(repo, "_publish", fail_after_publish)
    with pytest.raises(GeometryStorageError):
        initial(repo)
    assert repo.objects.data == {}
    with repo.engine.connect() as conn:
        for table in ("scenes", "versions", "receipts"):
            assert conn.execute(text(f"SELECT count(*) FROM geometry_scene.{table}")).scalar_one() == 0


def test_protected_immutable_run_evidence(repository):
    repo = repository
    evidence = {"status": "FAILED", "diagnostics": ["private"], "candidate": None}
    assert repo.save_run("student:a", "run", evidence) == {"run_id": "run"}
    repo.save_run("student:a", "run", evidence)
    assert len(repo.objects.data) == 1
    assert repo.read_run("student:a", "run") == evidence
    with pytest.raises(SceneNotFound):
        repo.read_run("student:b", "run")
    with pytest.raises(ReplayConflict):
        repo.save_run("student:a", "run", {"different": True})
    repo.review_run("student:a", "run", {"decision": "REJECTED"})
    assert repo.read_run("student:a", "run") == evidence
    assert repo.list_runs("student:a")[0]["review"] == {"decision": "REJECTED"}
    assert repo.list_runs("student:b") == []
    with pytest.raises(DBAPIError), repo.engine.begin() as conn:
        conn.execute(text("UPDATE geometry_scene.runs SET evidence_hash='tampered'"))
    asset = next(iter(repo.objects.data))
    repo.objects.data[asset] = b'{"corrupt":true}'
    with pytest.raises(GeometryStorageError):
        repo.read_run("student:a", "run")


def test_invalid_candidate_never_advances_head(repository):
    repo = repository
    base = initial(repo)
    candidate = apply_delta(base, StateDelta(expected_version=0))
    # Syntactically valid SVG but missing all semantic objects cannot be accepted.
    candidate = candidate.model_copy(update={"svg": "<svg></svg>"})
    with pytest.raises(InvalidFrame):
        repo.commit_candidate(candidate, "student:a", 0, "invalid")
    assert repo.current("geometry_test", "student:a") == base
    with repo.engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM geometry_scene.runs")).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM geometry_scene.versions")).scalar_one() == 1


def test_real_private_filesystem_assets(repository, monkeypatch):
    import shutil
    from pathlib import Path

    from mathbank_rest import object_store

    root = Path(__file__).resolve().parents[1] / (".geometry-test-objects-" + uuid4().hex)
    monkeypatch.setenv("MATHBANK_OBJECT_BACKEND", "filesystem")
    monkeypatch.setenv("MATHBANK_OBJECT_ROOT", str(root))
    repository.objects = object_store
    try:
        base = initial(repository)
        assert repository.read("geometry_test", 0, "student:a") == base
        assert len(list(root.iterdir())) == 2
        for asset in root.iterdir():
            assert asset.stat().st_mode & 0o077 == 0
    finally:
        if root.exists():
            shutil.rmtree(root, ignore_errors=False)
