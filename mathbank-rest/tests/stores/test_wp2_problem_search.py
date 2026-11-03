"""WP2 problem search on S3 Vectors + mb-content: code lookup first, vector ranking, eligibility re-check, hydration, hybrid with
graph, and the legacy path untouched when the flag is off. MemoryVectorStore + moto, no AWS, no Postgres."""
from __future__ import annotations

import datetime as dt
import random
import uuid

import pytest

from mathbank_rest import embeddings
from mathbank_rest.config import settings
from mathbank_rest.db import hybrid_search
from mathbank_rest.db import problem_search_vectors as psv
from mathbank_rest.models.ddb.content import ContentProblem
from mathbank_rest.stores import typed
from mathbank_rest.vector_catalog import DIMENSIONS, Family, ProblemMeta
from mathbank_rest.vector_store import MemoryVectorStore, VectorItem, set_vector_store_for_tests

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def vec(seed: int) -> list[float]:
    r = random.Random(seed)
    return [r.uniform(-1, 1) for _ in range(DIMENSIONS)]


@pytest.fixture()
def world(ddb, monkeypatch):
    ddb.create_table(TableName="mb-content-ut", AttributeDefinitions=[{"AttributeName": a, "AttributeType": "S"} for a in ("PK", "SK")],
                     KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
                     BillingMode="PAY_PER_REQUEST")
    store = MemoryVectorStore()
    set_vector_store_for_tests(store)
    monkeypatch.setattr(settings, "vector_store", "s3vectors")
    embeddings.reset_for_tests()
    queries: list[str] = []
    seeds = {"inversion": 1, "tangent circles": 2, "parity": 3}
    monkeypatch.setattr(embeddings, "EMBEDDER", lambda t: (queries.append(t), vec(seeds.get(t, 99)))[1])
    yield store, queries
    set_vector_store_for_tests(None)
    embeddings.reset_for_tests()


def add(store, code: str, seed: int, *, comp: str = "IMO", year: int | None = 2010, visibility: str = "ACTIVE", chunks: int = 1,
        stale: bool = False, statement: str | None = None) -> list[str]:
    keys = [str(uuid.uuid4()) for _ in range(chunks)]
    typed.put(ContentProblem.model_validate({
        "PK": f"PROBLEM#{code}", "SK": "META", "type": "PROBLEM", "canonical_code": code, "problem_number": int(code[-1]),
        "competition": {"competition_id": str(uuid.uuid4()), "external_code": comp, "level": "L", "name": f"{comp} name"},
        "content_sha256": "c" * 64, "created_at": NOW, "images": [], "paper_code": f"{comp}-{year}", "paper_id": str(uuid.uuid4()),
        "problem_id": str(uuid.uuid4()), "src_rev": 1, "updated_at": NOW, "visibility": visibility, "concepts": [], "techniques": [],
        "statement_text": statement or f"Statement of {code}", "source_url": f"https://x/{code}", **({"year": year} if year else {}),
        "vector_state": {"index": Family.PROBLEM.index_name, "keys": [str(uuid.uuid4())] if stale else keys,
                         "model": "text-embedding-3-small", "sha256": "s" * 64}}))
    store.put(Family.PROBLEM, [
        VectorItem(key=k, vector=vec(seed if i == 0 else seed + 500 + i), metadata=ProblemMeta(
            competition=comp, year=year, problem_id=str(uuid.uuid4()), chunk_kind="FULL", canonical_code=code, content_sha256="s" * 64,
            chunk_ordinal=i, representation_id="r").to_metadata()) for i, k in enumerate(keys)])
    return keys


def codes(rows) -> list[str]:
    return [r["canonical_code"] for r in rows]


