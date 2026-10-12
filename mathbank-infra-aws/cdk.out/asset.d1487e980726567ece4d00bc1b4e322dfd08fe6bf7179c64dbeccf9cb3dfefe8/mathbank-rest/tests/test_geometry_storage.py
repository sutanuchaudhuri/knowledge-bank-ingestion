"""Isolated adapter tests: no database, network, paid calls or temporary files."""
import hashlib
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from geometry_scene.errors import GeometryError, InvalidFrame
from geometry_scene.schemas import SceneInput
from geometry_scene.service import create_scene
from sqlalchemy.exc import OperationalError

from mathbank_rest.geometry_storage import GeometryStorageError, PostgresGeometryRepository

PAYLOAD = {
    "scene_id": "geometry_test",
    "objects": {"A": {"type": "POINT"}, "B": {"type": "POINT"}},
    "positions": {"A": [120, 120], "B": [380, 120]},
}


class MemoryObjects:
    def __init__(self):
        self.data = {}
        self.counter = 0

    def put_bytes(self, data, suffix):
        self.counter += 1
        key = f"{self.counter:032x}.{suffix}"
        self.data[key] = data
        return {"object_key": key, "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest()}

    def read_bytes(self, key):
        return self.data[key]

    def delete_object(self, key):
        del self.data[key]


class StubEngine:
    dialect = SimpleNamespace(name="postgresql")

    def __init__(self, conn=None, commit_error=None):
        self.conn = conn or Mock()
        self.commit_error = commit_error

    @contextmanager
    def begin(self):
        yield self.conn
        if self.commit_error:
            raise self.commit_error


def test_rejects_non_postgres_and_does_not_create_schema():
    with pytest.raises(ValueError, match="PostgreSQL"):
        PostgresGeometryRepository(SimpleNamespace(dialect=SimpleNamespace(name="sqlite")))
    engine = StubEngine()
    PostgresGeometryRepository(engine)
    engine.conn.execute.assert_not_called()


def test_transaction_cleans_uploaded_objects_on_commit_failure():
    objects = MemoryObjects()
    repo = PostgresGeometryRepository(StubEngine(commit_error=RuntimeError("commit")), objects)
    with pytest.raises(RuntimeError, match="commit"), repo._transaction() as (_, uploaded):
        repo._asset(b"private", "json", uploaded)
    assert objects.data == {}


def test_failed_second_upload_cleans_first():
    objects = MemoryObjects()
    repo = PostgresGeometryRepository(StubEngine(), objects)
    with pytest.raises(OSError), repo._transaction() as (_, uploaded):
        repo._asset(b"first", "json", uploaded)
        objects.put_bytes = Mock(side_effect=OSError("storage"))
        repo._asset(b"second", "svg", uploaded)
    assert not objects.data


def test_cleanup_failure_is_explicit():
    objects = MemoryObjects()
    repo = PostgresGeometryRepository(StubEngine(), objects)
    objects.delete_object = Mock(side_effect=OSError("cleanup"))
    with pytest.raises(GeometryStorageError, match="cleanup"), repo._transaction() as (_, uploaded):
        repo._asset(b"first", "json", uploaded)
        raise RuntimeError("rollback")


def test_asset_hash_and_size_verified_independently_of_store():
    objects = MemoryObjects()
    repo = PostgresGeometryRepository(StubEngine(), objects)
    asset = objects.put_bytes(b"accepted", "json")
    objects.data[asset["object_key"]] = b"tampered"
    with pytest.raises(GeometryStorageError, match="integrity"):
        repo._bytes(asset)


def test_oversized_evidence_is_rejected_before_upload(monkeypatch):
    from mathbank_rest import object_store

    repo = PostgresGeometryRepository(StubEngine(), MemoryObjects())
    monkeypatch.setattr(object_store, "MAX_OBJECT_BYTES", 3)
    with pytest.raises(GeometryError, match="size limit"):
        repo._asset(b"oversized", "json", [])
    assert not repo.objects.data


def test_read_reconstructs_frame_from_private_assets():
    frame = create_scene(SceneInput.model_validate(PAYLOAD))
    objects = MemoryObjects()
    assets = {
        "frame": objects.put_bytes(
            frame.model_dump_json(exclude={"svg"}).encode(), "json"),
        "svg": objects.put_bytes(frame.svg.encode(), "svg"),
    }
    conn = Mock()
    conn.execute.return_value.mappings.return_value.first.return_value = {"assets": assets}
    repo = PostgresGeometryRepository(StubEngine(conn), objects)
    assert repo._read(conn, "geometry_test", 0, "student:test") == frame
    with pytest.raises(GeometryStorageError, match="corrupt"):
        repo._read(conn, "wrong_identity", 0, "student:test")


def test_database_failure_is_sanitized_not_fallback():
    engine = StubEngine()
    engine.connect = Mock(side_effect=OperationalError("secret sql", {}, Exception("password")))
    repo = PostgresGeometryRepository(engine, MemoryObjects())
    with pytest.raises(GeometryStorageError) as error:
        repo.read("geometry_test", 0, "student:test")
    assert str(error.value) == "private geometry storage unavailable"


def test_invalid_candidate_preserves_private_evidence(monkeypatch):
    repo = PostgresGeometryRepository(StubEngine(), MemoryObjects())
    frame = create_scene(SceneInput.model_validate(PAYLOAD))
    monkeypatch.setattr(repo, "_replay", lambda *_: None)
    monkeypatch.setattr(repo, "_publish", Mock(side_effect=InvalidFrame("invalid", frame)))
    monkeypatch.setattr(repo, "save_run", Mock())
    with pytest.raises(InvalidFrame):
        repo.commit_candidate(frame, "student:test", None, "accept")
    args = repo.save_run.call_args.args
    assert args[0] == "student:test" and args[1].startswith("failed_")
    assert args[2]["status"] == "FAILED_CANDIDATE"
    assert args[2]["frame"]["svg"] == frame.svg


def test_cumulative_publication_requires_replay(monkeypatch):
    from geometry_scene.schemas import StateDelta
    from geometry_scene.service import apply_delta

    repo = PostgresGeometryRepository(StubEngine(), MemoryObjects())
    base = create_scene(SceneInput.model_validate(PAYLOAD))
    changed = apply_delta(base, StateDelta(expected_version=0))
    changed = changed.model_copy(update={"applied_delta": None})
    monkeypatch.setattr(repo, "_head", lambda *_: 0)
    monkeypatch.setattr(repo, "_read", lambda *_: base)
    with pytest.raises(GeometryError, match="replay"):
        repo._publish(repo.engine.conn, [], changed, "student:test", 0, None, "", {})
    assert not repo.objects.data
