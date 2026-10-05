"""Strict PDF split validation and HMMT classifier discovery."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import classify_pdf_corpus as classifier
from crawl_pdf_papers import validate_question_ids
from export_classifications_to_csv import matches_papers

from mathbank.crawl.pdf_parser import render_pdf_pages
from mathbank.crawl.pdf_parser import split_questions
import crawl_pdf_papers as crawler


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


def test_download_rejects_html_disguised_as_pdf(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(crawler, "_session", lambda: SimpleNamespace(
        get=lambda *args, **kwargs: SimpleNamespace(
            status_code=200, headers={"Content-Type": "application/pdf"},
            content=b"<html>not a PDF</html>",
        )
    ))
    with pytest.raises(crawler.DownloadError, match="not a PDF document"):
        crawler._fetch_pdf("https://example.test/paper.pdf", 0)


def test_postscript_converter_missing_is_explicit(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(crawler.DownloadError, match="requires Ghostscript"):
        crawler._convert_postscript(b"%!PS\nshowpage", "https://example.test/paper.ps")


def test_postscript_conversion_produces_readable_pdf():
    import shutil
    import pymupdf
    if not shutil.which("gs"):
        pytest.skip("Ghostscript not installed")
    data = crawler._convert_postscript(
        b"%!PS-Adobe-3.0\n/Helvetica findfont 12 scalefont setfont\n"
        b"72 720 moveto (Question 1. Compute 2+2.) show\nshowpage\n",
        "https://example.test/paper.ps",
    )
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        assert "Compute 2+2" in doc[0].get_text()


def test_question_boundaries_ignore_premature_numeric_lines():
    text = "1. First question.\n15. A number inside the first question.\n"
    text += "".join(f"{n}. Actual question {n}.\n" for n in range(2, 16))
    blocks = split_questions(text, "SMT", 15)
    assert len(blocks) == 15
    assert "A number inside" in blocks[1]
    assert blocks[14] == "14. Actual question 14."
    assert blocks[15] == "15. Actual question 15."
    assert all(block.strip() for block in blocks.values())


def test_repaired_smt_registry_uses_official_document_names():
    import csv
    registry = Path(__file__).resolve().parents[1] / "src/mathbank/data/maths_corpus/paper_registry.csv"
    with registry.open() as stream:
        rows = {row["Paper_ID"]: row for row in csv.DictReader(stream)}
    for code, subject in [
        ("ALG", "algebra"), ("CALC", "calculus"), ("DISCRETE", "discrete"),
        ("GEOM", "geometry"), ("GENERAL", "general"),
    ]:
        assert rows[f"PAPER_SMT_2019_{code}"]["Problem_URL"].endswith(f"/{subject}-exam.pdf")
        assert rows[f"PAPER_SMT_2019_TB_{code}"]["Problem_URL"].endswith(f"/{subject}-tiebreaker.pdf")
    assert rows["PAPER_SMT_2019_TEAM"]["Problem_URL"].endswith("/team-exam.pdf")
    assert rows["PAPER_SMT_2019_POWER"]["Problem_URL"].endswith("/power-exam.pdf")
    assert rows["PAPER_SMT_2014_POWER"]["Problem_URL"].endswith("/thuemorse-problems.pdf")
    assert rows["PAPER_SMT_2014_POWER"]["Solution_URL"].endswith("/thuemorse-solutions.pdf")
