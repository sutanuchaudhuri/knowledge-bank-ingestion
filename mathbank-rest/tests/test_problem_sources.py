from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from mathbank_rest.db import problem_sources as sources
from mathbank_rest.routers import step_runtime as routes


def test_cached_problem_pdf_is_embedded_without_exposing_local_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "PDF_ROOT", tmp_path)
    pdf = tmp_path / "smt/PAPER_SMT_2010_GEOM/problem.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF-fixture")
    record = {
        "crawl_dir": "smt",
        "paper_external_code": "PAPER_SMT_2010_GEOM",
        "problem_url": "https://example.test/problem.pdf",
        "source_url": None,
    }
    metadata = sources.source_metadata(record, "PAPER_SMT_2010_GEOM_Q06")
    assert metadata["embed_url"] == "/api/rest/solve/source-pdf/PAPER_SMT_2010_GEOM_Q06"
    assert metadata["kind"] == "pdf"
    assert str(tmp_path) not in str(metadata)
    assert sources.source_pdf(record) == pdf


def test_remote_pdf_and_web_sources_are_distinct():
    pdf = sources.source_metadata({"source_url": "https://example.test/download.PDF?x=1"}, "CODE")
    assert pdf["embed_url"] == pdf["url"] and pdf["kind"] == "pdf"
    web = sources.source_metadata({"source_url": "https://example.test/wiki/Problem"}, "CODE")
    assert web["embed_url"] is None and web["kind"] == "web"
    assert sources.source_metadata({}, "CODE") is None


def test_registered_remote_pdf_need_not_have_a_pdf_filename():
    pdf = sources.source_metadata(
        {"problem_url": "https://example.test/download?id=123", "link_scope": "DIRECT_PROBLEM_PDF"},
        "CODE",
    )
    assert pdf["kind"] == "pdf" and pdf["embed_url"] == pdf["url"]


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "https://user:password@example.test/a.pdf",
        "https://[",
    ],
)
def test_unsafe_source_urls_are_logged_and_not_published(url, caplog):
    assert sources.source_metadata({"source_url": url}, "CODE") is None
    assert "invalid original source URL" in caplog.text


def test_source_pdf_rejects_paths_outside_the_corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "PDF_ROOT", tmp_path)
    with pytest.raises(ValueError, match="outside"):
        sources.source_pdf({"crawl_dir": "../elsewhere", "paper_external_code": "PAPER"})


def test_binary_route_serves_only_recorded_problem_pdf(tmp_path, monkeypatch):
    pdf = tmp_path / "problem.pdf"
    pdf.write_bytes(b"%PDF-fixture")
    monkeypatch.setattr(routes, "engine", MagicMock())
    monkeypatch.setattr(routes, "source_record", lambda conn, code: {"problem": True})
    monkeypatch.setattr(routes, "source_pdf", lambda record: pdf)
    response = routes.get_problem_source_pdf("CODE")
    assert response.media_type == "application/pdf"
    assert str(response.path) == str(pdf)
    assert response.headers["content-disposition"].startswith("inline;")
    monkeypatch.setattr(routes, "source_pdf", lambda record: None)
    with pytest.raises(HTTPException) as error:
        routes.get_problem_source_pdf("CODE")
    assert error.value.status_code == 404


def test_unknown_problem_source_is_404_not_an_empty_success(monkeypatch):
    monkeypatch.setattr(routes, "engine", MagicMock())
    monkeypatch.setattr(routes, "source_record", lambda conn, code: None)
    with pytest.raises(HTTPException) as error:
        routes.get_problem_source("unknown")
    assert error.value.status_code == 404