def test_semantic_search_ranks_by_similarity_and_returns_the_legacy_row_shape(world):
    store, _ = world
    add(store, "IMO_2010_P1", 1), add(store, "IMO_2010_P2", 2), add(store, "IMO_2010_P3", 3)
    rows = psv.search_problems("inversion", limit=3)
    assert codes(rows) == ["IMO_2010_P1", *[c for c in codes(rows)[1:]]] and rows[0]["semantic_rank"] == 1
    assert rows[0]["rrf_score"] == pytest.approx(1.0) and rows[0]["lexical_rank"] is None
    assert set(rows[0]) == {"canonical_code", "problem_number", "statement_text", "source_url", "competition", "competition_code",
                            "year", "paper_code", "rrf_score", "semantic_rank", "lexical_rank"}
    assert rows[0]["statement_text"] == "Statement of IMO_2010_P1" and rows[0]["competition"] == "IMO name" and rows[0]["competition_code"] == "IMO"


def test_an_exact_canonical_code_is_found_first_without_being_nearest(world):
    store, _ = world
    add(store, "IMO_2010_P1", 1), add(store, "AMC_2011_P2", 2, comp="AMC", year=2011)
    rows = psv.search_problems("amc_2011_p2", limit=5)                          # lower-case code, query vector is nowhere near it
    assert rows[0]["canonical_code"] == "AMC_2011_P2" and rows[0]["semantic_rank"] == 1 and rows[0]["rrf_score"] == 1.0
    assert not psv.looks_like_code("tangent circles") and not psv.looks_like_code("power of a point 2") and psv.looks_like_code("IMO_2020_P1")


def test_filters_apply_in_the_index_and_again_on_the_authoritative_item(world):
    store, _ = world
    add(store, "IMO_2005_P1", 1, year=2005), add(store, "IMO_2015_P2", 1, year=2015), add(store, "AMC_2015_P3", 1, comp="AMC", year=2015)
    assert codes(psv.search_problems("inversion", competition="IMO", year_min=2010)) == ["IMO_2015_P2"]
    assert sorted(codes(psv.search_problems("inversion", year_max=2005))) == ["IMO_2005_P1"]
    assert codes(psv.search_problems("inversion", competition="IMO", order_by="year_asc")) == ["IMO_2005_P1", "IMO_2015_P2"]
    assert codes(psv.search_problems("inversion", competition="IMO", order_by="year_desc")) == ["IMO_2015_P2", "IMO_2005_P1"]


def test_withdrawn_stale_and_missing_content_never_surface(world):
    store, _ = world
    add(store, "IMO_2010_P1", 1)
    add(store, "IMO_2010_P2", 1, visibility="WITHDRAWN")
    add(store, "IMO_2010_P3", 1, stale=True)                                    # re-embedded: this vector is no longer current
    store.put(Family.PROBLEM, [VectorItem(key="orphan", vector=vec(1), metadata=ProblemMeta(
        competition="IMO", year=2010, problem_id="p", chunk_kind="FULL", canonical_code="IMO_2010_P9", content_sha256="s",
        chunk_ordinal=0, representation_id="r").to_metadata())])                 # entity deleted from mb-content
    assert codes(psv.search_problems("inversion")) == ["IMO_2010_P1"]


def test_a_problem_with_several_chunks_appears_once_with_its_best_chunk(world):
    store, _ = world
    add(store, "IMO_2010_P1", 1, chunks=3), add(store, "IMO_2010_P2", 2)
    rows = psv.search_problems("inversion", limit=10)
    assert codes(rows).count("IMO_2010_P1") == 1 and rows[0]["canonical_code"] == "IMO_2010_P1"


def test_offloaded_statement_is_fetched_only_for_returned_rows(world):
    store, _ = world
    big = "S" * 40_000
    add(store, "IMO_2010_P1", 1, statement=big)
    rows = psv.search_problems("inversion", limit=1)
    assert rows[0]["statement_text"] == big


def test_semantic_false_returns_nothing_and_makes_no_paid_call(world):
    store, queries = world
    add(store, "IMO_2010_P1", 1)
    assert psv.search_problems("inversion", semantic=False) == [] and queries == []


def test_query_embeddings_are_cached_between_searches(world):
    store, queries = world
    add(store, "IMO_2010_P1", 1)
    psv.search_problems("inversion"), psv.search_problems("inversion")
    assert queries == ["inversion"]


# ------------------------------------------------------------------ hybrid (vector + graph), flag routing

