"""Pydantic models for the JSON documents stored in S3 (release/catalogue snapshots, offloaded attributes).

``registry.DOC_MODELS`` (generated) maps a document *family* to its model; ``family(key)`` derives the family from an
object key the same way the profiler did.
"""
from __future__ import annotations


def family(key: str) -> str | None:
    parts = key.split("/")
    if parts[0] == "offload" and len(parts) >= 5:
        rest = parts[2:]
        if rest[0] == "students":
            rest = rest[2:]
        return f"offload:{parts[1]}:{rest[0]}:{parts[-1].removesuffix('.json')}"
    if parts[0] == "catalog" and len(parts) >= 3:
        return f"content:catalog:{parts[1]}"
    if parts[0] == "releases":
        return "content:release"
    return None
