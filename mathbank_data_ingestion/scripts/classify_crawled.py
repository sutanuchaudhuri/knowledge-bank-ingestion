"""
Classify crawled questions against the taxonomy using OpenAI.

For each CRAWLED question in unmapped_questions:
  1. Load parsed.json (problem text, solution, images)
  2. Store raw + LaTeX text in the questions table
  3. Call OpenAI to map to taxonomy concepts
  4. Upsert question_taxonomy_maps rows (existing or new concepts)
  5. Insert new concepts into the concepts table if needed
  6. Update unmapped_questions.mapping_status → CLASSIFIED
  7. Update questions.classification_status → SOLUTION_REVIEWED

Usage:
    python scripts/classify_crawled.py                     # 20 questions (safe first run)
    python scripts/classify_crawled.py --limit 100
    python scripts/classify_crawled.py --level AIME        # AIME only (gpt-4o)
    python scripts/classify_crawled.py --dry-run           # show queue, no API calls
    python scripts/classify_crawled.py --retry-failed      # re-try CLASSIFY_FAILED rows

Cost estimate:
    AMC  (gpt-4o-mini): ~$0.001 per question
    AIME (gpt-4o):      ~$0.010 per question
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
from mathbank.classify.concept_classifier import (
    ClassificationResult,
    ConceptMapping,
    classify_question,
    load_taxonomy_prompt_block,
)
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

console = Console()

CRAWL_DIR = ROOT / "data" / "crawl"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_parsed_json(question_id: str, exam_level: str) -> dict | None:
    """Find parsed.json for a question (crawl dir uses slugged exam_level)."""
    # Try exact slug match first, then scan all subdirs.
    for subdir in CRAWL_DIR.rglob(question_id):
        p = subdir / "parsed.json"
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    return None


# ── DB writes ─────────────────────────────────────────────────────────────────

def _upsert_question_text(
    conn: sqlite3.Connection,
    question_id: str,
    parsed: dict,
    exam_level: str,
) -> None:
    """Store problem/solution text and metadata in the questions table."""
    solutions = parsed.get("solution_texts") or []
    first_sol = solutions[0] if solutions else ""

    conn.execute(
        """UPDATE questions SET
            problem_text_latex  = ?,
            problem_text_raw    = ?,
            solution_text_latex = ?,
            all_solutions_json  = ?,
            image_paths         = ?,
            answer_value        = ?,
            parse_warnings      = ?,
            crawled_at          = ?
           WHERE question_id = ?""",
        (
            parsed.get("problem_text", ""),
            parsed.get("problem_text", ""),   # raw = latex for AoPS (already clean)
            first_sol,
            json.dumps(solutions, ensure_ascii=False),
            json.dumps(parsed.get("image_urls") or [], ensure_ascii=False),
            parsed.get("answer_value", ""),
            json.dumps(parsed.get("parse_warnings") or [], ensure_ascii=False),
            parsed.get("crawled_at", ""),
            question_id,
        ),
    )

    # Also ensure the question row exists (may be in unmapped_questions but not questions).
    exists = conn.execute(
        "SELECT 1 FROM questions WHERE question_id = ?", (question_id,)
    ).fetchone()
    if not exists:
        conn.execute(
            """INSERT OR IGNORE INTO questions
               (question_id, exam_level, problem_text_latex, problem_text_raw,
                solution_text_latex, all_solutions_json, image_paths,
                answer_value, parse_warnings, crawled_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                question_id,
                exam_level,
                parsed.get("problem_text", ""),
                parsed.get("problem_text", ""),
                first_sol,
                json.dumps(solutions, ensure_ascii=False),
                json.dumps(parsed.get("image_urls") or [], ensure_ascii=False),
                parsed.get("answer_value", ""),
                json.dumps(parsed.get("parse_warnings") or [], ensure_ascii=False),
                parsed.get("crawled_at", ""),
            ),
        )


