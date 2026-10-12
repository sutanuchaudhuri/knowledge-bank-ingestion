"""
Split PDF paper artifacts into per-question problem.md and solution.md files.

For each question that was parsed from a PDF paper:
  1. Reads parsed.json from  data/crawl/<comp>/<question_id>/
  2. Finds the paper directory in  data/crawl_pdf/<comp>/<paper_id>/
  3. Assigns a subset of the paper's rendered page PNGs to this question
  4. Writes:
       data/crawl_pdf/<comp>/<paper_id>/questions/Q{N:02d}/problem.md
       data/crawl_pdf/<comp>/<paper_id>/questions/Q{N:02d}/solution.md
       data/crawl_pdf/<comp>/<paper_id>/questions/Q{N:02d}/images/*.png  (copies)
  5. Updates questions table:
       artifact_base_path  — absolute path to the paper directory
       problem_md_path     — relative: questions/Q{N:02d}/problem.md
       solution_md_path    — relative: questions/Q{N:02d}/solution.md
       image_paths         — JSON list of question-specific image absolute paths

Usage:
    python scripts/split_pdf_artifacts.py                         # all papers
    python scripts/split_pdf_artifacts.py --competition CHMMC
    python scripts/split_pdf_artifacts.py --paper PAPER_CHMMC_2010_FALL_INDIV
    python scripts/split_pdf_artifacts.py --dry-run
    python scripts/split_pdf_artifacts.py --reprocess  # overwrite existing splits
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.db import DB_PATH
from mathbank.db.migrations import apply_all as apply_migrations
from mathbank.crawl.question_figures import extract_question_figures
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

console = Console()
log = logging.getLogger(__name__)
_FIGURE_CACHE = {}

CRAWL_DIR     = ROOT / "data" / "crawl"
CRAWL_PDF_DIR = ROOT / "data" / "crawl_pdf"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _q_num(question_id: str) -> int:
    """Extract 1-based question number from question_id suffix _Q{N:02d}."""
    m = re.search(r"_Q(\d+)$", question_id)
    return int(m.group(1)) if m else 0


def _paper_dir(competition_id: str, paper_id: str) -> Path:
    return CRAWL_PDF_DIR / _slug(competition_id) / paper_id


def _question_crawl_dir(competition_id: str, question_id: str) -> Path:
    return CRAWL_DIR / _slug(competition_id) / question_id


def _question_figures(paper_dir: Path, side: str, total_questions: int, dry_run: bool) -> dict[int, list[Path]]:
    source = paper_dir / f"{side}.pdf"
    if not source.is_file():
        log.warning("%s: %s PDF unavailable; no figure fallback", paper_dir.name, side)
        return {}
    key = (source.resolve(), source.stat().st_mtime_ns, total_questions, dry_run)
    if key not in _FIGURE_CACHE:
        try:
            _FIGURE_CACHE[key] = extract_question_figures(paper_dir, side=side,
                                                        expected_count=total_questions, write=not dry_run)
        except ValueError as exc:
            log.warning("%s: %s figures unavailable (%s); no page fallback", paper_dir.name, side, exc)
            _FIGURE_CACHE[key] = {}
    return _FIGURE_CACHE[key]


def _md_image_block(images: list[Path], base: Path) -> str:
    """Return markdown image lines using paths relative to base."""
    lines: list[str] = []
    for img in images:
        try:
            rel = img.relative_to(base)
        except ValueError:
            rel = img
        lines.append(f"![{img.stem}]({rel})")
    return "\n".join(lines)


# ── Markdown writers ──────────────────────────────────────────────────────────

def _write_problem_md(
    dest: Path,
    question_id: str,
    q_num: int,
    problem_text: str,
    image_paths: list[Path],
    base: Path,
) -> None:
    lines = [
        f"# {question_id} — Problem {q_num}",
        "",
        problem_text.strip(),
    ]
    if image_paths:
        lines += ["", "---", "", _md_image_block(image_paths, base)]
    dest.write_text("\n".join(lines), encoding="utf-8")


def _write_solution_md(
    dest: Path,
    question_id: str,
    q_num: int,
    solution_texts: list[str],
    answer_value: str,
    image_paths: list[Path],
    base: Path,
) -> None:
    lines = [f"# {question_id} — Solution {q_num}", ""]
    for i, sol in enumerate(solution_texts, 1):
        label = "Solution" if len(solution_texts) == 1 else f"Solution {i}"
        lines += [f"## {label}", "", sol.strip(), ""]
    if answer_value:
        lines += [f"**Answer:** {answer_value}", ""]
    if image_paths:
        lines += ["---", "", _md_image_block(image_paths, base)]
    dest.write_text("\n".join(lines), encoding="utf-8")


# ── DB helpers ────────────────────────────────────────────────────────────────

def _fetch_pdf_questions(
    conn: sqlite3.Connection,
    competition_filter: str | None,
    paper_filter: str | None,
    reprocess: bool,
) -> list[tuple]:
    """
    Return (question_id, competition_id, paper_id, q_number) for PDF questions.
    Skips already-split questions unless reprocess=True.
    """
    cond = (
        "WHERE competition_id IS NOT NULL AND competition_id != '' "
        "AND paper_id IS NOT NULL AND paper_id != '' "
        "AND (q_number > 0 OR question_id LIKE '%\\_Q%' ESCAPE '\\')"
    )
    params: list = []
    if competition_filter:
        cond += " AND competition_id = ?"
        params.append(competition_filter)
    if paper_filter:
        cond += " AND paper_id = ?"
        params.append(paper_filter)
    if not reprocess:
        cond += " AND (artifact_base_path IS NULL OR artifact_base_path = '')"
    # Exclude AoPS questions (they have AoPS URLs, not PDF papers)
    cond += " AND (aops_question_url IS NULL OR aops_question_url = '')"
    return conn.execute(
        f"SELECT question_id, competition_id, paper_id, q_number FROM questions {cond} ORDER BY paper_id, q_number",
        params,
    ).fetchall()


def _count_paper_questions(conn: sqlite3.Connection, paper_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE paper_id = ?", (paper_id,)
    ).fetchone()
    return row[0] if row else 1


def _update_question(
    conn: sqlite3.Connection,
    question_id: str,
    base_path: str,
    problem_md_path: str,
    solution_md_path: str,
    image_paths: list[str],
) -> None:
    conn.execute(
        """UPDATE questions SET
               artifact_base_path = ?,
               problem_md_path    = ?,
               solution_md_path   = ?,
               image_paths        = ?,
               updated_at         = ?
           WHERE question_id = ?""",
        (
            base_path,
            problem_md_path,
            solution_md_path,
            json.dumps(image_paths, ensure_ascii=False),
            datetime.now(timezone.utc).isoformat(),
            question_id,
        ),
    )


# ── Per-question processing ───────────────────────────────────────────────────

def _process_question(
    conn: sqlite3.Connection,
    question_id: str,
    competition_id: str,
    paper_id: str,
    q_number: int,
    total_q: int,
    dry_run: bool,
) -> str:
    """Write artifacts for one question. Returns status string."""
    paper_dir = _paper_dir(competition_id, paper_id)
    if not paper_dir.exists():
        return "SKIP:no_paper_dir"

    q_num = q_number or _q_num(question_id)
    if q_num == 0:
        return "SKIP:no_q_num"

    # Source 1: parsed.json (from crawl dir)
    parsed_path = _question_crawl_dir(competition_id, question_id) / "parsed.json"
    if parsed_path.exists():
        parsed = json.loads(parsed_path.read_text(encoding="utf-8"))
        problem_text   = parsed.get("problem_text", "")
        solution_texts = parsed.get("solution_texts") or []
        answer_value   = parsed.get("answer_value", "")
    else:
        # Source 2: DB columns (problem_text_latex, solution_text_latex)
        row = conn.execute(
            "SELECT problem_text_latex, solution_text_latex, all_solutions_json, answer_value "
            "FROM questions WHERE question_id = ?",
            (question_id,),
        ).fetchone()
        if not row or not row[0]:
            return "SKIP:no_text_source"
        problem_text = row[0] or ""
        # Prefer all_solutions_json (list of solutions); fall back to single solution_text_latex
        if row[2]:
            try:
                solution_texts = json.loads(row[2]) or []
            except (json.JSONDecodeError, TypeError):
                solution_texts = [row[1]] if row[1] else []
        else:
            solution_texts = [row[1]] if row[1] else []
        answer_value = row[3] or ""

    q_dir = paper_dir / "questions" / f"Q{q_num:02d}"
    native = sorted((q_dir / "images").glob("*_region_*.png"))
    if native:
        prob_imgs_local = [p for p in native if p.name.startswith("problem_")]
        sol_imgs_local = [p for p in native if p.name.startswith("solution_")]
    else:
        prob_imgs_local = _question_figures(paper_dir, "problem", total_q, dry_run).get(q_num, [])
        sol_imgs_local = _question_figures(paper_dir, "solution", total_q, dry_run).get(q_num, [])

    if dry_run:
        return f"DRY: Q{q_num:02d} problem_figures={len(prob_imgs_local)} solution_figures={len(sol_imgs_local)}"

    q_dir.mkdir(parents=True, exist_ok=True)

    all_imgs_local  = prob_imgs_local + sol_imgs_local

    # Write markdown files.
    prob_md = q_dir / "problem.md"
    sol_md  = q_dir / "solution.md"

    _write_problem_md(prob_md, question_id, q_num, problem_text, prob_imgs_local, q_dir)
    if not competition_id.startswith("PURPLE_") or solution_texts:
        _write_solution_md(sol_md, question_id, q_num, solution_texts, answer_value, sol_imgs_local, q_dir)
    elif sol_md.exists():
        sol_md.unlink()

    # Relative paths stored in DB (relative to artifact_base_path).
    _update_question(
        conn,
        question_id,
        base_path=str(paper_dir),
        problem_md_path=f"questions/Q{q_num:02d}/problem.md",
        solution_md_path=f"questions/Q{q_num:02d}/solution.md" if sol_md.exists() else "",
        image_paths=[str(p) for p in all_imgs_local],
    )

    return f"OK:Q{q_num:02d} imgs={len(all_imgs_local)}"


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Split PDF paper artifacts into per-question files")
    p.add_argument("--competition", type=str, default=None, help="Filter by competition_id")
    p.add_argument("--paper",       type=str, default=None, help="Process a single paper_id")
    p.add_argument("--db",          type=Path, default=DB_PATH)
    p.add_argument("--reprocess",   action="store_true", help="Overwrite already-split questions")
    p.add_argument("--dry-run",     action="store_true")
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    apply_migrations(conn)

    rows = _fetch_pdf_questions(conn, args.competition, args.paper, args.reprocess)
    if not rows:
        console.print("[yellow]No PDF questions to split. All may already be processed.")
        conn.close()
        return

    console.print(f"\n[bold]Splitting {len(rows)} questions into problem/solution files[/]  "
                  f"(dry_run={args.dry_run})\n")

    # Cache total-question counts per paper to avoid repeated DB queries.
    paper_counts: dict[str, int] = {}

    ok = skipped = 0

    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
                  console=console) as progress:
        task = progress.add_task("Splitting", total=len(rows))

        batch: list[tuple] = []
        for question_id, competition_id, paper_id, q_number in rows:
            progress.update(task, description=f"[cyan]{question_id}")

            if paper_id not in paper_counts:
                paper_counts[paper_id] = _count_paper_questions(conn, paper_id)

            status = _process_question(
                conn, question_id, competition_id, paper_id,
                q_number or 0, paper_counts[paper_id], args.dry_run,
            )

            if status.startswith("OK"):
                ok += 1
            else:
                skipped += 1
                if not status.startswith("DRY"):
                    console.print(f"  [dim]{question_id}: {status}")

            batch.append((question_id, status))

            # Commit every 100 rows to keep the DB writes efficient.
            if len(batch) >= 100:
                conn.commit()
                batch.clear()

            progress.advance(task)

        conn.commit()

    console.print(f"\n[bold green]Done.[/]  split={ok}  skipped={skipped}")
    console.print(f"\nFile layout per question:")
    console.print("  data/crawl_pdf/<comp>/<paper_id>/questions/Q{N}/problem.md")
    console.print("  data/crawl_pdf/<comp>/<paper_id>/questions/Q{N}/solution.md")
    console.print("  data/crawl_pdf/<comp>/<paper_id>/questions/Q{N}/images/*.png")
    console.print("\nDB columns updated: artifact_base_path, problem_md_path, solution_md_path, image_paths")
    conn.close()


if __name__ == "__main__":
    main()
