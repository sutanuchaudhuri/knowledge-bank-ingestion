"""Ingestion run tracking — one row per script invocation in `ingestion_runs`,
plus a full-detail text log file under `logs/`. Shared by every local
ingestion script (crawl_unmapped.py, classify_crawled.py,
classify_pdf_corpus.py, export_classifications_to_csv.py) so progress
survives across runs and across sessions — see scripts/show_progress.py to
view it as a table, and requirements/11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md
for how this ties into the rest of the pipeline.

mathbank-db/etl/load_corpus.py and mathbank-graph/etl/project_from_postgres.py
track their runs separately in Postgres (`pipeline.run` / `pipeline.graph_projection`)
since they already have a live DB connection — see those files.
"""
from __future__ import annotations

import json
import sqlite3
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOGS_DIR = Path(__file__).resolve().parents[3] / "logs"


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id TEXT PRIMARY KEY,
            script TEXT NOT NULL,
            params TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'RUNNING',
            started_at TEXT NOT NULL,
            finished_at TEXT,
            processed INTEGER NOT NULL DEFAULT 0,
            succeeded INTEGER NOT NULL DEFAULT 0,
            failed INTEGER NOT NULL DEFAULT 0,
            log_path TEXT,
            error TEXT
        )
        """
    )
    conn.commit()


class IngestionRun:
    """Context manager: tracks one script invocation.

    Usage:
        with IngestionRun(conn, "classify_crawled", params={"limit": args.limit}) as run:
            run.log("starting…")
            ...
            run.update(processed=10, succeeded=9, failed=1)
        # status is set to SUCCESS on clean exit, FAILED (with traceback logged)
        # if an uncaught exception propagates out of the `with` block.
    """

    def __init__(self, conn: sqlite3.Connection, script: str, params: dict | None = None):
        self.conn = conn
        self.script = script
        self.params = params or {}
        self.run_id = uuid.uuid4().hex[:12]
        self.started_at = datetime.now(timezone.utc)
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        ts = self.started_at.strftime("%Y%m%dT%H%M%SZ")
        self.log_path = LOGS_DIR / f"{ts}_{script}_{self.run_id}.log"
        self._processed = 0
        self._succeeded = 0
        self._failed = 0

    def __enter__(self) -> "IngestionRun":
        ensure_table(self.conn)
        self.conn.execute(
            "INSERT INTO ingestion_runs (run_id, script, params, status, started_at, log_path) "
            "VALUES (?, ?, ?, 'RUNNING', ?, ?)",
            (self.run_id, self.script, json.dumps(self.params), self.started_at.isoformat(), str(self.log_path)),
        )
        self.conn.commit()
        self.log(f"=== {self.script} run {self.run_id} started, params={self.params} ===")
        return self

    def log(self, message: str) -> None:
        line = f"[{datetime.now(timezone.utc).isoformat()}] {message}"
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def update(
        self, *, processed: int | None = None, succeeded: int | None = None, failed: int | None = None
    ) -> None:
        if processed is not None:
            self._processed = processed
        if succeeded is not None:
            self._succeeded = succeeded
        if failed is not None:
            self._failed = failed
        self.conn.execute(
            "UPDATE ingestion_runs SET processed = ?, succeeded = ?, failed = ? WHERE run_id = ?",
            (self._processed, self._succeeded, self._failed, self.run_id),
        )
        self.conn.commit()

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        finished_at = datetime.now(timezone.utc)
        if exc_type is None:
            status, error = "SUCCESS", None
        else:
            status = "FAILED"
            error = f"{exc_type.__name__}: {exc_val}"
            self.log("".join(traceback.format_exception(exc_type, exc_val, exc_tb)))
        self.conn.execute(
            "UPDATE ingestion_runs SET status = ?, finished_at = ?, processed = ?, succeeded = ?, "
            "failed = ?, error = ? WHERE run_id = ?",
            (status, finished_at.isoformat(), self._processed, self._succeeded, self._failed, error, self.run_id),
        )
        self.conn.commit()
        self.log(
            f"=== {self.script} run {self.run_id} finished: {status} "
            f"(processed={self._processed} succeeded={self._succeeded} failed={self._failed}) ==="
        )
        return False  # never swallow exceptions
