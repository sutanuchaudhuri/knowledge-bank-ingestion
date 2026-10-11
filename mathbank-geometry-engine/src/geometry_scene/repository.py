from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .errors import GeometryError, VersionConflict
from .schemas import Frame, SceneInput, StateDelta
from .service import apply_delta, create_scene


class SceneNotFound(GeometryError):
    status_code = 404
    code = "SCENE_NOT_FOUND"


class ReplayConflict(GeometryError):
    status_code = 409
    code = "IDEMPOTENCY_CONFLICT"


class Repository:
    """Local durable single-host adapter; SQL CAS/receipts share one transaction."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = path
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scenes (
                    scene_id TEXT PRIMARY KEY, owner TEXT NOT NULL, current_version INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS frames (
                    scene_id TEXT NOT NULL REFERENCES scenes(scene_id),
                    version INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(scene_id, version)
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    owner TEXT NOT NULL, key TEXT NOT NULL, request_hash TEXT NOT NULL,
                    scene_id TEXT NOT NULL, version INTEGER NOT NULL,
                    PRIMARY KEY(owner, key)
                );
            """)
        os.chmod(path, 0o600)

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def _hash(operation, body):
        return hashlib.sha256(json.dumps([operation, body], sort_keys=True).encode()).hexdigest()

    def _read(self, conn, scene_id, version, owner):
        record = conn.execute(
            "SELECT f.payload FROM frames f JOIN scenes s USING(scene_id) "
            "WHERE f.scene_id=? AND f.version=? AND s.owner=?",
            (scene_id, version, owner),
        ).fetchone()
        if record is None:
            raise SceneNotFound("scene/version not found")
        return Frame.model_validate_json(record[0])

    def read(self, scene_id, version, owner):
        with self._connect() as conn:
            return self._read(conn, scene_id, version, owner)

    def current(self, scene_id, owner):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT current_version FROM scenes WHERE scene_id=? AND owner=?", (scene_id, owner)
            ).fetchone()
            if row is None:
                raise SceneNotFound("scene not found")
            return self._read(conn, scene_id, row[0], owner)

    def frames(self, scene_id, owner):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT f.version FROM frames f JOIN scenes s USING(scene_id) "
                "WHERE f.scene_id=? AND s.owner=? ORDER BY f.version",
                (scene_id, owner),
            ).fetchall()
            if not rows:
                raise SceneNotFound("scene not found")
            return [
                {
                    "version": row[0],
                    "render_path": f"/v1/geometry-scenes/{scene_id}/versions/{row[0]}/render",
                }
                for row in rows
            ]

    def _replay(self, conn, owner, key, digest):
        if not key:
            return None
        row = conn.execute(
            "SELECT request_hash,scene_id,version FROM receipts WHERE owner=? AND key=?",
            (owner, key),
        ).fetchone()
        if row is None:
            return None
        if row[0] != digest:
            raise ReplayConflict("idempotency key already used for another request")
        return self._read(conn, row[1], row[2], owner)

    def _remember(self, conn, owner, key, digest, frame):
        if key:
            conn.execute(
                "INSERT INTO receipts VALUES(?,?,?,?,?)",
                (owner, key, digest, frame.scene_state.scene_id, frame.version),
            )

    def create(self, request: SceneInput, owner: str, key=None):
        digest = self._hash("create", request.model_dump(mode="json"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._replay(conn, owner, key, digest)
            if replay:
                return replay, True
            if request.scene_id is None:
                request = request.model_copy(update={"scene_id": "scene_" + uuid4().hex})
            frame = create_scene(request)
            scene_id = frame.scene_state.scene_id
            if conn.execute("SELECT 1 FROM scenes WHERE scene_id=?", (scene_id,)).fetchone():
                raise VersionConflict("scene identity already exists; use a new scene ID")
            conn.execute("INSERT INTO scenes VALUES(?,?,0)", (scene_id, owner))
            conn.execute("INSERT INTO frames VALUES(?,0,?)", (scene_id, frame.model_dump_json()))
            self._remember(conn, owner, key, digest, frame)
            return frame, False

    def apply(self, scene_id, delta: StateDelta, owner, key=None):
        digest = self._hash("apply:" + scene_id, delta.model_dump(mode="json"))
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._replay(conn, owner, key, digest)
            if replay:
                return replay, True
            row = conn.execute(
                "SELECT current_version FROM scenes WHERE scene_id=? AND owner=?", (scene_id, owner)
            ).fetchone()
            if row is None:
                raise SceneNotFound("scene not found")
            if row[0] != delta.expected_version:
                raise VersionConflict(
                    f"expected version {delta.expected_version}; current {row[0]}"
                )
            previous = self._read(conn, scene_id, row[0], owner)
            frame = apply_delta(previous, delta)
            conn.execute(
                "INSERT INTO frames VALUES(?,?,?)",
                (scene_id, frame.version, frame.model_dump_json()),
            )
            conn.execute(
                "UPDATE scenes SET current_version=? WHERE scene_id=?", (frame.version, scene_id)
            )
            self._remember(conn, owner, key, digest, frame)
            return frame, False
