import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
from question_figures import extract_question_figures, figure_regions


def source_pdf():
    doc = pymupdf.open()
    first = doc.new_page()
    first.insert_text((40, 40), "Contest header")
    first.insert_text((40, 100), "1. First problem with a diagram below.")
    first.draw_circle((180, 200), 50)
    first.insert_text((175, 140), "A")
    first.insert_text((40, 330), "2. This question continues onto the next page.")
    second = doc.new_page()
    second.insert_text((40, 40), "Contest header")
    second.draw_circle((250, 180), 70)
    second.insert_text((245, 100), "M")
    second.insert_text((40, 330), "3. Unrelated next question.")
    second.draw_rect(pymupdf.Rect(300, 450, 380, 520))
    return doc


def test_figure_on_continuation_page_is_tightly_cropped_without_other_questions():
    with source_pdf() as doc:
        regions = figure_regions(doc, 3)
        assert len(regions[2]) == 1
        page_number, clip = regions[2][0]
        assert page_number == 1
        assert clip.width < doc[1].rect.width / 2
        assert clip.height < doc[1].rect.height / 2
        clipped_text = doc[1].get_text(clip=clip)
        assert "M" in clipped_text
        assert "Contest" not in clipped_text
        assert "Unrelated" not in clipped_text
        assert "question" not in clipped_text


def test_questions_without_graphics_have_no_images():
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 100), "1. Compute 2+2.")
        page.insert_text((40, 300), "2. Compute 3+3.")
        assert figure_regions(doc, 2) == {1: [], 2: []}


def test_unverified_inventory_fails_instead_of_proportional_assignment():
    with source_pdf() as doc, pytest.raises(ValueError, match="spatial boundaries"):
        figure_regions(doc, 4)


def test_duplicate_numbering_and_two_columns_are_not_verified():
    for headings in (
        [(40, 100, "1. First"), (40, 250, "2. Second"), (40, 400, "1. Other paper")],
        [(40, 100, "1. Left column"), (330, 300, "2. Right column")],
    ):
        with pymupdf.open() as doc:
            page = doc.new_page()
            for x, y, text in headings:
                page.insert_text((x, y), text)
            page.draw_circle((180, 200), 30)
            with pytest.raises(ValueError, match="spatial boundaries"):
                figure_regions(doc, 2)


def test_dry_run_creates_no_files_and_apply_records_provenance(tmp_path):
    with source_pdf() as doc:
        doc.save(tmp_path / "problem.pdf")
    for number in (1, 2, 3):
        folder = tmp_path / "questions" / f"Q{number:02d}"
        folder.mkdir(parents=True)
        (folder / "problem.md").write_text("Question")
    planned = extract_question_figures(tmp_path)
    assert not list(tmp_path.glob("questions/*/images/*"))
    written = extract_question_figures(tmp_path, write=True)
    assert planned == written
    assert all(
        path.is_file() and path.with_suffix(".json").is_file()
        for images in written.values()
        for path in images
    )


def test_real_smt_q6_figure_contains_only_its_labels():
    paper = (
        Path(__file__).resolve().parents[2]
        / "mathbank_data_ingestion/data/crawl_pdf/smt/PAPER_SMT_2010_GEOM"
    )
    if not (paper / "problem.pdf").is_file():
        pytest.skip("Downloaded SMT fixture unavailable")
    with pymupdf.open(paper / "problem.pdf") as doc:
        page_number, clip = figure_regions(doc, 10)[6][0]
        assert page_number == 1
        text = doc[page_number].get_text(clip=clip).split()
        assert set(text) == {"A", "B", "M", "O", "T", "D"}
        assert clip.width < 230 and clip.height < 230
