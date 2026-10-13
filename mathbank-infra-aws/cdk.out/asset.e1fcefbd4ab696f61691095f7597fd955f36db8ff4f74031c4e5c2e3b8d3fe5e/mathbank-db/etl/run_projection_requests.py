#!/usr/bin/env python3
"""Drain pipeline.projection_request (admin "reproject missing" + outbox projection_requests consumer).

Graph targets (GRAPH_TEXTBOOK_STEPS, GRAPH_LEARNING_ITEMS) are free: one full, idempotent, pruning run of
``make textbook-graph-remote`` satisfies every pending graph request, which are then marked DONE.
Embedding targets (STEP_EMBEDDINGS, LEARNING_ITEM_EMBEDDINGS) call the paid OpenAI embedding API, so they
are only listed with the command to run, unless ``--allow-paid`` is passed.

Usage:
    run_projection_requests.py --status            # pending requests by target (read-only)
    run_projection_requests.py                     # run graph projection, mark graph requests DONE
    run_projection_requests.py --allow-paid        # also run textbook-vector-remote (paid), mark DONE
    run_projection_requests.py --dry-run           # show what would run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("PG_ENV_FILE", str(Path(__file__).resolve().parents[2] / "mathbank-graph" / "remote.env"))

import embed_corpus  # noqa: E402  (reuses the project .env-only connection helper)

DB_DIR = Path(__file__).resolve().parents[1]
GRAPH_TARGETS = ("GRAPH_TEXTBOOK_STEPS", "GRAPH_LEARNING_ITEMS")
PAID_TARGETS = ("STEP_EMBEDDINGS", "LEARNING_ITEM_EMBEDDINGS")
COMMANDS = {"graph": ["make", "-C", str(DB_DIR), "textbook-graph-remote"],
            "vector": ["make", "-C", str(DB_DIR), "textbook-vector-remote"]}


def pending(cur) -> dict[str, list[str]]:
    cur.execute("SELECT target, projection_request_id::text FROM pipeline.projection_request "
                "WHERE status = 'PENDING' ORDER BY requested_at")
    out: dict[str, list[str]] = {}
    for target, rid in cur.fetchall():
        out.setdefault(target, []).append(rid)
    return out


def mark_done(conn, ids: list[str], by: str) -> int:
    if not ids:
        return 0
    with conn.cursor() as cur:
        cur.execute("UPDATE pipeline.projection_request SET status = 'DONE', completed_at = now(), completed_by = %s "
                    "WHERE projection_request_id = ANY(%s::uuid[]) AND status = 'PENDING'", (by, ids))
        n = cur.rowcount
    conn.commit()
    return n


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-paid", action="store_true", help="Also run the paid embedding backfill")
    args = ap.parse_args(argv)

    conn = embed_corpus._connect()
    with conn.cursor() as cur:
        queue = pending(cur)
    conn.commit()  # requests are snapshotted now; anything enqueued during the run stays PENDING
    print("pending:", {t: len(ids) for t, ids in sorted(queue.items())} or "none")
    if args.status or not queue:
        return 0

    graph_ids = [rid for t in GRAPH_TARGETS for rid in queue.get(t, [])]
    paid_ids = [rid for t in PAID_TARGETS for rid in queue.get(t, [])]
    if graph_ids:
        print("graph:", " ".join(COMMANDS["graph"]))
        if not args.dry_run:
            subprocess.run(COMMANDS["graph"], check=True)
            print("marked DONE:", mark_done(conn, graph_ids, "run_projection_requests:graph"))
    if paid_ids:
        if args.allow_paid and not args.dry_run:
            print("paid embeddings:", " ".join(COMMANDS["vector"]))
            subprocess.run(COMMANDS["vector"], check=True)
            print("marked DONE:", mark_done(conn, paid_ids, "run_projection_requests:vector"))
        else:
            print(f"{len(paid_ids)} embedding request(s) need the PAID backfill; left PENDING. Run:\n  "
                  + " ".join(COMMANDS["vector"]) + "\n  or rerun with --allow-paid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
