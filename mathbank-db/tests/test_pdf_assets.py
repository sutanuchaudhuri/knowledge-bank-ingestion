import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "mathbank_data_ingestion/src")
)
from mathbank.crawl.pdf_pages import question_page_numbers
from pdf_assets import paper_images, question_images, store_images


def pdf_bytes(*texts):
    with pymupdf.open() as doc:
        for content in texts:
            page = doc.new_page()
            page.insert_text((50, 50), content)
        return doc.tobytes()


def test_mapping_keeps_shared_and_continuation_pages():
    mapping = question_page_numbers(
        pdf_bytes("1. First question\n2. Diagram below", "Diagram\n3. Third"), 3
    )
    assert mapping == {1: [1], 2: [1, 2], 3: [2]}


def test_mapping_refuses_incomplete_sequence():
    with pytest.raises(ValueError, match="Cannot locate"):
        question_page_numbers(pdf_bytes("1. First\n3. Third"), 3)


def test_images_have_explicit_solution_and_answer_provenance(tmp_path):
    folder = tmp_path / "images"
    folder.mkdir()
    for name in (
        "problem_page_001.png",
        "solution_page_001.png",
        "answer_page_001.png",
        "metadata.json",
    ):
        (folder / name).write_bytes(b"fixture")
    assert [s for _, s in question_images(tmp_path)] == [
        "PDF_ANSWER_PAGE",
        "PDF_PROBLEM_PAGE",
        "PDF_SOLUTION_PAGE",
    ]


def test_paper_does_not_import_whole_page_fallbacks(tmp_path):
    (tmp_path / "problem.pdf").write_bytes(
        pdf_bytes("1. First\n2. Second", "Continuation")
    )
    for n in (1, 2):
        q = tmp_path / "questions" / f"Q{n:02d}"
        q.mkdir(parents=True)
        (q / "problem.md").write_text("Question")
    pages = tmp_path / "visuals/pages"
    pages.mkdir(parents=True)
    for n in (1, 2):
        (pages / f"problem_page_{n:03d}.png").write_bytes(b"fixture")
    assert paper_images(tmp_path) == {1: [], 2: []}
    (pages / "problem_page_002.png").unlink()
    assert paper_images(tmp_path) == {1: [], 2: []}


def test_native_region_crops_are_preserved(tmp_path):
    q = tmp_path / "questions/Q01"
    (q / "images").mkdir(parents=True)
    region = q / "images/problem_region_001.png"
    region.write_bytes(b"fixture")
    assert paper_images(tmp_path) == {1: [(region.resolve(), "PDF_PROBLEM_PAGE")]}


def test_upsert_updates_provenance_not_only_path(tmp_path):
    cur = MagicMock()
    store_images(
        cur, "problem-id", [(tmp_path / "problem_page_002.png", "PDF_PROBLEM_PAGE")]
    )
    sql, params = cur.execute.call_args.args
    assert "source = EXCLUDED.source" in sql
    assert params[-1] == "PDF_PROBLEM_PAGE"


def test_direct_pdf_import_crops_solution_graphics_without_manifests(tmp_path):
    q = tmp_path / "questions/Q01"
    q.mkdir(parents=True)
    (q / "problem.md").write_text("Problem without graphics.")
    (tmp_path / "problem.pdf").write_bytes(pdf_bytes("1. Problem without graphics."))
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 100), "1. Worked solution.")
        page.draw_circle((240, 200), 30)
        page.insert_text((235, 165), "X")
        (tmp_path / "solution.pdf").write_bytes(doc.tobytes())
    images = paper_images(tmp_path)[1]
    assert len(images) == 1
    path, source = images[0]
    assert source == "PDF_SOLUTION_FIGURE"
    assert path.is_file() and "_figure_" in path.name and "_page_" not in path.name


def test_empty_verified_inventory_removes_only_the_matching_source_family():
    cur = MagicMock()
    store_images(cur, "problem-id", [], source_kind="PDF")
    sql, params = cur.execute.call_args.args
    assert "DELETE FROM core.problem_image" in sql and "source=ANY" in sql
    assert (
        params[1] == 0
        and "PDF_PARSED" in params[2]
        and "TEXTBOOK_PACKAGE" not in params[2]
    )


def test_pdf_mirrors_are_not_reimported_as_aops_diagrams(tmp_path, monkeypatch):
    import load_corpus

    folder = tmp_path / "smt/PAPER_SMT_2010_GEOM_Q06"
    folder.mkdir(parents=True)
    (folder / "parsed.json").write_text(
        json.dumps({"question_id": folder.name, "problem_text": "Original PDF statement"})
    )
    monkeypatch.setattr(load_corpus, "AOPS_CRAWL_DIR", tmp_path)
    cur = MagicMock()
    cur.fetchall.return_value = [(folder.name, "problem-id")]
    assert load_corpus.enrich_problems_from_aops_crawl(cur) == (0, 0)
    cur.execute.assert_called_once_with("SELECT canonical_code, problem_id FROM core.problem")
