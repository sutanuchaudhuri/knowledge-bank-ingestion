"""
Crawl and parse PDF-based competition papers (HMMT, SMT, PUMaC, CMM, CHMMC, MPG).

Unlike crawl_unmapped.py (which fetches per-question AoPS wiki pages),
this script processes whole-paper PDFs from competition archives.

Workflow per paper:
  1. Download problem PDF  → extract text → split by question number
  2. Download solution PDF → extract text → split by question number
  3. Render PDF pages to PNG for visual evidence
  4. Upsert each question into the questions table
  5. Add each question to unmapped_questions (status=CRAWLED) for classification
  6. Update unparsed_papers.question_index_status = 'INDEXED'

Usage:
    python scripts/crawl_pdf_papers.py                       # all competitions, 20 papers
    python scripts/crawl_pdf_papers.py --competition HMMT_FEB
    python scripts/crawl_pdf_papers.py --limit 50 --delay 3
    python scripts/crawl_pdf_papers.py --dry-run
    python scripts/crawl_pdf_papers.py --retry-failed

Supported competitions (PDF sources):
    HMMT_FEB, HMMT_NOV, HMMT_INV, SMT, PUMAC, CMM, CHMMC, MPG_MAIN, MPG_OLY
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.db import DB_PATH
from mathbank.db.migrations import apply_all as apply_migrations
from mathbank.crawl.downloader import DownloadError, fetch_binary, make_session
from mathbank.crawl.pdf_format import has_pdf_header
from mathbank.crawl.pdf_parser import (
    parse_pdf_paper, question_page_numbers, render_pdf_pages, save_question_artifacts, CRAWL_DIR as PDF_ARTIFACT_DIR,
)

import requests
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

console = Console()

PDF_CRAWL_DIR = ROOT / "data" / "crawl_pdf"

PDF_COMPETITIONS = {
    "HMMT_FEB", "HMMT_NOV", "HMMT_INV", "HMMT",
    "SMT", "PUMAC", "CMM", "CHMMC",
    "MPG_MAIN", "MPG_OLY", "MPG",
    "PURPLE_MS", "PURPLE_HS",
}


# ── HTTP fetch for binary PDFs ─────────────────────────────────────────────────

_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = make_session()
    return _SESSION


def _fetch_pdf(url: str, delay: float) -> bytes:
    import time
    time.sleep(delay)
    r = _session().get(url, timeout=60, allow_redirects=True)
    if r.status_code >= 400:
        raise DownloadError(f"HTTP {r.status_code} → {url}")
    ct = r.headers.get("Content-Type", "")
    if r.content.startswith(b"%!PS"):
        return _convert_postscript(r.content, url)
    if "pdf" not in ct.lower() and not url.lower().endswith(".pdf"):
        raise DownloadError(f"Expected PDF, got {ct} from {url}")
    if not has_pdf_header(r.content):
        raise DownloadError(f"Response is not a PDF document from {url}")
    return r.content


def _convert_postscript(content: bytes, url: str) -> bytes:
    import shutil
    import subprocess
    import tempfile

    gs = shutil.which("gs")
    if gs is None:
        raise DownloadError("PostScript source requires Ghostscript (gs); install it before retrying")
    with tempfile.TemporaryDirectory(prefix="mathbank-ps-") as directory:
        source = Path(directory) / "source.ps"
        output = Path(directory) / "converted.pdf"
        source.write_bytes(content)
        try:
            subprocess.run(
                [gs, "-dSAFER", "-dBATCH", "-dNOPAUSE", "-sDEVICE=pdfwrite",
                 f"-sOutputFile={output}", str(source)],
                check=True, capture_output=True, timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise DownloadError(f"PostScript conversion failed ({type(exc).__name__}) for {url}") from exc
        if not output.is_file() or not output.read_bytes().startswith(b"%PDF-"):
            raise DownloadError(f"Ghostscript produced no valid PDF for {url}")
        console.print(f"  Converted official PostScript source to PDF: {url}")
        return output.read_bytes()


# ── Artifact paths ─────────────────────────────────────────────────────────────

def _paper_dir(competition_id: str, paper_id: str) -> Path:
    return PDF_CRAWL_DIR / _slug(competition_id) / paper_id


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Queue ──────────────────────────────────────────────────────────────────────

def _fetch_queue(
    conn: sqlite3.Connection,
    limit: int,
    competition: str | None,
    retry_failed: bool,
) -> list[tuple]:
    statuses = ("NOT_PARSED", "PENDING", "NOT_STARTED") + (("FAILED",) if retry_failed else ())
    ph = ",".join("?" for _ in statuses)
    # also match rows where question_index_status IS NULL
    null_clause = "OR question_index_status IS NULL"
    comp_ids = ",".join(f"'{c}'" for c in PDF_COMPETITIONS)

    params: list = list(statuses)
    sql = f"""
        SELECT paper_id, competition_id, problem_url, solution_url,
               question_count, tournament_event_id
        FROM unparsed_papers
        WHERE (question_index_status IN ({ph}) {null_clause})
          AND competition_id IN ({comp_ids})
          AND length(problem_url) > 0
    """
    if competition:
        sql += " AND competition_id = ?"
        params.append(competition)
    sql += " ORDER BY competition_id, paper_id LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


# ── DB writes ──────────────────────────────────────────────────────────────────

def _upsert_question(
    conn: sqlite3.Connection,
    paper_id: str,
    competition_id: str,
    q_id: str,
    q_number: int,
    problem_text: str,
    solution_text: str,
    answer_value: str,
    image_paths: list[str],
    exam_level: str,
    year: str,
    tournament_event_id: str,
    warnings: list[str],
) -> None:
    solutions_json = json.dumps([solution_text] if solution_text else [], ensure_ascii=False)
    conn.execute(
        """INSERT OR REPLACE INTO questions
           (question_id, paper_id, competition_id, exam_level, year,
            q_number, classification_status,
            problem_text_latex, problem_text_raw,
            solution_text_latex, all_solutions_json,
            image_paths, answer_value, parse_warnings,
            tournament_event_id, crawled_at)
           VALUES (?, ?, ?, ?, ?, ?, 'UNCLASSIFIED', ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            q_id, paper_id, competition_id, exam_level, year,
            q_number,
            problem_text, problem_text,
            solution_text, solutions_json,
            json.dumps(image_paths, ensure_ascii=False),
            answer_value,
            json.dumps(warnings, ensure_ascii=False),
            tournament_event_id,
            _now(),
        ),
    )
    # Add to unmapped_questions for classification pipeline.
    conn.execute(
        """INSERT OR IGNORE INTO unmapped_questions
           (question_id, exam_level, mapping_status, next_action)
           VALUES (?, ?, 'CRAWLED', 'CLASSIFY')""",
        (q_id, exam_level),
    )


