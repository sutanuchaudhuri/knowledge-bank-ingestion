import sys
from pathlib import Path
from unittest.mock import MagicMock

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "etl"))
from pdf_assets import mapped_problem_pages, paper_images, question_images, store_images
from mathbank.crawl.pdf_pages import question_page_numbers


def pdf_bytes(*texts):
    with pymupdf.open() as doc:
        for content in texts:
            page = doc.new_page()
            page.insert_text((50, 50), content)
        return doc.tobytes()


def test_mapping_keeps_shared_and_continuation_pages():
    mapping = question_page_numbers(pdf_bytes("1. First question\n2. Diagram below", "Diagram\n3. Third"), 3)
    assert mapping == {1: [1], 2: [1, 2], 3: [2]}


def test_mapping_refuses_incomplete_sequence():
    with pytest.raises(ValueError, match="Cannot locate"):
        question_page_numbers(pdf_bytes("1. First\n3. Third"), 3)


def test_images_have_explicit_solution_and_answer_provenance(tmp_path):
    folder = tmp_path / "images"
    folder.mkdir()
    for name in ("problem_page_001.png", "solution_page_001.png", "answer_page_001.png", "metadata.json"):
        (folder / name).write_bytes(b"fixture")
    assert [s for _, s in question_images(tmp_path)] == ["PDF_ANSWER_PAGE", "PDF_PROBLEM_PAGE", "PDF_SOLUTION_PAGE"]


def test_paper_links_verified_visual_pages_not_proportional_copies(tmp_path):
    (tmp_path / "problem.pdf").write_bytes(pdf_bytes("1. First\n2. Second", "Continuation"))
    for n in (1, 2):
        q = tmp_path / "questions" / f"Q{n:02d}"
        q.mkdir(parents=True)
        (q / "problem.md").write_text("Question")
    pages = tmp_path / "visuals/pages"
    pages.mkdir(parents=True)
    for n in (1, 2):
        (pages / f"problem_page_{n:03d}.png").write_bytes(b"fixture")
    assert len(paper_images(tmp_path)[2]) == 2
    (pages / "problem_page_002.png").unlink()
    with pytest.raises(ValueError, match="Missing rendered"):
        mapped_problem_pages(tmp_path)


def test_native_region_crops_are_preserved(tmp_path):
    q = tmp_path / "questions/Q01"
    (q / "images").mkdir(parents=True)
    region = q / "images/problem_region_001.png"
    region.write_bytes(b"fixture")
    assert paper_images(tmp_path) == {1: [(region.resolve(), "PDF_PROBLEM_PAGE")]}


def test_upsert_updates_provenance_not_only_path(tmp_path):
    cur = MagicMock()
    store_images(cur, "problem-id", [(tmp_path / "problem_page_002.png", "PDF_PROBLEM_PAGE")])
    sql, params = cur.execute.call_args.args
    assert "source = EXCLUDED.source" in sql
    assert params[-1] == "PDF_PROBLEM_PAGE"
