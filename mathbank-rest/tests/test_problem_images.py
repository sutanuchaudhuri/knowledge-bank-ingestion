from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from mathbank_rest.db.problem_images import STUDENT_IMAGE_FILTER, list_images
from mathbank_rest.routers import step_runtime as routes


def test_diagram_metadata_does_not_expose_filesystem_paths():
    conn = MagicMock()
    image_id = str(uuid4())
    conn.execute.return_value.mappings.return_value = [
        {"problem_image_id": image_id, "ordinal": 1, "source": "PDF_PROBLEM_PAGE"}
    ]
    images = list_images(conn, "PAPER_SMT_2010_GEOM_Q06")
    assert images[0]["url"] == f"/v1/problem-images/{image_id}"
    assert f"/api/rest/solve/images/{image_id}" in images[0]["markdown"]
    assert "page" in images[0]["alt"]
    assert "local_path" not in images[0]
    assert STUDENT_IMAGE_FILTER in str(conn.execute.call_args.args[0])
    assert "PDF_SOLUTION_PAGE" in STUDENT_IMAGE_FILTER
    assert "STUDENT_PROBLEM" in STUDENT_IMAGE_FILTER


def test_hidden_or_missing_image_is_not_served(monkeypatch):
    conn = MagicMock()
    conn.execute.return_value.scalar.return_value = None
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    monkeypatch.setattr(routes, "engine", engine)
    with pytest.raises(HTTPException) as error:
        routes.get_problem_image(uuid4())
    assert error.value.status_code == 404
    assert STUDENT_IMAGE_FILTER in str(conn.execute.call_args.args[0])


def test_relative_image_is_resolved_against_repository_not_working_directory(tmp_path, monkeypatch):
    image = tmp_path / "assets/problem.png"
    image.parent.mkdir()
    image.write_bytes(b"fixture")
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.scalar.return_value = "assets/problem.png"
    monkeypatch.setattr(routes, "engine", engine)
    monkeypatch.setattr(routes, "IMAGE_ROOT", tmp_path)
    response = routes.get_problem_image(uuid4())
    assert Path(response.path) == image
    conn.execute.return_value.scalar.return_value = "../outside.png"
    with pytest.raises(HTTPException):
        routes.get_problem_image(uuid4())
