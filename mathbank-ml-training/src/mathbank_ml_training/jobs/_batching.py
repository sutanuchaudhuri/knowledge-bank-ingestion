"""Batching helper used by every job in this package (requirements/57 §3).

requirements/57 §3 — non-negotiable: every job must commit in bounded batches, never one
unbatched transaction across the whole student population (the exact lesson from this
session's own GOTCHAS.md §25 — the Neo4j canonical projector's original unbatched
DETACH DELETE only became safe once batched; the Postgres equivalent here is the same
principle, chunked INSERT ... ON CONFLICT, not one giant statement).
"""
from __future__ import annotations

from collections.abc import Callable, Iterable


def run_in_batches(rows: Iterable[dict], batch_size: int, on_batch: Callable[[list[dict]], None]) -> int:
    """TODO (requirements/57 §3): implement. Must be safe to interrupt mid-run — i.e.
    each batch's `on_batch` call should be its own committed transaction, so a kill at
    batch N leaves batches 1..N-1 durably applied and batch N+1..end simply not yet run
    (not a half-applied batch N). Returns the total row count processed.
    """
    raise NotImplementedError("requirements/57 §3 — batching helper")
