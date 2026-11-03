"""Hand-written model for the runtime query-embedding cache in ``mb-content`` (requirement 70 C6: ``QEMB``).

Not part of the migrated data (it did not exist in Postgres), so it is written here rather than generated. The key is the
sha256 of ``model || text`` - it contains no student identifier; the 30-day TTL bounds retention. The float32 vector is stored
base64-encoded (a pydantic JSON-mode dump cannot carry raw bytes).
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt, StrictStr

from mathbank_rest.models.base import DdbItem, UtcDateTime

KEY_RE = r"^QEMB#[0-9a-f]{64}$"


class ContentQemb(DdbItem, ctx="content", item_type="QEMB"):
    type: Literal["QEMB"] = "QEMB"
    PK: str = Field(pattern=KEY_RE)
    SK: str = Field(pattern=r"^V$")
    model: StrictStr
    dims: StrictInt = Field(ge=1)
    vector_b64: StrictStr = Field(min_length=4)
    created_at: UtcDateTime
