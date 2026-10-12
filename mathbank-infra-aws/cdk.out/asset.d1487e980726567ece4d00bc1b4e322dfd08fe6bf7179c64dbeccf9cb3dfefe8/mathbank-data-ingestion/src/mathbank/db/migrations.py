"""DB migrations — ALTER TABLE for columns added after initial build."""
from __future__ import annotations

import sqlite3

# All corpus tables that need the audit columns
_ALL_TABLES = [
    "aime_glossary", "aime_year_index", "archive_families", "competitions",
    "concepts", "corpus_tasks", "documents", "domain_indexed_questions",
    "exam_entries", "fast_topic_index", "fine_concept_gaps", "knowledge_graph_edges",
    "papers", "question_taxonomy_maps", "question_technique_maps", "questions",
    "source_ingestion", "techniques", "topic_aliases", "topic_coverage",
    "tournament_events", "unmapped_questions", "unparsed_papers", "visual_assets",
]

_AUDIT_COLS = [
    ("created_at", "TEXT"),
    ("created_by", "TEXT"),
    ("updated_at", "TEXT"),
    ("updated_by", "TEXT"),
]


def _col_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    return any(
        row[1] == col
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    )


def _add_col(conn: sqlite3.Connection, table: str, col: str, col_type: str) -> None:
    if not _col_exists(conn, table, col):
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" {col_type}')


def apply_all(conn: sqlite3.Connection) -> None:
    """Idempotent — safe to run on an already-migrated DB."""
    # ── Audit columns (nullable TEXT) on every table ──────────────────────────
    for table in _ALL_TABLES:
        for col, col_type in _AUDIT_COLS:
            _add_col(conn, table, col, col_type)

    # ── questions: pipeline text and classification columns ───────────────────
    for col in ("competition_id", "problem_text_latex", "problem_text_raw",
                "solution_text_latex", "all_solutions_json", "image_paths",
                "answer_value", "parse_warnings", "crawled_at", "classified_at",
                "classifier_model", "classifier_notes"):
        _add_col(conn, "questions", col, "TEXT")

    # ── questions: reviewer columns ───────────────────────────────────────────
    for col in ("review_status", "reviewed_at", "reviewer_model", "review_notes",
                "review_corrected_concept_id"):
        _add_col(conn, "questions", col, "TEXT")

    # ── unmapped_questions: crawl tracking ────────────────────────────────────
    _add_col(conn, "unmapped_questions", "crawl_dir", "TEXT")

    # ── questions: per-artifact file paths (PDF split output) ─────────────────
    _add_col(conn, "questions", "artifact_base_path", "TEXT")  # abs path to paper dir in crawl_pdf
    _add_col(conn, "questions", "problem_md_path",    "TEXT")  # relative to artifact_base_path
    _add_col(conn, "questions", "solution_md_path",   "TEXT")  # relative to artifact_base_path

    conn.commit()


def create_audit_triggers(conn: sqlite3.Connection) -> None:
    """
    Create AFTER UPDATE triggers that stamp updated_at / updated_by = 'system'.
    SQLite's recursive_triggers is OFF by default so no infinite loop.
    Idempotent — uses CREATE TRIGGER IF NOT EXISTS.
    """
    for table in _ALL_TABLES:
        conn.execute(f"""
            CREATE TRIGGER IF NOT EXISTS "trg_{table}_audit_update"
            AFTER UPDATE ON "{table}"
            BEGIN
                UPDATE "{table}"
                SET updated_at = datetime('now'),
                    updated_by = 'system'
                WHERE rowid = NEW.rowid;
            END
        """)
    conn.commit()

