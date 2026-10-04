"""
Classify PDF-archive competition questions (SMT / CHMMC / PUMaC / CMM / MPG_OLY)
against the taxonomy using OpenAI — the sibling of classify_crawled.py for
competitions whose problem text was never routed through unmapped_questions
(that table/pipeline is AoPS-only, i.e. AMC10/AMC12/AIME — see
mathbank_data_ingestion/Makefile's crawl-unmapped target).

Why this script exists (GOTCHAS.md #16 follow-up): `GET /v1/corpus/coverage`
showed SMT/CHMMC/PUMaC/CMM are 0-5% classified vs ~99% for AMC/AIME, because
classify_crawled.py structurally cannot see them. Their problem/solution text
already lives on disk, split per-question by mathbank-db/etl/load_corpus.py's
`load_pdf_crawl_problems()` (same source of truth core.problem.statement_text
comes from) at:
    data/crawl_pdf/<dir>/PAPER_<COMP>_<year>_<code>/questions/Q<nn>/problem.md (+ solution.md)

Reuses classify_crawled.py's taxonomy loader + concept/mapping writer
functions (same SQLite concepts/question_taxonomy_maps tables, so
export_classifications_to_csv.py bridges this run's output to the CSV mirror
exactly the same way it does for AMC/AIME — no changes needed there).

Idempotency: a `questions` row is created per canonical_code on first sight;
`classification_status = 'SOLUTION_REVIEWED'` marks it done, so re-running
this script only classifies newly-added or previously-failed
(`classification_status = 'PARTIAL'`, via --retry-failed) questions.

Usage:
    python scripts/classify_pdf_corpus.py --dry-run             # preview queue
    python scripts/classify_pdf_corpus.py --limit 50
    python scripts/classify_pdf_corpus.py --competition SMT --limit 100
    python scripts/classify_pdf_corpus.py --retry-failed --limit 20

Cost estimate: all five competitions use gpt-4o (see
concept_classifier._model_for_level) — ~$0.01/question.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from mathbank.db import DB_PATH  # noqa: E402
from mathbank.db.migrations import apply_all as apply_migrations  # noqa: E402
from mathbank.db.tracking import IngestionRun  # noqa: E402
from mathbank.classify.concept_classifier import classify_question, load_taxonomy_prompt_block  # noqa: E402
from classify_crawled import _insert_new_concept, _upsert_taxonomy_map  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()

# Must stay in sync with mathbank-db/etl/load_corpus.py's PDF_COMPETITION_DIRS /
# PAPER_ID_RE / MD_HEADER_RE / MD_IMAGE_BLOCK_RE — same source directories,
# same per-question split, same markdown cleanup (so classifier input text
# matches core.problem.statement_text as closely as possible).
PDF_CRAWL_DIR = ROOT / "data" / "crawl_pdf"
PDF_COMPETITION_DIRS = {
    "chmmc": "CHMMC",
    "cmm": "CMM",
    "mpg_oly": "MPG_OLY",
    "pumac": "PUMAC",
    "smt": "SMT",
    "hmmt_feb": "HMMT_FEB",
    "hmmt_nov": "HMMT_NOV",
    "hmmt_inv": "HMMT_INV",
}
PAPER_ID_RE = re.compile(r"^PAPER_[A-Z]+_(\d{4})_(.+)$")
MD_HEADER_RE = re.compile(r"^(#{1,2}[^\n]*\n+)+")
MD_IMAGE_BLOCK_RE = re.compile(r"\n+---\n+(!\[[^\n]*\n*)+\s*$")


def _clean_markdown(text: str) -> str:
    text = MD_HEADER_RE.sub("", text, count=1)
    text = MD_IMAGE_BLOCK_RE.sub("", text)
    return text.strip()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PdfQuestion:
    __slots__ = ("question_id", "exam_level", "paper_id", "problem_text", "solution_texts")

    def __init__(self, question_id: str, exam_level: str, paper_id: str, problem_text: str, solution_texts: list[str]):
        self.question_id = question_id
        self.exam_level = exam_level
        self.paper_id = paper_id
        self.problem_text = problem_text
        self.solution_texts = solution_texts


def discover_questions(competition_filter: str | None) -> list[PdfQuestion]:
    """Walk data/crawl_pdf/ the same way load_pdf_crawl_problems() does."""
    found: list[PdfQuestion] = []
    for dir_name, comp_code in PDF_COMPETITION_DIRS.items():
        if competition_filter and comp_code != competition_filter.upper():
            continue
        comp_dir = PDF_CRAWL_DIR / dir_name
        if not comp_dir.is_dir():
            continue
        for paper_dir in sorted(comp_dir.iterdir()):
            if not paper_dir.is_dir() or not PAPER_ID_RE.match(paper_dir.name):
                continue
            for q_dir in sorted((paper_dir / "questions").glob("Q*")):
                problem_md = q_dir / "problem.md"
                q_match = re.match(r"Q(\d+)", q_dir.name)
                if not problem_md.exists() or not q_match:
                    continue
                problem_number = int(q_match.group(1))
                canonical_code = f"{paper_dir.name}_Q{problem_number:02d}"
                statement_text = _clean_markdown(problem_md.read_text(encoding="utf-8").replace("\x00", ""))
                if not statement_text:
                    continue
                solution_texts = []
                solution_md = q_dir / "solution.md"
                if solution_md.exists():
                    sol = _clean_markdown(solution_md.read_text(encoding="utf-8").replace("\x00", ""))
                    if sol:
                        solution_texts = [sol]
                found.append(PdfQuestion(canonical_code, comp_code, paper_dir.name, statement_text, solution_texts))
    return found


def _ensure_question_row(conn: sqlite3.Connection, q: PdfQuestion) -> None:
    conn.execute(
        """INSERT OR IGNORE INTO questions
           (question_id, exam_level, paper_id, problem_text_latex, problem_text_raw,
            solution_text_latex, crawled_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (q.question_id, q.exam_level, q.paper_id, q.problem_text, q.problem_text,
         q.solution_texts[0] if q.solution_texts else "", _now()),
    )


