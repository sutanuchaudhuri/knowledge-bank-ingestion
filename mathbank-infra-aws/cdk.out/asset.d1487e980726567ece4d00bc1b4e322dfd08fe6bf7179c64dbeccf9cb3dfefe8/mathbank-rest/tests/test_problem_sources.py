import hashlib
import json
from unittest.mock import MagicMock

import pymupdf
import pytest
from fastapi import HTTPException

from mathbank_rest.db import problem_sources as sources
from mathbank_rest.routers import step_runtime as routes


def test_known_book_without_document_is_not_reported_as_unknown_source():
    source = sources.source_metadata({"book_title": "Book", "chapter_number": 6, "source_problem_id": "6.76"}, "CODE")
    assert source["kind"] == "identified" and source["label"] == "Book"
    assert source["provenance_status"] == "LOCATION_INCOMPLETE"
    assert source["embed_url"] is None and source["location"] is None
    assert sources.source_metadata({}, "CODE") is None

def test_cached_problem_pdf_is_embedded_without_exposing_local_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, "PDF_ROOT", tmp_path)
    pdf = tmp_path / "smt/PAPER_SMT_2010_GEOM/problem.pdf"
    pdf.parent.mkdir(parents=True)
    with pymupdf.open() as document:
        document.new_page()
        document.save(pdf)
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


def test_unique_source_text_is_highlighted_without_modifying_pdf(tmp_path):
    pdf = tmp_path / "problem.pdf"
    with pymupdf.open() as document:
        page = document.new_page()
        page.insert_text((50, 60), "6. In the diagram below, let OT = 25 and AM = MB = 30.")
        document.save(pdf)
    original = pdf.read_bytes()
    record = {
        "statement_text": "In the diagram below, let OT = 25 and AM = MB = 30.",
        "problem_number": 6,
    }
    location = sources.problem_location(pdf, record, "PAPER_SMT_2010_GEOM_Q06")
    assert location["page"] == 1 and location["rectangles"]
    assert sources.highlighted_page(pdf, location).startswith(b"\x89PNG")
    marked = sources.highlighted_pdf(pdf, location)
    with pymupdf.open(stream=marked, filetype="pdf") as document:
        annotations = list(document[0].annots())
        assert len(annotations) > 0
        assert annotations[0].colors["fill"] == pytest.approx([1, 0.9, 0.2])
        assert annotations[0].opacity == pytest.approx(0.25)
        assert document[0].get_text().startswith("6. In the diagram")
    assert pdf.read_bytes() == original


def test_ambiguous_source_text_never_guesses_a_highlight(tmp_path):
    pdf = tmp_path / "problem.pdf"
    with pymupdf.open() as document:
        for _ in range(2):
            document.new_page().insert_text((50, 60), "In the diagram below find the length.")
        document.save(pdf)
    assert (
        sources.problem_location(
            pdf, {"statement_text": "In the diagram below find the length."}, "CODE"
        )
        is None
    )


def test_extracted_figure_coordinates_require_current_pdf_hash(tmp_path):
    pdf = tmp_path / "problem.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(pdf)
    directory = tmp_path / "questions/Q06/images"
    directory.mkdir(parents=True)
    metadata = {
        "source_side": "problem",
        "question": 6,
        "page": 1,
        "clip": [40, 40, 120, 120],
        "pdf_sha256_prefix": hashlib.sha256(pdf.read_bytes()).hexdigest()[:16],
    }
    file = directory / "problem_figure_test.json"
    file.write_text(json.dumps(metadata))
    record = {"problem_number": 6, "statement_text": "Find MD."}
    assert sources.problem_location(pdf, record, "PAPER_Q06")["page"] == 1
    metadata["pdf_sha256_prefix"] = "stale"
    file.write_text(json.dumps(metadata))
    assert sources.problem_location(pdf, record, "PAPER_Q06") is None


def test_statement_and_continued_diagram_are_highlighted_on_both_pages(tmp_path):
    pdf = tmp_path / "problem.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_text((50, 60), "6. In the diagram below find the length.")
        document.new_page()
        document.save(pdf)
    directory = tmp_path / "questions/Q06/images"
    directory.mkdir(parents=True)
    (directory / "problem_figure_test.json").write_text(
        json.dumps(
            {
                "source_side": "problem",
                "question": 6,
                "page": 2,
                "clip": [40, 40, 120, 120],
                "pdf_sha256_prefix": hashlib.sha256(pdf.read_bytes()).hexdigest()[:16],
            }
        )
    )
    location = sources.problem_location(
        pdf,
        {
            "problem_number": 6,
            "statement_text": "In the diagram below find the length.",
        },
        "PAPER_Q06",
    )
    assert location["page"] == 1
    assert [region["page"] for region in location["pages"]] == [1, 2]
    with pymupdf.open(stream=sources.highlighted_pdf(pdf, location), filetype="pdf") as document:
        assert all(list(page.annots()) for page in document)


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
