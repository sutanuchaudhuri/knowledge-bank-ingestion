"""Shared private store acceptance tests; all scratch objects stay under this repository."""
from __future__ import annotations

import shutil
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest

from mathbank_rest import object_store


@pytest.fixture
def root(monkeypatch):
    path = Path(__file__).parent / f".private-store-{uuid4().hex}"
    monkeypatch.setenv("MATHBANK_OBJECT_BACKEND", "filesystem")
    monkeypatch.setenv("MATHBANK_OBJECT_ROOT", str(path))
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_private_write_read_delete_and_metadata(root):
    data = b"private original evidence"
    first = object_store.put_bytes(data, ".pdf")
    second = object_store.put_bytes(data, "pdf")
    assert first["object_key"] != second["object_key"]
    assert first["sha256"] == sha256(data).hexdigest() and first["size_bytes"] == len(data)
    assert set(first) == {"object_key", "sha256", "size_bytes"}
    assert object_store.read_bytes(first["object_key"]) == data
    assert (root / first["object_key"]).stat().st_mode & 0o777 == 0o600
    assert not any(path.name.startswith(".") for path in root.iterdir())
    object_store.delete_object(first["object_key"])
    object_store.delete_object(first["object_key"])
    with pytest.raises(FileNotFoundError):
        object_store.read_bytes(first["object_key"])


@pytest.mark.parametrize("key", ["../secrets", "/etc/passwd", "https://example.org/x", "",
                                 "f" * 32 + "/file.svg", "f" * 32 + ".svg/../key"])
def test_keys_cannot_escape_or_be_urls(root, key):
    with pytest.raises(ValueError):
        object_store.read_bytes(key)
    with pytest.raises(ValueError):
        object_store.delete_object(key)


@pytest.mark.parametrize("suffix", ["../svg", "SVG", "svg/../../file", "svg?x", "x" * 11])
def test_suffix_rejection(root, suffix):
    with pytest.raises(ValueError):
        object_store.put_bytes(b"x", suffix)


def test_oversized_empty_and_nonbytes_rejected(root, monkeypatch):
    monkeypatch.setattr(object_store, "MAX_OBJECT_BYTES", 4)
    for data in (b"", b"12345", "not bytes"):
        with pytest.raises(ValueError):
            object_store.put_bytes(data, "bin")
    item = object_store.put_bytes(b"1234", "bin")
    (root / item["object_key"]).write_bytes(b"12345")
    with pytest.raises(ValueError):
        object_store.read_bytes(item["object_key"])


def test_symlink_keys_rejected(root):
    item = object_store.put_bytes(b"source", "bin")
    alias = "f" * 32 + ".bin"
    (root / alias).symlink_to(root / item["object_key"])
    with pytest.raises(ValueError):
        object_store.read_bytes(alias)
    with pytest.raises(ValueError):
        object_store.delete_object(alias)


def test_atomic_publish_failure_leaves_no_partial_object(root, monkeypatch):
    def fail_link(*args):
        raise FileExistsError("exclusive destination collision")

    monkeypatch.setattr(object_store.os, "link", fail_link)
    with pytest.raises(FileExistsError):
        object_store.put_bytes(b"complete object", "bin")
    assert list(root.iterdir()) == []


def test_default_root_is_repository_runtime_directory(monkeypatch):
    monkeypatch.delenv("MATHBANK_OBJECT_ROOT", raising=False)
    expected = Path(object_store.__file__).resolve().parents[3] / "data" / "runtime_objects"
    # Inspect the default without creating a directory in an unrelated user's environment.
    assert expected.parent.name == "data"
    assert expected.parent.parent == Path(__file__).resolve().parents[2]
