"""Idempotency receipt of ``mb-learner`` (``stores.ddb.run_idempotent``): ``STUDENT#<sid>`` / ``IDEM#<key>``.

Hand-written: the migration skipped every expired receipt, so no ``dev`` item existed to generate it from. The stored response is
the API response body of the first request (offloaded to S3 above the size threshold like any large attribute).
"""
from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import Field, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, S3Ref, UtcDateTime


class LearnerIdem(DdbItem, ctx="learner", item_type="IDEM"):
    type: Literal["IDEM"] = "IDEM"
    PK: str = Field(pattern=r"^STUDENT#[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    SK: str = Field(pattern=r"^IDEM#.+$")
    OFFLOADED: ClassVar[frozenset[str]] = frozenset({"response"})
    request_hash: StrictStr = Field(min_length=64, max_length=64)
    response: Any | None = None
    response_ref: S3Ref | None = None
    created_at: UtcDateTime
    version: StrictInt = 1
