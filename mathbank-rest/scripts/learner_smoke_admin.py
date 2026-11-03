"""Read-only smoke check of the admin area of the DynamoDB learner store against a real environment (requirement 71 WP5).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/learner_smoke_admin.py [--students 10]

Only DynamoDB reads (GetItem, Query, BatchGetItem); the script fails when it observes any other API operation and it only calls
store methods whose names are reads. PostgreSQL is never touched. It never calls ``request_erasure``, ``erase_partition``, a rebuild or
any other write.

Checks: the ``STUDENT_DIR`` directory pages with signed tokens and no repeated student (and a tampered token is refused); no listed or
detailed profile carries ``password_hash``/``search_blob``; a text search finds a sampled student; for each sampled student the admin
profile, the full-payload event feed, the solve-attempt list, the mastery summary, the daily-activity range and the interaction-event
listing all read back; the erasure queue (``ERASURE#REQUESTED``) is listed and reported.
Exit code 1 on a failed check.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.stores import ddb
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.errors import InvalidToken
from mathbank_rest.stores.learner import DynamoDBLearnerStore

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"GetItem", "Query", "BatchGetItem", "GetCallerIdentity", "GetObject", "HeadObject", "ListObjectsV2"}
ROW_KEYS = {"student_id", "email", "first_name", "last_name", "display_name", "status", "created_at", "is_anonymous"}
SECRETS = ("password_hash", "search_blob")
DAILY_KEYS = {"student_id", "activity_date", "attempts_started", "attempts_completed", "attempts_abandoned", "steps_evaluated",
              "steps_succeeded", "gaps_diagnosed", "knowledge_gaps_created", "recovery_plans_created", "recovery_plans_completed"}


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def record_operation(**kwargs) -> None:
    OPERATIONS.add(kwargs["model"].name)


def watch_operations() -> None:
    """Record every AWS API operation the toolkit's clients issue, so a write fails the run."""
    for service in ("dynamodb", "s3", "sts"):
        ddb.client(service).meta.events.register("before-call", record_operation)


def has_secret(obj) -> bool:
    text = repr(obj)
    return any(s in text for s in SECRETS)


class ReadOnlyStore:
    """The only store surface the script uses: read methods (a write would be a bug here)."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        if not name.startswith(stores.READ_PREFIXES):
            raise AssertionError(f"{name} is not a read")
        return getattr(self._inner, name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--students", type=int, default=10, help="students sampled for the per-student reads")
    args = parser.parse_args()
    settings.learner_store = "dynamodb"
    watch_operations()
    store = DynamoDBLearnerStore()
    with stores.override_store("learner", store), stores.override_store("content", DynamoDBContentStore()):
        reads = ReadOnlyStore(store)
        page = reads.list_admin_students(limit=min(args.students, 200))
        sample = page["items"]
        check(bool(sample), "the STUDENT_DIR directory is not empty", f"{len(sample)} rows")
        check(all(set(r) == ROW_KEYS for r in sample), "directory rows have exactly the admin columns")
        check(not has_secret(page), "the directory carries no password_hash / search_blob")
        first = reads.list_admin_students(limit=3)
        if first["next_token"]:
            second = reads.list_admin_students(limit=3, next_token=first["next_token"])
            ids = [r["student_id"] for r in first["items"]] + [r["student_id"] for r in second["items"]]
            check(len(ids) == len(set(ids)), "paging by signed token repeats no student", f"{len(ids)} rows over two pages")
            try:
                reads.list_admin_students(limit=3, next_token=first["next_token"][:-3] + "AAA")
                check(False, "a tampered next_token is refused")
            except InvalidToken:
                check(True, "a tampered next_token is refused")
        if sample:
            needle = sample[0]["email"].split("@")[0][:6]
            hits = reads.list_admin_students(q=needle, limit=200)["items"]
            check(any(h["student_id"] == sample[0]["student_id"] for h in hits), "a text search finds a sampled student", needle)
            by_id = reads.list_admin_students(q=sample[0]["student_id"])["items"]
            check([r["student_id"] for r in by_id] == [sample[0]["student_id"]], "an exact student id search finds the student")
        end = dt.datetime.now(dt.UTC).date()
        start = end - dt.timedelta(days=90)
        for row in sample[: args.students]:
            sid = row["student_id"]
            tag = sid[:8]
            profile = reads.get_admin_student(sid)
            check(profile is not None and not has_secret(profile) and profile["token_version"] >= 0, f"{tag} admin profile",
                  "missing" if profile is None else profile["status"])
            events = reads.list_events_page(UUID(sid), limit=20, student_view=False)
            check(isinstance(events["items"], list), f"{tag} full-payload event feed", f"{len(events['items'])} events")
            check("items" in reads.list_solve_attempts(UUID(sid), limit=20), f"{tag} solve attempts")
            check("concepts" in reads.get_mastery_summary(UUID(sid)), f"{tag} mastery summary")
            daily = reads.list_admin_daily_activity(date_from=start, date_to=end, student_id=sid)
            check(all(DAILY_KEYS <= set(r) for r in daily["items"]), f"{tag} daily activity", f"{len(daily['items'])} days")
            ix = reads.list_admin_interaction_events(student_id=sid, limit=20)
            check(isinstance(ix["items"], list), f"{tag} interaction events", f"{len(ix['items'])} events")
            job = reads.get_erasure_job(sid)
            check(job is None, f"{tag} has no erasure job", "" if job is None else job["status"])
        print(f"info pending erasure requests: {len(reads.list_pending_erasures())}")
        summed = reads.list_admin_daily_activity(date_from=start, date_to=end, group_by="day", limit=20)
        check(summed["scope"] == "page", "cross-student daily activity (one directory page, summed per day)",
              f"{len(summed['items'])} days")
    writes = OPERATIONS - READS
    check(not writes, "only read operations were issued", ",".join(sorted(writes or OPERATIONS)))
    print("FAILED" if FAILURES else "all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
