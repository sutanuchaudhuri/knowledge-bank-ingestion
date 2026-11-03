"""Query-embedding cache layers and the typed mb-content reader used by vector search (requirement 71 §2.5)."""
from __future__ import annotations

import datetime as dt
import uuid

import pytest

from mathbank_rest import content_lookup as cl
from mathbank_rest import embeddings
from mathbank_rest.config import settings
from mathbank_rest.models.ddb.content import ContentProblem, ContentStep
from mathbank_rest.models.manual.content_runtime import ContentQemb
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.vector_catalog import DIMENSIONS


@pytest.fixture()
def content(ddb):
    """moto: add the content table next to learner/exam."""
    ddb.create_table(
        TableName="mb-content-ut",
        AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("PK", "SK")],
        KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        BillingMode="PAY_PER_REQUEST",
    )
    embeddings.reset_for_tests()
    yield ddb
    embeddings.reset_for_tests()


def fake_embedder(calls: list):
    def embed(text: str) -> list[float]:
        calls.append(text)
        return [float((len(text) + i) % 7) + 0.5 for i in range(DIMENSIONS)]

    return embed


# ------------------------------------------------------------------ embeddings

def test_pack_unpack_round_trips_float32():
    v = [0.5, -1.25, 3.0] + [0.0] * (DIMENSIONS - 3)
    assert embeddings.unpack(embeddings.pack(v)) == v


def test_cache_key_depends_on_model_and_text_only():
    assert embeddings.cache_key("a") == embeddings.cache_key("a") != embeddings.cache_key("b") != embeddings.cache_key("a", "other-model")
    assert len(embeddings.cache_key("a")) == 64


def test_lru_serves_repeat_queries_without_the_provider(content, monkeypatch):
    monkeypatch.setattr(settings, "vector_store", "pgvector")                   # no shared cache, no AWS
    calls: list = []
    monkeypatch.setattr(embeddings, "EMBEDDER", fake_embedder(calls))
    a, b = embeddings.embed_text("  power of a point "), embeddings.embed_text("power of a point")
    assert a == b and len(calls) == 1                                          # trimmed text hits the same entry
    a[0] = 99.0
    assert embeddings.embed_text("power of a point")[0] != 99.0                # callers get a copy


def test_shared_cache_is_written_then_read_by_another_process(content, monkeypatch):
    monkeypatch.setattr(settings, "vector_store", "s3vectors")
    calls: list = []
    monkeypatch.setattr(embeddings, "EMBEDDER", fake_embedder(calls))
    v1 = embeddings.embed_text("inversion")
    key = embeddings.cache_key("inversion")
    stored = typed.require(ContentQemb, f"QEMB#{key}", "V")
    assert stored.dims == DIMENSIONS and stored.model == "text-embedding-3-small" and stored.ttl and stored.ttl > toolkit.epoch_after(29)
    raw = toolkit.get_item("content", f"QEMB#{key}", "V")
    assert raw["type"] == "QEMB" and "vector" not in raw and "student_id" not in raw     # nothing identifies a caller
    embeddings.reset_for_tests()                                               # a fresh Lambda: empty LRU
    assert embeddings.embed_text("inversion") == pytest.approx(v1) and len(calls) == 1


def test_a_failing_shared_cache_never_blocks_search(content, monkeypatch):
    monkeypatch.setattr(settings, "vector_store", "s3vectors")
    calls: list = []
    monkeypatch.setattr(embeddings, "EMBEDDER", fake_embedder(calls))
    monkeypatch.setattr(typed, "get", lambda *a, **k: (_ for _ in ()).throw(toolkit.StoreUnavailable("down")))
    monkeypatch.setattr(typed, "put", lambda *a, **k: (_ for _ in ()).throw(toolkit.StoreUnavailable("down")))
    assert len(embeddings.embed_text("tangent circles")) == DIMENSIONS and len(calls) == 1


