"""Resumable automatic corpus enrichment; logs failures, never approves bad output."""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait

from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.db.postgres import engine
from mathbank_rest.enrichment import EnrichmentUnavailable, enrich_problem
from mathbank_rest.publication import publish_current

logger = logging.getLogger(__name__)


def select_work(
    conn: Connection, limit: int, excluded: list[str] | None = None
) -> tuple[list[str], list[str]]:
    pending_publication = list(
        conn.execute(
            text(
                "SELECT p.canonical_code FROM knowledge.enrichment_job j "
                "JOIN core.problem p USING(problem_id) WHERE j.status='COMPLETED' AND j.published_at IS NULL "
                "ORDER BY j.updated_at,p.canonical_code LIMIT 25"
            )
        )
        .scalars()
        .all()
    )
    codes = list(
        conn.execute(
            text("""
                SELECT p.canonical_code FROM core.problem p
                LEFT JOIN knowledge.enrichment_job j USING(problem_id)
                WHERE p.canonical_code <> ALL(:excluded) AND (
                  NOT EXISTS(SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id=p.problem_id)
                  OR NOT EXISTS(SELECT 1 FROM knowledge.problem_pedagogy d WHERE d.problem_id=p.problem_id)
                ) AND (j.problem_id IS NULL OR
                  (j.status='FAILED' AND j.attempts<3 AND j.updated_at<now()-interval '5 minutes') OR
                  (j.status='IN_PROGRESS' AND j.updated_at<now()-interval '10 minutes'))
                ORDER BY CASE WHEN j.status='FAILED' THEN 0
                              WHEN j.status='IN_PROGRESS' THEN 1 ELSE 2 END,
                         j.updated_at NULLS LAST,p.canonical_code LIMIT :limit
            """),
            {"limit": limit, "excluded": excluded or []},
        )
        .scalars()
        .all()
    )
    return pending_publication, codes


def run_worker(
    watch: bool, limit: int, workers: int = 1, stop: threading.Event | None = None
) -> None:
    if workers < 1 or workers > 8:
        raise ValueError("workers must be between 1 and 8")
    stop = stop if stop is not None else threading.Event()
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="enrichment") as executor:
        coordinate(watch, limit, workers, stop, executor)


def coordinate(
    watch: bool,
    limit: int,
    workers: int,
    stop: threading.Event,
    executor: ThreadPoolExecutor,
) -> None:
    attempted = 0
    active: dict[Future, str] = {}
    publication_due = 0.0
    publication_retry = 0.0
    while True:
        for future in list(active):
            if not future.done():
                continue
            code = active.pop(future)
            try:
                result = future.result()
                logger.info("stage=generation problem=%s status=%s", code, result["status"])
            except (EnrichmentUnavailable, SQLAlchemyError, ValueError, OSError):
                logger.exception(
                    "stage=generation problem=%s failed; see stored last_error; "
                    "retry after five-minute cooldown (maximum three job attempts)",
                    code,
                )
        capacity = workers - len(active)
        if not watch:
            capacity = min(capacity, max(0, limit - attempted))
        if stop.is_set():
            capacity = 0
        try:
            with engine.connect() as conn:
                pending_publication, codes = select_work(conn, capacity, list(active.values()))
        except SQLAlchemyError:
            logger.exception("stage=scheduling Could not read enrichment jobs from Postgres")
            if not watch or stop.is_set():
                raise
            time.sleep(60)
            continue
        now = time.monotonic()
        if (
            pending_publication
            and now >= publication_retry
            and (
                len(pending_publication) >= 25
                or now >= publication_due
                or (not codes and not active)
            )
        ):
            try:
                publish_current(pending_publication)
                logger.info("stage=publication published problems=%s", len(pending_publication))
                publication_due = time.monotonic() + 60
                if not codes and not active:
                    continue
            except (
                SQLAlchemyError,
                ValueError,
                OSError,
                Neo4jError,
                ServiceUnavailable,
                SessionExpired,
                RuntimeError,
            ):
                logger.exception(
                    "stage=publication problems=%s failed; COMPLETED Postgres metadata retained "
                    "for publication replay in 60 seconds; no model regeneration",
                    len(pending_publication),
                )
                publication_retry = time.monotonic() + 60
                if not watch or stop.is_set():
                    raise
        for code in codes:
            attempted += 1
            active[executor.submit(enrich_problem, code)] = code
            logger.info(
                "stage=scheduling submitted problem=%s active=%s/%s", code, len(active), workers
            )
        if active:
            wait(active, timeout=1, return_when=FIRST_COMPLETED)
            continue
        if not watch or stop.is_set():
            logger.info("Worker complete; generation attempts=%s", attempted)
            return
        stop.wait(60)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", action="store_true")
    parser.add_argument(
        "--workers", type=int, default=1, help="Concurrent model jobs (1-8); one graph publisher"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="Maximum generation attempts in one-shot mode; watch mode is uncapped",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    stop = threading.Event()

    def request_stop(signum, frame):
        logger.info("Shutdown requested; draining active jobs and stored publication work")
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info(
        "Recovery worker started watch=%s workers=%s generation_limit=%s publication_batch=25 "
        "publication_interval=60s; reselecting due retries between problems",
        args.watch,
        args.workers,
        "uncapped" if args.watch else args.limit,
    )
    run_worker(args.watch, args.limit, args.workers, stop)


if __name__ == "__main__":
    main()