def _fetch_queue(conn: sqlite3.Connection, all_questions: list[PdfQuestion], limit: int, retry_failed: bool) -> list[PdfQuestion]:
    done_statuses = {"SOLUTION_REVIEWED"} | (set() if retry_failed else {"PARTIAL"})
    rows = conn.execute(
        "SELECT question_id, classification_status FROM questions WHERE question_id IN (%s)"
        % ",".join("?" for _ in all_questions),
        [q.question_id for q in all_questions],
    ).fetchall() if all_questions else []
    status_by_id = {qid: status for qid, status in rows}
    queue = [q for q in all_questions if status_by_id.get(q.question_id) not in done_statuses]
    return queue[:limit]


def _finalize(conn: sqlite3.Connection, question_id: str, mapping_count: int, fine_count: int, model: str, notes: str) -> None:
    conn.execute(
        """UPDATE questions SET
            classification_status = 'SOLUTION_REVIEWED',
            taxonomy_evidence_status = 'AGENT_INFERRED',
            taxonomy_mapping_count = ?, distinct_concept_id_count = ?,
            fine_concept_mapping_count = ?, classified_at = ?,
            classifier_model = ?, classifier_notes = ?
           WHERE question_id = ?""",
        (mapping_count, mapping_count, fine_count, _now(), model, notes, question_id),
    )


def _mark_failed(conn: sqlite3.Connection, question_id: str, error: str) -> None:
    conn.execute(
        "UPDATE questions SET classification_status = 'PARTIAL', classifier_notes = ? WHERE question_id = ?",
        (error[:400], question_id),
    )


