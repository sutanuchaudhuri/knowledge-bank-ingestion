"""Immutable S3 snapshots referenced from mb-content items (requirement 70 C6 section 5: release and catalogue snapshots).

Snapshot objects are content-addressed: ``.../<sha256>.json``. ``SnapshotStore.get_json`` fetches from the content bucket,
verifies the body's SHA-256 against the key's file stem when it is a 64-hex digest, and keeps the parsed document in a
byte-bounded per-process LRU (an immutable object can be cached forever; the key changes when the content does).
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import OrderedDict
from typing import Any

from pydantic import TypeAdapter, ValidationError

from mathbank_rest.stores import ddb
from mathbank_rest.stores.errors import ItemSchemaError, StoreError

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
DEFAULT_MAX_BYTES = 128 * 1024 * 1024


class SnapshotStore:
    def __init__(self, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
        self._max, self._bytes = max_bytes, 0
        self._lru: OrderedDict[tuple[str, str], tuple[Any, int]] = OrderedDict()
        self._lock = threading.Lock()

    def get_json(self, key: str, *, bucket: str | None = None) -> Any:
        bucket = bucket or ddb.content_bucket()
        ck = (bucket, key)
        with self._lock:
            hit = self._lru.get(ck)
            if hit is not None:
                self._lru.move_to_end(ck)
                return hit[0]
        body = ddb.client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
        stem = key.rsplit("/", 1)[-1].removesuffix(".json")
        if _HEX64.match(stem) and hashlib.sha256(body).hexdigest() != stem:
            raise StoreError("snapshot checksum mismatch", key=key)
        doc = json.loads(body)
        with self._lock:
            self._lru[ck] = (doc, len(body))
            self._bytes += len(body)
            while self._bytes > self._max and len(self._lru) > 1:
                _, (_, n) = self._lru.popitem(last=False)
                self._bytes -= n
        return doc

    def get_model(self, key: str, model: Any, *, bucket: str | None = None) -> Any:
        """The snapshot validated into a pydantic model / type (``ItemSchemaError`` on drift)."""
        try:
            return TypeAdapter(model).validate_python(self.get_json(key, bucket=bucket))
        except ValidationError as exc:
            raise ItemSchemaError(f"snapshot {key} failed validation ({exc.error_count()} errors)", key=key,
                                  errors=[{"loc": ".".join(map(str, e["loc"])), "msg": e["msg"]} for e in exc.errors()[:5]]) from None

    def clear(self) -> None:
        with self._lock:
            self._lru.clear()
            self._bytes = 0


snapshots = SnapshotStore()
