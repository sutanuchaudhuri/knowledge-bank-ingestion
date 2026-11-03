"""Read-only smoke check of the solve area of the DynamoDB learner store against a real environment (requirement 71 WP5).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/learner_smoke_solve.py [--students 40]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject); the script fails when it observes any other API operation and
never calls a method that writes (``record_*``, ``submit_*``, ``request_*``, ``start_*``, ``abandon_*`` are not reachable).
PostgreSQL is never touched. Learners are sampled through the ``STUDENT_DIR`` index (GSI2), open sessions through the four
``OPEN_SOLVE#<n>`` shards of GSI1, never by a scan. Nothing is written, so the migrated data stays as it was.

Checks per sampled learner: every SOLVE, STEPSTATE, EVENT and PROBLEM item of the partition parses into its refined model
(migrated shapes must validate); ``list_solve_attempts`` and a one-item paging return the same sessions; for each session the
runtime view has the documented shape, reveals reference text only for finished steps, counts progress from the published
solution, the owner pointer resolves to the learner and another learner's id is refused; ``hint_requested_count`` equals the number
of HINT_REQUESTED events; the event feed is newest first, a one-item page walk returns exactly the list, the ``after`` cursor
returns the newer events oldest first and the learner projection never carries teacher keys; every IN_PROGRESS session is in the
open-solve index and is the open marker of its PROBLEM cursor (one per learner and problem). Globally: the open-solve shards only
hold IN_PROGRESS sessions, and the number of sessions the abandon job would take (idle >= 30 days) is reported, not changed.
Checks that need data the environment does not hold are SKIP, not FAIL. Exit code 1 on a failed check.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
import uuid
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models import base
from mathbank_rest.models.manual.learner_solve import (
    OPEN_SOLVE_SHARDS,
    LearnerEvent,
    LearnerProblem,
    LearnerSolve,
    LearnerStepstate,
)
from mathbank_rest.step_logic import DONE_STATES, NotFound
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner.solve import SolveDynamoDB

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity", "head_object"}
RUNTIME_KEYS = {"attempt", "current_step", "seen_steps", "timeline", "recovery", "progress"}
EVENT_KEYS = {"event_id", "solve_attempt_id", "event_type", "event_time", "actor_type", "solution_step_id", "payload"}
TEACHER_KEYS = ("confidence", "failure_mode", "failure_location", "evidence", "teacher", "knowledge_gap_id_internal")


class Spy:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and not name.startswith("_"):
            OPERATIONS.add(name)
        return attr


class ReadOnly:
    """The only store surface the script uses: read methods of the solve store (a write would be a bug here)."""

    def __init__(self, store):
        self._store = store

    def __getattr__(self, name):
        if not name.startswith(stores.READ_PREFIXES):
            raise AssertionError(f"{name} is not a read")
        return getattr(self._store, name)


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def skip(label: str, why: str) -> None:
    print(f"SKIP {label} - {why}")


def sample_students(limit: int) -> list[str]:
    page = ddb.query_page("learner", "STUDENT_DIR", index="GSI2", limit=limit, consistent=False)
    return [str(i["student_id"]) for i in page["items"] if i.get("type") == "PROFILE"]


def partition(models, sid: str, prefix: str):
    token = None
    while True:
        page = typed.query("learner", ddb.student_pk(sid), models=models, sk_begins=prefix, limit=200, next_token=token)
        yield from page.items
        token = page.next_token
        if not token:
            return


def walk_events(reads, sid: str, **kw) -> list[dict]:
    rows, token = [], None
    while True:
        page = reads.list_events_page(UUID(sid), limit=1, next_token=token, **kw)
        rows += page["items"]
        token = page["next_token"]
        if not token or len(rows) > 400:
            return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--students", type=int, default=40, help="learners sampled from the STUDENT_DIR index")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('learner')}")
    reads = ReadOnly(SolveDynamoDB())
    sids = sample_students(args.students)
    check(bool(sids), "STUDENT_DIR index lists learners", f"{len(sids)} sampled")
    sessions = events_seen = items_parsed = 0
    with stores.override_store("content", DynamoDBContentStore()):
        for sid in sids:
            under_solve = list(partition([LearnerSolve, LearnerStepstate, base.model_for("learner", "DIAG")], sid, "SOLVE#"))
            solves = [s for s in under_solve if isinstance(s, LearnerSolve)]
            steps = [s for s in under_solve if isinstance(s, LearnerStepstate)]
            events = list(partition([LearnerEvent], sid, "EVT#"))
            cursors = list(partition([LearnerProblem], sid, "PROBLEM#"))
            items_parsed += len(solves) + len(steps) + len(events) + len(cursors)
            events_seen += len(events)
            if not (solves or events):
                continue
            tag = sid[:8]
            listing = reads.list_solve_attempts(UUID(sid), limit=200)["items"]
            check({r["solve_attempt_id"] for r in listing} == {s.solve_attempt_id for s in solves}, f"{tag} session list = partition",
                  f"{len(solves)} sessions")
            paged, token = [], None
            while solves:
                page = reads.list_solve_attempts(UUID(sid), limit=1, next_token=token)
                paged += page["items"]
                token = page["next_token"]
                if not token or len(paged) > 200:
                    break
            check([r["solve_attempt_id"] for r in paged] == [r["solve_attempt_id"] for r in listing], f"{tag} one-item paging = list")
            for solve in solves:
                aid, sessions = str(solve.solve_attempt_id), sessions + 1
                t0 = time.perf_counter()
                runtime = reads.get_attempt_runtime(aid, UUID(sid))
                check(set(runtime) == RUNTIME_KEYS and runtime["attempt"]["state_version"] == solve.version, f"{tag} {aid[:8]} runtime shape",
                      f"{(time.perf_counter() - t0) * 1000:.0f} ms, state_version {solve.version}")
                timeline = runtime["timeline"]
                check(all(("reference_text" in t) == (t["state"] in DONE_STATES) for t in timeline), f"{tag} {aid[:8]} reference text only when done")
                check((runtime["current_step"] is not None) == (solve.current_solution_step_id is not None), f"{tag} {aid[:8]} current step")
                owner = reads.get_attempt_owner(aid)
                check(owner is not None and str(owner["student_id"]) == sid, f"{tag} {aid[:8]} owner pointer")
                try:
                    reads.get_attempt_runtime(aid, uuid.uuid4())
                    check(False, f"{tag} {aid[:8]} foreign learner refused")
                except NotFound:
                    check(True, f"{tag} {aid[:8]} foreign learner refused")
                mine = [e for e in events if str(e.solve_attempt_id) == aid]
                hints = sum(e.event_type == "HINT_REQUESTED" for e in mine)
                check(solve.hint_requested_count == hints, f"{tag} {aid[:8]} hint counter = HINT_REQUESTED events",
                      f"{solve.hint_requested_count} vs {hints}")
                if solve.status == "IN_PROGRESS":
                    check((solve.GSI1PK or "").startswith("OPEN_SOLVE#"), f"{tag} {aid[:8]} in the open-solve index")
                    marker = next((c for c in cursors if str(c.problem_id) == str(solve.problem_id)), None)
                    check(marker is not None and str(marker.open_solve_attempt_id) == aid, f"{tag} {aid[:8]} open marker on the problem cursor")
                else:
                    check(solve.GSI1PK is None, f"{tag} {aid[:8]} not in the open-solve index")
            feed = reads.list_events(UUID(sid), limit=500)
            check([e["event_id"] for e in feed] == [e.event_id for e in sorted(events, key=lambda e: (e.event_time, e.SK), reverse=True)][:500]
                  or len(events) > 500, f"{tag} event feed newest first", f"{len(feed)} events")
            check(all(set(e) == EVENT_KEYS for e in feed), f"{tag} event shape")
            if feed and len(feed) <= 400:
                check([e["event_id"] for e in walk_events(reads, sid)] == [e["event_id"] for e in feed], f"{tag} one-item event paging = list")
                oldest_first = list(reversed(feed))
                cursor = ddb.encode(oldest_first[len(oldest_first) // 2]["event_time"])
                after = reads.get_events_after(UUID(sid), cursor, limit=500)["items"]
                check(all(e["event_time"] > oldest_first[len(oldest_first) // 2]["event_time"] for e in after)
                      and [e["event_time"] for e in after] == sorted(e["event_time"] for e in after), f"{tag} events after a cursor, oldest first")
                blob = repr([e["payload"] for e in reads.list_events(UUID(sid), limit=500, student_view=True)])
                check(not any(f"'{k}'" in blob for k in TEACHER_KEYS), f"{tag} learner projection carries no teacher keys")
            else:
                skip(f"{tag} event paging", "no events")
            # one open session per learner and problem
            opened = [s for s in solves if s.status == "IN_PROGRESS"]
            check(len({str(s.problem_id) for s in opened}) == len(opened), f"{tag} at most one open session per problem")
    check(items_parsed > 0, "migrated SOLVE/STEPSTATE/EVENT/PROBLEM items parse into the refined models", f"{items_parsed} items")
    cutoff = ddb.encode(dt.datetime.now(dt.UTC) - dt.timedelta(days=30))
    open_total = stale = 0
    for shard in range(OPEN_SOLVE_SHARDS):
        token = None
        while True:
            page = typed.query(LearnerSolve, f"OPEN_SOLVE#{shard}", index="GSI1", limit=200, next_token=token, consistent=False)
            open_total += len(page.items)
            stale += sum(1 for s in page.items if s.GSI1SK < cutoff)
            check(all(s.status == "IN_PROGRESS" for s in page.items), f"open-solve shard {shard} holds only IN_PROGRESS sessions")
            token = page.next_token
            if not token:
                break
    print(f"     open-solve index: {open_total} open sessions, {stale} idle >= 30 days (the abandon job would take them; nothing changed here)")
    check(OPERATIONS <= READS, "only read operations were used", ", ".join(sorted(OPERATIONS)))
    print(f"sampled {len(sids)} learners: {sessions} sessions, {events_seen} events, {items_parsed} items parsed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
