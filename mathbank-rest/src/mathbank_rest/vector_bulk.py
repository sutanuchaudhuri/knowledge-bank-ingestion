"""Bulk vector operations for batch tooling: Bodo when installed, the boto3 adapter otherwise (requirement 71 §2.5).

Request paths use ``vector_store`` (boto3, validated, no heavy dependencies). Batch jobs that write or query **many** vectors -
re-index after a model change, the recall gate, similarity generation, the sync worker's backfill - can use Bodo's
auto-parallel ``DataFrame.to_s3_vectors`` / ``Series.ai.query_s3_vectors`` through this module. Bodo is an optional extra
(``pip install 'mathbank-rest[bulk]'``): it brings numba, pyarrow and OpenMPI and must never be part of the Lambda image.

What this wrapper adds around Bodo (each verified against the real service, see requirement 71 §2.5):
* every item is validated with the family's pydantic metadata model first, exactly like ``VectorStore.put``;
* **metadata is grouped by key set**: Bodo builds a struct column, so a key missing on some rows becomes ``null`` and S3 Vectors
  rejects the whole batch ("Metadata values must be strings, numbers, booleans, or arrays"). One uniform batch per key set avoids it;
* query metadata comes back from Bodo as Python-repr strings, parsed with ``ast.literal_eval`` (never ``eval``);
* AWS credentials of the configured profile are exported for Bodo's workers (it does not read ``AWS_PROFILE`` from our settings).
"""
from __future__ import annotations

import ast
import collections
import concurrent.futures as cf
import importlib.util
import os
import time
from collections.abc import Iterable, Sequence
from typing import Any, Literal

from pydantic import BaseModel

from mathbank_rest.config import settings
from mathbank_rest.stores import ddb
from mathbank_rest.vector_catalog import DIMENSIONS, Family
from mathbank_rest.vector_store import (
    MAX_TOP_K,
    S3VectorsStore,
    VectorHit,
    VectorItem,
    VectorStore,
    _check_query,
    _validated_items,
)

Engine = Literal["auto", "bodo", "boto3"]


class BulkWriteResult(BaseModel):
    engine: str
    written: int
    batches: int
    seconds: float


def bodo_available() -> bool:
    return importlib.util.find_spec("bodo") is not None


def resolve_engine(engine: Engine) -> str:
    if engine == "auto":
        return "bodo" if bodo_available() else "boto3"
    if engine == "bodo" and not bodo_available():
        raise RuntimeError("Bodo is not installed: pip install 'mathbank-rest[bulk]'")
    return engine


def _export_credentials() -> None:
    """Bodo's workers use the default credential chain; make the configured profile's credentials visible to them."""
    import boto3

    session = boto3.session.Session(profile_name=settings.aws_profile or None, region_name=settings.ddb_region)
    creds = session.get_credentials()
    if creds is None:
        raise RuntimeError(f"no AWS credentials: {ddb.credential_hint()}")
    frozen = creds.get_frozen_credentials()
    os.environ["AWS_ACCESS_KEY_ID"], os.environ["AWS_SECRET_ACCESS_KEY"] = frozen.access_key, frozen.secret_key
    if frozen.token:
        os.environ["AWS_SESSION_TOKEN"] = frozen.token
    os.environ["AWS_DEFAULT_REGION"] = settings.ddb_region


def _bucket(store: VectorStore | None) -> str:
    return store.bucket if isinstance(store, S3VectorsStore) else S3VectorsStore().bucket


# ------------------------------------------------------------------ write

def bulk_put(family: Family, items: Iterable[VectorItem], *, engine: Engine = "auto", store: VectorStore | None = None) -> BulkWriteResult:
    """Validate and write many vectors. ``store`` (default S3 Vectors) is used by the boto3 engine."""
    batch = _validated_items(family, items)
    which = resolve_engine(engine)
    t0 = time.time()
    if which == "boto3":
        (store or S3VectorsStore()).put(family, batch)
        return BulkWriteResult(engine="boto3", written=len(batch), batches=1, seconds=round(time.time() - t0, 3))
    import bodo.pandas as bd
    import pandas as pd

    _export_credentials()
    groups: dict[tuple[str, ...], list[VectorItem]] = collections.defaultdict(list)
    for it in batch:
        groups[tuple(sorted(it.metadata))].append(it)
    for rows in groups.values():
        df = pd.DataFrame({"key": [r.key for r in rows], "data": [list(map(float, r.vector or [])) for r in rows],
                           "metadata": [dict(r.metadata) for r in rows]})
        bd.from_pandas(df).to_s3_vectors(vector_bucket_name=_bucket(store), index_name=family.index_name, region=settings.ddb_region)
    return BulkWriteResult(engine="bodo", written=len(batch), batches=len(groups), seconds=round(time.time() - t0, 3))


# ------------------------------------------------------------------ query

def _parse_metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if raw is None or raw == "":
        return {}
    parsed = ast.literal_eval(raw)
    if not isinstance(parsed, dict):
        raise TypeError(f"unexpected metadata from Bodo: {raw!r}")
    return parsed


def bulk_query(family: Family, vectors: Sequence[Sequence[float]], *, top_k: int = 10, filter: dict | None = None,
               engine: Engine = "auto", store: VectorStore | None = None, workers: int = 16) -> list[list[VectorHit]]:
    """Top-``top_k`` hits for every query vector, in input order. All queries share one filter."""
    if not vectors:
        return []
    for v in vectors[:1]:
        _check_query(family, v, min(top_k, MAX_TOP_K), filter)
    which = resolve_engine(engine)
    if which == "boto3":
        st = store or S3VectorsStore()
        with cf.ThreadPoolExecutor(min(workers, len(vectors))) as ex:
            return list(ex.map(lambda v: st.query(family, v, top_k, filter), vectors))
    import bodo.pandas as bd
    import pandas as pd

    _export_credentials()
    q = bd.from_pandas(pd.DataFrame({"data": [list(map(float, v)) for v in vectors]}))
    kw: dict[str, Any] = {"vector_bucket_name": _bucket(store), "index_name": family.index_name, "region": settings.ddb_region,
                          "topk": top_k, "return_distance": True, "return_metadata": True}
    if filter:
        kw["filter"] = filter
    out = q.data.ai.query_s3_vectors(**kw)
    frame = pd.DataFrame(out.execute_plan() if hasattr(out, "execute_plan") else out)
    return [[VectorHit(key=k, distance=float(d), metadata=_parse_metadata(m))
             for k, d, m in zip(row["keys"], row["distances"], row["metadata"], strict=True)]
            for _, row in frame.iterrows()]


__all__ = ["DIMENSIONS", "BulkWriteResult", "Engine", "bodo_available", "bulk_put", "bulk_query", "resolve_engine"]
