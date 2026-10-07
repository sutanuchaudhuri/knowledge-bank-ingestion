"""Private S3 objects; filesystem storage is an explicit offline/development opt-in.

S3 credentials come from process environment or the repository-root .env only. Neither Neon Auth
nor AI Gateway credentials are storage credentials. Object bytes are always served through REST
ownership/publication checks, never public or presigned URLs.

Required Neon S3 configuration: AWS_ENDPOINT_URL_S3, AWS_REGION, AWS_ACCESS_KEY_ID,
AWS_SECRET_ACCESS_KEY. MATHBANK_OBJECT_BUCKET (AWS_BUCKET_NAME alias) defaults to mathbank-runtime.
Optional AWS_SESSION_TOKEN. Development-only: MATHBANK_OBJECT_BACKEND=filesystem and
MATHBANK_OBJECT_ROOT (defaults to repository data/runtime_objects).
"""
from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from dotenv import dotenv_values

MAX_OBJECT_BYTES = 25 * 1024 * 1024
_KEY = re.compile(r"[0-9a-f]{32}\.[a-z0-9]{1,10}\Z")
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_NAMES = (
    "MATHBANK_OBJECT_BACKEND", "MATHBANK_OBJECT_ROOT", "MATHBANK_OBJECT_BUCKET",
    "AWS_ENDPOINT_URL_S3", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
    "AWS_REGION", "AWS_SESSION_TOKEN",
    "AWS_BUCKET_NAME",
)


class ObjectStoreError(OSError):
    """Sanitized failure: never includes endpoints, credentials or raw SDK exception text."""


def _config() -> dict[str, str]:
    root_file = REPOSITORY_ROOT / ".env"
    # Never search cwd/service .env files or modify process variables.
    values = dotenv_values(root_file, interpolate=False) if root_file.is_file() else {}
    config = {name: os.environ[name] if name in os.environ else str(values.get(name) or "")
              for name in _CONFIG_NAMES}
    if config["MATHBANK_OBJECT_BUCKET"] and config["AWS_BUCKET_NAME"] and (
        config["MATHBANK_OBJECT_BUCKET"] != config["AWS_BUCKET_NAME"]
    ):
        raise ObjectStoreError("MATHBANK_OBJECT_BUCKET and AWS_BUCKET_NAME conflict")
    if "MATHBANK_OBJECT_BUCKET" not in os.environ and not values.get("MATHBANK_OBJECT_BUCKET"):
        config["MATHBANK_OBJECT_BUCKET"] = config["AWS_BUCKET_NAME"] or "mathbank-runtime"
    return config


def _backend(config: dict[str, str]) -> str:
    backend = config["MATHBANK_OBJECT_BACKEND"] or "s3"
    if backend not in ("s3", "filesystem"):
        raise ObjectStoreError("MATHBANK_OBJECT_BACKEND must be s3 or filesystem")
    return backend


def _s3_settings(config: dict[str, str]) -> dict[str, str]:
    required = ("AWS_ENDPOINT_URL_S3", "AWS_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY",
                "MATHBANK_OBJECT_BUCKET")
    missing = [name for name in required if not config[name]]
    if missing:
        raise ObjectStoreError("S3 storage configuration missing: " + ", ".join(missing))
    try:
        parsed = urlsplit(config["AWS_ENDPOINT_URL_S3"])
    except ValueError:
        raise ObjectStoreError("AWS_ENDPOINT_URL_S3 must be a valid HTTPS endpoint") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ObjectStoreError("AWS_ENDPOINT_URL_S3 must be a credential-free HTTPS endpoint")
    if not re.fullmatch(r"[a-z0-9-]{1,64}", config["AWS_REGION"]):
        raise ObjectStoreError("AWS_REGION must be a valid storage region")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", config["MATHBANK_OBJECT_BUCKET"]):
        raise ObjectStoreError("MATHBANK_OBJECT_BUCKET must be a valid bucket name")
    return config


def _s3_client(config: dict[str, str]):
    try:
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3", endpoint_url=config["AWS_ENDPOINT_URL_S3"],
            aws_access_key_id=config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=config["AWS_SECRET_ACCESS_KEY"],
            aws_session_token=config["AWS_SESSION_TOKEN"] or None,
            region_name=config["AWS_REGION"],
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                          connect_timeout=10, read_timeout=30, retries={"max_attempts": 2}),
        )
    except ImportError:
        raise ObjectStoreError("S3 storage requires the boto3 dependency") from None
    except Exception:  # noqa: BLE001 -- SDK exception text may contain credentials
        raise ObjectStoreError("S3 storage client configuration failed") from None


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("invalid object key")


