"""Watchdog: checks the active route-compiler run every 15 minutes and stops it
if the cumulative failure rate among terminal (non-queued/running) jobs exceeds
25%, once at least MIN_SAMPLE jobs have finished (avoids stopping on early
noise). Each cycle appends a row to a human-readable observations log.

This process does ONLY the failure-rate check so its cadence can never be
delayed by slower bookkeeping; see route_auto_publish.py for the independent
auto-approve/auto-publish loop, and run_final_graph_projection.py for the
one-shot graph refresh once the whole corpus finishes.
"""

import json
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text

from mathbank_rest.db.postgres import engine

RUN_ID = "4f163e6c-940d-41e1-b7d6-15e29c5056f0"
COMPILER_PID = 65837  # restarted after the original process's thread pool stalled
CHECK_SECONDS = 900
MIN_SAMPLE = 20
FAILURE_THRESHOLD = 0.25
LOG_DIR = Path("/Volumes/External/Developer/databases/logs/openai-mandatory-enrichment-routes")
LOG_PATH = LOG_DIR / "watchdog.log"
OBSERVATIONS_PATH = LOG_DIR / "full-run-observations.md"


def log(message: str) -> None:
    line = f"{datetime.now(UTC).isoformat()} {message}"
    print(line, flush=True)
    with LOG_PATH.open("a") as handle:
        handle.write(line + "\n")


def record_observation(row: dict) -> None:
    is_new = not OBSERVATIONS_PATH.exists()
    with OBSERVATIONS_PATH.open("a") as handle:
        if is_new:
            handle.write(
                "# Full-run observations: tutoring-route-compiler-v2-mandatory-enrichment\n\n"
                f"Run ID: `{RUN_ID}`. Checked every {CHECK_SECONDS // 60} minutes; "
                f"stops the run if the cumulative failure rate exceeds "
                f"{FAILURE_THRESHOLD:.0%} over at least {MIN_SAMPLE} terminal jobs. "
                "Approvals/publishing happen independently in route_auto_publish.py.\n\n"
                "| Time (UTC) | Draft | Failed | Running | Queued | Terminal | Failure rate | "
                "Note |\n"
                "|---|---|---|---|---|---|---|---|\n"
            )
        handle.write(
            f"| {row['time']} | {row['draft']} | {row['failed']} | {row['running']} | "
            f"{row['queued']} | {row['terminal']} | {row['rate']:.1%} | {row['note']} |\n"
        )


def counts() -> dict:
    with engine.connect() as conn:
        return dict(
            conn.execute(
                text("""
            SELECT status, count(*) FROM pedagogy.route_compiler_job
            WHERE run_id=:run GROUP BY status
        """),
                {"run": RUN_ID},
            ).all()
        )


def still_running(pid: int) -> bool:
    try:
        subprocess.run(["ps", "-p", str(pid)], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def stop_run(reason: str) -> None:
    log(f"STOPPING run {RUN_ID}: {reason}")
    if still_running(COMPILER_PID):
        import os

        os.kill(COMPILER_PID, signal.SIGTERM)
        time.sleep(3)
        if still_running(COMPILER_PID):
            os.kill(COMPILER_PID, signal.SIGKILL)
    with engine.begin() as conn:
        conn.execute(
            text("""
            UPDATE pedagogy.route_compiler_run SET status='PARTIAL', completed_at=now()
            WHERE run_id=:run AND status='RUNNING'
        """),
            {"run": RUN_ID},
        )
    log("Stopped and marked PARTIAL.")


def main() -> None:
    log(f"Watchdog started for run {RUN_ID}; checking every {CHECK_SECONDS}s.")
    while True:
        time.sleep(CHECK_SECONDS)
        job_counts = counts()
        terminal = (
            job_counts.get("DRAFT", 0) + job_counts.get("REUSED", 0) + job_counts.get("FAILED", 0)
        )
        failures = job_counts.get("FAILED", 0)
        rate = failures / terminal if terminal else 0.0
        log(f"counts={json.dumps(job_counts)} terminal={terminal} failure_rate={rate:.3f}")
        running = still_running(COMPILER_PID)
        note = ""
        breach = terminal >= MIN_SAMPLE and rate > FAILURE_THRESHOLD
        if breach:
            note = f"STOPPED: failure_rate {rate:.1%} > {FAILURE_THRESHOLD:.0%}"
        elif not running:
            note = "Compiler process no longer running."
        record_observation(
            {
                "time": datetime.now(UTC).isoformat(),
                "draft": job_counts.get("DRAFT", 0),
                "failed": failures,
                "running": job_counts.get("RUNNING", 0),
                "queued": job_counts.get("QUEUED", 0),
                "terminal": terminal,
                "rate": rate,
                "note": note,
            }
        )
        if breach:
            stop_run(f"failure_rate={rate:.3f} > {FAILURE_THRESHOLD} over {terminal} terminal jobs")
            return
        if not running:
            log("Compiler process is no longer running; watchdog exiting.")
            return


if __name__ == "__main__":
    main()
