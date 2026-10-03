"""
Build the local SQLite corpus database.

Usage:
    python scripts/build_sqlite.py               # builds data/mathbank.db
    python scripts/build_sqlite.py --fresh       # drops and rebuilds from scratch
    python scripts/build_sqlite.py --db /tmp/x.db

After running, inspect with:
    sqlite3 data/mathbank.db ".tables"
    sqlite3 data/mathbank.db "SELECT * FROM v_topic_question_counts LIMIT 20;"
    sqlite3 -column -header data/mathbank.db "SELECT * FROM v_competition_coverage;"
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.db import DB_PATH
from mathbank.db.schema import TABLES, INDEXES, VIEWS
from mathbank.db.loader import load_all
from rich.console import Console
from rich.table import Table as RichTable

console = Console()


# ── DDL helpers ───────────────────────────────────────────────────────────────

def _col_ddl(col_name: str, col_type: str) -> str:
    """Handle SQL comments in column type strings."""
    # Strip inline SQL comments (-- ...) which are valid in schema.py docs
    # but not in column definitions
    type_part = col_type.split("--")[0].strip()
    return f'    "{col_name}" {type_part}'


def create_schema(conn: sqlite3.Connection) -> None:
    console.print("\n[bold]Creating tables...")
    for table_name, cols in TABLES:
        col_defs = ",\n".join(_col_ddl(n, t) for n, t in cols)
        sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n{col_defs}\n)'
        conn.execute(sql)
    conn.commit()

    console.print("[bold]Creating indexes...")
    for idx_name, table_name, cols in INDEXES:
        col_list = ", ".join(f'"{c}"' for c in cols)
        sql = f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table_name}" ({col_list})'
        conn.execute(sql)
    conn.commit()

    console.print("[bold]Creating views...")
    for view_name, view_sql in VIEWS:
        conn.execute(f'DROP VIEW IF EXISTS "{view_name}"')
        conn.execute(f'CREATE VIEW "{view_name}" AS {view_sql}')
    conn.commit()


def drop_all(conn: sqlite3.Connection) -> None:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    for (name,) in cur.fetchall():
        conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='view'")
    for (name,) in cur.fetchall():
        conn.execute(f'DROP VIEW IF EXISTS "{name}"')
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
    for (name,) in cur.fetchall():
        conn.execute(f'DROP INDEX IF EXISTS "{name}"')
    conn.commit()


# ── Summary ───────────────────────────────────────────────────────────────────

def print_summary(conn: sqlite3.Connection, counts: dict[str, int]) -> None:
    console.print("\n[bold green]Build complete.[/]\n")

    t = RichTable("Table", "Rows", show_lines=False, min_width=50)
    total = 0
    for table, n in sorted(counts.items(), key=lambda x: -x[1]):
        t.add_row(table, f"{n:,}")
        total += n
    t.add_row("[bold]TOTAL", f"[bold]{total:,}")
    console.print(t)

    console.print("\n[bold]Key views available:")
    for view_name, _ in VIEWS:
        cur = conn.execute(f'SELECT COUNT(*) FROM "{view_name}"')
        n = cur.fetchone()[0]
        console.print(f"  {view_name:<40} {n:>6} rows")

    console.print(f"\nDB path: [cyan]{conn.execute('PRAGMA database_list').fetchone()[2]}")
    console.print("\nQuick-start queries:")
    console.print("  sqlite3 -column -header data/mathbank.db \"SELECT * FROM v_topic_question_counts LIMIT 20;\"")
    console.print("  sqlite3 -column -header data/mathbank.db \"SELECT * FROM v_competition_coverage;\"")
    console.print("  sqlite3 -column -header data/mathbank.db \"SELECT question_id,primary_topic,difficulty_band,classification_status FROM questions WHERE exam_level='AIME' LIMIT 20;\"")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Build mathbank SQLite database")
    p.add_argument("--db", type=Path, default=DB_PATH, help="Output DB path")
    p.add_argument("--fresh", action="store_true", help="Drop all tables before building")
    args = p.parse_args()

    db_path: Path = args.db
    db_path.parent.mkdir(parents=True, exist_ok=True)

    console.print(f"\n[bold]MathBank SQLite Builder[/]  →  {db_path}")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    if args.fresh:
        console.print("[yellow]--fresh: dropping existing schema...")
        drop_all(conn)

    create_schema(conn)

    console.print("\n[bold]Loading CSVs...")
    counts = load_all(conn, TABLES)

    print_summary(conn, counts)
    conn.close()


if __name__ == "__main__":
    main()