def _insert_new_concept(conn: sqlite3.Connection, data: dict) -> None:
    """Insert a new concept proposed by the classifier."""
    conn.execute(
        """INSERT OR IGNORE INTO concepts
           (canonical_topic_id, domain, topic, subtopic, concept_or_technique,
            node_type, canonical_path, definition)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get("canonical_topic_id", ""),
            data.get("domain", ""),
            data.get("topic", ""),
            data.get("subtopic", ""),
            data.get("concept_or_technique", ""),
            data.get("node_type", "Concept"),
            data.get("canonical_path", ""),
            data.get("definition", ""),
        ),
    )


def _upsert_taxonomy_map(
    conn: sqlite3.Connection,
    question_id: str,
    mapping: ConceptMapping,
    exam_level: str,
    test_id: str,
    paper_id: str,
    model: str,
) -> None:
    mapping_id = f"MAP_{mapping.canonical_topic_id}_{question_id}_OPENAI_V1"
    conn.execute(
        """INSERT OR REPLACE INTO question_taxonomy_maps
           (mapping_id, question_id, test_id, exam_level,
            concept_id, association_type, evidence_source,
            confidence, notes, canonical_paper_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            mapping_id,
            question_id,
            test_id,
            exam_level,
            mapping.canonical_topic_id,
            mapping.association_type,
            f"OpenAI {model} classifier — {mapping.evidence}",
            mapping.confidence,
            mapping.evidence,
            paper_id,
        ),
    )


def _finalize_question(
    conn: sqlite3.Connection,
    question_id: str,
    result: ClassificationResult,
    mapping_count: int,
) -> None:
    conn.execute(
        """UPDATE questions SET
            classification_status  = 'SOLUTION_REVIEWED',
            taxonomy_evidence_status = 'AGENT_INFERRED',
            taxonomy_mapping_count = ?,
            distinct_concept_id_count = ?,
            fine_concept_mapping_count = ?,
            classified_at   = ?,
            classifier_model = ?,
            classifier_notes = ?
           WHERE question_id = ?""",
        (
            mapping_count,
            mapping_count,
            sum(1 for m in result.all_mappings
                if not m.is_new),   # fine = matched to existing concept
            _now(),
            result.model,
            result.classifier_notes,
            question_id,
        ),
    )
    conn.execute(
        """UPDATE unmapped_questions
           SET mapping_status = 'CLASSIFIED', next_action = 'REVIEW'
           WHERE question_id = ?""",
        (question_id,),
    )


def _mark_failed(conn: sqlite3.Connection, question_id: str, error: str) -> None:
    conn.execute(
        "UPDATE unmapped_questions SET mapping_status = 'CLASSIFY_FAILED', notes = ? WHERE question_id = ?",
        (error[:400], question_id),
    )
    conn.execute(
        "UPDATE questions SET classification_status = 'PARTIAL' WHERE question_id = ?",
        (question_id,),
    )


# ── Queue ─────────────────────────────────────────────────────────────────────

def _fetch_queue(
    conn: sqlite3.Connection,
    limit: int,
    level_filter: str | None,
    retry_failed: bool,
) -> list[tuple[str, str, str]]:
    statuses = ("CRAWLED",) + (("CLASSIFY_FAILED",) if retry_failed else ())
    ph = ",".join("?" for _ in statuses)
    params: list = list(statuses)
    sql = f"""
        SELECT u.question_id, u.exam_level, u.problem_url
        FROM unmapped_questions u
        WHERE u.mapping_status IN ({ph})
    """
    if level_filter:
        sql += " AND u.exam_level = ?"
        params.append(level_filter)
    sql += " ORDER BY u.exam_level, u.question_id LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def _question_meta(conn: sqlite3.Connection, qid: str) -> tuple[str, str]:
    """Return (test_id, paper_id) for a question, empty string if not found."""
    row = conn.execute(
        "SELECT test_id, paper_id FROM questions WHERE question_id = ?", (qid,)
    ).fetchone()
    return (row[0] or "", row[1] or "") if row else ("", "")


# ── Summary ───────────────────────────────────────────────────────────────────

