"""Transactional-outbox consumers (runtime_extension/16) and the stale-attempt job (08).

Each consumer handles events it subscribes to and records ``pipeline.outbox_consumption`` in the SAME
transaction, so processing an event twice is a no-op. Consumers never touch Neo4j or embeddings
directly (no dual-write): content events become ``pipeline.projection_request`` rows that operators or
the admin import page drain with the existing idempotent projectors.

    python -m mathbank_rest.outbox_worker --once            # drain all consumers once
    python -m mathbank_rest.outbox_worker --watch 30        # poll every 30 s
    python -m mathbank_rest.outbox_worker --abandon-idle-days 30
    python -m mathbank_rest.outbox_worker --status
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection

log = logging.getLogger(__name__)

# event_type -> analytics.learner_daily_activity column
ANALYTICS_COLUMNS = {
    "ATTEMPT_STARTED": "attempts_started",
    "ATTEMPT_COMPLETED": "attempts_completed",
    "ATTEMPT_ABANDONED": "attempts_abandoned",
    "STEP_EVALUATED": "steps_evaluated",
    "GAP_DIAGNOSED": "gaps_diagnosed",
    "KNOWLEDGE_GAP_CREATED": "knowledge_gaps_created",
    "RECOVERY_PLAN_CREATED": "recovery_plans_created",
    "RECOVERY_PLAN_COMPLETED": "recovery_plans_completed",
}

# event_type -> projection requests (target, scope_type, payload key or None for aggregate_id)
PROJECTIONS = {
    "CONTENT_PACKAGE_IMPORTED": [("GRAPH_TEXTBOOK_STEPS", "BOOK", "book_code"),
                                 ("STEP_EMBEDDINGS", "BOOK", "book_code"),
                                 ("LEARNING_ITEM_EMBEDDINGS", "BOOK", "book_code"),
                                 ("GRAPH_LEARNING_ITEMS", "BOOK", "book_code")],
    "SOLUTION_STEP_CHANGED": [("GRAPH_TEXTBOOK_STEPS", "STEP", None), ("STEP_EMBEDDINGS", "STEP", None)],
    "LEARNING_ITEM_PUBLISHED": [("LEARNING_ITEM_EMBEDDINGS", "LEARNING_ITEM", None),
                                ("GRAPH_LEARNING_ITEMS", "LEARNING_ITEM", None)],
    # Withdrawn (rejected) items: the graph projector prunes non-APPROVED items on the next run.
    "LEARNING_ITEM_WITHDRAWN": [("GRAPH_LEARNING_ITEMS", "LEARNING_ITEM", None)],
}


@dataclass(frozen=True)
class Consumer:
    name: str
    event_types: tuple[str, ...]
    handle: Callable[[Connection, dict], None]


def _analytics(conn: Connection, event: dict) -> None:
    column = ANALYTICS_COLUMNS[event["event_type"]]
    payload = event["payload"] or {}
    student_id = payload.get("student_id")
    if not student_id:
        return
    succeeded = 1 if event["event_type"] == "STEP_EVALUATED" and payload.get("result") == "SUCCESS" else 0
    conn.execute(text(
        f"INSERT INTO analytics.learner_daily_activity (student_id, activity_date, {column}, steps_succeeded) "
        "SELECT CAST(:s AS uuid), (CAST(:t AS timestamptz) AT TIME ZONE 'UTC')::date, 1, :ok "
        " WHERE EXISTS (SELECT 1 FROM learner.student_profile WHERE student_id = CAST(:s AS uuid)) "
        "ON CONFLICT (student_id, activity_date) DO UPDATE SET "
        f"  {column} = analytics.learner_daily_activity.{column} + 1, "
        "  steps_succeeded = analytics.learner_daily_activity.steps_succeeded + EXCLUDED.steps_succeeded, "
        "  updated_at = now()"),
        {"s": student_id, "t": event["created_at"], "ok": succeeded})


def _projection(conn: Connection, event: dict) -> None:
    payload = event["payload"] or {}
    for target, scope_type, key in PROJECTIONS[event["event_type"]]:
        scope_id = payload.get(key) if key else event["aggregate_id"]
        if not scope_id:
            continue
        conn.execute(text(
            "INSERT INTO pipeline.projection_request (target, scope_type, scope_id, reason, source_outbox_event_id) "
            "VALUES (:t, :st, :sid, :why, CAST(:e AS uuid)) "
            "ON CONFLICT (target, scope_type, scope_id) WHERE status = 'PENDING' DO NOTHING"),
            {"t": target, "st": scope_type, "sid": str(scope_id), "why": event["event_type"],
             "e": event["outbox_event_id"]})


CONSUMERS = (
    Consumer("learner_analytics", tuple(ANALYTICS_COLUMNS), _analytics),
    Consumer("projection_requests", tuple(PROJECTIONS), _projection),
)


def drain(conn_factory, consumer: Consumer, batch: int = 200) -> int:
    """Process up to ``batch`` unconsumed events for one consumer; returns how many were handled.

    ``conn_factory`` is ``engine.begin`` (one transaction per batch; SKIP LOCKED lets workers run in
    parallel without double processing)."""
    with conn_factory() as conn:
        rows = conn.execute(text(
            "SELECT o.outbox_event_id::text, o.event_type, o.aggregate_type, o.aggregate_id, o.payload, o.created_at "
            "  FROM pipeline.outbox_event o "
            " WHERE o.event_type = ANY(:types) AND NOT EXISTS (SELECT 1 FROM pipeline.outbox_consumption c "
            "        WHERE c.outbox_event_id = o.outbox_event_id AND c.consumer_name = :c) "
            " ORDER BY o.created_at LIMIT :n FOR UPDATE OF o SKIP LOCKED"),
            {"types": list(consumer.event_types), "c": consumer.name, "n": batch}).mappings().all()
        for row in rows:
            event = dict(row)
            if isinstance(event["payload"], str):
                event["payload"] = json.loads(event["payload"])
            with conn.begin_nested():
                consumer.handle(conn, event)
                conn.execute(text(
                    "INSERT INTO pipeline.outbox_consumption (outbox_event_id, consumer_name) "
                    "VALUES (CAST(:e AS uuid), :c) ON CONFLICT DO NOTHING"),
                    {"e": event["outbox_event_id"], "c": consumer.name})
        return len(rows)


def drain_all(conn_factory, batch: int = 200) -> dict[str, int]:
    handled: dict[str, int] = {}
    for consumer in CONSUMERS:
        total = 0
        while True:
            n = drain(conn_factory, consumer, batch)
            total += n
            if n < batch:
                break
        handled[consumer.name] = total
    return handled


def status(conn: Connection) -> dict:
    lag = {c.name: conn.execute(text(
        "SELECT count(*) FROM pipeline.outbox_event o WHERE o.event_type = ANY(:types) AND NOT EXISTS ("
        " SELECT 1 FROM pipeline.outbox_consumption c WHERE c.outbox_event_id = o.outbox_event_id "
        " AND c.consumer_name = :c)"), {"types": list(c.event_types), "c": c.name}).scalar_one()
        for c in CONSUMERS}
    events = dict(conn.execute(text(
        "SELECT event_type, count(*) FROM pipeline.outbox_event GROUP BY 1 ORDER BY 1")).all())
    requests = [dict(r) for r in conn.execute(text(
        "SELECT target, scope_type, status, count(*) AS n FROM pipeline.projection_request "
        "GROUP BY 1, 2, 3 ORDER BY 1, 2, 3")).mappings()]
    return {"outbox_events": events, "unconsumed": lag, "projection_requests": requests}


def main(argv: list[str] | None = None) -> int:
    from mathbank_rest import step_runtime
    from mathbank_rest.db.postgres import engine

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--once", action="store_true", help="drain every consumer once")
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="poll forever")
    parser.add_argument("--abandon-idle-days", type=int, metavar="DAYS",
                        help="mark IN_PROGRESS attempts idle for DAYS as ABANDONED (then drain)")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.abandon_idle_days:
        with engine.begin() as conn:
            abandoned = step_runtime.abandon_stale_attempts(conn, args.abandon_idle_days)
        print(json.dumps({"abandoned": len(abandoned)}))
    if args.once or args.abandon_idle_days:
        print(json.dumps({"handled": drain_all(engine.begin)}))
    if args.watch:
        while True:
            handled = drain_all(engine.begin)
            if any(handled.values()):
                log.info("outbox handled %s", handled)
            time.sleep(args.watch)
    if args.status or not (args.once or args.watch or args.abandon_idle_days):
        with engine.connect() as conn:
            print(json.dumps(status(conn), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
