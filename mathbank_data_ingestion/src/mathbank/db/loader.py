"""
CSV → SQLite loader.

Loads each CSV into its pre-created table using bulk INSERT.
Handles:
  - Column name normalisation (CSV header → snake_case DB column)
  - Skipped files (malformed / layout-only sheets)
  - Domain-union tables (4 domain CSVs → domain_indexed_questions)
  - Integer / real coercion where the schema specifies non-TEXT columns
"""
from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console()

CORPUS_DIR = Path(__file__).resolve().parents[1] / "data" / "maths_corpus"

# ── Column normalisation ──────────────────────────────────────────────────────

def _slug(s: str) -> str:
    """CSV header cell → snake_case identifier."""
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_") or "col"


def _coerce(value: str, col_type: str) -> Any:
    v = value.strip()
    if col_type == "INTEGER":
        try:
            return int(float(v)) if v else None
        except (ValueError, OverflowError):
            return None
    if col_type == "REAL":
        try:
            return float(v) if v else None
        except ValueError:
            return None
    return v if v else None


# ── Schema column type lookup ─────────────────────────────────────────────────

def _build_type_map(schema_tables: list) -> dict[str, dict[str, str]]:
    """Returns {table_name: {col_name: col_type}} from schema.TABLES."""
    result: dict[str, dict[str, str]] = {}
    for table_name, cols in schema_tables:
        result[table_name] = {}
        for col_name, col_type in cols:
            base_type = col_type.split()[0]  # strip PRIMARY KEY etc.
            result[table_name][col_name] = base_type
    return result


# ── CSV file map: table_name → (csv_filename, pk_column or None) ──────────────

CSV_TABLE_MAP: dict[str, tuple[str, str | None]] = {
    "competitions":           ("competition_catalog.csv",             "competition_id"),
    "archive_families":       ("archive_family_registry.csv",         "archive_record_id"),
    "tournament_events":      ("tournament_archive_registry.csv",     "tournament_event_id"),
    "exam_entries":           ("test_registry.csv",                   "test_id"),
    "papers":                 ("paper_registry.csv",                  "paper_id"),
    "questions":              ("question_index.csv",                  "question_id"),
    "concepts":               ("canonical_topic_hierarchy.csv",       "canonical_topic_id"),
    "topic_aliases":          ("topic_alias_index.csv",               None),
    "techniques":             ("technique_catalog.csv",               "technique_id"),
    "question_taxonomy_maps": ("question_taxonomy_map.csv",           "mapping_id"),
    "question_technique_maps":("question_technique_map.csv",          "technique_map_id"),
    "knowledge_graph_edges":  ("knowledge_graph_edges.csv",           "edge_id"),
    "source_ingestion":       ("source_ingestion_queue.csv",          "source_id"),
    "topic_coverage":         ("topic_coverage_matrix.csv",           None),
    "aime_year_index":        ("aime_year_index.csv",                 "test_id"),
    "aime_glossary":          ("aime_glossary.csv",                   "glossary_id"),
    "unparsed_papers":        ("unparsed_paper_queue.csv",            "paper_id"),
    "unmapped_questions":     ("unmapped_question_queue.csv",         "question_id"),
    "fine_concept_gaps":      ("fine_concept_gap_queue.csv",          "question_id"),
    "corpus_tasks":           ("corpus_task_tracker.csv",             "task_id"),
    "fast_topic_index":       ("fast_topic_question_index.csv",       "index_key"),
}

# Domain CSV files → domain_indexed_questions (unioned with domain label)
DOMAIN_CSVS: dict[str, str] = {
    "Combinatorics":   "combinatorics_indexed_questions.csv",
    "Geometry":        "geometry_indexed_questions.csv",
    "Number Theory":   "number_theory_indexed_questions.csv",
    "Complex Numbers": "complex_numbers_indexed_questio.csv",
}

# CSV column headers → DB column names overrides (where slug doesn't match)
COLUMN_OVERRIDES: dict[str, dict[str, str]] = {
    "questions": {
        "latest_tika_answer": "latest_student_answer",
        "latest_tika_result": "latest_result",
    },
    "fast_topic_index": {
        "tika_attempt_status": "student_attempt_status",
        "tika_result":         "student_result",
    },
}


def _load_csv(
    conn: sqlite3.Connection,
    table: str,
    csv_path: Path,
    type_map: dict[str, str],
    overrides: dict[str, str] | None = None,
    extra_cols: dict[str, Any] | None = None,
) -> int:
    """Load one CSV into one table. Returns number of rows inserted."""
    if not csv_path.exists():
        console.print(f"  [yellow]SKIP (not found)[/] {csv_path.name}")
        return 0

    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        raw_headers = reader.fieldnames or []

    # Map CSV header → DB column name
    col_map: dict[str, str] = {}
    for h in raw_headers:
        db_col = _slug(h)
        if overrides and db_col in overrides:
            db_col = overrides[db_col]
        col_map[h] = db_col

    # Only insert columns that exist in the DB schema
    valid_db_cols = set(type_map.keys())
    # Extra fixed columns (e.g. domain for domain union table)
    extra = extra_cols or {}

    rows_inserted = 0
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        batch: list[dict] = []
        for row in reader:
            record: dict[str, Any] = {}
            for csv_col, db_col in col_map.items():
                if db_col in valid_db_cols:
                    raw_val = row.get(csv_col, "") or ""
                    record[db_col] = _coerce(raw_val, type_map.get(db_col, "TEXT"))
            record.update(extra)
            if record:
                batch.append(record)

            if len(batch) >= 500:
                _insert_batch(conn, table, batch)
                rows_inserted += len(batch)
                batch = []

        if batch:
            _insert_batch(conn, table, batch)
            rows_inserted += len(batch)

    return rows_inserted


def _insert_batch(conn: sqlite3.Connection, table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(f'"{c}"' for c in cols)
    sql = f'INSERT OR REPLACE INTO "{table}" ({col_list}) VALUES ({placeholders})'
    conn.executemany(sql, [[r.get(c) for c in cols] for r in rows])
    conn.commit()


def load_all(conn: sqlite3.Connection, schema_tables: list) -> dict[str, int]:
    """Load all CSVs into the database. Returns {table: row_count}."""
    type_maps = _build_type_map(schema_tables)
    counts: dict[str, int] = {}

    for table, (csv_file, _pk) in CSV_TABLE_MAP.items():
        path = CORPUS_DIR / csv_file
        overrides = COLUMN_OVERRIDES.get(table)
        n = _load_csv(conn, table, path, type_maps.get(table, {}), overrides)
        counts[table] = n
        status = f"[green]{n:>6} rows" if n else "[dim]      0 rows (empty)"
        console.print(f"  {status}[/]  →  {table}")

    # Domain union
    domain_table = "domain_indexed_questions"
    domain_type_map = type_maps.get(domain_table, {})
    total_domain = 0
    for domain_label, csv_file in DOMAIN_CSVS.items():
        path = CORPUS_DIR / csv_file
        n = _load_csv(conn, domain_table, path, domain_type_map,
                      extra_cols={"domain": domain_label})
        total_domain += n
    counts[domain_table] = total_domain
    console.print(f"  [green]{total_domain:>6} rows[/]  →  {domain_table} (4 domains unioned)")

    return counts
