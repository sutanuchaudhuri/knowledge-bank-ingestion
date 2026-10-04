"""Print a progress table of every ingestion_runs row (one per script
invocation of crawl_unmapped.py / classify_crawled.py / classify_pdf_corpus.py /
export_classifications_to_csv.py) — see src/mathbank/db/tracking.py.

Usage:
    python scripts/show_progress.py                  # last 20 runs, any script
    python scripts/show_progress.py --script classify_pdf_corpus
    python scripts/show_progress.py --limit 50
    python scripts/show_progress.py --tail-log <run_id>   # print that run's full log file
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.db import DB_PATH  # noqa: E402
from mathbank.db.tracking import ensure_table  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--script", type=str, default=None, help="Filter by script name")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--tail-log", type=str, default=None, help="Print the full log for this run_id")
    args = p.parse_args()

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    if args.tail_log:
        row = conn.execute(
            "SELECT log_path FROM ingestion_runs WHERE run_id = ?", (args.tail_log,)
        ).fetchone()
        if not row or not row[0]:
            console.print(f"[red]No log found for run_id {args.tail_log!r}")
            return
        console.print(Path(row[0]).read_text(encoding="utf-8"))
        return

    clauses, params = [], []
    if args.script:
        clauses.append("script = ?")
        params.append(args.script)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT run_id, script, status, started_at, finished_at, processed, succeeded, failed "
        f"FROM ingestion_runs {where} ORDER BY started_at DESC LIMIT ?",
        [*params, args.limit],
    ).fetchall()

    table = Table(title="Ingestion runs (mathbank_data_ingestion)")
    for col in ("run_id", "script", "status", "started_at", "finished_at", "processed", "succeeded", "failed"):
        table.add_column(col)
    status_colour = {"SUCCESS": "green", "FAILED": "red", "RUNNING": "yellow"}
    for run_id, script, status, started_at, finished_at, processed, succeeded, failed in rows:
        colour = status_colour.get(status, "white")
        table.add_row(
            run_id, script, f"[{colour}]{status}[/]",
            (started_at or "")[:19], (finished_at or "—")[:19],
            str(processed), str(succeeded), str(failed),
        )
    console.print(table)

    running = [r for r in rows if r[2] == "RUNNING"]
    if running:
        console.print(
            f"[yellow]{len(running)} run(s) still marked RUNNING — if the process isn't actually "
            "alive (check `ps aux`), it crashed/was killed without updating its final status."
        )
    console.print(f"\nFull log: python scripts/show_progress.py --tail-log <run_id>")


if __name__ == "__main__":
    main()
