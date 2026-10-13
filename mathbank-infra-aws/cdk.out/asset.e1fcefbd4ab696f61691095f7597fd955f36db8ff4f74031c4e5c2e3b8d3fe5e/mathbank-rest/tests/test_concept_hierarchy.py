"""Regression test for GOTCHAS.md #16 — concept taxonomy is a tree
(HAS_SUBCONCEPT), so /v1/concepts/{slug}/problems must include descendants,
not just exact-slug tags. Needs a live Postgres (same as test_health.py).
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from mathbank_rest.main import app

client = TestClient(app)


def test_broad_parent_concept_returns_subconcept_tagged_problems() -> None:
    # 'count' (Combinatorics) is a parent concept; classification mostly tags
    # leaves like 'count-subset'/'count-perm'/etc. Before the fix this endpoint
    # only matched the literal 'count' slug and missed almost all of them.
    response = client.get("/v1/concepts/count/problems", params={"limit": 50})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) > 0
    # At least some rows must come from a descendant leaf, not only literal
    # 'count' tags, otherwise the hierarchy walk isn't actually contributing.
    assert any(row["matched_concept_slug"] != "count" for row in rows)
    assert all(row["matched_concept_slug"].startswith("count") for row in rows)


def test_leaf_concept_still_matches_itself() -> None:
    response = client.get("/v1/concepts/count-subset/problems", params={"limit": 10})
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) > 0
    assert all(row["matched_concept_slug"] == "count-subset" for row in rows)
