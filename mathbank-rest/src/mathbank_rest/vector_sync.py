"""Embedding sync worker core: ``mb-content-vector-sync`` (requirement 70 C6, requirement 71 WP2).

A DynamoDB Stream consumer on ``mb-content`` keeps S3 Vectors in step with the published content:

    Stream record --events_from_stream_records--> VectorSyncEvent --apply_events--> S3 Vectors + ``vector_state``

* **Trigger** - an item of type PROBLEM / STEP / LI / TAXNODE / THEOREM / MISCONCEPTION whose render hash
  (``search_render_sha256``, else ``vector_source_sha256``, else ``content_sha256``) changed, or whose publication
  (``visibility`` / ``eligible`` / ``status``) flipped. Everything else on the stream is ignored, including the worker's own
  ``vector_state`` write-back.
* **Chunk texts are not on the item.** The publisher writes the rendered chunks to
  ``s3://<data bucket>/vector-sync/<family>/<entity_id>/<sha256>.json`` (``RenderedChunks``; the object carries a ``sha256``
  metadata entry of its body and the document its own ``chunks_sha256``). ``load_rendered`` verifies both.
* **Idempotent by (entity, sha256).** When the item's ``vector_state`` already holds the event's sha256 and exactly the event's
  chunk keys nothing is read, embedded or written. Otherwise a chunk is embedded only when no stored vector with the same key
  and the same ``content_sha256``/``source_sha256`` metadata exists (that vector is reused, re-put when only metadata moved).
* **Write order is vectors → state → stale keys**: the item's ``vector_state`` is what makes a vector visible to search
  (``content_lookup.hit_is_current``), so a crash between the steps leaves invisible orphans, never a visible stale hit.
  ``withdraw`` hides first (state keys emptied), then deletes.
* The state write is a version CAS (``typed.update``) guarded by "the item still has this render hash"; an item without a
  ``version`` gets a typed put of the same item under the same guard. A newer event that overtook this one wins.

No Postgres anywhere in this module.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Any, Literal

from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from mathbank_rest.models.base import DdbItem
from mathbank_rest.models.ddb import content as cm
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import (
    ConditionFailed,
    NotFound,
    RevisionConflict,
    StoreError,
    ValidationFailed,
)
from mathbank_rest.vector_catalog import EMBEDDING_MODEL, Family, meta_model
from mathbank_rest.vector_store import VectorItem, VectorStore, get_vector_store, uses_s3_vectors

LOG = logging.getLogger(__name__)

EMBED_BATCH = 100
STATE_ATTEMPTS = 3
RENDER_SHA_ATTRS = ("search_render_sha256", "vector_source_sha256", "content_sha256")
# The per-chunk metadata key holding the hash of what the vector was made from (absent: the chunk is always re-embedded).
CHUNK_SHA_KEY: dict[Family, str] = {
    Family.PROBLEM: "content_sha256", Family.STEP: "content_sha256", Family.LEARNING_ITEM: "content_sha256",
    Family.TAXONOMY_SEARCH: "content_sha256", Family.TAXONOMY_NODE: "source_sha256",
    Family.MISCONCEPTION: "source_sha256", Family.THEOREM: "source_sha256",
}

Op = Literal["upsert", "withdraw"]
Status = Literal["synced", "unchanged", "withdrawn", "superseded", "skipped", "failed"]
BatchEmbedder = Callable[[list[str]], list[list[float]]]
Loader = Callable[[Family, str, str], "RenderedChunks"]


# ------------------------------------------------------------------ models

class Chunk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=1024)
    text: str
    metadata: dict[str, Any]


class VectorSyncEvent(BaseModel):
    """One entity to (re)sync. ``old_keys`` lets a withdraw of an already deleted item still remove its vectors."""

    model_config = ConfigDict(extra="forbid")

    family: Family
    entity_id: str = Field(min_length=1)
    op: Op
    content_sha256: str = Field(min_length=1)
    chunks: list[Chunk] = Field(default_factory=list)
    old_keys: list[str] = Field(default_factory=list)
    sequence_number: str | None = None

    @model_validator(mode="after")
    def _shape(self) -> VectorSyncEvent:
        if self.op == "upsert":
            if not self.chunks:
                raise ValueError("an upsert needs at least one chunk")
            if len({c.key for c in self.chunks}) != len(self.chunks):
                raise ValueError("duplicate chunk keys")
        return self


class RenderedChunks(BaseModel):
    """The chunk document the publisher stores at ``vector-sync/<family>/<entity_id>/<sha256>.json``."""

    model_config = ConfigDict(extra="forbid")

    family: Family
    entity_id: str
    content_sha256: str
    chunks: list[Chunk]
    chunks_sha256: str | None = None

    def digest(self) -> str:
        return chunks_digest(self.chunks)


class EventOutcome(BaseModel):
    family: Family
    entity_id: str
    op: Op
    status: Status
    embedded: int = 0
    embed_calls: int = 0
    reused: int = 0
    written: int = 0
    deleted: int = 0
    error: str | None = None
    sequence_number: str | None = None


class SyncResult(BaseModel):
    outcomes: list[EventOutcome] = Field(default_factory=list)

    @property
    def failed(self) -> list[EventOutcome]:
        return [o for o in self.outcomes if o.status == "failed"]

    @property
    def ok(self) -> bool:
        return not self.failed

    def total(self, field: Literal["embedded", "embed_calls", "reused", "written", "deleted"]) -> int:
        return sum(getattr(o, field) for o in self.outcomes)


class StateDoc(BaseModel):
    """``vector_state`` as written back (shared shape of every ContentXVectorState)."""

    model_config = ConfigDict(extra="forbid")

    index: str
    keys: list[str]
    model: str
    sha256: str


class StateView(BaseModel):
    model_config = ConfigDict(extra="ignore")

    keys: list[str] = Field(default_factory=list)
    sha256: str | None = None


class ItemView(BaseModel):
    """The few attributes of an ``mb-content`` item the sync decisions depend on (stream images and consistent reads alike)."""

    model_config = ConfigDict(extra="ignore")

    PK: str
    SK: str = "META"
    type: str
    version: int | None = None
    visibility: str | None = None
    eligible: bool | None = None
    status: str | None = None
    review_status: str | None = None
    search_render_sha256: str | None = None
    vector_source_sha256: str | None = None
    content_sha256: str | None = None
    vector_state: StateView | None = None
    search_vector_state: StateView | None = None

    @property
    def render_attr(self) -> str | None:
        return next((a for a in RENDER_SHA_ATTRS if getattr(self, a)), None)

    @property
    def render_sha(self) -> str | None:
        attr = self.render_attr
        return getattr(self, attr) if attr else None

    @property
    def published(self) -> bool:
        if self.type == "PROBLEM":
            return self.visibility == "ACTIVE"
        if self.type in ("MISCONCEPTION", "THEOREM"):
            return (self.status or "ACTIVE") == "ACTIVE" and (self.review_status or "APPROVED") == "APPROVED"
        return bool(self.eligible)

    def state(self, attr: str) -> StateView | None:
        return getattr(self, attr)

    @property
    def entity_id(self) -> str:
        return self.PK.split("#", 1)[1]


@dataclasses.dataclass(frozen=True)
class Owner:
    """Where a family's ``vector_state`` lives: the item type, its typed model (None: no model yet) and the state attribute."""

    family: Family
    item_type: str
    model: type[DdbItem] | None
    state_attr: str

    def pk(self, entity_id: str) -> str:
        return f"{self.item_type}#{entity_id}"