def _print_summary(conn: sqlite3.Connection) -> None:
    t = Table("Status", "Count", show_lines=False, min_width=40)
    for status, n in conn.execute(
        "SELECT mapping_status, COUNT(*) FROM unmapped_questions GROUP BY mapping_status ORDER BY 2 DESC"
    ).fetchall():
        colour = {
            "CLASSIFIED": "green", "CRAWLED": "cyan",
            "CLASSIFY_FAILED": "red", "FAILED": "red",
            "UNMAPPED": "dim",
        }.get(status, "white")
        t.add_row(f"[{colour}]{status}", str(n))
    console.print()
    console.print(t)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Classify crawled questions with OpenAI")
    p.add_argument("--limit",        type=int,   default=20)
    p.add_argument("--level",        type=str,   default=None, help="Filter by exam_level")
    p.add_argument("--db",           type=Path,  default=DB_PATH)
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--dry-run",      action="store_true")
    args = p.parse_args()

    conn = sqlite3.connect(args.db)
    apply_migrations(conn)

    queue = _fetch_queue(conn, args.limit, args.level, args.retry_failed)

    if not queue:
        console.print("[yellow]No CRAWLED questions to classify. Run crawl_unmapped.py first.")
        _print_summary(conn)
        conn.close()
        return

    console.print(f"\n[bold]Classifying {len(queue)} questions[/]  (dry_run={args.dry_run})")

    if args.dry_run:
        for qid, level, url in queue[:10]:
            console.print(f"  [dim]{qid:<35} {level}")
        _print_summary(conn)
        conn.close()
        return

    # Build taxonomy block once — reused across all calls.
    taxonomy_block = load_taxonomy_prompt_block(conn)
    concept_count = taxonomy_block.count("\n")
    console.print(f"Taxonomy loaded: {concept_count} concepts in prompt\n")

    ok = failed = new_concepts = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Classifying", total=len(queue))

        for question_id, exam_level, url in queue:
            progress.update(task, description=f"[cyan]{question_id}")

            parsed = _load_parsed_json(question_id, exam_level)
            if not parsed:
                console.print(f"  [yellow]WARN {question_id}: no parsed.json found — crawl first")
                progress.advance(task)
                continue

            # Store raw+latex text in questions table first.
            _upsert_question_text(conn, question_id, parsed, exam_level)
            conn.commit()

            problem_text = parsed.get("problem_text", "")
            if not problem_text.strip():
                console.print(f"  [yellow]WARN {question_id}: empty problem text — skipping classify")
                _mark_failed(conn, question_id, "empty_problem_text")
                conn.commit()
                progress.advance(task)
                continue

            try:
                result = classify_question(
                    conn=conn,
                    question_id=question_id,
                    exam_level=exam_level,
                    problem_text=problem_text,
                    solution_texts=parsed.get("solution_texts") or [],
                    image_paths=parsed.get("image_urls") or [],
                    answer_value=parsed.get("answer_value", ""),
                    taxonomy_block=taxonomy_block,
                )
            except Exception as exc:
                console.print(f"  [red]FAIL classify {question_id}: {exc}")
                _mark_failed(conn, question_id, str(exc)[:400])
                conn.commit()
                failed += 1
                progress.advance(task)
                continue

            # Apply difficulty suggestion back to questions table.
            if result.suggested_difficulty:
                conn.execute(
                    "UPDATE questions SET difficulty_band = ? WHERE question_id = ? AND (difficulty_band IS NULL OR difficulty_band = '')",
                    (result.suggested_difficulty, question_id),
                )

            if result.suggested_primary_topic:
                conn.execute(
                    "UPDATE questions SET primary_topic = ? WHERE question_id = ? AND (primary_topic IS NULL OR primary_topic = '')",
                    (result.suggested_primary_topic, question_id),
                )

            test_id, paper_id = _question_meta(conn, question_id)
            mapping_count = 0

            for mapping in result.all_mappings:
                if not mapping.canonical_topic_id or mapping.canonical_topic_id == "UNKNOWN":
                    continue

                # Insert new concept into taxonomy if needed.
                if mapping.is_new and mapping.new_concept_data:
                    _insert_new_concept(conn, mapping.new_concept_data)
                    new_concepts += 1
                    console.print(
                        f"  [magenta]NEW concept: {mapping.canonical_topic_id} "
                        f"({mapping.new_concept_data.get('canonical_path', '')})"
                    )

                _upsert_taxonomy_map(
                    conn, question_id, mapping, exam_level, test_id, paper_id, result.model
                )
                mapping_count += 1

            _finalize_question(conn, question_id, result, mapping_count)
            conn.commit()
            ok += 1
            progress.advance(task)

    console.print(
        f"\n[bold green]Done.[/]  "
        f"classified={ok}  failed={failed}  new_concepts_created={new_concepts}"
    )
    _print_summary(conn)
    conn.close()


if __name__ == "__main__":
    main()
