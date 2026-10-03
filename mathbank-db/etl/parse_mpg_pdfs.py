"""Parse already-downloaded MPG (Math Prize for Girls) PDFs into per-question
problem.md / solution.md / images — the same on-disk layout pdf_pipeline.py's
`reconcile`/`ingest` stages already understand, so no new ingestion code is
needed.

MUST run with mathbank_data_ingestion's own venv (needs docling + pymupdf):

    cd mathbank-db
    /Volumes/External/Developer/knowledge-bank-ingestion/mathbank_data_ingestion/.venv/bin/python \\
        etl/parse_mpg_pdfs.py --limit 5

Purely filesystem-based — touches no database. After running, use
`make pdf-pipeline` (mathbank-db's own venv) to reconcile + ingest the newly
parsed questions/solutions (+ images) into Postgres.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pymupdf as fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
INGESTION_ROOT = REPO_ROOT / "mathbank_data_ingestion"
PDF_CRAWL_DIR = INGESTION_ROOT / "data" / "crawl_pdf"

sys.path.insert(0, str(INGESTION_ROOT / "src"))
from mathbank.crawl.pdf_parser import parse_pdf_paper  # noqa: E402

MPG_DIRS = {"mpg_main": "MPG_MAIN", "mpg_oly": "MPG_OLY"}


def _drop_cover_page(problem_bytes: bytes) -> bytes:
    """MPG problem PDFs lead with a 'Directions' page whose own numbered list
    (1. Do not open..., 2. Fill out...) collides with the real Problem 1/2/...
    during splitting, silently discarding the real early problems. Drop it."""
    doc = fitz.open(stream=problem_bytes, filetype="pdf")
    try:
        if len(doc) <= 1:
            return problem_bytes
        first_page_text = doc[0].get_text("text")[:300].lower()
        if "directions" in first_page_text or "do not open" in first_page_text:
            doc.delete_page(0)
            return doc.tobytes()
        return problem_bytes
    finally:
        doc.close()


def _write_question_artifacts(paper_dir: Path, paper_id: str, q_num: int, problem_text: str,
                               solution_text: str, image_paths: list[str]) -> None:
    qdir = paper_dir / "questions" / f"Q{q_num:02d}"
    qdir.mkdir(parents=True, exist_ok=True)

    (qdir / "problem.md").write_text(
        f"# {paper_id}_Q{q_num:02d} — Problem {q_num}\n\n{problem_text.strip()}\n",
        encoding="utf-8",
    )
    if solution_text.strip():
        (qdir / "solution.md").write_text(
            f"# {paper_id}_Q{q_num:02d} — Solution 1\n\n## Solution\n\n{solution_text.strip()}\n",
            encoding="utf-8",
        )

    if image_paths:
        images_dir = qdir / "images"
        images_dir.mkdir(exist_ok=True)
        for src in image_paths:
            src_path = Path(src)
            if src_path.is_file():
                shutil.copy2(src_path, images_dir / src_path.name)


def parse_paper(paper_dir: Path, competition_id: str, reprocess: bool) -> tuple[str, int]:
    """Returns (status, questions_written)."""
    questions_dir = paper_dir / "questions"
    if questions_dir.exists() and any(questions_dir.iterdir()) and not reprocess:
        return "already_parsed", 0

    problem_pdf = paper_dir / "problem.pdf"
    solution_pdf = paper_dir / "solution.pdf"
    if not problem_pdf.exists():
        return "no_problem_pdf", 0

    paper_id = paper_dir.name
    problem_bytes = _drop_cover_page(problem_pdf.read_bytes())
    solution_bytes = solution_pdf.read_bytes() if solution_pdf.exists() else None

    results = parse_pdf_paper(
        paper_id=paper_id,
        competition_id=competition_id,
        problem_bytes=problem_bytes,
        solution_bytes=solution_bytes,
        expected_count=None,
        save_artifacts=False,  # we write our own questions/Qnn layout below, not data/crawl/
        exam_level=competition_id,
        paper_url="",
        visuals_dir=paper_dir / "visuals",
    )

    if len(results) == 1 and results[0].question_id == paper_id:
        # split_questions() fell back to the whole, unsplit PDF text — don't
        # fabricate a single giant "question"; leave for manual review.
        return "split_failed", 0

    if questions_dir.exists() and reprocess:
        shutil.rmtree(questions_dir)

    written = 0
    for result in results:
        if not result.has_problem:
            continue
        q_num = int(result.question_id.rsplit("_Q", 1)[-1])
        solution_text = result.solution_texts[0] if result.solution_texts else ""
        _write_question_artifacts(paper_dir, paper_id, q_num, result.problem_text, solution_text, result.image_urls)
        written += 1

    return ("parsed" if written else "no_questions"), written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=5, help="max papers to process this run")
    parser.add_argument("--competition", choices=["mpg_main", "mpg_oly"], help="restrict to one dir")
    parser.add_argument("--reprocess", action="store_true", help="re-parse papers that already have questions/")
    args = parser.parse_args()

    dirs = [args.competition] if args.competition else list(MPG_DIRS)
    processed = 0
    counts: dict[str, int] = {}
    for dir_name in dirs:
        competition_id = MPG_DIRS[dir_name]
        comp_dir = PDF_CRAWL_DIR / dir_name
        if not comp_dir.is_dir():
            continue
        for paper_dir in sorted(comp_dir.iterdir()):
            if not paper_dir.is_dir() or processed >= args.limit:
                continue
            status, written = parse_paper(paper_dir, competition_id, args.reprocess)
            counts[status] = counts.get(status, 0) + 1
            print(f"{paper_dir.name}: {status} ({written} questions)")
            if status != "already_parsed":
                processed += 1

    print("\nSummary:", counts)


if __name__ == "__main__":
    main()
