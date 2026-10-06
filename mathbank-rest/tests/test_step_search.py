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
