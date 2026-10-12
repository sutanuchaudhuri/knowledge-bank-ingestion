"""PostgreSQL acceptance transactions with private, integrity-checked frame assets.

No schema creation or fallback database. Migrate explicitly before deployment. Advisory
transaction locks serialize scene identities and owner-scoped receipts across workers.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from functools import wraps
from uuid import uuid4

from geometry_scene.errors import GeometryError, InvalidFrame, VersionConflict
from geometry_scene.repository import ReplayConflict, SceneNotFound
from geometry_scene.schemas import Frame, SceneInput, StateDelta
from geometry_scene.service import apply_delta, create_scene, validate_frame
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import object_store
from mathbank_rest.db.postgres import engine


class GeometryStorageError(GeometryError):
    code = "GEOMETRY_STORAGE_UNAVAILABLE"
    status_code = 503


def _storage_boundary(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (SQLAlchemyError, OSError) as exc:
            raise GeometryStorageError("private geometry storage unavailable") from exc
    return wrapped


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


class PostgresGeometryRepository:
    def __init__(self, db_engine=engine, objects=object_store):
        if db_engine.dialect.name != "postgresql":
            raise ValueError("geometry production storage requires PostgreSQL")
        self.engine = db_engine
        self.objects = objects

    @contextmanager
    def _transaction(self):
        uploaded = []
        try:
            with self.engine.begin() as conn:
                yield conn, uploaded
        except Exception:
            # UUID write-once objects belong exclusively to this uncommitted transaction.
            failures = []
            for key in uploaded:
                try:
                    self.objects.delete_object(key)
                except (OSError, ValueError) as exc:
                    failures.append(exc)
            if failures:
                raise GeometryStorageError("geometry rollback object cleanup failed") from failures[0]
            raise

    @staticmethod
    def _lock(conn, namespace, identity):
        lock = int.from_bytes(hashlib.sha256(_json([namespace, identity])).digest()[:8],
                              "big", signed=True)
        conn.execute(text("SELECT pg_advisory_xact_lock(:lock)"), {"lock": lock})

    def _asset(self, value, suffix, uploaded):
        if not 0 < len(value) <= object_store.MAX_OBJECT_BYTES:
            raise GeometryError("geometry asset exceeds the private object size limit")
        asset = self.objects.put_bytes(value, suffix)
        uploaded.append(asset["object_key"])
        return asset

    def _bytes(self, asset):
        data = self.objects.read_bytes(asset["object_key"])
        if len(data) != asset["size_bytes"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
            raise GeometryStorageError("geometry asset integrity check failed")
        return data

    def _read(self, conn, scene_id, version, owner):
        row = conn.execute(text(
            "SELECT v.assets FROM geometry_scene.versions v "
            "JOIN geometry_scene.scenes s USING(scene_id) "
            "WHERE v.scene_id=:scene AND v.version=:version AND s.owner=:owner"
        ), {"scene": scene_id, "version": version, "owner": owner}).mappings().first()
        if row is None:
            raise SceneNotFound("scene/version not found")
        try:
            payload = json.loads(self._bytes(row["assets"]["frame"]))
            payload["svg"] = self._bytes(row["assets"]["svg"]).decode()
            frame = Frame.model_validate(payload)
            if frame.version != version or frame.scene_state.scene_id != scene_id:
                raise ValueError("frame identity mismatch")
            if not validate_frame(frame).valid:
                raise ValueError("stored frame is invalid")
            return frame
        except (ValueError, KeyError, TypeError) as exc:
            raise GeometryStorageError("stored geometry frame is corrupt") from exc

    def _head(self, conn, scene_id, owner):
        row = conn.execute(text(
            "SELECT current_version FROM geometry_scene.scenes "
            "WHERE scene_id=:scene AND owner=:owner"
        ), {"scene": scene_id, "owner": owner}).first()
        if row is None:
            raise SceneNotFound("scene not found")
        return row[0]

    def _replay(self, conn, owner, key, digest):
        if key is None:
            return None
        if not isinstance(key, str) or not 1 <= len(key) <= 200:
            raise GeometryError("idempotency key must contain 1 to 200 characters")
        self._lock(conn, "receipt", [owner, key])
        row = conn.execute(text(
            "SELECT request_hash,scene_id,version FROM geometry_scene.receipts "
            "WHERE owner=:owner AND key=:key"
        ), {"owner": owner, "key": key}).mappings().first()
        if row is None:
            return None
        if row["request_hash"] != digest:
            raise ReplayConflict("idempotency key already used for another request")
        return self._read(conn, row["scene_id"], row["version"], owner)

    def _publish(self, conn, uploaded, frame, owner, expected_version, key, digest, lineage):
        frame = Frame.model_validate(frame.model_dump(mode="json"))
        report = validate_frame(frame)
        if not report.valid:
            raise InvalidFrame("; ".join(report.errors), frame)
        # Never trust a caller-provided PASS report.
        frame = frame.model_copy(update={"validation": report})
        scene_id = frame.scene_state.scene_id
        self._lock(conn, "scene", scene_id)
        if expected_version is None:
            if frame.version != 0 or frame.applied_delta is not None:
                raise VersionConflict("initial candidate must have version zero and no delta")
            if conn.execute(text(
                "SELECT 1 FROM geometry_scene.scenes WHERE scene_id=:scene"
            ), {"scene": scene_id}).first():
                raise VersionConflict("scene identity already exists")
            conn.execute(text(
                "INSERT INTO geometry_scene.scenes(scene_id,owner,current_version) "
                "VALUES(:scene,:owner,0)"
            ), {"scene": scene_id, "owner": owner})
        else:
            current = self._head(conn, scene_id, owner)
            if current != expected_version or frame.version != expected_version + 1:
                raise VersionConflict(f"expected version {expected_version}; current {current}")
            previous = self._read(conn, scene_id, current, owner)
            if frame.applied_delta is None or apply_delta(previous, frame.applied_delta) != frame:
                raise GeometryError("candidate must replay cumulatively from the accepted frame")
        lineage = lineage or {}
        if len(_json(lineage)) > 65536:
            raise GeometryError("lineage exceeds 64 KiB")
        assets = {
            "frame": self._asset(_json(frame.model_dump(mode="json", exclude={"svg"})),
                                 "json", uploaded),
            "svg": self._asset(frame.svg.encode(), "svg", uploaded),
        }
        conn.execute(text(
            "INSERT INTO geometry_scene.versions(scene_id,version,assets,lineage) "
            "VALUES(:scene,:version,CAST(:assets AS jsonb),CAST(:lineage AS jsonb))"
        ), {"scene": scene_id, "version": frame.version,
            "assets": _json(assets).decode(), "lineage": _json(lineage).decode()})
        if expected_version is not None:
            updated = conn.execute(text(
                "UPDATE geometry_scene.scenes SET current_version=:version "
                "WHERE scene_id=:scene AND owner=:owner AND current_version=:expected"
            ), {"scene": scene_id, "owner": owner, "version": frame.version,
                "expected": expected_version})
            if updated.rowcount != 1:
                raise VersionConflict("accepted scene changed concurrently")
        if key is not None:
            conn.execute(text(
                "INSERT INTO geometry_scene.receipts(owner,key,request_hash,scene_id,version) "
                "VALUES(:owner,:key,:digest,:scene,:version)"
            ), {"owner": owner, "key": key, "digest": digest,
                "scene": scene_id, "version": frame.version})
        return frame, False

    def _write(self, owner, key, digest, build, expected_version, lineage=None):
        try:
            with self._transaction() as (conn, uploaded):
                replay = self._replay(conn, owner, key, digest)
                if replay is not None:
                    return replay, True
                return self._publish(conn, uploaded, build(conn), owner, expected_version,
                                     key, digest, lineage)
        except InvalidFrame as exc:
            self.save_run(owner, "failed_" + uuid4().hex, {
                "status": "FAILED_CANDIDATE", "request_hash": digest,
                "frame": exc.frame.model_dump(mode="json"),
            })
            raise

    @_storage_boundary
    def create(self, request: SceneInput, owner: str, key=None):
        digest = _digest(["create", request.model_dump(mode="json")])
        if request.scene_id is None:
            request = request.model_copy(update={"scene_id": "scene_" + uuid4().hex})
        return self._write(owner, key, digest, lambda _: create_scene(request), None)

    @_storage_boundary
    def apply(self, scene_id, delta: StateDelta, owner, key=None):
        digest = _digest(["apply:" + scene_id, delta.model_dump(mode="json")])

        def build(conn):
            self._lock(conn, "scene", scene_id)
            current = self._head(conn, scene_id, owner)
            if current != delta.expected_version:
                raise VersionConflict(f"expected version {delta.expected_version}; current {current}")
            return apply_delta(self._read(conn, scene_id, current, owner), delta)

        return self._write(owner, key, digest, build, delta.expected_version)

    @_storage_boundary
    def commit_candidate(self, frame: Frame, owner, expected_version, key, lineage=None,
                         *, request_body=None):
        """Accept validated initial (expected_version=None) or cumulative version; returns (frame,replayed)."""
        digest = (
            _digest(["interpret", request_body]) if request_body is not None
            else _digest(["candidate", frame.model_dump(mode="json"), expected_version, lineage])
        )
        return self._write(owner, key, digest, lambda _: frame, expected_version, lineage)

    @_storage_boundary
    def lookup_receipt(self, owner, key, operation, body):
        """Preflight receipt lookup, using the same canonical request hash as acceptance.

        For interpretation pass operation='interpret' and the JSON-mode GeometryRequest
        dict, then supply that unchanged dict as commit_candidate(request_body=...).
        Concurrent misses may still invoke providers; acceptance remains serialized.
        """
        with self.engine.begin() as conn:
            return self._replay(conn, owner, key, _digest([operation, body]))

    @_storage_boundary
    def read(self, scene_id, version, owner):
        with self.engine.connect() as conn:
            return self._read(conn, scene_id, version, owner)

    @_storage_boundary
    def current(self, scene_id, owner):
        with self.engine.connect() as conn:
            return self._read(conn, scene_id, self._head(conn, scene_id, owner), owner)

    @_storage_boundary
    def frames(self, scene_id, owner):
        with self.engine.connect() as conn:
            self._head(conn, scene_id, owner)
            rows = conn.execute(text(
                "SELECT version FROM geometry_scene.versions WHERE scene_id=:scene ORDER BY version"
            ), {"scene": scene_id})
            return [{"version": row[0],
                     "render_path": f"/v1/geometry-scenes/{scene_id}/versions/{row[0]}/render"}
                    for row in rows]

    @_storage_boundary
    def save_run(self, owner, run_id, evidence):
        if not isinstance(run_id, str) or not 1 <= len(run_id) <= 200:
            raise GeometryError("run ID must contain 1 to 200 characters")
        data = _json(evidence)
        digest = hashlib.sha256(data).hexdigest()
        with self._transaction() as (conn, uploaded):
            self._lock(conn, "run", [owner, run_id])
            row = conn.execute(text(
                "SELECT evidence_hash FROM geometry_scene.runs WHERE owner=:owner AND run_id=:run"
            ), {"owner": owner, "run": run_id}).first()
            if row:
                if row[0] != digest:
                    raise ReplayConflict("run ID already has different evidence")
            else:
                asset = self._asset(data, "json", uploaded)
                conn.execute(text(
                    "INSERT INTO geometry_scene.runs(owner,run_id,evidence_asset,evidence_hash) "
                    "VALUES(:owner,:run,CAST(:asset AS jsonb),:digest)"
                ), {"owner": owner, "run": run_id, "asset": _json(asset).decode(), "digest": digest})
        return {"run_id": run_id}

    @_storage_boundary
    def read_run(self, owner, run_id):
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT evidence_asset FROM geometry_scene.runs WHERE owner=:owner AND run_id=:run"
            ), {"owner": owner, "run": run_id}).first()
            if not row:
                raise SceneNotFound("geometry run not found")
            try:
                return json.loads(self._bytes(row[0]))
            except (ValueError, KeyError, TypeError) as exc:
                raise GeometryStorageError("stored geometry evidence is corrupt") from exc

    @_storage_boundary
    def list_runs(self, owner, limit=50):
        if not 1 <= limit <= 100:
            raise GeometryError("run list limit must be between 1 and 100")
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT run_id,created_at,review FROM geometry_scene.runs "
                "WHERE owner=:owner ORDER BY created_at DESC,run_id LIMIT :limit"
            ), {"owner": owner, "limit": limit}).mappings()
            return [dict(row) for row in rows]

    @_storage_boundary
    def review_run(self, owner, run_id, review):
        with self.engine.begin() as conn:
            result = conn.execute(text(
                "UPDATE geometry_scene.runs SET review=CAST(:review AS jsonb) "
                "WHERE owner=:owner AND run_id=:run"
            ), {"owner": owner, "run": run_id, "review": _json(review).decode()})
            if result.rowcount != 1:
                raise SceneNotFound("geometry run not found")
        return {"run_id": run_id, "review": review}


def get_geometry_repository():
    """Shared-engine production dependency; constructor never connects or migrates."""
    return PostgresGeometryRepository()