OWNERS: dict[Family, Owner] = {o.family: o for o in (
    Owner(Family.PROBLEM, "PROBLEM", cm.ContentProblem, "vector_state"),
    Owner(Family.STEP, "STEP", cm.ContentStep, "vector_state"),
    Owner(Family.LEARNING_ITEM, "LI", cm.ContentLi, "vector_state"),
    Owner(Family.TAXONOMY_NODE, "TAXNODE", cm.ContentTaxnode, "vector_state"),
    Owner(Family.TAXONOMY_SEARCH, "TAXNODE", cm.ContentTaxnode, "search_vector_state"),
    Owner(Family.MISCONCEPTION, "MISCONCEPTION", cm.ContentMisconception, "vector_state"),
    Owner(Family.THEOREM, "THEOREM", None, "vector_state"),
)}
STREAM_OWNERS: dict[str, tuple[Owner, ...]] = {
    t: tuple(o for o in OWNERS.values() if o.item_type == t) for t in {o.item_type for o in OWNERS.values()}}


# ------------------------------------------------------------------ embedding

_openai_client = None


def openai_batch_embedder(texts: list[str]) -> list[list[float]]:
    """One OpenAI call for ``texts`` (<= EMBED_BATCH), ``text-embedding-3-small`` 1536, in input order."""
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        from mathbank_rest.project_credentials import configure_openai

        _openai_client = OpenAI(api_key=configure_openai())
    rows = sorted(_openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts).data, key=lambda r: r.index)
    return [list(r.embedding) for r in rows]


