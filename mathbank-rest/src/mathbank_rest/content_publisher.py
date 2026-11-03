"""Publisher client contract for ``mb-content`` (requirement 70 C6 §4a, requirement 71 WP4).

The authoring plane (WP10 outbox consumers) is the only writer of content items. It builds one ``PublishedAggregate``
per item and calls ``publish_aggregate`` / ``withdraw_aggregate``. The contract:

* every write is conditional on ``src_rev``: ``attribute_not_exists(PK) OR src_rev < :rev``. A lower-or-equal revision
  never overwrites a newer item (``stale``); the same revision with different content is a ``conflict``;
* idempotent by ``(id, content_sha256)``: replaying the same revision, hash and state is a ``noop``, and a newer
  revision with identical content and state only bumps ``src_rev`` (``bumped``), so reconciliation, which compares the
  revision, converges;
* ``content_sha256`` is the sha256 of the item's canonical JSON payload, computed exactly as the migration does
  (``mathbank-db/aws/dynamo/specs/content.py::_item``): top-level ``None`` dropped, values converted by ``to_ddb``,
  keys sorted, compact separators, non-ASCII kept. Keys, GSI keys and ``type``/``version``/``src_rev``/``content_sha256``
  are not part of the payload. The hash is computed before S3 offload. ``tests/stores/test_wp4_reconcile.py`` pins this
  function against vectors produced by the migration code, so a freshly migrated item reconciles with 0 diffs.
"""
from __future__ import annotations

import base64
import datetime as dt
import decimal
import hashlib
import json
import math
import re
import uuid
from collections.abc import Iterable, Mapping
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mathbank_rest.models import base
from mathbank_rest.models.base import DdbItem
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import ConditionFailed, RevisionConflict

State = Literal["ACTIVE", "WITHDRAWN"]
PublishStatus = Literal["written", "bumped", "noop", "stale", "conflict", "withdrawn", "absent"]

