"""Bodo engine of vector_bulk.py against the REAL `test` vector bucket (make test-ddb-integration): optional metadata keys,
metadata survives, filtered query equals exact search and the plain adapter."""
from __future__ import annotations

import os
import random

import pytest

from mathbank_rest import vector_bulk as vb
from mathbank_rest.vector_catalog import DIMENSIONS, Family, LearningItemMeta
from mathbank_rest.vector_store import VectorItem, cosine_distance, vf


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


def li(i: int) -> VectorItem:
    meta = LearningItemMeta(kind="Q", learning_item_id=f"li{i}", content_sha256="c" * 64,
                            target_skill_node_id=f"S{i % 3}" if i % 4 else None,
                            anchor_step_ids=["a", "b"] if i % 3 == 0 else None,
                            difficulty_direction="LOWER" if i % 2 else None)
    return VectorItem(key=f"k{i:03d}", vector=vec(i), metadata=meta.to_metadata())


@pytest.mark.ddb_integration
@pytest.mark.skipif(not vb.bodo_available(), reason="Bodo not installed (pip install 'mathbank-rest[bulk]')")
def test_bodo_engine_handles_optional_metadata_and_matches_exact_search(real_env, monkeypatch):
    from mathbank_rest.config import settings
    from mathbank_rest.vector_store import S3VectorsStore

    monkeypatch.setattr(settings, "vector_bucket", "")
    assert os.getenv("MB_DDB_ENV") == "test"
    store = S3VectorsStore()
    items = [li(i) for i in range(60)]                                              # ragged: optional keys absent on many rows
    keys = [i.key for i in items]
    try:
        res = vb.bulk_put(Family.LEARNING_ITEM, items, engine="bodo")
        assert res.engine == "bodo" and res.written == 60 and res.batches > 1          # grouped by metadata key set
        stored = {i.key: i.metadata for i in store.get(Family.LEARNING_ITEM, keys, with_data=False)}
        assert stored == {i.key: i.metadata for i in items}                            # metadata survived, no nulls invented
        flt = vf.and_(vf.eq("kind", "Q"), vf.eq("difficulty_direction", "LOWER"))
        q = [vec(5), vec(9)]
        hits = vb.bulk_query(Family.LEARNING_ITEM, q, top_k=8, filter=flt, engine="bodo")
        eligible = [i for i in items if i.metadata.get("difficulty_direction") == "LOWER"]
        for qv, got in zip(q, hits, strict=True):
            exact = sorted(eligible, key=lambda it: (cosine_distance(qv, it.vector or []), it.key))[:8]
            assert [h.key for h in got] == [e.key for e in exact]
            assert all(h.metadata["difficulty_direction"] == "LOWER" for h in got)
        assert [h.key for h in hits[0]] == [h.key for h in store.query(Family.LEARNING_ITEM, q[0], 8, flt)]
    finally:
        store.delete(Family.LEARNING_ITEM, keys)
    assert list(store.keys(Family.LEARNING_ITEM)) == []
