import pytest

from mathbank_rest.db.step_search import build_search_sql


def test_learning_item_search_always_requires_published_no_proof():
    sql, params = build_search_sql("learning_item", {}, semantic=True, lexical=True)
    assert "li.review_status = 'APPROVED' AND li.student_visible AND li.no_proof" in sql
    assert params["kinds"] == ["LEARNING_ITEM_QUESTION", "LEARNING_ITEM_SKILL_SIGNATURE"]


def test_recovery_filters_are_hard_filters_with_bound_values():
    sql, params = build_search_sql(
        "learning_item",
        {"target_skill_node_id": "SKILL'; DROP TABLE x;--", "difficulty": "LOWER", "learning_item_type": None},
        semantic=False,
        lexical=True,
    )
    assert "c.skill_node_id = :target_skill_node_id" in sql
    assert "li.difficulty_direction = :difficulty" in sql
    assert "DROP TABLE" not in sql
    assert params["target_skill_node_id"].startswith("SKILL'")
    assert "learning_item_type" not in params
    eligible = sql.split("semantic_ranked")[0]
    assert ":target_skill_node_id" in eligible, "filters must apply before ranking"


def test_step_search_uses_exact_distance_over_filtered_candidates():
    sql, _ = build_search_sql("step", {"skill_node_id": "SKILL.1"}, semantic=True, lexical=False)
    assert "s.publication_status = 'PUBLISHED'" in sql
    assert "CAST(:query_vector AS public.vector)" in sql
    assert "vector(1536)" not in sql


def test_unknown_filter_and_no_ranking_are_rejected():
    with pytest.raises(ValueError, match="Unsupported"):
        build_search_sql("step", {"target_skill_node_id": "X"}, semantic=True, lexical=True)
    with pytest.raises(ValueError, match="At least one"):
        build_search_sql("step", {}, semantic=False, lexical=False)


def test_step_technique_filter_is_bound_and_approved_only():
    from mathbank_rest.db import step_search

    sql, params = step_search.build_search_sql(
        "step", {"technique_node_id": "TECH.GEO.INVERSION"}, semantic=False, lexical=True)
    assert "pedagogy.solution_step_technique" in sql and ":technique_node_id" in sql
    assert "t.review_status = 'APPROVED'" in sql and "TECH.GEO.INVERSION" not in sql
    assert params["technique_node_id"] == "TECH.GEO.INVERSION"


def test_taxonomy_search_keys_on_metadata_node_id_and_binds_filters():
    sql, params = build_search_sql(
        "taxonomy", {"node_types": ["TECHNIQUE"], "chapter_number": 3}, semantic=True, lexical=True)
    eligible = sql.split("semantic AS")[0]
    assert "n.taxonomy_node_id AS entity_id" in eligible
    assert "c.metadata->>'taxonomy_node_id'" in eligible
    assert "n.node_type = ANY(:node_types)" in eligible and "n.chapter_number = :chapter_number" in eligible
    assert params["kinds"] == ["TAXONOMY_NODE"] and params["node_types"] == ["TECHNIQUE"]
    assert "TECHNIQUE'" not in sql


def test_taxonomy_search_rejects_unknown_node_type_before_querying():
    from mathbank_rest.db import step_search

    with pytest.raises(ValueError, match="Unsupported node type"):
        step_search.search_taxonomy_nodes("x", node_types=["PROBLEM"], semantic=False)


def test_concept_search_route_falls_back_to_lexical_with_warning(monkeypatch):
    from fastapi.testclient import TestClient

    from mathbank_rest.db import step_search
    from mathbank_rest.main import app

    calls = []

    def fake(query, *, semantic, lexical, **kwargs):
        calls.append(semantic)
        if semantic:
            raise RuntimeError("embedding provider down")
        return [{"taxonomy_node_id": "GEO.C03.S10"}]

    monkeypatch.setattr(step_search, "search_taxonomy_nodes", fake)
    body = TestClient(app).post("/v1/search/concepts", json={"query": " radical axis "}).json()
    assert calls == [True, False]
    assert body["results"] == [{"taxonomy_node_id": "GEO.C03.S10"}]
    assert body["retrieval"]["semantic"] == "unavailable" and body["warnings"]


def test_concept_search_route_validates_node_types():
    from fastapi.testclient import TestClient

    from mathbank_rest.main import app

    response = TestClient(app).post("/v1/search/concepts", json={"query": "x", "node_types": ["PROBLEM"]})
    assert response.status_code == 422
