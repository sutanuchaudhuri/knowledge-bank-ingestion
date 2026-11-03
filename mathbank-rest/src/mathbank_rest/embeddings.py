"""Query embeddings for vector search (requirement 71 §2.5).

``embed_text`` returns the 1536-float ``text-embedding-3-small`` vector of a query, through three layers:
  1. a per-process LRU (no I/O),
  2. the ``QEMB`` item in ``mb-content`` (shared across Lambdas; only when the vector store is S3 Vectors, i.e. DynamoDB is configured),
  3. OpenAI (paid; ``rate_limit.assert_embeddings_allowed`` still applies, so an anonymous caller can never reach it).
The cache key is ``sha256(model || text)``; nothing identifies the caller. ``EMBEDDER`` is replaceable in tests.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import struct
import threading
from collections import OrderedDict
from collections.abc import Callable

from mathbank_rest import rate_limit
from mathbank_rest.config import settings
from mathbank_rest.models.manual.content_runtime import ContentQemb
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.errors import StoreError
from mathbank_rest.vector_catalog import DIMENSIONS, EMBEDDING_MODEL

LOG = logging.getLogger(__name__)
TTL_DAYS = 30
LRU_SIZE = 512
_lru: OrderedDict[str, list[float]] = OrderedDict()
_lock = threading.Lock()
_client = None


def cache_key(text: str, model: str = EMBEDDING_MODEL) -> str:
    return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()


def pack(vector: list[float]) -> str:
    return base64.b64encode(struct.pack(f"<{len(vector)}f", *vector)).decode()


def unpack(b64: str) -> list[float]:
    raw = base64.b64decode(b64)
    return list(struct.unpack(f"<{len(raw) // 4}f", raw))


def _openai(text: str) -> list[float]:
    global _client
    if _client is None:
        from openai import OpenAI

        from mathbank_rest.project_credentials import configure_openai

        _client = OpenAI(api_key=configure_openai())
    return list(_client.embeddings.create(model=EMBEDDING_MODEL, input=[text]).data[0].embedding)


EMBEDDER: Callable[[str], list[float]] = _openai


def _shared_cache_enabled() -> bool:
    return settings.vector_store == "s3vectors"


def embed_text(text: str) -> list[float]:
    text = text.strip()
    if not text:
        raise ValueError("cannot embed empty text")
    key = cache_key(text)
    with _lock:
        if key in _lru:
            _lru.move_to_end(key)
            return list(_lru[key])
    vector = _from_shared_cache(key) if _shared_cache_enabled() else None
    if vector is None:
        rate_limit.assert_embeddings_allowed()
        vector = EMBEDDER(text)
        if len(vector) != DIMENSIONS:
            raise ValueError(f"embedder returned {len(vector)} dimensions, expected {DIMENSIONS}")
        if _shared_cache_enabled():
            _to_shared_cache(key, vector)
    with _lock:
        _lru[key] = vector
        while len(_lru) > LRU_SIZE:
            _lru.popitem(last=False)
    return list(vector)


def _from_shared_cache(key: str) -> list[float] | None:
    try:
        item = typed.get(ContentQemb, f"QEMB#{key}", "V", consistent=False)
    except StoreError:
        LOG.warning("query-embedding cache unavailable; falling back to the provider", exc_info=True)
        return None
    if item is None or item.model != EMBEDDING_MODEL or item.dims != DIMENSIONS:
        return None
    return unpack(item.vector_b64)


def _to_shared_cache(key: str, vector: list[float]) -> None:
    try:
        typed.put(ContentQemb(PK=f"QEMB#{key}", SK="V", model=EMBEDDING_MODEL, dims=len(vector), vector_b64=pack(vector),
                              created_at=ddb.now_iso(), ttl=ddb.epoch_after(TTL_DAYS)))
    except StoreError:
        LOG.warning("could not write the query-embedding cache", exc_info=True)


def reset_for_tests() -> None:
    global _client
    with _lock:
        _lru.clear()
    _client = None