def test_hybrid_fuses_graph_hydrates_from_content_and_reports_lexical(world, monkeypatch):
    store, _ = world
    add(store, "IMO_2010_P1", 1), add(store, "IMO_2010_P2", 2), add(store, "AMC_2012_P3", 3, comp="AMC", year=2012)
    monkeypatch.setattr(hybrid_search, "graph_candidates", lambda q, seeds, eligible, limit: [
        {"canonical_code": "AMC_2012_P3", "evidence": [{"slug": "parity"}]}, {"canonical_code": "IMO_2010_P2", "evidence": []}])
    out = hybrid_search.search_problems("inversion", limit=5)
    assert out["retrieval"]["engine"] == "s3vectors" and out["retrieval"]["lexical_applied"] is False and out["retrieval"]["graph"] == "queried"
    assert any("Lexical retrieval is not available" in w for w in out["warnings"])
    by = {r["canonical_code"]: r for r in out["results"]}
    assert set(by) == {"IMO_2010_P1", "IMO_2010_P2", "AMC_2012_P3"}
    assert by["AMC_2012_P3"]["graph_rank"] == 1 and by["AMC_2012_P3"]["graph_evidence"] == [{"slug": "parity"}] and by["AMC_2012_P3"]["semantic_rank"] is not None
    assert by["IMO_2010_P2"]["rrf_score"] > by["IMO_2010_P1"]["rrf_score"] - 1                      # fused score present
    assert by["IMO_2010_P1"]["statement_text"] == "Statement of IMO_2010_P1" and by["IMO_2010_P1"]["competition_code"] == "IMO"
    assert out["results"][0]["rrf_score"] >= out["results"][-1]["rrf_score"]


def test_hybrid_post_filters_graph_candidates_with_the_request_filters(world, monkeypatch):
    store, _ = world
    add(store, "IMO_2010_P1", 1), add(store, "AMC_2012_P3", 3, comp="AMC", year=2012)
    monkeypatch.setattr(hybrid_search, "graph_candidates", lambda q, seeds, eligible, limit: [{"canonical_code": "AMC_2012_P3", "evidence": []}])
    out = hybrid_search.search_problems("inversion", competition="IMO", limit=5)
    assert [r["canonical_code"] for r in out["results"]] == ["IMO_2010_P1"]


def test_hybrid_survives_a_graph_outage_with_a_warning(world, monkeypatch):
    from neo4j.exceptions import ServiceUnavailable

    store, _ = world
    add(store, "IMO_2010_P1", 1)
    monkeypatch.setattr(hybrid_search, "graph_candidates", lambda *a, **k: (_ for _ in ()).throw(ServiceUnavailable("down")))
    out = hybrid_search.search_problems("inversion", limit=5)
    assert out["results"][0]["canonical_code"] == "IMO_2010_P1" and out["retrieval"]["graph"] == "unavailable"
    assert any(w.startswith("Graph retrieval unavailable") for w in out["warnings"])


def test_vector_search_entry_point_routes_to_the_adapter_and_never_touches_postgres(world, monkeypatch):
    from mathbank_rest.db import vector_search

    store, _ = world
    add(store, "IMO_2010_P1", 1)
    monkeypatch.setattr(vector_search, "engine", type("NoPg", (), {"connect": lambda self: (_ for _ in ()).throw(AssertionError("Postgres used"))})())
    assert codes(vector_search.search_problems("inversion", limit=3)) == ["IMO_2010_P1"]


def test_flag_off_keeps_the_legacy_postgres_path(monkeypatch):
    from mathbank_rest.db import vector_search

    monkeypatch.setattr(settings, "vector_store", "pgvector")
    set_vector_store_for_tests(None)
    monkeypatch.setattr(vector_search, "embed_query", lambda q: "[0.1]")
    monkeypatch.setattr(vector_search, "_active_model_id", lambda: "m")
    seen = {}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, params):
            seen["sql"] = str(sql)
            return type("R", (), {"mappings": lambda s: []})()

    monkeypatch.setattr(vector_search, "engine", type("E", (), {"connect": lambda self: Conn()})())
    assert vector_search.search_problems("x") == [] and "search.embedding" in seen["sql"]