def _print_summary(conn: sqlite3.Connection, all_questions: list[PdfQuestion]) -> None:
    ids = [q.question_id for q in all_questions]
    if not ids:
        return
    rows = conn.execute(
        "SELECT COALESCE(classification_status, 'UNMAPPED'), COUNT(*) FROM questions "
        "WHERE question_id IN (%s) GROUP BY 1 ORDER BY 2 DESC" % ",".join("?" for _ in ids),
        ids,
    ).fetchall()
    t = Table("Status", "Count", min_width=40)
    for status, n in rows:
        colour = {"SOLUTION_REVIEWED": "green", "PARTIAL": "red"}.get(status, "dim")
        t.add_row(f"[{colour}]{status}", str(n))
    console.print(t)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--competition", type=str, default=None, help="SMT|CHMMC|PUMAC|CMM|MPG_OLY")
    p.add_argument("--paper", type=str, help="Only classify this exact paper")
    p.add_argument("--db", type=Path, default=DB_PATH)
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument(
        "--shard-count", type=int, default=1,
        help="Split a large competition's queue across N concurrent processes (see --shard-index)",
    )
    p.add_argument(
        "--shard-index", type=int, default=0,
        help="Which 0-based shard this process handles (0 <= shard-index < shard-count)",
    )
    args = p.parse_args()
    if not (0 <= args.shard_index < max(args.shard_count, 1)):
        p.error("--shard-index must be 0 <= shard-index < shard-count")

    conn = sqlite3.connect(args.db)
    # WAL + a generous busy_timeout let multiple `classify_pdf_corpus.py --competition X`
    # processes run concurrently against the same data/mathbank.db — the slow part
    # (OpenAI call) holds no lock; only the brief per-item INSERT/UPDATE does, and
    # WAL readers never block writers. Without this, parallel runs intermittently
    # hit "database is locked" since SQLite's default rollback-journal mode only
    # allows one writer at a time with no wait.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    apply_migrations(conn)

    run = IngestionRun(conn, "classify_pdf_corpus", params=vars(args) | {"db": str(args.db)})
    run.__enter__()

    all_questions = discover_questions(args.competition)
    if args.paper:
        all_questions = [q for q in all_questions if q.paper_id == args.paper]
    if not all_questions:
        console.print(f"[yellow]No PDF-archive questions found under {PDF_CRAWL_DIR}")
        run.__exit__(None, None, None)
        conn.close()
        return

    if args.shard_count > 1:
        # discover_questions() iterates sorted() paper/question dirs, so this
        # slice is stable across processes/runs regardless of how many rows
        # have since been classified — unlike an OFFSET on the dynamic
        # "still pending" queue, which would shift under concurrent workers.
        all_questions = all_questions[args.shard_index :: args.shard_count]
        console.print(
            f"[dim]shard {args.shard_index}/{args.shard_count}: "
            f"{len(all_questions)} of the full discovered set"
        )

    for q in all_questions:
        _ensure_question_row(conn, q)
    conn.commit()

    queue = _fetch_queue(conn, all_questions, args.limit, args.retry_failed)
    if not queue:
        console.print("[yellow]No PDF-archive questions left to classify.")
        _print_summary(conn, all_questions)
        run.__exit__(None, None, None)
        conn.close()
        return

    console.print(f"\n[bold]Classifying {len(queue)} PDF-archive questions[/]  (dry_run={args.dry_run})")
    if args.dry_run:
        for q in queue[:10]:
            console.print(f"  [dim]{q.question_id:<35} {q.exam_level}")
        _print_summary(conn, all_questions)
        run.__exit__(None, None, None)
        conn.close()
        return

    taxonomy_block = load_taxonomy_prompt_block(conn)
    console.print(f"Taxonomy loaded: {taxonomy_block.count(chr(10))} concepts in prompt\n")

    ok = failed = new_concepts = 0
    with Progress(
        SpinnerColumn(), TextColumn("[progress.description]{task.description}"),
        BarColumn(), MofNCompleteColumn(), TimeElapsedColumn(), console=console,
    ) as progress:
        task = progress.add_task("Classifying", total=len(queue))
        for q in queue:
            progress.update(task, description=f"[cyan]{q.question_id}")
            try:
                result = classify_question(
                    conn=conn,
                    question_id=q.question_id,
                    exam_level=q.exam_level,
                    problem_text=q.problem_text,
                    solution_texts=q.solution_texts,
                    image_paths=[],
                    answer_value="",
                    taxonomy_block=taxonomy_block,
                )
            except Exception as exc:
                console.print(f"  [red]FAIL classify {q.question_id}: {exc}")
                _mark_failed(conn, q.question_id, str(exc))
                conn.commit()
                failed += 1
                progress.advance(task)
                continue

            mapping_count = 0
            for mapping in result.all_mappings:
                if not mapping.canonical_topic_id or mapping.canonical_topic_id == "UNKNOWN":
                    continue
                if mapping.is_new and mapping.new_concept_data:
                    _insert_new_concept(conn, mapping.new_concept_data)
                    new_concepts += 1
                    console.print(
                        f"  [magenta]NEW concept: {mapping.canonical_topic_id} "
                        f"({mapping.new_concept_data.get('canonical_path', '')})"
                    )
                _upsert_taxonomy_map(conn, q.question_id, mapping, q.exam_level, "", q.paper_id, result.model)
                mapping_count += 1

            fine_count = sum(1 for m in result.all_mappings if not m.is_new)
            if not mapping_count:
                _mark_failed(conn, q.question_id, "Model returned no usable taxonomy mapping")
                conn.commit()
                failed += 1
                progress.advance(task)
                continue
            _finalize(conn, q.question_id, mapping_count, fine_count, result.model, result.classifier_notes)
            conn.commit()
            ok += 1
            progress.advance(task)

    console.print(f"\nDone.  classified={ok}  failed={failed}  new_concepts_created={new_concepts}\n")
    _print_summary(conn, all_questions)
    run.update(processed=ok + failed, succeeded=ok, failed=failed)
    if failed:
        run.__exit__(RuntimeError, RuntimeError(f"{failed} questions failed classification"), None)
        conn.close()
        raise SystemExit(1)
    run.__exit__(None, None, None)
    conn.close()


if __name__ == "__main__":
    main()