BATCH_EMBEDDER: BatchEmbedder = openai_batch_embedder


def _embed_all(texts: Sequence[str], embedder: BatchEmbedder) -> tuple[list[list[float]], int]:
    out: list[list[float]] = []
    calls = 0
    for i in range(0, len(texts), EMBED_BATCH):
        batch = list(texts[i:i + EMBED_BATCH])
        got = embedder(batch)
        calls += 1
        if len(got) != len(batch):
            raise StoreError("embedder returned a different number of vectors", expected=len(batch), got=len(got))
        out.extend(got)
    return out, calls


# ------------------------------------------------------------------ rendered chunk documents

def rendered_key(family: Family, entity_id: str, sha256: str) -> str:
    return f"vector-sync/{family.value}/{entity_id}/{sha256}.json"


def chunks_digest(chunks: Sequence[Chunk]) -> str:
    body = json.dumps([c.model_dump(mode="json") for c in chunks], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def put_rendered(doc: RenderedChunks) -> str:
    """Publisher side: store ``doc`` with its integrity data; returns the S3 key."""
    sealed = doc.model_copy(update={"chunks_sha256": doc.digest()})
    body = sealed.model_dump_json().encode()
    key = rendered_key(doc.family, doc.entity_id, doc.content_sha256)
    ddb.client("s3").put_object(Bucket=ddb.data_bucket(), Key=key, Body=body, ContentType="application/json",
                                ChecksumAlgorithm="SHA256", Metadata={"sha256": hashlib.sha256(body).hexdigest()})
    return key


def load_rendered(family: Family, entity_id: str, sha256: str) -> RenderedChunks:
    """Read and verify the rendered chunk document: body checksum (object metadata), the document's own ``chunks_sha256`` and
    that it describes this (family, entity, sha256). A document with neither checksum is refused."""
    bucket, key, s3 = ddb.data_bucket(), rendered_key(family, entity_id, sha256), ddb.client("s3")
    try:
        head = s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
            raise NotFound(f"rendered chunks missing: {key}") from None
        raise
    body_sha = (head.get("Metadata") or {}).get("sha256")
    if body_sha:
        body = ddb.resolve_ref({"bucket": bucket, "key": key, "sha256": body_sha, "bytes": head["ContentLength"]})
    else:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    try:
        doc = RenderedChunks.model_validate_json(body)
    except ValidationError as exc:
        raise StoreError(f"rendered chunks {key} are malformed", errors=[e["msg"] for e in exc.errors()[:3]]) from None
    if (doc.family, doc.entity_id, doc.content_sha256) != (family, entity_id, sha256):
        raise StoreError("rendered chunks describe another entity or hash", key=key)
    if doc.chunks_sha256 is None and not body_sha:
        raise StoreError("rendered chunks carry no checksum", key=key)
    if doc.chunks_sha256 is not None and doc.chunks_sha256 != doc.digest():
        raise StoreError("rendered chunks checksum mismatch", key=key)
    return doc


# ------------------------------------------------------------------ DynamoDB Stream records -> events

_DES = TypeDeserializer()
_ATTR_TYPES = {"S", "N", "B", "SS", "NS", "BS", "M", "L", "NULL", "BOOL"}


def _image(raw: dict | None) -> dict | None:
    """A stream image as a plain dict, whether it is already deserialised or in raw attribute-value form."""
    if not raw:
        return None
    pk = raw.get("PK")
    if isinstance(pk, dict) and len(pk) == 1 and next(iter(pk)) in _ATTR_TYPES:
        return ddb.decode({k: _DES.deserialize(v) for k, v in raw.items()})
    return raw


def _view(image: dict | None) -> ItemView | None:
    if image is None or image.get("SK") != "META" or image.get("type") not in STREAM_OWNERS:
        return None
    return ItemView.model_validate(image)


def _state_matches(view: ItemView, owner: Owner, sha: str | None) -> bool:
    state = view.state(owner.state_attr)
    return bool(state and state.keys and sha and state.sha256 == sha)


def events_from_record(record: dict, *, loader: Loader | None = None) -> list[VectorSyncEvent]:
    """Events for one stream record: empty unless a render hash changed or publication flipped (see module doc)."""
    arn = record.get("eventSourceARN")
    if arn and ":table/mb-content-" not in arn:
        return []
    body = record.get("dynamodb") or {}
    old, new = _view(_image(body.get("OldImage"))), _view(_image(body.get("NewImage")))
    ref = new or old
    if ref is None:
        return []
    load = loader or load_rendered
    seq = body.get("SequenceNumber")
    events: list[VectorSyncEvent] = []
    for owner in STREAM_OWNERS[ref.type]:
        # a node's search chunks exist only for nodes that carry a search_vector_state
        if owner.family == Family.TAXONOMY_SEARCH and not ((new and new.search_vector_state) or (old and old.search_vector_state)):
            continue
        if new is None:
            old_state = old.state(owner.state_attr) if old else None
            if old_state and old_state.keys:
                events.append(VectorSyncEvent(family=owner.family, entity_id=ref.entity_id, op="withdraw",
                                              content_sha256=old.render_sha or "removed", old_keys=old_state.keys, sequence_number=seq))
            continue
        sha = new.render_sha
        new_state = new.state(owner.state_attr)
        if not new.published:
            flipped = old is not None and old.published
            leftovers = old is None and bool(new_state and new_state.keys)
            if flipped or leftovers:
                events.append(VectorSyncEvent(family=owner.family, entity_id=new.entity_id, op="withdraw",
                                              content_sha256=sha or "withdrawn", old_keys=new_state.keys if new_state else [],
                                              sequence_number=seq))
            continue
        changed = old is None or not old.published or old.render_sha != sha
        if not changed or sha is None or _state_matches(new, owner, sha):
            continue
        doc = load(owner.family, new.entity_id, sha)
        events.append(VectorSyncEvent(family=owner.family, entity_id=new.entity_id, op="upsert", content_sha256=sha,
                                      chunks=doc.chunks, old_keys=new_state.keys if new_state else [], sequence_number=seq))
    return events


def events_from_stream_records(records: Iterable[dict], *, loader: Loader | None = None) -> list[VectorSyncEvent]:
    return [e for r in records for e in events_from_record(r, loader=loader)]


# ------------------------------------------------------------------ applying events

def _load(owner: Owner, entity_id: str) -> tuple[ItemView, dict] | None:
    raw = ddb.get_item("content", owner.pk(entity_id), "META", consistent=True)
    return None if raw is None else (ItemView.model_validate(raw), raw)


def _write_state(owner: Owner, loaded: tuple[ItemView, dict], keys: list[str], sha: str, *, expect_sha: str | None) -> bool:
    """Store ``vector_state`` (CAS on ``version``, retried when only the version moved). False: superseded by a newer render."""
    view, raw = loaded
    doc = StateDoc(index=Family(owner.family).index_name, keys=keys, model=EMBEDDING_MODEL, sha256=sha).model_dump(mode="json")
    for _ in range(STATE_ATTEMPTS):
        cond = ddb.Cond("#rs = :rs", {"#rs": view.render_attr}, {":rs": expect_sha}) if expect_sha and view.render_attr else None
        try:
            if view.version is not None:
                if owner.model is not None:
                    typed.update(owner.model, view.PK, view.SK, view.version, {owner.state_attr: doc}, cond=cond)
                else:
                    ddb.cas_update("content", view.PK, view.SK, view.version, {owner.state_attr: doc}, cond=cond)
            elif owner.model is not None:
                typed.put(owner.model.from_item({**raw, owner.state_attr: doc}), cond=cond)
            else:
                raise StoreError(f"{owner.item_type} item has no version and no typed model", PK=view.PK)
            return True
        except ConditionFailed:
            return False
        except RevisionConflict:
            fresh = _load(owner, view.entity_id)
            if fresh is None or (expect_sha and fresh[0].render_sha != expect_sha):
                return False
            view, raw = fresh
    raise StoreError("vector_state update kept losing the version race", PK=view.PK)


def _validate_chunks(event: VectorSyncEvent) -> dict[str, dict[str, Any]]:
    model = meta_model(event.family)
    out: dict[str, dict[str, Any]] = {}
    for c in event.chunks:
        if not c.text.strip():
            raise ValidationFailed("chunk text is empty", key=c.key)
        try:
            out[c.key] = model.model_validate(c.metadata).to_metadata()
        except ValidationError as exc:
            raise ValidationFailed(f"{event.family.value}: metadata of {c.key!r} invalid",
                                   errors=[{"loc": ".".join(map(str, e["loc"])), "msg": e["msg"]} for e in exc.errors()[:3]]) from None
    return out


def _withdraw(owner: Owner, event: VectorSyncEvent, loaded: tuple[ItemView, dict] | None, store: VectorStore) -> EventOutcome:
    out = EventOutcome(family=event.family, entity_id=event.entity_id, op="withdraw", status="unchanged", sequence_number=event.sequence_number)
    state = loaded[0].state(owner.state_attr) if loaded else None
    keys = list(dict.fromkeys([*(state.keys if state else []), *event.old_keys]))
    if not keys:
        return out
    if loaded and state and state.keys:
        _write_state(owner, loaded, [], state.sha256 or event.content_sha256, expect_sha=None)
    out.deleted = store.delete(owner.family, keys)
    out.status = "withdrawn"
    return out


def _apply_one(event: VectorSyncEvent, store: VectorStore, embedder: BatchEmbedder) -> EventOutcome:
    owner = OWNERS.get(event.family)
    if owner is None:
        raise ValidationFailed(f"{event.family.value} has no mb-content owner for vector sync")
    out = EventOutcome(family=event.family, entity_id=event.entity_id, op=event.op, status="unchanged", sequence_number=event.sequence_number)
    loaded = _load(owner, event.entity_id)
    if event.op == "withdraw" or (loaded and not loaded[0].published):
        return _withdraw(owner, event, loaded, store)
    if loaded is None:
        out.status = "skipped"
        return out
    view = loaded[0]
    if view.render_sha != event.content_sha256:
        out.status = "superseded"
        return out
    state = view.state(owner.state_attr)
    new_keys = [c.key for c in event.chunks]
    if state and state.sha256 == event.content_sha256 and set(state.keys) == set(new_keys):
        return out

    metas = _validate_chunks(event)
    sha_key = CHUNK_SHA_KEY.get(event.family)
    existing = {i.key: i for i in store.get(event.family, new_keys, with_data=True)}
    todo: list[Chunk] = []
    reuse: dict[str, VectorItem] = {}
    for c in event.chunks:
        have = existing.get(c.key)
        if have is not None and have.vector and sha_key and sha_key in metas[c.key] and have.metadata.get(sha_key) == metas[c.key][sha_key]:
            reuse[c.key] = have
        else:
            todo.append(c)
    fresh, out.embed_calls = _embed_all([c.text for c in todo], embedder)
    vectors = {c.key: v for c, v in zip(todo, fresh, strict=True)}
    out.embedded, out.reused = len(todo), len(reuse)

    items = []
    for c in event.chunks:
        if c.key in reuse and dict(reuse[c.key].metadata) == metas[c.key]:
            continue
        items.append(VectorItem(key=c.key, vector=vectors.get(c.key) or reuse[c.key].vector, metadata=metas[c.key]))
    out.written = store.put(event.family, items) if items else 0

    if not _write_state(owner, loaded, new_keys, event.content_sha256, expect_sha=event.content_sha256):
        out.status = "superseded"
        return out
    stale = [k for k in dict.fromkeys([*(state.keys if state else []), *event.old_keys]) if k not in set(new_keys)]
    out.deleted = store.delete(event.family, stale) if stale else 0
    out.status = "synced"
    return out


def _default_store() -> VectorStore:
    from mathbank_rest.vector_store import S3VectorsStore

    return get_vector_store() if uses_s3_vectors() else S3VectorsStore()


def apply_events(events: Iterable[VectorSyncEvent], *, store: VectorStore | None = None,
                 embedder: BatchEmbedder | None = None) -> SyncResult:
    """Apply events in order; a failing event is reported in the result (status ``failed``) and does not stop the others."""
    store = store or _default_store()
    embedder = embedder or BATCH_EMBEDDER
    result = SyncResult()
    for ev in events:
        try:
            result.outcomes.append(_apply_one(ev, store, embedder))
        except Exception as exc:
            LOG.warning("vector sync failed for %s %s", ev.family.value, ev.entity_id, exc_info=True)
            result.outcomes.append(EventOutcome(family=ev.family, entity_id=ev.entity_id, op=ev.op, status="failed",
                                                error=f"{type(exc).__name__}: {str(exc)[:300]}", sequence_number=ev.sequence_number))
    return result


# ------------------------------------------------------------------ Lambda entry point

def handler(event: dict, context: Any = None) -> dict:
    """Stream batch handler with partial-batch responses. A record that fails (mapping, S3 read, embedding, write) is returned
    in ``batchItemFailures``, as is every later record of the same item in the batch, so per-item order is preserved."""
    failures: list[dict[str, str]] = []
    blocked: set[str] = set()
    for rec in event.get("Records", []):
        body = rec.get("dynamodb") or {}
        seq = body.get("SequenceNumber") or rec.get("eventID") or ""
        keys = _image(body.get("Keys")) or {}
        item = keys.get("PK", "")
        if item in blocked:
            failures.append({"itemIdentifier": seq})
            continue
        try:
            result = apply_events(events_from_record(rec))
            error = result.failed[0].error if result.failed else None
        except Exception as exc:
            LOG.warning("vector sync could not map record %s", seq, exc_info=True)
            error = f"{type(exc).__name__}: {str(exc)[:300]}"
        if error:
            LOG.error("vector sync record %s failed: %s", seq, error)
            failures.append({"itemIdentifier": seq})
            if item:
                blocked.add(item)
    return {"batchItemFailures": failures}
