"""Strict PDF split validation and HMMT classifier discovery."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import classify_pdf_corpus as classifier
from crawl_pdf_papers import validate_question_ids
from export_classifications_to_csv import matches_papers

from mathbank.crawl.pdf_parser import render_pdf_pages


def test_strict_split_rejects_partial_cached_or_whole_paper():
    validate_question_ids(["P_Q01", "P_Q02"], "P", 2)
    for ids, expected in [
        ([], None),
        (["P"], None),
        (["P_Q01", "P_Q01"], None),
        (["P_Q02"], None),
        (["P_Q01", "P_Q02"], 10),
    ]:
        with pytest.raises(ValueError):
            validate_question_ids(ids, "P", expected)


def test_hmmt_discovery_and_exact_paper_identity(tmp_path, monkeypatch):
    monkeypatch.setattr(classifier, "PDF_CRAWL_DIR", tmp_path)
    paper = tmp_path / "hmmt_feb/PAPER_HMMT_2025_FEB_GEO/questions/Q01"
    paper.mkdir(parents=True)
    (paper / "problem.md").write_text("# Problem\n\nFind the area.")
    result = classifier.discover_questions("HMMT_FEB")
    assert len(result) == 1
    assert result[0].question_id == "PAPER_HMMT_2025_FEB_GEO_Q01"
    assert result[0].exam_level == "HMMT_FEB"


def test_page_renderer_returns_real_image_paths(tmp_path):
    import pymupdf

    with pymupdf.open() as pdf:
        page = pdf.new_page()
        page.insert_text((72, 72), "Problem 1. Find the area.")
        data = pdf.tobytes()
    paths = render_pdf_pages(data, tmp_path, "problem", dpi=72)
    assert len(paths) == 1
    assert Path(paths[0]).is_file()


def test_scoped_export_ignores_unrelated_and_unlinked_legacy_maps():
    assert matches_papers("PAPER_HMMT_2025_FEB_GEO_Q01", ["PAPER_HMMT_2025_FEB_GEO"])
    assert not matches_papers(None, ["PAPER_HMMT_2025_FEB_GEO"])
    assert not matches_papers("PAPER_CMM_2026_INDIV_Q01", ["PAPER_HMMT_2025_FEB_GEO"])
    assert matches_papers(None, None)
