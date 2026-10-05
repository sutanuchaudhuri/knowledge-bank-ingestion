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
from mathbank.crawl.pdf_parser import question_page_numbers


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


def test_legacy_official_pdf_header_may_have_leading_whitespace():
    from mathbank.crawl.pdf_format import has_pdf_header
    assert has_pdf_header(b"\r\n        %PDF-1.5\n")
    assert not has_pdf_header(b"<html>%PDF-1.5 fake</html>")


def test_docling_markdown_headings_are_real_question_boundaries():
    text = "## Contest title\n\n## Problem 1\nSynthetic question one.\n\n## Problem 2\nSynthetic question two."
    assert set(split_questions(text, "PURPLE_MS", 2)) == {1, 2}


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


def test_page_spans_preserve_shared_pages_and_continuation_diagrams():
    import pymupdf
    with pymupdf.open() as pdf:
        pdf.new_page().insert_text((72, 72), "1. Synthetic first question.")
        pdf.new_page().insert_text((72, 72), "Continuation and vector diagram.")
        pdf.new_page().insert_text((72, 72), "2. Synthetic second question.")
        data = pdf.tobytes()
    spans = question_page_numbers(data, 2)
    assert 1 in spans[1] and 2 in spans[1]
    assert spans[2] == [3]
    with pytest.raises(ValueError, match="Cannot locate all"):
        question_page_numbers(data, 3)


def test_purple_divisions_are_supported_by_download_and_classification():
    assert {"PURPLE_MS", "PURPLE_HS"} <= crawler.PDF_COMPETITIONS
    assert classifier.PDF_COMPETITION_DIRS["purple_ms"] == "PURPLE_MS"
    assert classifier.PDF_COMPETITION_DIRS["purple_hs"] == "PURPLE_HS"


def test_visual_classifier_sends_actual_png_bytes_and_keeps_answer_separate(tmp_path):
    import base64
    from mathbank.classify.concept_classifier import _visual_content
    image = tmp_path / "problem_page_001.png"
    data = b"\x89PNG\r\n\x1a\nsynthetic fixture"
    image.write_bytes(data)
    content = _visual_content("Classify synthetic Q01.", [str(image), str(image)])
    assert len(content) == 2
    assert base64.b64decode(content[1]["image_url"]["url"].split(",", 1)[1]) == data
    assert content[1]["image_url"]["detail"] == "high"
    image.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="not a PNG"):
        _visual_content("Question", [str(image)])


def test_purple_classifier_discovers_all_image_pages_and_official_answer(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(classifier, "PDF_CRAWL_DIR", tmp_path)
    folder = tmp_path / "purple_ms/PAPER_PURPLE_2026_MS"
    q = folder / "questions/Q01"
    (q / "images").mkdir(parents=True)
    (q / "problem.md").write_text("Synthetic question with a diagram.")
    (q / "solution.md").write_text("Synthetic worked explanation.")
    (q / "images/problem_page_001.png").write_bytes(b"fixture")
    (q / "images/solution_page_002.png").write_bytes(b"fixture")
    (folder / "answers.json").write_text(json.dumps({"1": "17"}))
    result = classifier.discover_questions("PURPLE_MS")
    assert len(result) == 1 and len(result[0].image_paths) == 2
    assert result[0].answer_value == "17"


@pytest.mark.parametrize("directory,competition", [
    ("arml", "ARML"), ("arml_local", "ARML_LOCAL"), ("arml_power", "ARML_POWER"),
])
def test_arml_visual_discovery_preserves_proof_questions(tmp_path, monkeypatch, directory, competition):
    monkeypatch.setattr(classifier, "PDF_CRAWL_DIR", tmp_path)
    question = tmp_path / directory / f"PAPER_{competition}_2015_MAIN_POWER/questions/Q01"
    (question / "images").mkdir(parents=True)
    (question / "problem.md").write_text("Synthetic multipart proof with shared context.")
    (question / "solution.md").write_text("Synthetic multipart proof explanation.")
    (question / "images/problem_page_001.png").write_bytes(b"fixture")
    result = classifier.discover_questions(competition)
    assert len(result) == 1
    assert result[0].image_paths
    assert not result[0].answer_value
    assert result[0].solution_texts == ["Synthetic multipart proof explanation."]


def test_arml_classifier_uses_actual_images_and_gpt41(tmp_path, monkeypatch):
    from mathbank.classify import concept_classifier
    image = tmp_path / "problem_page_001.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nsynthetic fixture")
    calls = []
    monkeypatch.setattr(concept_classifier, "_call_openai", lambda *args: calls.append(args) or "{}")
    monkeypatch.setattr(concept_classifier, "_parse_response", lambda *args: "visual result")
    assert concept_classifier.classify_question(
        None, "PAPER_ARML_2015_MAIN_TEAM_Q01", "ARML", "Synthetic question.", [],
        [str(image)], "", "Synthetic taxonomy",
    ) == "visual result"
    assert calls[0][2] == "gpt-4.1"
    assert calls[0][3] == [str(image)]


def test_legacy_remote_image_references_do_not_become_local_file_reads(monkeypatch):
    from mathbank.classify import concept_classifier
    calls = []
    monkeypatch.setattr(concept_classifier, "_call_openai", lambda *args: calls.append(args) or "{}")
    monkeypatch.setattr(concept_classifier, "_parse_response", lambda *args: "legacy result")
    assert concept_classifier.classify_question(
        None, "LEGACY_Q01", "AMC10", "Synthetic question.", [],
        ["https://example.test/figure.jpg"], "", "Synthetic taxonomy",
    ) == "legacy result"
    assert len(calls[0]) == 3


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