def _root() -> Path:
    config = _config()
    if _backend(config) != "filesystem":
        raise ObjectStoreError("filesystem storage requires MATHBANK_OBJECT_BACKEND=filesystem")
    default = REPOSITORY_ROOT / "data" / "runtime_objects"
    root = Path(config["MATHBANK_OBJECT_ROOT"] or str(default)).expanduser()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root.resolve(strict=True)


def _path(key: str) -> Path:
    _validate_key(key)
    root = _root()
    path = root / key
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError("object path escapes private store")
    return path


def put_bytes(data: bytes, suffix: str) -> dict:
    """Write once, publish atomically; no caller-chosen paths or public URLs."""
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_OBJECT_BYTES:
        raise ValueError("object must contain 1 to 26214400 bytes")
    suffix = suffix.removeprefix(".")
    if not re.fullmatch(r"[a-z0-9]{1,10}", suffix):
        raise ValueError("invalid object suffix")
    key = f"{uuid4().hex}.{suffix}"
    digest = hashlib.sha256(data).hexdigest()
    config = _config()
    if _backend(config) == "s3":
        _s3_settings(config)
        client = _s3_client(config)
        try:
            # S3 PUT is atomic; conditional creation refuses overwrites, even on UUID collision.
            client.put_object(Bucket=config["MATHBANK_OBJECT_BUCKET"], Key=key, Body=data,
                              ContentLength=len(data), ContentType="application/octet-stream",
                              Metadata={"sha256": digest}, IfNoneMatch="*")
        except Exception:  # noqa: BLE001 -- never return raw SDK/network exception text
            raise ObjectStoreError("private S3 object write failed") from None
        return {"object_key": key, "sha256": digest, "size_bytes": len(data)}
    path = _path(key)
    staging = path.with_name(f".{uuid4().hex}.pending")
    try:
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        # A hard link publishes the fully written inode, refusing any existing destination.
        os.link(staging, path)
    finally:
        staging.unlink(missing_ok=True)
    return {"object_key": key, "sha256": digest,
            "size_bytes": len(data)}


def read_bytes(key: str) -> bytes:
    _validate_key(key)
    config = _config()
    if _backend(config) == "s3":
        _s3_settings(config)
        client = _s3_client(config)
        body = None
        try:
            response = client.get_object(Bucket=config["MATHBANK_OBJECT_BUCKET"], Key=key)
            body = response["Body"]
            size = response["ContentLength"]
            if not isinstance(size, int) or not 0 < size <= MAX_OBJECT_BYTES:
                raise ValueError("invalid object size")
            data = body.read(MAX_OBJECT_BYTES + 1)
            digest = response.get("Metadata", {}).get("sha256")
            if (not isinstance(data, bytes) or len(data) != size or len(data) > MAX_OBJECT_BYTES
                    or digest != hashlib.sha256(data).hexdigest()):
                raise ValueError("invalid object integrity")
            return data
        except Exception:  # noqa: BLE001 -- keep object identifiers/credentials out of errors
            raise ObjectStoreError("private S3 object read or integrity check failed") from None
        finally:
            if body is not None:
                try:
                    body.close()
                except Exception:  # noqa: BLE001, S110 -- close failure must not disclose SDK internals
                    pass
    path = _path(key)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_OBJECT_BYTES:
            raise ValueError("invalid or oversized stored object")
        data = stream.read(MAX_OBJECT_BYTES + 1)
    if len(data) > MAX_OBJECT_BYTES:
        raise ValueError("oversized stored object")
    return data


def delete_object(key: str) -> None:
    _validate_key(key)
    config = _config()
    if _backend(config) == "s3":
        _s3_settings(config)
        client = _s3_client(config)
        try:
            client.delete_object(Bucket=config["MATHBANK_OBJECT_BUCKET"], Key=key)
        except Exception:  # noqa: BLE001 -- never expose SDK exception text
            raise ObjectStoreError("private S3 object delete failed") from None
        return
    _path(key).unlink(missing_ok=True)
