"""Vector store adapter (requirement 71 §2.5): one protocol, an S3 Vectors implementation and an in-memory exact one.

    store = get_vector_store()
    hits = store.query(Family.PROBLEM, vector, top_k=50, filter=vf.and_(vf.eq("competition", "IMO"), vf.gte("year", 2010)))
    items = store.get(Family.STEP, keys)
    store.put(Family.STEP, [VectorItem(key=..., vector=..., metadata=StepMeta(...).to_metadata())])
    store.delete(Family.STEP, keys)

Contract notes (verified against the real service):
* ``QueryVectors`` returns at most **100** results and silently clamps a larger ``topK``; the adapter rejects ``top_k > 100``
  instead. ``GetVectors`` takes <= 100 keys, ``PutVectors``/``DeleteVectors`` <= 500 (the adapter chunks).
* A filter may only use *filterable* metadata keys; the adapter checks the filter against the family's metadata model before
  the call. On list-valued metadata ``$eq``/``$in`` match when any element matches.
* ``distance`` is cosine distance (0 identical, 2 opposite); ``VectorHit.similarity`` is ``1 - distance``.
* Metadata values are string / number / boolean / list of strings only (no null, no empty list), <= 40 KB, <= 2 KB filterable.
* No scan semantics exist: ``keys()`` (list) is for reconciliation and tests, never request paths.

This module deliberately has no Postgres implementation: with ``VECTOR_STORE=pgvector`` the legacy SQL paths in ``db/*search*``
stay untouched, so the flag is also the rollback.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Protocol, runtime_checkable

from botocore.exceptions import ClientError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from mathbank_rest.config import settings
from mathbank_rest.stores import ddb
from mathbank_rest.stores.errors import NotFound, StoreError, StoreUnavailable, ValidationFailed
from mathbank_rest.vector_catalog import DIMENSIONS, Family, meta_model

MAX_TOP_K = 100
GET_BATCH = 100
WRITE_BATCH = 500
MAX_METADATA_BYTES = 40 * 1024
MAX_FILTERABLE_BYTES = 2 * 1024

MetaValue = StrictStr | StrictInt | StrictFloat | StrictBool | list[StrictStr]
OPERATORS = {"$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin", "$exists"}
LOGICAL = {"$and", "$or"}


# ------------------------------------------------------------------ filter builders (S3 Vectors filter JSON)

class vf:
    @staticmethod
    def eq(key: str, value: Any) -> dict:
        return {key: {"$eq": value}}

    @staticmethod
    def ne(key: str, value: Any) -> dict:
        return {key: {"$ne": value}}

    @staticmethod
    def gt(key: str, value: float) -> dict:
        return {key: {"$gt": value}}

    @staticmethod
    def gte(key: str, value: float) -> dict:
        return {key: {"$gte": value}}

    @staticmethod
    def lt(key: str, value: float) -> dict:
        return {key: {"$lt": value}}

    @staticmethod
    def lte(key: str, value: float) -> dict:
        return {key: {"$lte": value}}

    @staticmethod
    def in_(key: str, values: Sequence[Any]) -> dict:
        return {key: {"$in": list(values)}}

    @staticmethod
    def nin(key: str, values: Sequence[Any]) -> dict:
        return {key: {"$nin": list(values)}}

    @staticmethod
    def exists(key: str, present: bool = True) -> dict:
        return {key: {"$exists": present}}

    @staticmethod
    def and_(*parts: dict | None) -> dict | None:
        live = [p for p in parts if p]
        return None if not live else live[0] if len(live) == 1 else {"$and": live}

    @staticmethod
    def or_(*parts: dict | None) -> dict | None:
        live = [p for p in parts if p]
        return None if not live else live[0] if len(live) == 1 else {"$or": live}


def filter_keys(flt: dict) -> set[str]:
    """Every metadata key a filter references; raises ValidationFailed for a malformed filter."""
    keys: set[str] = set()

    def walk(node: Any) -> None:
        if not isinstance(node, dict) or not node:
            raise ValidationFailed("vector filter must be a non-empty object")
        for k, v in node.items():
            if k in LOGICAL:
                if not isinstance(v, list) or not v:
                    raise ValidationFailed(f"{k} needs a non-empty list")
                for part in v:
                    walk(part)
            elif k.startswith("$"):
                raise ValidationFailed(f"unknown filter operator {k}")
            else:
                keys.add(k)
                if isinstance(v, dict):
                    bad = set(v) - OPERATORS
                    if bad:
                        raise ValidationFailed(f"unknown filter operator {sorted(bad)}", key=k)

    walk(flt)
    return keys


def check_filter(family: Family, flt: dict | None) -> None:
    if flt is None:
        return
    model = meta_model(family)
    unknown = filter_keys(flt) - model.filterable()
    if unknown:
        raise ValidationFailed(f"{family.value}: cannot filter on {sorted(unknown)}", filterable=sorted(model.filterable()))


# ------------------------------------------------------------------ models

class VectorItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=1024)
    vector: list[float] | None = None
    metadata: dict[str, MetaValue] = Field(default_factory=dict)

    @field_validator("vector")
    @classmethod
    def _vector(cls, v: list[float] | None) -> list[float] | None:
        if v is None:
            return v
        if len(v) != DIMENSIONS:
            raise ValueError(f"vector has {len(v)} dimensions, expected {DIMENSIONS}")
        if not all(math.isfinite(x) for x in v):
            raise ValueError("vector contains NaN or infinity")
        if not any(abs(x) > 1e-12 for x in v):
            raise ValueError("vector norm is too small for cosine distance")
        return v

    @model_validator(mode="after")
    def _metadata_size(self) -> VectorItem:
        if len(json.dumps(self.metadata, separators=(",", ":")).encode()) > MAX_METADATA_BYTES:
            raise ValueError("metadata exceeds 40 KB")
        return self


class VectorHit(BaseModel):
    key: str
    distance: float
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def similarity(self) -> float:
        return 1.0 - self.distance


def _validated_items(family: Family, items: Iterable[VectorItem]) -> list[VectorItem]:
    model = meta_model(family)
    out = []
    for it in items:
        if it.vector is None:
            raise ValidationFailed("put needs the vector", key=it.key)
        try:
            model.model_validate(it.metadata)
        except ValidationError as exc:
            raise ValidationFailed(f"{family.value}: metadata of {it.key!r} invalid",
                                   errors=[{"loc": ".".join(map(str, e["loc"])), "msg": e["msg"]} for e in exc.errors()[:3]]) from None
        filterable = {k: v for k, v in it.metadata.items() if k in model.filterable()}
        if len(json.dumps(filterable, separators=(",", ":")).encode()) > MAX_FILTERABLE_BYTES:
            raise ValidationFailed(f"{family.value}: filterable metadata of {it.key!r} exceeds 2 KB")
        out.append(it)
    return out


def _chunks(seq: Sequence[Any], n: int) -> Iterator[Sequence[Any]]:
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


@runtime_checkable
class VectorStore(Protocol):
    def query(self, family: Family, vector: Sequence[float], top_k: int = 10, filter: dict | None = None) -> list[VectorHit]: ...
    def get(self, family: Family, keys: Iterable[str], *, with_data: bool = True) -> list[VectorItem]: ...
    def put(self, family: Family, items: Iterable[VectorItem]) -> int: ...
    def delete(self, family: Family, keys: Iterable[str]) -> int: ...
    def keys(self, family: Family) -> Iterator[str]: ...


def _check_query(family: Family, vector: Sequence[float], top_k: int, flt: dict | None) -> None:
    if not 1 <= top_k <= MAX_TOP_K:
        raise ValidationFailed(f"top_k must be 1..{MAX_TOP_K} (the service clamps larger values)", top_k=top_k)
    if len(vector) != DIMENSIONS:
        raise ValidationFailed(f"query vector has {len(vector)} dimensions, expected {DIMENSIONS}")
    check_filter(family, flt)


# ------------------------------------------------------------------ S3 Vectors

def _translate(exc: ClientError, what: str) -> StoreError:
    code = exc.response.get("Error", {}).get("Code", "")
    msg = exc.response.get("Error", {}).get("Message", "")
    if code in ("ThrottlingException", "TooManyRequestsException", "ServiceUnavailableException", "InternalServerException",
                "ServiceQuotaExceededException", "RequestTimeout"):
        return StoreUnavailable(f"vector store busy ({what}: {code})")
    if code in ("NotFoundException", "ResourceNotFoundException"):
        return NotFound(f"vector index or bucket missing ({what})")
    if code == "ValidationException":
        return ValidationFailed(f"vector store rejected {what}: {msg[:200]}")
    if code in ("AccessDeniedException", "UnrecognizedClientException", "ExpiredTokenException"):
        return StoreUnavailable(f"vector store access denied ({what}): {ddb.credential_hint()}")
    return StoreUnavailable(f"vector store error ({what}: {code})")


class S3VectorsStore:
    """``VectorStore`` over the ``mathbank-vectors-<env>`` bucket; one index per ``Family``."""

    def __init__(self, bucket: str | None = None, client: Any = None) -> None:
        self._bucket = bucket
        self._client = client

    @property
    def bucket(self) -> str:
        return self._bucket or settings.vector_bucket or f"mathbank-vectors-{ddb.env_for('vectors')}"

    @property
    def c(self) -> Any:
        return self._client or ddb.client("s3vectors")

    def _call(self, op: str, **kw: Any) -> Any:
        try:
            return getattr(self.c, op)(vectorBucketName=self.bucket, **kw)
        except ClientError as exc:
            raise _translate(exc, op) from None

    def query(self, family: Family, vector: Sequence[float], top_k: int = 10, filter: dict | None = None) -> list[VectorHit]:
        _check_query(family, vector, top_k, filter)
        kw: dict[str, Any] = {"indexName": family.index_name, "queryVector": {"float32": [float(x) for x in vector]},
                              "topK": top_k, "returnDistance": True, "returnMetadata": True}
        if filter:
            kw["filter"] = filter
        r = self._call("query_vectors", **kw)
        return [VectorHit(key=v["key"], distance=float(v.get("distance", 0.0)), metadata=v.get("metadata") or {})
                for v in r.get("vectors", [])]

    def get(self, family: Family, keys: Iterable[str], *, with_data: bool = True) -> list[VectorItem]:
        out: list[VectorItem] = []
        for chunk in _chunks(list(dict.fromkeys(keys)), GET_BATCH):
            r = self._call("get_vectors", indexName=family.index_name, keys=list(chunk), returnData=with_data, returnMetadata=True)
            for v in r.get("vectors", []):
                out.append(VectorItem.model_construct(key=v["key"], vector=(v.get("data") or {}).get("float32"),
                                                      metadata=v.get("metadata") or {}))
        return out

    def put(self, family: Family, items: Iterable[VectorItem]) -> int:
        batch = _validated_items(family, items)
        for chunk in _chunks(batch, WRITE_BATCH):
            self._call("put_vectors", indexName=family.index_name,
                       vectors=[{"key": i.key, "data": {"float32": [float(x) for x in i.vector or []]}, "metadata": i.metadata}
                                for i in chunk])
        return len(batch)

    def delete(self, family: Family, keys: Iterable[str]) -> int:
        ks = list(dict.fromkeys(keys))
        for chunk in _chunks(ks, WRITE_BATCH):
            self._call("delete_vectors", indexName=family.index_name, keys=list(chunk))
        return len(ks)

    def keys(self, family: Family) -> Iterator[str]:
        token = None
        while True:
            kw: dict[str, Any] = {"indexName": family.index_name, "maxResults": 500}
            if token:
                kw["nextToken"] = token
            r = self._call("list_vectors", **kw)
            for v in r.get("vectors", []):
                yield v["key"]
            token = r.get("nextToken")
            if not token:
                return


# ------------------------------------------------------------------ in-memory exact store

def _num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def matches(meta: dict[str, Any], flt: dict | None) -> bool:
    """Evaluate an S3 Vectors filter against metadata (list values match when any element matches)."""
    if not flt:
        return True
    for k, cond in flt.items():
        if k == "$and":
            if not all(matches(meta, p) for p in cond):
                return False
        elif k == "$or":
            if not any(matches(meta, p) for p in cond):
                return False
        else:
            have = meta.get(k)
            ops = cond if isinstance(cond, dict) else {"$eq": cond}
            for op, want in ops.items():
                items = have if isinstance(have, list) else [have]
                if op == "$exists":
                    ok = (k in meta) == bool(want)
                elif have is None:
                    ok = op in ("$ne", "$nin")
                elif op == "$eq":
                    ok = want in items
                elif op == "$ne":
                    ok = want not in items
                elif op == "$in":
                    ok = any(x in want for x in items)
                elif op == "$nin":
                    ok = not any(x in want for x in items)
                else:
                    ok = _num(have) and _num(want) and {"$gt": have > want, "$gte": have >= want,
                                                        "$lt": have < want, "$lte": have <= want}[op]
                if not ok:
                    return False
    return True


def cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na, nb = math.sqrt(sum(x * x for x in a)), math.sqrt(sum(y * y for y in b))
    return 1.0 - dot / (na * nb)


class MemoryVectorStore:
    """Exact brute-force store with the same contract as S3 Vectors: tests, and ground truth for the recall gate."""

    def __init__(self) -> None:
        self._data: dict[Family, dict[str, VectorItem]] = {}

    def query(self, family: Family, vector: Sequence[float], top_k: int = 10, filter: dict | None = None) -> list[VectorHit]:
        _check_query(family, vector, top_k, filter)
        scored = [VectorHit(key=i.key, distance=cosine_distance(vector, i.vector or []), metadata=dict(i.metadata))
                  for i in self._data.get(family, {}).values() if matches(i.metadata, filter)]
        scored.sort(key=lambda h: (h.distance, h.key))
        return scored[:top_k]

    def get(self, family: Family, keys: Iterable[str], *, with_data: bool = True) -> list[VectorItem]:
        store = self._data.get(family, {})
        return [i if with_data else VectorItem.model_construct(key=i.key, vector=None, metadata=i.metadata)
                for k in dict.fromkeys(keys) if (i := store.get(k))]

    def put(self, family: Family, items: Iterable[VectorItem]) -> int:
        batch = _validated_items(family, items)
        self._data.setdefault(family, {}).update({i.key: i for i in batch})
        return len(batch)

    def delete(self, family: Family, keys: Iterable[str]) -> int:
        ks = list(dict.fromkeys(keys))
        for k in ks:
            self._data.get(family, {}).pop(k, None)
        return len(ks)

    def keys(self, family: Family) -> Iterator[str]:
        yield from sorted(self._data.get(family, {}))


# ------------------------------------------------------------------ selection

_override: VectorStore | None = None
_default: S3VectorsStore | None = None


def uses_s3_vectors() -> bool:
    """True when searches go through the adapter; False keeps the legacy pgvector SQL paths (and is the rollback)."""
    return _override is not None or settings.vector_store == "s3vectors"


def get_vector_store() -> VectorStore:
    global _default
    if _override is not None:
        return _override
    if settings.vector_store != "s3vectors":
        raise StoreUnavailable("VECTOR_STORE is pgvector; the vector adapter is only used with VECTOR_STORE=s3vectors")
    if _default is None:
        _default = S3VectorsStore()
    return _default


def set_vector_store_for_tests(store: VectorStore | None) -> None:
    global _override, _default
    _override, _default = store, None
