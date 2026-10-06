"""
Crawl and parse unmapped questions from AoPS wiki.

Queries the local SQLite DB for questions with no concept mapping
(mapping_status = PENDING or FAILED), fetches each AoPS wiki page,
parses problem + solution text, saves artifacts locally, and updates
the DB row to mapping_status = CRAWLED.

Usage:
    python scripts/crawl_unmapped.py                    # 50 questions, 2s delay
    python scripts/crawl_unmapped.py --limit 200        # larger batch
    python scripts/crawl_unmapped.py --delay 3.0        # slower (safer)
    python scripts/crawl_unmapped.py --level "AIME"     # one competition only
    python scripts/crawl_unmapped.py --retry-failed     # re-process FAILED rows
    python scripts/crawl_unmapped.py --dry-run          # print queue, no fetches

Artifacts written per question under:
    data/crawl/<exam_level_slug>/<question_id>/
        problem.html          raw HTML from AoPS
        problem_text.md       parsed markdown (problem + solutions)
        parsed.json           structured JSON (problem_text, solutions, images…)

Run repeatedly to process the full 3,135 question backlog in batches.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.db import DB_PATH
from mathbank.db.migrations import apply_all as apply_migrations
from mathbank.db.tracking import IngestionRun
from mathbank.crawl.downloader import DownloadError, fetch_html, make_session, save_html
from mathbank.crawl.aops_parser import ParsedQuestion, parse_aops_page
from mathbank.crawl.image_downloader import save_aops_images
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn, TimeElapsedColumn

console = Console()

CRAWL_DIR = ROOT / "data" / "crawl"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _question_dir(exam_level: str, question_id: str) -> Path:
    return CRAWL_DIR / _slug(exam_level) / question_id


def _already_crawled(question_id: str, exam_level: str) -> bool:
    parsed = _question_dir(exam_level, question_id) / "parsed.json"
    return parsed.exists()


def _save_artifacts(q: ParsedQuestion, exam_level: str) -> Path:
    qdir = _question_dir(exam_level, q.question_id)
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "problem_text.md").write_text(q.to_md(), encoding="utf-8")
    record = {
        "question_id": q.question_id,
        "url": q.url,
        "problem_text": q.problem_text,
        "solution_texts": q.solution_texts,
        "answer_choices": q.answer_choices,
        "answer_value": q.answer_value,
        "image_urls": q.image_urls,
        "parse_warnings": q.parse_warnings,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    (qdir / "parsed.json").write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    return qdir


def _update_db(
    conn: sqlite3.Connection,
    question_id: str,
    status: str,
    error: str = "",
    has_problem: bool = False,
    solution_count: int = 0,
) -> None:
    conn.execute(
        """UPDATE unmapped_questions
           SET mapping_status = ?,
               next_action    = ?,
               notes          = ?
           WHERE question_id = ?""",
        (
            status,
            "CLASSIFY" if status == "CRAWLED" else "RETRY",
            error or (f"solutions:{solution_count}" if has_problem else "no_problem_found"),
            question_id,
        ),
    )
    conn.commit()


# ── Queue fetcher ─────────────────────────────────────────────────────────────

def _fetch_queue(
    conn: sqlite3.Connection,
    limit: int,
    level_filter: str | None,
    retry_failed: bool,
) -> list[tuple[str, str, str]]:
    statuses = ("PENDING", "UNMAPPED") + (("FAILED",) if retry_failed else ())
    placeholders = ",".join("?" for _ in statuses)
    params: list = list(statuses)

    sql = f"""
        SELECT question_id, exam_level, problem_url
        FROM unmapped_questions
        WHERE mapping_status IN ({placeholders})
          AND problem_url != ''
    """
    if level_filter:
        sql += " AND exam_level = ?"
        params.append(level_filter)

    sql += " ORDER BY exam_level, question_id LIMIT ?"
    params.append(limit)

    return conn.execute(sql, params).fetchall()


# ── Progress summary ──────────────────────────────────────────────────────────

def _print_db_summary(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT mapping_status, COUNT(*) FROM unmapped_questions GROUP BY mapping_status ORDER BY 2 DESC"
    ).fetchall()
    console.print("\n[bold]Unmapped questions DB status:[/]")
    for status, n in rows:
        colour = {"CRAWLED": "green", "FAILED": "red", "PENDING": "dim"}.get(status, "white")
        console.print(f"  [{colour}]{status:<15} {n:>5}[/]")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Crawl and parse unmapped AoPS questions")
    p.add_argument("--limit",  type=int,   default=50,  help="Max questions per run (default 50)")
    p.add_argument("--delay",  type=float, default=3.0, help="Seconds between requests (default 3.0)")
    p.add_argument("--level",  type=str,   default=None,help="Filter by exam_level, e.g. 'AIME'")
    p.add_argument("--db",     type=Path,  default=DB_PATH)
    p.add_argument("--retry-failed", action="store_true", help="Re-process FAILED rows")
    p.add_argument("--reparse",      action="store_true", help="Re-parse already-downloaded HTML (no network)")
    p.add_argument("--dry-run", action="store_true", help="Show queue only, no network requests")
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    run = IngestionRun(conn, "crawl_unmapped", params=vars(args) | {"db": str(args.db)})
    run.__enter__()
    queue = _fetch_queue(conn, args.limit, args.level, args.retry_failed)

    if not queue:
        console.print("[yellow]No unmapped questions to process.[/]")
        _print_db_summary(conn)
        run.__exit__(None, None, None)
        conn.close()
        return

    console.print(f"\n[bold]Crawling {len(queue)} unmapped questions[/]  "
                  f"(delay={args.delay}s, dry_run={args.dry_run})")

    if args.dry_run:
        for qid, level, url in queue:
            console.print(f"  [dim]{qid:<30} {level:<10} {url}")
        _print_db_summary(conn)
        run.__exit__(None, None, None)
        conn.close()
        return

    # Reparse mode: scan filesystem for existing HTML, re-parse all without network.
    if args.reparse:
        html_files = sorted(CRAWL_DIR.rglob("problem.html"))
        if not html_files:
            console.print("[yellow]No downloaded HTML files found in data/crawl/.")
            conn.close()
            return

        # Build a lookup: question_id → (exam_level, url)
        db_lookup: dict[str, tuple[str, str]] = {
            qid: (level, url)
            for qid, level, url in conn.execute(
                "SELECT question_id, exam_level, problem_url FROM unmapped_questions"
            ).fetchall()
        }

        console.print(f"Reparsing {len(html_files)} downloaded HTML files...")
        ok = failed = 0
        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                      BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
                      console=console) as progress:
            task = progress.add_task("Reparsing", total=len(html_files))
            for html_path in html_files:
                question_id = html_path.parent.name
                level, url = db_lookup.get(question_id, ("", ""))
                progress.update(task, description=f"[cyan]{question_id}")
                try:
                    html = html_path.read_text(encoding="utf-8")
                    parsed = parse_aops_page(html, question_id, url)
                    _save_artifacts(parsed, level or html_path.parent.parent.name)
                    from mathbank.crawl.image_downloader import save_aops_images

                    save_aops_images(
                        conn, question_id, level or html_path.parent.parent.name,
                        html, url, download_missing=False,
                    )
                    _update_db(conn, question_id, "CRAWLED",
                               has_problem=parsed.has_problem,
                               solution_count=parsed.solution_count)
                    ok += 1
                except Exception as exc:
                    console.print(f"  [red]FAIL {question_id}: {exc}")
                    failed += 1
                progress.advance(task)

        console.print(f"\n[bold green]Reparse done.[/]  ok={ok}  failed={failed}")
        _print_db_summary(conn)
        run.update(processed=ok + failed, succeeded=ok, failed=failed)
        run.__exit__(None, None, None)
        conn.close()
        return

    session = make_session(warmup_aops=True)   # pre-seed AoPS cookies to avoid 403
    ok = failed = skipped = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task("Crawling", total=len(queue))

        for question_id, exam_level, url in queue:
            progress.update(task, description=f"[cyan]{question_id}")
            qdir = _question_dir(exam_level, question_id)

            # Skip questions already crawled in a previous run.
            if _already_crawled(question_id, exam_level):
                _update_db(conn, question_id, "CRAWLED")
                skipped += 1
                progress.advance(task)
                continue

            try:
                html = fetch_html(session, url, delay=args.delay)
            except (DownloadError, Exception) as exc:
                console.print(f"  [red]FAIL download {question_id}: {exc}")
                _update_db(conn, question_id, "FAILED", error=str(exc)[:200])
                failed += 1
                progress.advance(task)
                continue

            save_html(html, qdir / "problem.html")

            # Parse.
            try:
                parsed = parse_aops_page(html, question_id, url)
            except Exception as exc:
                console.print(f"  [red]FAIL parse {question_id}: {exc}")
                _update_db(conn, question_id, "FAILED", error=f"parse:{exc}"[:200])
                failed += 1
                progress.advance(task)
                continue

            _save_artifacts(parsed, exam_level)

            # Download actual diagram images (non-LaTeX) from the AoPS page.
            img_count = 0
            try:
                from mathbank.crawl.image_downloader import save_aops_images
                imgs = save_aops_images(conn, question_id, exam_level, html, url, session)
                img_count = len(imgs)
            except (OSError, sqlite3.Error) as exc:
                console.print(f"  [yellow]WARN {question_id}: diagram persistence failed: {exc}")

            _update_db(
                conn,
                question_id,
                "CRAWLED",
                has_problem=parsed.has_problem,
                solution_count=parsed.solution_count,
            )

            if parsed.parse_warnings:
                for w in parsed.parse_warnings:
                    console.print(f"  [yellow]WARN {question_id}: {w}")

            ok += 1
            progress.advance(task)

    console.print(
        f"\n[bold green]Done.[/]  "
        f"ok={ok}  failed={failed}  skipped(already crawled)={skipped}"
    )
    _print_db_summary(conn)
    console.print(f"\nArtifacts in: [cyan]{CRAWL_DIR}")
    run.update(processed=ok + failed + skipped, succeeded=ok, failed=failed)
    run.__exit__(None, None, None)
    conn.close()


if __name__ == "__main__":
    main()