def test_paid_calls_still_respect_the_rate_limit_gate(content, monkeypatch):
    from mathbank_rest import rate_limit

    monkeypatch.setattr(settings, "vector_store", "pgvector")
    monkeypatch.setattr(embeddings, "EMBEDDER", fake_embedder([]))
    with rate_limit.embeddings_blocked(), pytest.raises(rate_limit.EmbeddingsNotPermitted):
        embeddings.embed_text("never embedded")


def test_bad_embedder_output_and_empty_text_are_rejected(content, monkeypatch):
    monkeypatch.setattr(settings, "vector_store", "pgvector")
    monkeypatch.setattr(embeddings, "EMBEDDER", lambda t: [1.0, 2.0])
    with pytest.raises(ValueError, match="dimensions"):
        embeddings.embed_text("x")
    with pytest.raises(ValueError, match="empty"):
        embeddings.embed_text("   ")


# ------------------------------------------------------------------ content lookup

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def put_problem(code: str, *, visibility: str = "ACTIVE", vector_keys: list[str] | None = None):
    typed.put(ContentProblem.model_validate({
        "PK": f"PROBLEM#{code}", "SK": "META", "type": "PROBLEM", "canonical_code": code, "competition": {
            "competition_id": str(uuid.uuid4()), "external_code": "IMO", "level": "X", "name": "IMO"},
        "content_sha256": "c" * 64, "created_at": NOW, "images": [], "paper_code": "P", "paper_id": str(uuid.uuid4()),
        "problem_id": str(uuid.uuid4()), "problem_number": 1, "src_rev": 1, "updated_at": NOW, "visibility": visibility,
        "concepts": [], "techniques": [],
        "vector_state": {"index": "problem-te3small-1536-v1", "keys": vector_keys or [], "model": "text-embedding-3-small", "sha256": "s" * 64},
    }))


def test_problems_by_code_returns_typed_items_and_skips_missing(content):
    k = str(uuid.uuid4())
    put_problem("IMO_2020_P1", vector_keys=[k])
    got = cl.problems_by_code(["IMO_2020_P1", "NOPE", "IMO_2020_P1"])
    assert list(got) == ["IMO_2020_P1"] and isinstance(got["IMO_2020_P1"], ContentProblem)


def test_a_hit_is_current_only_when_published_and_its_vector_is_live(content):
    live, old = str(uuid.uuid4()), str(uuid.uuid4())
    put_problem("A", vector_keys=[live])
    put_problem("B", visibility="WITHDRAWN", vector_keys=[live])
    items = cl.problems_by_code(["A", "B"])
    assert cl.hit_is_current(items["A"], live)
    assert not cl.hit_is_current(items["A"], old)                              # re-embedded: the old vector is stale
    assert not cl.hit_is_current(items["B"], live)                             # withdrawn
    assert not cl.hit_is_current(None, live)                                   # deleted entity


def test_step_eligibility_uses_the_eligible_flag(content):
    sid, vk = "BOOK/STEP-1", str(uuid.uuid4())
    base = {"PK": f"STEP#{sid}", "SK": "META", "type": "STEP", "book_code": "B", "concept_node_id": "C", "content_sha256": "c" * 64,
            "global_step_index": 1, "hint_level": 1, "is_checkpoint": False, "problem_code": "P", "problem_id": str(uuid.uuid4()),
            "skill_name": "s", "skill_node_id": "S", "solution_id": str(uuid.uuid4()), "solution_part_id": "MAIN", "solution_step_id": sid,
            "src_rev": 1, "step_index_in_part": 1, "step_type": "T", "subconcept_node_id": "SC", "technique_node_ids": [],
            "tutor_role": "CORE_BRIDGE", "updated_at": NOW,
            "vector_state": {"index": "step-te3small-1536-v1", "keys": [vk], "model": "text-embedding-3-small", "sha256": "s" * 64}}
    typed.put(ContentStep.model_validate({**base, "eligible": True}))
    assert cl.hit_is_current(cl.steps_by_id([sid])[sid], vk)
    typed.put(ContentStep.model_validate({**base, "eligible": False}))
    assert not cl.hit_is_current(cl.steps_by_id([sid])[sid], vk)