# The attribute that carries the publication state of a type (requirement 70 C6 §3/§4a). Other types have none and
# are never withdrawn in place.
STATE_ATTR: dict[str, Literal["visibility", "eligible"]] = {
    "PROBLEM": "visibility", "STEP": "eligible", "LI": "eligible", "TAXNODE": "eligible",
}
# A retire also drops the listing keys so no index query can return the item (C6 §4a PROBLEM).
WITHDRAW_REMOVES: dict[str, tuple[str, ...]] = {"PROBLEM": ("GSI2PK", "GSI2SK")}
_ACTIVE_STATUSES = frozenset({"ACTIVE", "PUBLISHED", "APPROVED", "VALID"})
_BOOKKEEPING = frozenset({"PK", "SK", "type", "version", "src_rev", "content_sha256", "ttl"})
_GSI = re.compile(r"^GSI\d+(PK|SK)$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


# ------------------------------------------------------------------ canonical hashing (identical to the migration)

def _to_ddb(v: Any) -> Any:
    """``aws.common.to_ddb``: Python value -> DynamoDB-safe value. Nested ``None`` is kept (only the top level is cleaned)."""
    if v is None or isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return str(v)
        return decimal.Decimal(repr(v))
    if isinstance(v, decimal.Decimal):
        return v if v.is_finite() else str(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, dt.datetime):
        if v.tzinfo is not None:
            v = v.astimezone(dt.UTC).replace(tzinfo=None)
        return v.isoformat(timespec="microseconds") + "Z"
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return decimal.Decimal(str(v.total_seconds()))
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v)
    if isinstance(v, dict):
        return {str(k): _to_ddb(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_to_ddb(x) for x in v]
    if isinstance(v, (set, frozenset)):
        return [_to_ddb(x) for x in sorted(v, key=str)]
    return str(v)


def _json_bytes(obj: Any) -> bytes:
    """``aws.common.json_bytes``: sorted keys, compact, UTF-8 without ASCII escaping, Decimals back to int/float."""

    def default(o: Any) -> Any:
        if isinstance(o, decimal.Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        if isinstance(o, (bytes, bytearray)):
            return base64.b64encode(bytes(o)).decode()
        return str(o)

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=default).encode()


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    """The ``content_sha256`` of an item payload (its attributes, without keys, GSI keys and bookkeeping)."""
    body = {k: v for k, v in payload.items() if v is not None}
    return hashlib.sha256(_json_bytes(_to_ddb(body))).hexdigest()


def item_state(attrs: Mapping[str, Any]) -> State:
    """Publication state of an item (or of its source): ``visibility``, else ``eligible``, else ``status``; items
    without any of them (FACET, PTAG, ...) exist only while published."""
    if attrs.get("visibility") is not None:
        return "ACTIVE" if attrs["visibility"] == "ACTIVE" else "WITHDRAWN"
    if attrs.get("eligible") is not None:
        return "ACTIVE" if attrs["eligible"] else "WITHDRAWN"
    if attrs.get("status") is not None:
        return "ACTIVE" if attrs["status"] in _ACTIVE_STATUSES else "WITHDRAWN"
    return "ACTIVE"


def _state_value(type_: str, state: State) -> str | bool:
    attr = STATE_ATTR[type_]
    return state if attr == "visibility" else state == "ACTIVE"


# ------------------------------------------------------------------ typed bookkeeping view

class ContentBookkeeping(DdbItem):
    """Lenient typed projection of any ``mb-content`` item: the bookkeeping the publisher and reconciliation read.
    Not registered for a ``type`` (it matches all of them); per-type models stay the write schema."""

    CTX: ClassVar[str] = "content"

    src_rev: int | None = None
    content_sha256: str | None = None
    visibility: str | None = None
    eligible: bool | None = None
    status: str | None = None
    vector_state: dict[str, Any] | None = None
    search_vector_state: dict[str, Any] | None = None

    @property
    def rev(self) -> int:
        return self.src_rev or 0

    @property
    def state(self) -> State:
        return item_state({"visibility": self.visibility, "eligible": self.eligible, "status": self.status})


# ------------------------------------------------------------------ contract

class PublishedAggregate(BaseModel):
    """One content item as the publisher builds it.

    ``payload`` is the item's full attribute set *including* the state attribute of types that have one (so the hash
    covers it, as in the migration) and excluding keys and bookkeeping. ``sha_basis="external"`` is for items whose hash
    is defined elsewhere (release snapshots hash their S3 objects): ``content_sha256`` is then required and trusted."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    id: str = Field(min_length=1, description="natural id, used for logs and idempotency reports")
    pk: str = Field(min_length=1)
    sk: str = Field(min_length=1)
    gsi: dict[str, str] = Field(default_factory=dict, description="GSI1PK/GSI1SK/GSI2PK/GSI2SK")
    src_rev: int = Field(ge=0, description="pipeline.content_revision.rev the payload was built at")
    content_sha256: str | None = None
    sha_basis: Literal["payload", "external"] = "payload"
    state: State = "ACTIVE"
    payload: dict[str, Any]

    @model_validator(mode="after")
    def _check(self) -> PublishedAggregate:
        bad = sorted(k for k in self.payload if k in _BOOKKEEPING or _GSI.match(k))
        if bad:
            raise ValueError(f"payload must not contain keys or bookkeeping: {bad}")
        if any(not _GSI.match(k) for k in self.gsi):
            raise ValueError("gsi may only hold GSI<n>PK/GSI<n>SK attributes")
        if self.type in STATE_ATTR:
            attr = STATE_ATTR[self.type]
            want = _state_value(self.type, self.state)
            if self.payload.get(attr, want) != want:
                raise ValueError(f"payload.{attr}={self.payload[attr]!r} contradicts state={self.state}")
            self.payload = {**self.payload, attr: want}
        elif self.state != "ACTIVE":
            raise ValueError(f"type {self.type} has no visibility/eligible attribute; it cannot be published as WITHDRAWN")
        if self.sha_basis == "payload":
            computed = canonical_sha256(self.payload)
            if self.content_sha256 not in (None, computed):
                raise ValueError("content_sha256 does not match the canonical sha256 of the payload")
            self.content_sha256 = computed
        elif not self.content_sha256:
            raise ValueError("content_sha256 is required when sha_basis='external'")
        if not _SHA.match(self.content_sha256 or ""):
            raise ValueError("content_sha256 must be 64 lowercase hex characters")
        return self

    def to_item(self, *, version: int) -> dict[str, Any]:
        return {**self.payload, "PK": self.pk, "SK": self.sk, "type": self.type, **self.gsi, "version": version,
                "src_rev": self.src_rev, "content_sha256": self.content_sha256}


class PublishResult(BaseModel):
    status: PublishStatus
    type: str
    pk: str
    sk: str
    src_rev: int
    existing_src_rev: int | None = None
    content_sha256: str | None = None

    @property
    def applied(self) -> bool:
        return self.status in ("written", "bumped", "withdrawn")


_REV_COND = ddb.Cond("attribute_not_exists(PK) OR #srev < :nrev", {"#srev": "src_rev"})


def _model(type_: str) -> type[DdbItem]:
    m = base.model_for("content", type_)
    if m is None:
        raise ValueError(f"no mb-content model registered for type {type_!r}")
    return m


def _result(status: PublishStatus, type_: str, pk: str, sk: str, rev: int, existing: ContentBookkeeping | None,
            sha: str | None) -> PublishResult:
    return PublishResult(status=status, type=type_, pk=pk, sk=sk, src_rev=rev,
                         existing_src_rev=None if existing is None else existing.rev, content_sha256=sha)


def _rev_cond(rev: int) -> ddb.Cond:
    return ddb.Cond(_REV_COND.expr, dict(_REV_COND.names), {":nrev": rev})


def _bump_cond(rev: int) -> ddb.Cond:
    return ddb.Cond("#srev < :nrev", {"#srev": "src_rev"}, {":nrev": rev})


def _verdict(existing: ContentBookkeeping, agg: PublishedAggregate) -> PublishResult | None:
    """Decide from the stored item alone: noop / stale / conflict, else None (a write is needed)."""
    if existing.rev >= agg.src_rev:
        same = existing.rev == agg.src_rev
        if same and existing.content_sha256 == agg.content_sha256 and existing.state == agg.state:
            return _result("noop", agg.type, agg.pk, agg.sk, agg.src_rev, existing, agg.content_sha256)
        return _result("conflict" if same else "stale", agg.type, agg.pk, agg.sk, agg.src_rev, existing, agg.content_sha256)
    return None


def publish_aggregate(agg: PublishedAggregate, *, raise_on_stale: bool = False) -> PublishResult:
    """Write one item. Never overwrites an item with a higher or equal ``src_rev``.

    ``raise_on_stale`` turns ``stale``/``conflict`` into ``ConditionFailed`` for callers that prefer an exception
    (an outbox consumer normally treats ``stale`` as success: a newer snapshot is already applied)."""
    existing = typed.get(ContentBookkeeping, agg.pk, agg.sk)
    result = _publish(agg, existing)
    if raise_on_stale and result.status in ("stale", "conflict"):
        raise ConditionFailed(f"{agg.pk} {agg.sk}: {result.status} (stored src_rev={result.existing_src_rev}, offered {agg.src_rev})")
    return result


def _publish(agg: PublishedAggregate, existing: ContentBookkeeping | None) -> PublishResult:
    if existing is not None:
        verdict = _verdict(existing, agg)
        if verdict is not None:
            return verdict
        if existing.content_sha256 == agg.content_sha256 and existing.state == agg.state and existing.version is not None:
            try:
                typed.update(ContentBookkeeping, agg.pk, agg.sk, existing.version, {"src_rev": agg.src_rev},
                             cond=_bump_cond(agg.src_rev))
                return _result("bumped", agg.type, agg.pk, agg.sk, agg.src_rev, existing, agg.content_sha256)
            except (RevisionConflict, ConditionFailed):
                return _after_race(agg)
    version = (existing.version or 0) + 1 if existing is not None else 1
    item = _model(agg.type).from_item(agg.to_item(version=version))
    try:
        typed.put(item, cond=_rev_cond(agg.src_rev), conflict=ConditionFailed(f"{agg.pk} {agg.sk}: a newer revision is stored"))
    except ConditionFailed:
        return _after_race(agg)
    return _result("written", agg.type, agg.pk, agg.sk, agg.src_rev, existing, agg.content_sha256)


def _after_race(agg: PublishedAggregate) -> PublishResult:
    """Another publisher got there first: report what is stored now (stale, noop or conflict), never retry blindly."""
    current = typed.get(ContentBookkeeping, agg.pk, agg.sk)
    if current is None:
        return _result("stale", agg.type, agg.pk, agg.sk, agg.src_rev, None, agg.content_sha256)
    verdict = _verdict(current, agg)
    return verdict or _result("stale", agg.type, agg.pk, agg.sk, agg.src_rev, current, agg.content_sha256)


def publish_all(aggregates: Iterable[PublishedAggregate]) -> list[PublishResult]:
    """Apply an aggregate's items in the given order (put the root item last, as C6 §4a requires). Each item is
    independently conditional, so a replay after a partial failure converges without double writes."""
    return [publish_aggregate(a) for a in aggregates]


def withdraw_aggregate(type_: str, pk: str, sk: str, src_rev: int, *, content_sha256: str | None = None,
                       raise_on_stale: bool = False) -> PublishResult:
    """Flip ``visibility``/``eligible`` to withdrawn and bump ``src_rev`` (``withdrawn``); a PROBLEM also loses its
    listing keys. ``content_sha256`` is the hash of the withdrawn payload when the caller has it; the stored hash is
    left alone otherwise. A missing item is ``absent`` (nothing to withdraw), an already-withdrawn one only gets the
    newer revision (``bumped``)."""
    if type_ not in STATE_ATTR:
        raise ValueError(f"type {type_} has no visibility/eligible attribute; it cannot be withdrawn")
    existing = typed.get(ContentBookkeeping, pk, sk)
    if existing is None:
        return _result("absent", type_, pk, sk, src_rev, None, content_sha256)
    if existing.rev >= src_rev:
        same_state = existing.state == "WITHDRAWN"
        status: PublishStatus = "noop" if existing.rev == src_rev and same_state else "conflict" if existing.rev == src_rev else "stale"
        if raise_on_stale and status in ("stale", "conflict"):
            raise ConditionFailed(f"{pk} {sk}: {status} (stored src_rev={existing.rev}, offered {src_rev})")
        return _result(status, type_, pk, sk, src_rev, existing, existing.content_sha256)
    attr = STATE_ATTR[type_]
    changes: dict[str, Any] = {"src_rev": src_rev}
    if content_sha256:
        changes["content_sha256"] = content_sha256
    already = existing.state == "WITHDRAWN"
    if not already:
        changes[attr] = _state_value(type_, "WITHDRAWN")
    try:
        typed.update(ContentBookkeeping, pk, sk, existing.version or 0, changes,
                     remove=() if already else WITHDRAW_REMOVES.get(type_, ()), cond=_bump_cond(src_rev))
    except (RevisionConflict, ConditionFailed):
        current = typed.get(ContentBookkeeping, pk, sk)
        return _result("stale", type_, pk, sk, src_rev, current, content_sha256)
    return _result("bumped" if already else "withdrawn", type_, pk, sk, src_rev, existing, content_sha256 or existing.content_sha256)
