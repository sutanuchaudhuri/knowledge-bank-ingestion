"""An object store for this project's own ephemeral, 1-day-TTL render outputs.
Filesystem storage (default) is unchanged for local dev. S3 storage
(`MATHBANK_OBJECT_BACKEND=s3`, requirements/63) is an opt-in used only by the Lambda
deployment, where the API handler and the scheduled worker handler are *separate*
invocations/containers that cannot share a local `/tmp` — it reuses mathbank-rest's
already-provisioned Neon S3-compatible bucket under a `manim-studio/` key prefix so the
two services' key namespaces never collide. Deliberately not importing mathbank-rest's
own `object_store.py` module directly: these are disposable drafts with a different
schema (200MB video cap vs 25MB corpus-asset cap), and importing a sibling service's
internal module would violate the "no cross-project Python imports, only data calls"
boundary already established in mathbank-mcp-competitions (requirements/49).
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


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError("invalid object key")


def _root() -> Path:
    root = Path(get_settings().studio_object_root).expanduser()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root.resolve(strict=True)


def _path(key: str) -> Path:
    _validate_key(key)
    root = _root()
    path = root / key
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError("object path escapes private store")
    return path


def _s3_client():
    settings = get_settings()
    try:
        import boto3
        from botocore.config import Config
    except ImportError:
        raise ObjectStoreError("S3 storage requires the boto3 dependency") from None
    required = {
        "endpoint": settings.mathbank_s3_endpoint_url,
        "region": settings.mathbank_s3_region,
        "access key": settings.mathbank_s3_access_key_id,
        "secret key": settings.mathbank_s3_secret_access_key,
        "bucket": settings.mathbank_object_bucket,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ObjectStoreError("S3 storage configuration missing: " + ", ".join(missing))
    try:
        return boto3.client(
            "s3", endpoint_url=settings.mathbank_s3_endpoint_url,
            aws_access_key_id=settings.mathbank_s3_access_key_id,
            aws_secret_access_key=settings.mathbank_s3_secret_access_key,
            aws_session_token=settings.mathbank_s3_session_token or None,
            region_name=settings.mathbank_s3_region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                          connect_timeout=10, read_timeout=60, retries={"max_attempts": 2}),
        )
    except Exception:  # noqa: BLE001 -- SDK exception text may contain credentials
        raise ObjectStoreError("S3 storage client configuration failed") from None


def _s3_key(key: str) -> str:
    return f"{get_settings().mathbank_object_key_prefix}{key}"


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
    settings = get_settings()
    if settings.mathbank_object_backend == "s3":
        client = _s3_client()
        try:
            client.put_object(
                Bucket=settings.mathbank_object_bucket, Key=_s3_key(key),
                Body=source.read_bytes(),
                ContentType="video/mp4" if suffix == "mp4" else "application/octet-stream",
                IfNoneMatch="*",  # conditional creation refuses overwrites, even on key collision
            )
        except Exception:  # noqa: BLE001 -- never return raw SDK/network exception text
            raise ObjectStoreError("private S3 object write failed") from None
        return key
    destination = _path(key)
    destination.write_bytes(source.read_bytes())
    return key


def read_bytes(key: str) -> bytes:
    _validate_key(key)
    settings = get_settings()
    if settings.mathbank_object_backend == "s3":
        client = _s3_client()
        try:
            resp = client.get_object(Bucket=settings.mathbank_object_bucket, Key=_s3_key(key))
            return resp["Body"].read()
        except ObjectStoreError:
            raise
        except Exception:  # noqa: BLE001 -- never return raw SDK/network exception text
            raise ObjectStoreError("object not found") from None
    path = _path(key)
    if not path.is_file():
        raise ObjectStoreError("object not found")
    return path.read_bytes()


def delete_object(key: str) -> None:
    _validate_key(key)
    settings = get_settings()
    if settings.mathbank_object_backend == "s3":
        client = _s3_client()
        try:
            client.delete_object(Bucket=settings.mathbank_object_bucket, Key=_s3_key(key))
        except Exception:  # noqa: BLE001 -- never return raw SDK/network exception text
            raise ObjectStoreError("private S3 object delete failed") from None
        return
    path = _path(key)
    path.unlink(missing_ok=True)
