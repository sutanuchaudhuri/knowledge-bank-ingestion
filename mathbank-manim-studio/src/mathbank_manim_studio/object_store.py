"""A small, filesystem-only object store for this project's own ephemeral, 1-day-TTL
render outputs. Deliberately not shared with mathbank-rest's S3-capable
`object_store.py` (requirements/60 §1): these are disposable drafts, not production
corpus assets, so a simple local store is the right-sized tool, and keeping this
project's code self-contained preserves the "no cross-project Python imports, only data
calls" boundary already established in mathbank-mcp-competitions (requirements/49).
"""
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

from mathbank_manim_studio.config import get_settings

MAX_OBJECT_BYTES = 200 * 1024 * 1024  # generous enough for a short explainer video
_KEY = re.compile(r"[0-9a-f]{32}\.[a-z0-9]{1,10}\Z")


class ObjectStoreError(OSError):
    pass


def _root() -> Path:
    root = Path(get_settings().studio_object_root).expanduser()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root.resolve(strict=True)


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("invalid object key")


def _path(key: str) -> Path:
    _validate_key(key)
    root = _root()
    path = root / key
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError("object path escapes private store")
    return path


def put_file(source: Path, suffix: str) -> str:
    """Move a locally-rendered file into the store under a fresh random key; returns
    the key (not the path — callers never construct paths themselves)."""
    suffix = suffix.removeprefix(".")
    if not re.fullmatch(r"[a-z0-9]{1,10}", suffix):
        raise ValueError("invalid suffix")
    size = source.stat().st_size
    if not 0 < size <= MAX_OBJECT_BYTES:
        raise ValueError(f"object must contain 1 to {MAX_OBJECT_BYTES} bytes")
    key = f"{uuid4().hex}.{suffix}"
    destination = _path(key)
    destination.write_bytes(source.read_bytes())
    return key


def read_bytes(key: str) -> bytes:
    path = _path(key)
    if not path.is_file():
        raise ObjectStoreError("object not found")
    return path.read_bytes()


def delete_object(key: str) -> None:
    path = _path(key)
    path.unlink(missing_ok=True)
