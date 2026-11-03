"""Declarative spec API used by aws/dynamo/specs/<context>.py.

A spec module defines:
    TABLES   = [Table("learner", gsis=["GSI1", "GSI2"], stream=True, ttl=True)]
    MAPPINGS = [Mapping("learner.student_profile", table="learner", sql="SELECT ...", transform=fn)]

`transform(row: dict) -> Iterable[dict | S3Put]` returns DynamoDB items (each must contain PK, SK and
`type`) and/or S3 objects. Items may include GSI key attributes; None attributes are dropped. The engine
converts types (UUID→str, timestamptz→ISO-8601 UTC 'Z', float→Decimal, json→map/list), batches writes,
and records a manifest for verification.

Large payloads (problem statements/solution sets, student quiz responses, uploaded-artifact payloads):
declare them in a module-level `OFFLOAD = {("<table ctx>", "<item type>"): ("attr", ...)}` or per mapping
with `Mapping.offload_attrs`. Any such attribute larger than MB_OFFLOAD_THRESHOLD (16 KiB) is written to
s3://mathbank-data-<env>-<account>/offload/<table>/… (student items under …/students/<student_id>/… so
erasure is one prefix delete) and replaced by `<attr>_ref = {bucket, key, sha256, bytes, content_type}`.
Independently, any item still above 350 KB has its largest attributes offloaded the same way.
Spec modules must not hand-roll their own S3 references for item attributes.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
from typing import Any, Callable, Iterable


@dataclasses.dataclass(frozen=True)
class Table:
    ctx: str                                  # table name becomes mb-<ctx>-<env>
    gsis: tuple[str, ...] = ()                # e.g. ("GSI1", "GSI2"): keys <name>PK / <name>SK (strings)
    stream: bool = False                      # NEW_AND_OLD_IMAGES
    ttl: bool = False                         # TTL attribute "ttl" (epoch seconds)
    keys_only_gsis: tuple[str, ...] = ()      # GSIs projected KEYS_ONLY (default ALL)
    include_gsis: tuple[tuple[str, tuple[str, ...]], ...] = ()  # (("GSI1", ("attr", ...)),) → INCLUDE projection
    description: str = ""


@dataclasses.dataclass(frozen=True)
class S3Put:
    bucket: str                               # "data" | "content"
    key: str
    body: Any                                 # dict/list (serialized as canonical JSON) or bytes
    content_type: str = "application/json"


@dataclasses.dataclass
class Mapping:
    name: str                                 # usually the source table, e.g. "learner.student_profile"
    table: str                                # ctx of the target Table
    sql: str                                  # read-only SELECT (may aggregate with json_agg)
    transform: Callable[[dict], Iterable[Any]]
    params: dict | None = None
    expected_source: str | None = None        # source table whose live row count must equal rows read
    offload_attrs: tuple[str, ...] = ()       # attributes moved to S3 (<attr>_ref) when larger than the threshold
    offload_threshold: int | None = None      # bytes; default MB_OFFLOAD_THRESHOLD (16 KiB)
    note: str = ""


# ---------------------------------------------------------------- helpers for spec authors

def iso(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return v.isoformat(timespec="microseconds") + "Z"
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def epoch(v: Any) -> int | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=dt.timezone.utc)
        return int(v.timestamp())
    return int(v)


def ttl_after(v: Any, days: int) -> int | None:
    """Epoch-seconds TTL `days` after timestamp v (None if v is None)."""
    if v is None:
        return None
    return epoch(v) + days * 86400


def s(v: Any) -> str | None:
    return None if v is None else str(v)


def pick(row: dict, *cols: str, **renames: str) -> dict:
    """Copy selected columns (and renamed ones: new=old) from a source row."""
    out = {c: row.get(c) for c in cols}
    out.update({new: row.get(old) for new, old in renames.items()})
    return out


def rest(row: dict, *exclude: str) -> dict:
    """All columns except the excluded ones (useful for 1:1 copies)."""
    return {k: v for k, v in row.items() if k not in exclude}
