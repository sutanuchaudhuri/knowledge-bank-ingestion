"""Read-only smoke check of the identity and outcome areas of the DynamoDB learner store against a real environment (requirement 71 WP5).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/learner_smoke_identity.py [--students 10] [--accepted-mismatches 28]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject); the script fails when it observes any other API operation, and it
never calls a method that writes. PostgreSQL is never touched. Students are sampled through the ``STUDENT_DIR`` index (GSI2), no scan.

Checks per sampled student: the profile validates against the refined model and the three lookups (profile, e-mail sentinel, Cognito
sentinel) agree; every stored MASTERY item is recomputed from its MEVID evidence with the unchanged formula (evaluated at the item's
own ``updated_at``) and compared with the migrated score; the outcome list, mastery summary, practice progress and daily activity
read back in the PostgreSQL response shapes. Mastery rows that differ are counted, not hidden: the migration counted a tag that was
attached twice to one problem twice (the accepted 28-row tag de-duplication), so up to ``--accepted-mismatches`` differing tags pass.
Exit code 1 on a failed check.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import mastery, stores
from mathbank_rest.config import settings
from mathbank_rest.models.manual.learner_identity import IdentityProfile
from mathbank_rest.models.manual.learner_outcomes import MasteryItem
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner.identity import IdentityDynamoDB
from mathbank_rest.stores.learner.outcomes import OutcomesDynamoDB

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity", "head_object"}
PROFILE_KEYS = {"student_id", "email", "first_name", "last_name", "display_name", "status", "created_at", "last_login_at", "grade", "phone"}
ATTEMPT_KEYS = {"attempt_id", "is_correct", "submitted_answer", "time_spent_seconds", "hint_count", "attempted_at", "source",
                "canonical_code", "problem_number", "difficulty_band", "competition", "year"}
SUMMARY_KEYS = {"slug", "name", "mastery_score", "attempts_count", "correct_count", "last_attempt_at"}
DAILY_KEYS = {"activity_date", "attempts_started", "attempts_completed", "attempts_abandoned", "steps_evaluated", "steps_succeeded",
              "gaps_diagnosed", "knowledge_gaps_created", "recovery_plans_created", "recovery_plans_completed"}


class Spy:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and not name.startswith("_"):
            OPERATIONS.add(name)
        return attr


class ReadOnly:
    """The only store surface the script uses: read methods of the two stores (a write would be a bug here)."""

    def __init__(self, *stores_):
        self._stores = stores_

    def __getattr__(self, name):
        if not name.startswith(stores.READ_PREFIXES):
            raise AssertionError(f"{name} is not a read")
        return next(getattr(s, name) for s in self._stores if hasattr(s, name))


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def sample_students(limit: int) -> list[str]:
    page = ddb.query_page("learner", "STUDENT_DIR", index="GSI2", limit=limit, consistent=False)
    return [str(i["student_id"]) for i in page["items"] if i.get("type") == "PROFILE"]


def verify_mastery(sid: str, outcomes: OutcomesDynamoDB) -> tuple[int, int]:
    """(tags compared, tags that differ) - the stored score against the formula over the stored evidence."""
    items = typed.query(MasteryItem, ddb.student_pk(sid), sk_begins="MASTERY#", limit=200).items
    different = 0
    for item in items:
        rows = (outcomes.get_attempts_for_concept if item.tag_kind == "C" else outcomes.get_attempts_for_technique)(UUID(sid), item.tag_id)
        score = mastery.compute_mastery_score(rows, now=item.updated_at)
        if (len(rows), sum(1 for r in rows if r["is_correct"])) != (item.attempts_count, item.correct_count) or abs(
                score - item.mastery_score) > 1e-6:
            different += 1
            print(f"     differs: {item.tag_kind} {item.tag_id} stored={item.mastery_score:.6f}/{item.attempts_count} "
                  f"recomputed={score:.6f}/{len(rows)}")
    return len(items), different


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--students", type=int, default=10, help="students sampled from the STUDENT_DIR index")
    parser.add_argument("--accepted-mismatches", type=int, default=28, help="mastery tags allowed to differ (tag de-duplication)")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('learner')}")
    identity, outcomes = IdentityDynamoDB(), OutcomesDynamoDB()
    reads = ReadOnly(identity, outcomes)
    sids = sample_students(args.students)
    check(bool(sids), "STUDENT_DIR index lists students", f"{len(sids)} sampled")
    compared = differing = attempts = themes = days = 0
    with stores.override_store("content", DynamoDBContentStore()), stores.override_store("learner", reads):
        for sid in sids:
            profile = typed.require(IdentityProfile, ddb.student_pk(sid), "PROFILE")
            got = reads.get_student_profile(UUID(sid))
            check(set(got) == PROFILE_KEYS and got["status"] == profile.status, f"{sid[:8]} profile shape")
            check(reads.get_student_status(UUID(sid)) == profile.status and reads.get_student_token_version(UUID(sid)) == profile.token_version,
                  f"{sid[:8]} status and token_version")
            by_email = reads.get_student_by_email(profile.email)
            check(by_email is not None and by_email["student_id"] == profile.student_id, f"{sid[:8]} e-mail sentinel resolves")
            if profile.cognito_sub is not None:
                bound = reads.get_student_by_cognito_sub(str(profile.cognito_sub))
                check(bound is not None and bound["student_id"] == profile.student_id, f"{sid[:8]} Cognito sentinel resolves")
            rows = reads.list_attempts(UUID(sid), limit=200)
            check(all(set(r) == ATTEMPT_KEYS for r in rows), f"{sid[:8]} attempts shape", f"{len(rows)} rows")
            attempts += len(rows)
            summary = reads.get_mastery_summary(UUID(sid))
            check(all(set(r) == SUMMARY_KEYS for k in summary for r in summary[k]) and set(summary) == {"concepts", "techniques"},
                  f"{sid[:8]} mastery summary shape", f"{len(summary['concepts'])} concepts, {len(summary['techniques'])} techniques")
            n, bad = verify_mastery(sid, outcomes)
            compared, differing = compared + n, differing + bad
            daily = reads.list_daily_activity(UUID(sid), dt.date(2000, 1, 1), dt.date(2100, 1, 1))
            check(all(set(r) == DAILY_KEYS for r in daily), f"{sid[:8]} daily activity shape", f"{len(daily)} days")
            days += len(daily)
        if sids:
            t0 = time.perf_counter()
            progress = reads.get_practice_progress(UUID(sids[0]))["items"]
            themes = len(progress)
            check(themes > 0 and all(r["available"] - r["attempted"] == r["remaining"] >= 0 for r in progress), "practice progress",
                  f"{themes} themes in {(time.perf_counter() - t0) * 1000:.0f} ms (first call builds the theme cache)")
        cohort = reads.get_cohort_weak_concepts(min_students=1, limit=20)
        check(all(r["student_count"] >= settings.cohort_min_students for r in cohort), "cohort rows respect the minimum cohort floor",
              f"{len(cohort)} concepts reported (floor {settings.cohort_min_students})")
    check(differing <= args.accepted_mismatches, "mastery equals the formula over the stored evidence",
          f"{compared} tags compared, {differing} differ (accepted: {args.accepted_mismatches})")
    check(OPERATIONS <= READS, "only read operations were used", ", ".join(sorted(OPERATIONS)))
    print(f"sampled {len(sids)} students: {attempts} attempts, {days} activity days, {themes} practice themes")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