def _mark_paper(conn: sqlite3.Connection, paper_id: str, status: str, notes: str = "") -> None:
    conn.execute(
        "UPDATE unparsed_papers SET question_index_status = ?, agent_next_action = ? WHERE paper_id = ?",
        (status, notes[:400], paper_id),
    )


# ── Per-paper processing ───────────────────────────────────────────────────────

def _process_paper(
    conn: sqlite3.Connection,
    paper_id: str,
    competition_id: str,
    problem_url: str,
    solution_url: str,
    expected_count: int | None,
    tournament_event_id: str,
    delay: float,
    require_split: bool = False,
    reparse: bool = False,
) -> tuple[int, str]:
    """Download, parse, and store one paper. Returns (question_count, status)."""
    pdir = _paper_dir(competition_id, paper_id)

    # Derive metadata from paper_id (e.g. HMMT_FEB_2023_ALGEBRA → year=2023, level=HMMT_FEB)
    year_match = re.search(r"(\d{4})", paper_id)
    year = year_match.group(1) if year_match else ""
    exam_level = competition_id

    # Check if already done.
    if (pdir / "index.json").exists() and not reparse:
        existing = json.loads((pdir / "index.json").read_text())
        n = len(existing.get("questions", []))
        if require_split:
            validate_question_ids(existing.get("questions", []), paper_id, expected_count)
        if competition_id.startswith("PURPLE_"):
            ids = existing["questions"]
            placeholders = ",".join("?" for _ in ids)
            stored = {row[0] for row in conn.execute(
                f"SELECT question_id FROM questions WHERE question_id IN ({placeholders})", ids
            )}
            if stored != set(ids):
                raise ValueError("Cached question index lacks committed staging rows; reparse required")
            for question_id in existing["questions"]:
                path = PDF_ARTIFACT_DIR / _slug(competition_id) / question_id / "parsed.json"
                record = json.loads(path.read_text())
                if any("_page_" in Path(image).name for image in record.get("image_urls", [])):
                    raise ValueError(f"{question_id}: cached whole-page image references require figure repair")
        console.print(f"  [dim]SKIP (cached) {paper_id} — {n} questions")
        return n, "INDEXED"

    pdir.mkdir(parents=True, exist_ok=True)

    # Download PDFs.
    try:
        console.print(f"  ↓ problem PDF {problem_url[-60:]}")
        cached = pdir / "problem.pdf"
        prob_bytes = cached.read_bytes() if competition_id.startswith("PURPLE_") and cached.is_file() else _fetch_pdf(problem_url, delay)
        if not has_pdf_header(prob_bytes):
            raise DownloadError("Cached problem is not a PDF")
        (pdir / "problem.pdf").write_bytes(prob_bytes)
    except Exception as exc:
        return 0, f"FAILED: problem download — {exc}"

    sol_bytes: bytes | None = None
    if solution_url:
        try:
            console.print(f"  ↓ solution PDF {solution_url[-60:]}")
            cached = pdir / "solution.pdf"
            sol_bytes = cached.read_bytes() if competition_id.startswith("PURPLE_") and cached.is_file() else _fetch_pdf(solution_url, delay)
            if not has_pdf_header(sol_bytes):
                raise DownloadError("Cached solution is not a PDF")
            (pdir / "solution.pdf").write_bytes(sol_bytes)
        except Exception as exc:
            console.print(f"  [yellow]WARN solution download failed: {exc}")

    # Render pages to PNG.
    prob_images = render_pdf_pages(prob_bytes, pdir / "visuals", "problem")
    sol_images = render_pdf_pages(sol_bytes, pdir / "visuals", "solution") if sol_bytes else []

    # Parse into questions — Docling extracts Markdown + figures; artifacts saved to data/crawl/.
    parsed_questions = parse_pdf_paper(
        paper_id, competition_id, prob_bytes, sol_bytes, expected_count,
        save_artifacts=True,
        exam_level=exam_level,
        paper_url=problem_url,
        visuals_dir=pdir / "visuals",
    )
    if require_split:
        validate_question_ids([q.question_id for q in parsed_questions], paper_id, expected_count)
        if any(not q.problem_text.strip() for q in parsed_questions):
            raise ValueError("Parsed question has no problem text; refusing paper completion")
        if competition_id.startswith("PURPLE_") and solution_url and any(not q.solution_texts for q in parsed_questions):
            raise ValueError("Official worked-solution PDF did not produce every numbered solution")

    answers_path = pdir / "answers.json"
    answers = json.loads(answers_path.read_text()) if competition_id.startswith("PURPLE_") and answers_path.is_file() else {}
    if competition_id.startswith("PURPLE_"):
        spans = {"problem": question_page_numbers(prob_bytes, len(parsed_questions))}
        if sol_bytes:
            spans["solution"] = question_page_numbers(sol_bytes, len(parsed_questions))
        (pdir / "page_spans.json").write_text(json.dumps(spans, indent=2))

    index: dict = {"paper_id": paper_id, "competition_id": competition_id,
                   "year": year, "questions": []}

    for pq in parsed_questions:
        q_num_match = re.search(r"Q(\d+)$", pq.question_id)
        q_num = int(q_num_match.group(1)) if q_num_match else 0
        if answers:
            if str(q_num) not in answers:
                raise ValueError("Parsed question has no official answer-key entry")
            pq.answer_value = answers[str(q_num)]
            save_question_artifacts(
                pq.question_id, exam_level, pq.problem_text, pq.solution_texts,
                pq.answer_value, pq.image_urls, pq.parse_warnings, problem_url,
            )

        q_images = pq.image_urls

        _upsert_question(
            conn, paper_id, competition_id,
            pq.question_id, q_num,
            pq.problem_text, pq.solution_texts[0] if pq.solution_texts else "",
            pq.answer_value, q_images,
            exam_level, year, tournament_event_id,
            pq.parse_warnings,
        )
        index["questions"].append(pq.question_id)

    # Save index.json for resumability.
    index["image_pages_problem"] = prob_images
    index["image_pages_solution"] = sol_images
    index["crawled_at"] = _now()
    (pdir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

    return len(parsed_questions), "INDEXED"

def validate_question_ids(ids: list[str], paper_id: str, expected_count: int | None) -> None:
    numbers = []
    for question_id in ids:
        match = re.fullmatch(re.escape(paper_id) + r"_Q(\d+)", question_id)
        if not match:
            raise ValueError("Whole-paper fallback is not a question-level parse")
        numbers.append(int(match.group(1)))
    if not numbers or sorted(numbers) != list(range(1, len(numbers) + 1)):
        raise ValueError("Question numbers must be nonempty, unique and contiguous from 1")
    if expected_count and len(numbers) != expected_count:
        raise ValueError(f"Expected {expected_count} questions, parsed {len(numbers)}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Crawl PDF-based competition papers")
    p.add_argument("--competition", type=str, default=None,
                   help="Filter by competition_id (e.g. HMMT_FEB, SMT, PUMAC)")
    p.add_argument("--limit",  type=int,   default=20)
    p.add_argument("--delay",  type=float, default=2.0)
    p.add_argument("--db",     type=Path,  default=DB_PATH)
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--dry-run",      action="store_true")
    p.add_argument("--sources-file", type=Path, help="Explicit JSON paper sources from Postgres")
    p.add_argument("--require-split", action="store_true", help="Reject incomplete/whole-paper parses")
    p.add_argument("--reparse", action="store_true", help="Reparse even if a cached index exists")
    p.add_argument("--native-extraction", action="store_true", help="Explicit native-text extraction instead of Docling")
    args = p.parse_args()
    if args.native_extraction:
        os.environ["MATHBANK_PDF_EXTRACTOR"] = "pymupdf"
        console.print("[yellow]Explicit PyMuPDF native-text extraction; review math/figure quality.")

    conn = sqlite3.connect(args.db)
    apply_migrations(conn)

    if args.sources_file:
        sources = json.loads(args.sources_file.read_text())
        queue = [
            (s["paper_external_code"], s["competition_external_code"],
             s["problem_url"], s.get("solution_url"), s.get("expected_count"), "")
            for s in sources
        ]
        if any(row[1] not in PDF_COMPETITIONS for row in queue):
            p.error("Unsupported competition in sources file")
    else:
        queue = _fetch_queue(conn, args.limit, args.competition, args.retry_failed)

    if not queue:
        console.print("[yellow]No PDF papers to process.")
        rows = conn.execute(
            "SELECT competition_id, COUNT(*) FROM unparsed_papers "
            "GROUP BY competition_id ORDER BY 2 DESC"
        ).fetchall()
        for r in rows:
            console.print(f"  {(r[0] or '?'):<15} {r[1]}")
        conn.close()
        return

    console.print(f"\n[bold]PDF crawl:[/] {len(queue)} papers  "
                  f"(delay={args.delay}s  dry_run={args.dry_run})\n")

    if args.dry_run:
        for paper_id, comp, prob_url, sol_url, qcount, _ in queue:
            console.print(f"  [dim]{paper_id:<40} {comp:<12} q={qcount}  {prob_url[-50:]}")
        conn.close()
        return

    total_q = 0

    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
                  console=console) as progress:
        task = progress.add_task("Papers", total=len(queue))

        for paper_id, comp, prob_url, sol_url, qcount, event_id in queue:
            progress.update(task, description=f"[cyan]{paper_id}")

            n, status = _process_paper(
                conn, paper_id, comp,
                prob_url, sol_url or "",
                qcount, event_id or "",
                args.delay, args.require_split, args.reparse,
            )
            _mark_paper(conn, paper_id, status if status == "INDEXED" else "FAILED", status)
            conn.commit()
            if args.require_split and status != "INDEXED":
                raise RuntimeError(f"{paper_id}: {status}")
            total_q += n
            progress.advance(task)

    console.print(f"\n[bold green]Done.[/]  papers={len(queue)}  questions_created={total_q}")
    console.print(f"Artifacts in: [cyan]{PDF_CRAWL_DIR}")
    console.print("\nRun classify_crawled.py to classify the extracted questions.")
    conn.close()


if __name__ == "__main__":
    main()
