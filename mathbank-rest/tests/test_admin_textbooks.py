"""Offline tests for the admin textbook corpus browser (requirements/24)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import mathbank_rest.config as config_module
from mathbank_rest.db import textbook_admin as t
from mathbank_rest.main import app
from mathbank_rest.routers import admin_textbooks

client = TestClient(app)
ADMIN = {"X-Admin-Api-Key": config_module.settings.admin_api_key}


@pytest.mark.parametrize("path", [
    "/v1/admin/textbooks/coverage", "/v1/admin/textbooks/problems", "/v1/admin/textbooks/problems/X",
    "/v1/admin/textbooks/learning-items", "/v1/admin/textbooks/taxonomy", "/v1/admin/textbooks/taxonomy/X",
    "/v1/admin/textbooks/diagrams/PRASOLOV-S-1_9-D01/image",
])
def test_every_route_requires_admin_key(path: str) -> None:
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"X-Admin-Api-Key": "wrong"}).status_code == 401


def test_validation_rejects_bad_parameters() -> None:
    assert client.get("/v1/admin/textbooks/problems?limit=0", headers=ADMIN).status_code == 422
    assert client.get("/v1/admin/textbooks/problems?book=drop;table", headers=ADMIN).status_code == 422
    assert client.get("/v1/admin/textbooks/taxonomy?node_type=WIDGET", headers=ADMIN).status_code == 422
    assert client.get("/v1/admin/textbooks/diagrams/bad%20id/image", headers=ADMIN).status_code == 422


def test_problem_404_and_list_passthrough(monkeypatch) -> None:
    monkeypatch.setattr(admin_textbooks, "_read", lambda fn, *a, **k: None if fn is t.problem_detail else
                        {"total": 0, "items": [], "kw": sorted(k)})
    assert client.get("/v1/admin/textbooks/problems/NOPE", headers=ADMIN).status_code == 404
    body = client.get("/v1/admin/textbooks/problems?chapter=3&q=chord&has_diagram=true", headers=ADMIN).json()
    assert body["kw"] == ["book", "chapter", "has_diagram", "has_solution", "limit", "node", "offset", "q"]


def test_build_matrix_flags_gaps_and_provenance() -> None:
    source = {"problem": 10, "solution_step": 5, "taxonomy_node": 4, "legacy_transformation": 9}
    pg = {"problem": 10, "solution_step": 5, "taxonomy_node": 4, "taxonomy_node_linked": 3}
    vec = {"problem": 10, "solution_step": 4, "taxonomy_node": 0}
    graph = {"ok": True, "problem": 10, "solution_step": 5, "taxonomy_node": 3}
    rows = {r["entity"]: r for r in t.build_matrix(source, pg, vec, graph)}
    assert rows["problem"]["status"] == "OK"
    assert rows["solution_step"]["gaps"] == ["vector"]
    # graph is compared against linked taxonomy nodes, so only the vector gap remains
    assert rows["taxonomy_node"]["gaps"] == ["vector"] and rows["taxonomy_node"]["graph_expected"] == 3
    assert rows["legacy_transformation"]["status"] == "PROVENANCE" and rows["legacy_transformation"]["source_rows"] == 9
    assert rows["diagram"]["expected"] == ["pg"] and rows["diagram"]["status"] == "OK"


def test_build_matrix_learning_item_concept_links_are_graph_only() -> None:
    rows = {r["entity"]: r for r in t.build_matrix(
        {}, {"learning_item_concept": 4}, {}, {"ok": True, "learning_item_concept": 3})}
    row = rows["learning_item_concept"]
    assert row["expected"] == ["pg", "graph"] and row["vector"] is None
    assert row["gaps"] == ["graph"] and row["status"] == "GAP"


def test_build_matrix_graph_unobserved_is_unknown() -> None:
    rows = {r["entity"]: r for r in t.build_matrix({}, {"problem": 1}, {"problem": 1}, {"ok": False})}
    assert rows["problem"]["status"] == "UNKNOWN" and rows["problem"]["graph"] is None


def test_graph_counts_never_raises() -> None:
    class Broken:
        def session(self):
            raise RuntimeError("down")
    assert t.graph_counts("PRASOLOV_PGV1", Broken()) == {"ok": False, "error": "RuntimeError"}


def test_diagram_path_refuses_files_outside_root(tmp_path: Path) -> None:
    inside = tmp_path / "repo" / "d.png"
    inside.parent.mkdir()
    inside.write_bytes(b"png")
    outside = tmp_path / "elsewhere.png"
    outside.write_bytes(b"png")

    class Conn:
        def __init__(self, value):
            self.value = value

        def execute(self, *_):
            return self

        def scalar(self):
            return self.value

    root = (tmp_path / "repo").resolve()
    assert t.diagram_path(Conn(str(inside)), "B", "x", root) == inside.resolve()
    assert t.diagram_path(Conn(str(outside)), "B", "x", root) is None
    assert t.diagram_path(Conn(None), "B", "x", root) is None


def test_build_matrix_step_technique_compares_pg_tags_with_graph_edges() -> None:
    rows = {r["entity"]: r for r in t.build_matrix(
        {}, {"step_technique": 4354}, {}, {"ok": True, "step_technique": 4354})}
    assert rows["step_technique"]["status"] == "OK"
