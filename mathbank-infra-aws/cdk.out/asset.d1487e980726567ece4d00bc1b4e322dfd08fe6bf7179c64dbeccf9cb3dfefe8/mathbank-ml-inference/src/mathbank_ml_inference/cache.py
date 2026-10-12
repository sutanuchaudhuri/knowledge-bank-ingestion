"""Response caching (requirements/13 §8, requirements/56 §5).

requirements/13 §8: "Cache keyed by: student feature snapshot ID, model version, request
parameters, content projection watermark. Invalidate when relevant learner event
watermark advances."
"""
from __future__ import annotations

import hashlib
import json


def cache_key(*, feature_snapshot_id: str, model_version: str, request_params: dict,
               content_projection_watermark: str) -> str:
    """Builds a deterministic cache key. Implemented (this one function is simple enough
    to not need a TODO) — but nothing in this module actually stores/retrieves a cached
    value yet; see `get`/`set` below.
    """
    payload = json.dumps(
        {
            "feature_snapshot_id": feature_snapshot_id,
            "model_version": model_version,
            "request_params": request_params,
            "content_projection_watermark": content_projection_watermark,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get(key: str) -> dict | None:
    """TODO (requirements/56 §5): decide Redis vs in-process LRU vs a Postgres-backed
    cache table once request volume is known. Do not default to Redis without confirming
    ops capacity — this is an explicit open decision, not an oversight."""
    raise NotImplementedError("requirements/56 §5 — cache read, backend undecided")


def set(key: str, value: dict, *, ttl_seconds: int = 300) -> None:
    """TODO (requirements/56 §5): see get() above — same undecided backend."""
    raise NotImplementedError("requirements/56 §5 — cache write, backend undecided")


def invalidate_for_watermark(content_projection_watermark: str) -> None:
    """TODO (requirements/13 §8): invalidate every cached entry keyed to a watermark
    older than the given one, once a real cache backend exists."""
    raise NotImplementedError("requirements/56 §5 — watermark-based invalidation")
