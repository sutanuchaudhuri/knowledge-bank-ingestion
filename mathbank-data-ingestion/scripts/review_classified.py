"""
Standalone reviewer — runs independently of the classifier.

Reviews SOLUTION_REVIEWED (or specified) questions using GPT-4o vision.
Loads local diagram images for questions that have them.

Usage:
    python scripts/review_classified.py                  # 20 questions
    python scripts/review_classified.py --limit 100
    python scripts/review_classified.py --level AIME
    python scripts/review_classified.py --status SOLUTION_REVIEWED
    python scripts/review_classified.py --retry-failed   # re-review NEEDS_HUMAN_REVIEW
    python scripts/review_classified.py --dry-run

Verdicts written to questions table:
    review_status              APPROVED | CORRECTED | NEEDS_HUMAN_REVIEW
    reviewed_at                timestamp
    reviewer_model             gpt-4o
    review_notes               explanation
    review_corrected_concept_id  non-empty when CORRECTED

When CORRECTED the question_taxonomy_maps row for the old primary mapping
is updated to association_type='Reviewed-incorrect' and a new PRIMARY row
is inserted for the corrected concept_id.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.db import DB_PATH
from mathbank.db.migrations import apply_all as apply_migrations
from mathbank.classify.reviewer import ReviewResult, review_question
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()
CRAWL_DIR = ROOT / "data" / "crawl"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _load_image_paths(question_id: str, exam_level: str, image_paths_json: str) -> list[str]:
    """Return existing local image paths for the question."""
    stored: list[str] = json.loads(image_paths_json) if image_paths_json else []
    # Filter to local files that actually exist (exclude AoPS CDN URLs)
    local = [p for p in stored if Path(p).exists()]

    # Also scan crawl dir for any PNG renders we have
    slug = _slug(exam_level)
    img_dir = CRAWL_DIR / slug / question_id / "images"
    if img_dir.exists():
        for f in sorted(img_dir.glob("*.png")):
            if str(f) not in local:
                local.append(str(f))
    return local


# ── Queue ─────────────────────────────────────────────────────────────────────

def _fetch_queue(
    conn: sqlite3.Connection,
    limit: int,
    level_filter: str | None,
    status_filter: str,
    retry_failed: bool,
) -> list[tuple]:
    statuses = [status_filter]
    if retry_failed:
        statuses.append("NEEDS_HUMAN_REVIEW")
    ph = ",".join("?" for _ in statuses)
    params: list = list(statuses)
    sql = f"""
        SELECT q.question_id, q.exam_level,
               COALESCE(m.concept_id, '') as primary_concept_id,
               COALESCE(q.difficulty_band, '') as difficulty_band,
               COALESCE(q.problem_text_latex, '') as problem_text,
               COALESCE(q.solution_text_latex, '') as solution_text,
               COALESCE(q.image_paths, '[]') as image_paths
        FROM questions q
        LEFT JOIN question_taxonomy_maps m
               ON m.question_id = q.question_id
              AND m.association_type = 'Primary Concept'
        WHERE q.classification_status IN ({ph})
          AND (q.review_status IS NULL OR q.review_status = '')
    """
    if level_filter:
        sql += " AND q.exam_level = ?"
        params.append(level_filter)
    sql += " ORDER BY q.exam_level, q.question_id LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


# ── DB writes ─────────────────────────────────────────────────────────────────

def _apply_review(conn: sqlite3.Connection, result: ReviewResult, old_concept_id: str) -> None:
    conn.execute(
        """UPDATE questions SET
              review_status                = ?,
              reviewed_at                  = ?,
              reviewer_model               = ?,
              review_notes                 = ?,
              review_corrected_concept_id  = ?,
              classification_status        = CASE
                WHEN ? = 'APPROVED' THEN 'FINE_COMPLETE'
                WHEN ? = 'CORRECTED' THEN 'FINE_COMPLETE'
                ELSE 'PARTIAL'
              END
           WHERE question_id = ?""",
        (
            result.verdict,
            _now(),
            result.model,
            result.review_notes,
            result.corrected_concept_id or "",
            result.verdict, result.verdict,
            result.question_id,
        ),
    )

    if result.verdict == "CORRECTED" and result.corrected_concept_id:
        # Demote old primary mapping.
        conn.execute(
            """UPDATE question_taxonomy_maps
               SET association_type = 'Reviewed-incorrect'
               WHERE question_id = ? AND association_type = 'Primary Concept'""",
            (result.question_id,),
        )
        # Insert corrected mapping.
        mapping_id = f"MAP_{result.corrected_concept_id}_{result.question_id}_REVIEW_V1"
        conn.execute(
            """INSERT OR REPLACE INTO question_taxonomy_maps
               (mapping_id, question_id, concept_id, association_type,
                evidence_source, confidence, notes)
               VALUES (?, ?, ?, 'Primary Concept',
                       ?, ?, ?)""",
            (
                mapping_id, result.question_id, result.corrected_concept_id,
                f"GPT-4o reviewer corrected from {old_concept_id}",
                result.confidence,
                result.review_notes,
            ),
        )
        # Update taxonomy_mapping_count.
        conn.execute(
            """UPDATE questions SET
                  taxonomy_mapping_count = (
                    SELECT COUNT(*) FROM question_taxonomy_maps
                    WHERE question_id = ? AND association_type != 'Reviewed-incorrect'
                  )
               WHERE question_id = ?""",
            (result.question_id, result.question_id),
        )

    conn.commit()


# ── Summary ───────────────────────────────────────────────────────────────────

def _print_summary(conn: sqlite3.Connection) -> None:
    t = Table("Review Status", "Count", show_lines=False, min_width=45)
    for status, n in conn.execute(
        "SELECT COALESCE(review_status,'PENDING'), COUNT(*) "
        "FROM questions WHERE classification_status NOT IN ('','UNCLASSIFIED') "
        "GROUP BY review_status ORDER BY 2 DESC"
    ).fetchall():
        colour = {"APPROVED": "green", "CORRECTED": "magenta",
                  "NEEDS_HUMAN_REVIEW": "yellow", "PENDING": "dim"}.get(status, "white")
        t.add_row(f"[{colour}]{status}", str(n))
    console.print()
    console.print(t)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Review classified questions with GPT-4o")
    p.add_argument("--limit",        type=int,   default=20)
    p.add_argument("--level",        type=str,   default=None)
    p.add_argument("--status",       type=str,   default="SOLUTION_REVIEWED",
                   help="classification_status to review (default: SOLUTION_REVIEWED)")
    p.add_argument("--db",           type=Path,  default=DB_PATH)
    p.add_argument("--retry-failed", action="store_true",
                   help="Also re-review NEEDS_HUMAN_REVIEW questions")
    p.add_argument("--dry-run",      action="store_true")
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    apply_migrations(conn)

    queue = _fetch_queue(conn, args.limit, args.level, args.status, args.retry_failed)

    if not queue:
        console.print("[yellow]No questions ready for review.")
        console.print("Run classify_crawled.py first, or check --status filter.")
        _print_summary(conn)
        conn.close()
        return

    console.print(f"\n[bold]Reviewing {len(queue)} questions[/]  "
                  f"(model=gpt-4o  dry_run={args.dry_run})\n")

    if args.dry_run:
        for qid, level, concept, diff, _, _, _ in queue[:10]:
            console.print(f"  [dim]{qid:<35} {level:<10} {concept}")
        _print_summary(conn)
        conn.close()
        return

    approved = corrected = needs_human = failed = 0

    with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                  BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(),
                  console=console) as progress:
        task = progress.add_task("Reviewing", total=len(queue))

        for qid, level, concept, diff, prob, sol, img_json in queue:
            progress.update(task, description=f"[cyan]{qid}")
            image_paths = _load_image_paths(qid, level, img_json)

            try:
                result = review_question(
                    conn, qid, level, concept, diff, prob, sol, image_paths
                )
            except Exception as exc:
                console.print(f"  [red]FAIL review {qid}: {exc}")
                failed += 1
                progress.advance(task)
                continue

            _apply_review(conn, result, old_concept_id=concept)

            if result.verdict == "APPROVED":
                approved += 1
            elif result.verdict == "CORRECTED":
                corrected += 1
                console.print(
                    f"  [magenta]CORRECTED {qid}: {concept} → {result.corrected_concept_id}"
                )
            else:
                needs_human += 1
                console.print(f"  [yellow]NEEDS_HUMAN {qid}: {result.review_notes[:80]}")

            progress.advance(task)

    console.print(
        f"\n[bold green]Done.[/]  "
        f"approved={approved}  corrected={corrected}  "
        f"needs_human={needs_human}  failed={failed}"
    )
    _print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
