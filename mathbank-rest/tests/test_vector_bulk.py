"""Bulk vector operations (vector_bulk.py): boto3 engine on the memory store, metadata parsing (the real-AWS Bodo test is tests/stores/test_vector_bulk_integration.py)."""
from __future__ import annotations

import random

import pytest

from mathbank_rest import vector_bulk as vb
from mathbank_rest.stores.errors import ValidationFailed
from mathbank_rest.vector_catalog import DIMENSIONS, Family, LearningItemMeta
from mathbank_rest.vector_store import MemoryVectorStore, VectorItem, vf


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


def li(i: int, *, optional: bool = True) -> VectorItem:
    meta = LearningItemMeta(kind="Q", learning_item_id=f"li{i}", content_sha256="c" * 64,
                            target_skill_node_id=f"S{i % 3}" if optional and i % 4 else None,
                            anchor_step_ids=["a", "b"] if optional and i % 3 == 0 else None,
                            difficulty_direction="LOWER" if optional and i % 2 else None)
    return VectorItem(key=f"k{i:03d}", vector=vec(i), metadata=meta.to_metadata())


def test_engine_resolution(monkeypatch):
    assert vb.resolve_engine("boto3") == "boto3"
    monkeypatch.setattr(vb, "bodo_available", lambda: False)
    assert vb.resolve_engine("auto") == "boto3"
    with pytest.raises(RuntimeError, match="mathbank-rest\\[bulk\\]"):
        vb.resolve_engine("bodo")
    monkeypatch.setattr(vb, "bodo_available", lambda: True)
    assert vb.resolve_engine("auto") == "bodo"


def test_boto3_engine_validates_then_writes_and_queries_in_order():
    st = MemoryVectorStore()
    res = vb.bulk_put(Family.LEARNING_ITEM, [li(i) for i in range(30)], engine="boto3", store=st)
    assert (res.engine, res.written) == ("boto3", 30)
    qs = [vec(3), vec(7), vec(11)]
    out = vb.bulk_query(Family.LEARNING_ITEM, qs, top_k=4, filter=vf.eq("kind", "Q"), engine="boto3", store=st)
    assert [hits[0].key for hits in out] == ["k003", "k007", "k011"]
    assert out[1] == st.query(Family.LEARNING_ITEM, qs[1], 4, vf.eq("kind", "Q"))
    assert vb.bulk_query(Family.LEARNING_ITEM, [], engine="boto3", store=st) == []


def test_bulk_put_rejects_invalid_metadata_before_any_write():
    st = MemoryVectorStore()
    bad = VectorItem(key="x", vector=vec(1), metadata={"kind": "Q"})                 # missing required keys
    with pytest.raises(ValidationFailed):
        vb.bulk_put(Family.LEARNING_ITEM, [li(1), bad], engine="boto3", store=st)
    assert list(st.keys(Family.LEARNING_ITEM)) == []


def test_bulk_query_checks_filter_and_top_k():
    st = MemoryVectorStore()
    with pytest.raises(ValidationFailed):
        vb.bulk_query(Family.LEARNING_ITEM, [vec(1)], top_k=500, engine="boto3", store=st)
    with pytest.raises(ValidationFailed):
        vb.bulk_query(Family.LEARNING_ITEM, [vec(1)], filter=vf.eq("learning_item_id", "x"), engine="boto3", store=st)


def test_bodo_metadata_comes_back_as_python_repr_and_is_parsed_safely():
    raw = "{'anchor_step_ids': ['x', 'y'], 'is_checkpoint': True, 'hint_level': 3, 'kind': 'Q'}"
    assert vb._parse_metadata(raw) == {"anchor_step_ids": ["x", "y"], "is_checkpoint": True, "hint_level": 3, "kind": "Q"}
    assert vb._parse_metadata({"a": 1}) == {"a": 1} and vb._parse_metadata(None) == {} and vb._parse_metadata("") == {}
    for evil in ("__import__('os').system('true')", "[1, 2]", "open('/etc/passwd')"):
        with pytest.raises((ValueError, SyntaxError, TypeError)):
            vb._parse_metadata(evil)
