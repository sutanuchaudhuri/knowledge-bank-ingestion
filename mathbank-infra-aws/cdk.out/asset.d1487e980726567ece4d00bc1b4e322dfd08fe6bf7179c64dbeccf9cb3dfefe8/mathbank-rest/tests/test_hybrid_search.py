from unittest.mock import MagicMock

from neo4j.exceptions import ServiceUnavailable
from fastapi.testclient import TestClient

from mathbank_rest.db import hybrid_search
from mathbank_rest.main import app


def test_fusion_deduplicates_chunks_and_preserves_source_evidence():
    merged = hybrid_search.fuse(
        [
            {"canonical_code": "A", "semantic_rank": 1, "lexical_rank": None},
            {"canonical_code": "A", "semantic_rank": 2, "lexical_rank": 2},
            {"canonical_code": "B", "semantic_rank": 3, "lexical_rank": 1},
        ],
        [{"canonical_code": "A", "evidence": [{"name": "Synthetic skill"}]}],
    )
    assert len(merged) == 2
    assert merged["A"]["rrf_score"] == 1 / 61 + 1 / 62 + 1 / 61
    assert merged["A"]["graph_rank"] == 1
    assert merged["A"]["graph_evidence"]


def test_graph_outage_is_explicit_degraded_response(monkeypatch):
    monkeypatch.setattr(hybrid_search.vector_search, "search_problems", lambda *a, **k: [])

    def fail(*a, **k):
        raise ServiceUnavailable("offline")

    monkeypatch.setattr(hybrid_search, "graph_candidates", fail)
    result = hybrid_search.search_problems("Synthetic")
    assert result["warnings"]
    assert result["retrieval"]["graph"] == "unavailable"


def test_filters_are_passed_before_graph_candidates(monkeypatch):
    conn = MagicMock()
    conn.__enter__.return_value = conn
    conn.execute.return_value.scalars.return_value = ["ALLOWED"]
    monkeypatch.setattr(hybrid_search.engine, "connect", lambda: conn)
    monkeypatch.setattr(hybrid_search.vector_search, "search_problems", lambda *a, **k: [])
    seen = []
    monkeypatch.setattr(
        hybrid_search,
        "graph_candidates",
        lambda q, seeds, eligible, limit: seen.append(eligible) or [],
    )
    hybrid_search.search_problems("Synthetic", competition="SMT", year_min=2020)
    assert seen == [["ALLOWED"]]
    assert conn.__enter__.return_value.execute.call_args.args[1]["competition"] == "SMT"


def test_graph_only_does_not_call_embeddings(monkeypatch):
    monkeypatch.setattr(
        hybrid_search.vector_search,
        "search_problems",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("vector called")),
    )
    monkeypatch.setattr(hybrid_search, "graph_candidates", lambda *a, **k: [])
    assert (
        hybrid_search.search_problems("Synthetic", semantic=False, lexical=False)["results"] == []
    )


def test_search_contract_validation_and_graph_routing(monkeypatch):
    seen = []
    monkeypatch.setattr(
        hybrid_search,
        "search_problems",
        lambda *a, **k: seen.append(k) or {"results": [], "warnings": []},
    )
    client = TestClient(app)
    assert client.post("/v1/search/problems", json={"query": "circles"}).status_code == 200
    assert seen[0]["graph"] is True
    for payload in [
        {"query": " "},
        {"query": "a", "limit": 0},
        {"query": "a", "order_by": "invalid"},
    ]:
        assert client.post("/v1/search/problems", json=payload).status_code == 422
    assert (
        client.post(
            "/v1/search/problems",
            json={
                "query": "a",
                "retrieval": {"semantic": False, "lexical": False, "graph": False},
            },
        ).status_code
        == 400
    )
