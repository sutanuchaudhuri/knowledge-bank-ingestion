"""Classification-quality eval — blind re-classification against hand-reviewed
gold labels, plus always-on corpus health checks (no LLM needed).

Ground truth strategy: rows where a human (via scripts/review_classified.py)
set review_status IN ('APPROVED', 'CORRECTED') have a verified-correct
Primary Concept mapping — APPROVED rows were left as-is by the reviewer,
CORRECTED rows already had their Primary Concept row replaced with the
human-corrected concept_id (see review_classified.py's _apply_review). This
reuses the review pass as a free hand-verified gold set instead of hand
labeling a separate one.

Usage:
    python scripts/evaluate_classification.py                 # corpus health only
    python scripts/evaluate_classification.py --reclassify --limit 20   # + blind LLM re-run (costs credits)
    python scripts/evaluate_classification.py --reclassify --level AIME --limit 10
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.classify.concept_classifier import classify_question, load_taxonomy_prompt_block
from mathbank.db import DB_PATH

EVAL_HISTORY_PATH = ROOT / "eval_history.csv"
_CSV_FIELDS = ["run_at", "git_sha", "metric", "value", "n", "details"]


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return "unknown"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _append_history(log_file: Path | None, rows: list[dict]) -> None:
    if log_file is None:
        return
    is_new = not log_file.exists()
    with open(log_file, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        if is_new:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


# ── Corpus health (cheap, always runs, no LLM) ───────────────────────────────

def corpus_health(conn: sqlite3.Connection) -> list[dict]:
    run_at, git_sha = _now(), _git_sha()
    rows: list[dict] = []

    total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    rows.append({"run_at": run_at, "git_sha": git_sha, "metric": "corpus_total_questions",
                 "value": total, "n": total, "details": ""})

    for col, label in (
        ("problem_text_latex", "pct_with_problem_text"),
        ("solution_text_latex", "pct_with_solution_text"),
        ("answer_value", "pct_with_answer_value"),
    ):
        n = conn.execute(
            f"SELECT COUNT(*) FROM questions WHERE {col} IS NOT NULL AND TRIM({col}) != ''"
        ).fetchone()[0]
        pct = round(n / total, 4) if total else 0.0
        rows.append({"run_at": run_at, "git_sha": git_sha, "metric": label,
                     "value": pct, "n": total, "details": f"{n}/{total} non-empty"})

    status_counts = conn.execute(
        "SELECT COALESCE(classification_status, 'UNMAPPED'), COUNT(*) FROM questions GROUP BY 1 ORDER BY 2 DESC"
    ).fetchall()
    for status, count in status_counts:
        rows.append({"run_at": run_at, "git_sha": git_sha, "metric": f"status_count__{status}",
                     "value": count, "n": total, "details": ""})

    fine_complete = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE classification_status = 'FINE_COMPLETE'"
    ).fetchone()[0]
    reviewed = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE classification_status = 'FINE_COMPLETE' "
        "AND review_status IN ('APPROVED', 'CORRECTED')"
    ).fetchone()[0]
    pct_reviewed = round(reviewed / fine_complete, 4) if fine_complete else 0.0
    rows.append({"run_at": run_at, "git_sha": git_sha, "metric": "pct_fine_complete_human_reviewed",
                 "value": pct_reviewed, "n": fine_complete,
                 "details": f"{reviewed}/{fine_complete} FINE_COMPLETE rows have a review_status"})

    corrected = conn.execute(
        "SELECT COUNT(*) FROM questions WHERE review_status = 'CORRECTED'"
    ).fetchone()[0]
    pct_corrected_of_reviewed = round(corrected / reviewed, 4) if reviewed else 0.0
    rows.append({"run_at": run_at, "git_sha": git_sha, "metric": "pct_reviewed_that_were_corrected",
                 "value": pct_corrected_of_reviewed, "n": reviewed,
                 "details": "high values signal the classifier prompt/taxonomy needs attention"})

    return rows


# ── Blind re-classification accuracy (costs OpenAI credits) ──────────────────

def _fetch_gold_rows(conn: sqlite3.Connection, limit: int, level: str | None) -> list[tuple]:
    sql = """
        SELECT q.question_id, q.exam_level, q.problem_text_latex, q.solution_text_latex,
               q.image_paths, q.answer_value, m.concept_id AS gold_concept_id
        FROM questions q
        JOIN question_taxonomy_maps m
          ON m.question_id = q.question_id AND m.association_type = 'Primary Concept'
        WHERE q.review_status IN ('APPROVED', 'CORRECTED')
    """
    params: list = []
    if level:
        sql += " AND q.exam_level = ?"
        params.append(level)
    sql += " ORDER BY RANDOM() LIMIT ?"
    params.append(limit)
    return conn.execute(sql, params).fetchall()


def reclassification_accuracy(conn: sqlite3.Connection, limit: int, level: str | None) -> list[dict]:
    import json

    rows = _fetch_gold_rows(conn, limit, level)
    if not rows:
        print("No hand-reviewed (APPROVED/CORRECTED) rows found — run `make review` first.")
        return []

    taxonomy_block = load_taxonomy_prompt_block(conn)
    matches = 0
    mismatches: list[str] = []
    for question_id, exam_level, problem_text, solution_text, image_paths_json, answer_value, gold_concept_id in rows:
        image_paths = json.loads(image_paths_json) if image_paths_json else []
        try:
            result = classify_question(
                conn=conn,
                question_id=question_id,
                exam_level=exam_level,
                problem_text=problem_text or "",
                solution_texts=[solution_text] if solution_text else [],
                image_paths=image_paths,
                answer_value=answer_value or "",
                taxonomy_block=taxonomy_block,
            )
        except Exception as exc:
            print(f"  FAIL re-classify {question_id}: {exc}")
            continue
        predicted = result.primary_mapping.canonical_topic_id
        if predicted == gold_concept_id:
            matches += 1
        else:
            mismatches.append(f"{question_id}: predicted={predicted!r} gold={gold_concept_id!r}")
        print(f"  {question_id}: predicted={predicted!r} gold={gold_concept_id!r} "
              f"{'MATCH' if predicted == gold_concept_id else 'MISMATCH'}")

    n = len(rows)
    accuracy = round(matches / n, 4) if n else 0.0
    details = "; ".join(mismatches[:10]) + (" ..." if len(mismatches) > 10 else "")
    return [{
        "run_at": _now(), "git_sha": _git_sha(), "metric": "primary_concept_reclassification_accuracy",
        "value": accuracy, "n": n, "details": details,
    }]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(DB_PATH))
    parser.add_argument("--reclassify", action="store_true",
                         help="Also blind re-run the classifier against hand-reviewed gold rows (costs OpenAI credits)")
    parser.add_argument("--limit", type=int, default=20, help="Gold rows to sample for --reclassify (default: 20)")
    parser.add_argument("--level", default=None, help="Filter gold rows to one exam_level (e.g. AIME)")
    parser.add_argument("--log-file", default=str(EVAL_HISTORY_PATH),
                         help="CSV to append results to ('' disables)")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    log_file = Path(args.log_file) if args.log_file else None

    print("=== Corpus health ===")
    health_rows = corpus_health(conn)
    for row in health_rows:
        print(f"  {row['metric']}: {row['value']}  ({row['details']})")
    _append_history(log_file, health_rows)

    if args.reclassify:
        print(f"\n=== Blind re-classification accuracy (n<={args.limit}, level={args.level or 'all'}) ===")
        accuracy_rows = reclassification_accuracy(conn, args.limit, args.level)
        for row in accuracy_rows:
            print(f"\n  {row['metric']}: {row['value']} (n={row['n']})")
        _append_history(log_file, accuracy_rows)

    conn.close()
    if log_file:
        print(f"\nAppended results to {log_file}")


if __name__ == "__main__":
    main()
