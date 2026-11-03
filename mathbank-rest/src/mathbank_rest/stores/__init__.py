"""Store selection (requirement 71 §2.2).

One store per bounded context, chosen by flag. Backends:

- ``postgres``  today's SQL (moved verbatim into ``stores/<ctx>/postgres.py`` as the work packages land)
- ``dynamodb``  the data-plane implementation (``stores/<ctx>/dynamodb.py``)
- ``frozen`` / ``frozen:<backend>``  cutover window: reads are served by <backend> (default postgres), every
  write is rejected with 503 Retry-After. A method is a read when its name starts with a READ_PREFIXES entry.

The flag comes from settings (``<CTX>_STORE``) and, when ``STORE_FLAGS_SSM_PREFIX`` is set, from SSM parameter
``<prefix>/<ctx>`` (cached ``STORE_FLAGS_REFRESH_SECONDS``), so a cutover needs no redeploy. There are no dual
writes: a store instance writes to exactly one backend.
"""
from __future__ import annotations

import importlib
import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

from mathbank_rest.config import settings
from mathbank_rest.stores.errors import StoreFrozen, StoreNotImplemented

LOG = logging.getLogger("mathbank_rest.stores")

CONTEXTS: tuple[str, ...] = (
    "content", "learner", "exam", "live", "media", "artifacts", "geometry", "jobs", "notify", "socratic",
    "agent_sessions", "audit",
)
BACKENDS = ("postgres", "dynamodb")
READ_PREFIXES = ("get_", "list_", "read_", "find_", "count_", "exists_", "search_", "load_", "query_", "fetch_")

# ctx -> backend -> "module:Class". Filled as each work package lands its implementation.
IMPLEMENTATIONS: dict[str, dict[str, str]] = {ctx: {} for ctx in CONTEXTS}

_overrides: dict[str, Any] = {}
_cache: dict[str, tuple[float, str]] = {}
_lock = threading.Lock()
_ssm: Any = None


def parse_mode(value: str) -> tuple[str, str]:
    """'postgres' -> ('postgres','postgres'); 'frozen:dynamodb' -> ('frozen','dynamodb'); 'frozen' -> ('frozen','postgres')."""
    v = (value or "postgres").strip().lower()
    if v.startswith("frozen"):
        _, _, backend = v.partition(":")
        backend = backend or "postgres"
        if backend not in BACKENDS:
            raise ValueError(f"invalid frozen backend {backend!r}")
        return "frozen", backend
    if v not in BACKENDS:
        raise ValueError(f"invalid store mode {value!r}; expected one of {BACKENDS} or frozen[:backend]")
    return v, v


def _setting(ctx: str) -> str:
    return getattr(settings, f"{ctx}_store")


def _ssm_client():
    global _ssm
    if _ssm is None:
        import boto3

        _ssm = boto3.client("ssm", region_name=settings.ddb_region)
    return _ssm


def store_mode(ctx: str) -> tuple[str, str]:
    """(mode, backend) for a context: SSM override (cached) else settings."""
    if ctx not in CONTEXTS:
        raise KeyError(f"unknown store context {ctx!r}; expected one of {CONTEXTS}")
    prefix = settings.store_flags_ssm_prefix
    if prefix:
        now = time.monotonic()
        with _lock:
            hit = _cache.get(ctx)
            if hit is None or now - hit[0] > settings.store_flags_refresh_seconds:
                try:
                    value = _ssm_client().get_parameter(Name=f"{prefix}/{ctx}")["Parameter"]["Value"]
                except Exception:  # noqa: BLE001 - a flag read must never take the API down; keep the last value
                    LOG.warning("store flag %s/%s unreadable; using %s", prefix, ctx, "cached value" if hit else "settings")
                    value = hit[1] if hit else _setting(ctx)
                _cache[ctx] = (now, value)
                hit = _cache[ctx]
        return parse_mode(hit[1])
    return parse_mode(_setting(ctx))


class FrozenProxy:
    """Serves reads from the wrapped store and rejects writes with StoreFrozen."""

    def __init__(self, ctx: str, inner: Any):
        self._ctx, self._inner = ctx, inner

    def __getattr__(self, name: str):
        attr = getattr(self._inner, name)
        if name.startswith("_") or not callable(attr) or name.startswith(READ_PREFIXES):
            return attr

        def blocked(*_a, **_k):
            raise StoreFrozen(self._ctx)

        return blocked


def _load(ctx: str, backend: str) -> Any:
    target = IMPLEMENTATIONS[ctx].get(backend)
    if not target:
        raise StoreNotImplemented(f"{ctx}: no {backend} store implementation yet", context=ctx, backend=backend)
    module, _, cls = target.partition(":")
    return getattr(importlib.import_module(module), cls)()


def get_store(ctx: str) -> Any:
    """The store for `ctx` per the current flag. Raises StoreNotImplemented (HTTP 501) when the selected
    backend has no implementation yet, rather than silently falling back to another backend."""
    if ctx in _overrides:
        return _overrides[ctx]
    mode, backend = store_mode(ctx)
    store = _load(ctx, backend)
    return FrozenProxy(ctx, store) if mode == "frozen" else store


@contextmanager
def override_store(ctx: str, store: Any) -> Iterator[Any]:
    """Tests and stubs: use `store` for `ctx` inside the block (no flag lookup)."""
    if ctx not in CONTEXTS:
        raise KeyError(ctx)
    prev = _overrides.get(ctx)
    _overrides[ctx] = store
    try:
        yield store
    finally:
        if prev is None:
            _overrides.pop(ctx, None)
        else:
            _overrides[ctx] = prev


def register_implementation(ctx: str, backend: str, target: str | Callable) -> None:
    """Register 'module:Class' for (ctx, backend); called from each work package's stores/<ctx>/__init__."""
    if ctx not in CONTEXTS or backend not in BACKENDS:
        raise KeyError((ctx, backend))
    IMPLEMENTATIONS[ctx][backend] = target if isinstance(target, str) else f"{target.__module__}:{target.__qualname__}"


def describe() -> dict[str, dict]:
    """Flag state for /health/stores: mode, backend and whether an implementation is registered."""
    out = {}
    for ctx in CONTEXTS:
        try:
            mode, backend = store_mode(ctx)
            out[ctx] = {"mode": mode, "backend": backend, "implemented": backend in IMPLEMENTATIONS[ctx] or ctx in _overrides}
        except Exception as exc:  # noqa: BLE001
            out[ctx] = {"error": str(exc)}
    out["vectors"] = {"backend": settings.vector_store}
    return out


def reset_for_tests() -> None:
    _overrides.clear()
    _cache.clear()
