"""Independent loop: auto-approves DRAFT routes and auto-publishes REVIEWED
routes on a short cadence, decoupled from route_watchdog.py's failure-rate
check so a slow/large approval backlog can never delay that safety check.
Runs until the compiler process exits, then does one final drain pass and
attempts the end-of-run graph projection (best-effort; AI-proposed taxonomy
nodes are self-sufficient for this since route_projection.py's fix, but a
transient DB/graph hiccup here should not be treated as fatal).
"""

import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.route_compiler import approve_drafts, publish_reviewed
from mathbank_rest.step_runtime import RuntimeError_

COMPILER_PID = 65837  # restarted after the original process's thread pool stalled
CHECK_SECONDS = 180
APPROVAL_IDENTITY = "auto-pipeline:openai-full-run"
LOG_DIR = Path("/Volumes/External/Developer/databases/logs/openai-mandatory-enrichment-routes")
LOG_PATH = LOG_DIR / "auto-publish.log"


def log(message: str) -> None:
    line = f"{datetime.now(UTC).isoformat()} {message}"
    print(line, flush=True)
    with LOG_PATH.open("a") as handle:
        handle.write(line + "\n")


def still_running(pid: int) -> bool:
    try:
        subprocess.run(["ps", "-p", str(pid)], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def drain() -> None:
    try:
        approved = approve_drafts(APPROVAL_IDENTITY)
    except (ValueError, SQLAlchemyError, RuntimeError_) as exc:
        log(f"approve_drafts failed: {type(exc).__name__}: {exc}")
        approved = {"selected": 0, "reviewed": 0, "failures": 0}
    try:
        published = publish_reviewed()
    except (ValueError, SQLAlchemyError, RuntimeError_) as exc:
        log(f"publish_reviewed failed: {type(exc).__name__}: {exc}")
        published = {"selected": 0, "published": 0, "failures": 0}
    log(
        f"approved={approved.get('reviewed', 0)}/{approved.get('selected', 0)} "
        f"(failures={approved.get('failures', 0)}) "
        f"published={published.get('published', 0)}/{published.get('selected', 0)} "
        f"(failures={published.get('failures', 0)})"
    )


def final_graph_projection() -> None:
    try:
        from neo4j.exceptions import Neo4jError

        from mathbank_rest.route_projection import project

        report = project()
        log(f"Final graph projection succeeded: {report}")
    except (Neo4jError, SQLAlchemyError, ValueError) as exc:
        log(f"Final graph projection failed (non-fatal): {type(exc).__name__}: {exc}")


def main() -> None:
    log(f"Auto-publish loop started; draining every {CHECK_SECONDS}s.")
    while True:
        running = still_running(COMPILER_PID)
        drain()
        if not running:
            log("Compiler process no longer running; final drain done, projecting graph.")
            final_graph_projection()
            log("Auto-publish loop exiting.")
            return
        time.sleep(CHECK_SECONDS)


if __name__ == "__main__":
    main()
