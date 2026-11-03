"""Read-only smoke check of the micro-course area of the DynamoDB learner store against a real environment (requirement 71 WP5).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/learner_smoke_microcourse.py [--limit 5]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject): enrollments are found through the per-release index
(GSI1 ``MC_RELEASE#<release>``) of each published course, never by a scan, and nothing is written. PostgreSQL is never touched.
For each sampled enrollment it checks that the migrated item parses into the refined models, that the learner runtime view is
the documented shape and carries no answer key or explanation before the learner answered, that the answered items equal
``last_responses``, that the owner pointer, "my enrollments" and the admin activity numbers agree with the index, and that the
misconception state of the learner (when any) parses. Exits 1 when a check fails; checks that need data the environment does not
hold (published courses, enrollments, interaction events) are reported as SKIP, not FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models.manual import learner_microcourse as mc
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner.microcourse import MicroCourseDynamoDB

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity"}
FORBIDDEN_KEYS = {"correctness_policy", "correct_answer", "answer_or_solution_seed", "canonical_policy", "expected_response",
                  "correct_index", "correct_value"}
SUMMARY_KEYS = {"enrollment_id", "canonical_code", "micro_course_id", "release_id", "status", "current_state_id", "state_version",
                "started_at", "completed_at"}
RUNTIME_KEYS = {"enrollment_id", "enrollment_status", "started_at", "completed_at", "micro_course_id", "release_id", "version",
                "state_version", "canonical_code", "course_title", "course_description", "estimated_minutes", "step_count",
                "step_number", "current_state", "can_continue", "can_go_back", "can_finish"}
STATE_KEYS = {"state_id", "state_key", "state_type", "title", "ordinal", "objective", "student_instruction", "estimated_seconds",
              "required", "module_id", "module_title", "assets", "interactions", "activities", "learning_items",
              "transcript_segments", "qa_contexts", "items", "answered_learning_item_ids"}
ACTIVITY_KEYS = {"canonical_code", "release_id", "version", "total_enrollments", "in_progress", "completed", "completion_rate",
                 "step_funnel", "quiz_accuracy", "recent_activity"}


class Spy:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and not name.startswith("_"):
            OPERATIONS.add(name)
        return attr


def check(ok: bool, label: str, detail: str = "") -> None:
    print(f"{'ok  ' if ok else 'FAIL'} {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(label)


def skip(label: str, why: str) -> None:
    print(f"SKIP {label} - {why}")


def timed(label: str, fn, *args, **kwargs):
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    print(f"     {label}: {(time.perf_counter() - t0) * 1000:.0f} ms")
    return out


def leaked_keys(payload) -> set[str]:
    found, stack = set(), [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            found |= FORBIDDEN_KEYS & set(node)
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


def release_enrollments(release_id: str, limit: int) -> list[mc.LearnerEnroll]:
    """The first ``limit`` enrollments of a release from the per-release index (A29), parsed into the refined model."""
    return typed.query(mc.LearnerEnroll, f"MC_RELEASE#{release_id}", index="GSI1", limit=limit).items


def smoke_enrollment(store: MicroCourseDynamoDB, e: mc.LearnerEnroll) -> None:
    sid, eid = str(e.student_id), str(e.enrollment_id)
    label = f"enrollment {eid[:8]} ({e.status})"
    check(e.state_version == e.version and e.GSI1SK.startswith(f"{e.status}#"), f"{label}: item shape", f"state_version={e.state_version}")
    check(store.get_enrollment_owner(None, eid) == sid, f"{label}: A30 owner pointer names the student")
    check(store.get_enrollment_owner(None, "00000000-0000-4000-8000-00000000dead") is None, f"{label}: unknown owner is None")
    runtime = timed(f"{label}: get_enrollment_runtime", store.get_enrollment_runtime, None, eid, sid)
    check(set(runtime) == RUNTIME_KEYS, f"{label}: A27 runtime shape", f"step {runtime['step_number']}/{runtime['step_count']}")
    check(set(runtime["current_state"]) == STATE_KEYS, f"{label}: A27 state shape")
    check(runtime["state_version"] == e.state_version and runtime["enrollment_status"] == e.status, f"{label}: A27 matches the item")
    answered = {k for k, v in (e.resolve("last_responses", dict[str, mc.LastResponse]) or {}).items()}
    state = runtime["current_state"]
    ids = {i["learning_item_id"] for i in state["learning_items"]} | {a["activity_id"] for a in state["activities"]}
    shown = {i["learning_item_id"] for i in state["learning_items"] if "answered_correctly" in i} | \
            {a["activity_id"] for a in state["activities"] if "answered_correctly" in a}
    check(shown == answered & ids, f"{label}: answered items equal last_responses", f"{len(shown)} of {len(ids)} answered")
    unanswered = [i for i in state["learning_items"] + state["activities"] if "answered_correctly" not in i]
    check(all("explanation" not in i for i in unanswered), f"{label}: WP1 no explanation before answering", f"{len(unanswered)} open")
    check(not leaked_keys(runtime), f"{label}: WP1 no answer-key field in the runtime")
    other = store.list_enrollments(None, sid)
    check(any(i["enrollment_id"] == eid for i in other["items"]) and all(set(i) == SUMMARY_KEYS for i in other["items"]),
          f"{label}: A28 listed for its owner", f"{other['total']} enrollment(s)")
    check(all(i["status"] == e.status for i in store.list_enrollments(None, sid, status=e.status)["items"]),
          f"{label}: A28 status filter")
    foreign = "00000000-0000-4000-8000-0000000000f0"
    try:
        store.get_enrollment_runtime(None, eid, foreign)
        check(False, f"{label}: another student's id is refused")
    except Exception as exc:  # noqa: BLE001
        check(type(exc).__name__ == "MicroCourseNotFound", f"{label}: another student's id is refused", type(exc).__name__)
    misc = store.list_misconceptions(None, sid)
    check(all(0 <= m["confidence"] <= 1 for m in misc["items"]), f"{label}: A32 misconception state parses", f"{misc['total']} item(s)")
    events = typed.query(mc.LearnerIxevent, ddb.student_pk(sid), sk_begins=f"ENROLL#{eid}#IX#", limit=1).items
    if events:
        recent = store.list_item_interactions(None, eid, sid, str(events[0].interaction_instance_id))
        check(0 < len(recent) <= 10, f"{label}: A31 last interactions of an item", f"{len(recent)} event(s)")
    else:
        skip(f"{label}: A31 interactions", "the enrollment has no interaction events")


def smoke(limit: int) -> None:
    content = DynamoDBContentStore()
    courses = content.list_published_micro_courses(None, 200)
    if not courses:
        return skip("micro-course enrollments", "no published course in GSI2 CATALOG#MC")
    store, sampled = MicroCourseDynamoDB(), 0
    for course in courses:
        enrollments = release_enrollments(course["release_id"], limit)
        activity = timed(f"list_course_activity({course['canonical_code']})", store.list_course_activity, None, course["canonical_code"])
        check(set(activity) == ACTIVITY_KEYS, f"A29 {course['canonical_code']}: activity shape",
              f"{activity['total_enrollments']} enrollment(s)")
        check(activity["in_progress"] + activity["completed"] <= activity["total_enrollments"],
              f"A29 {course['canonical_code']}: counts are consistent")
        check(not leaked_keys(activity), f"A29 {course['canonical_code']}: no answer key in the activity view")
        if not enrollments:
            skip(f"{course['canonical_code']}: enrollments", "none on the release")
            continue
        for e in enrollments:
            if sampled >= limit:
                return
            smoke_enrollment(store, e)
            sampled += 1
    if not sampled:
        skip("enrollment checks", "no enrollment on any published release")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=5, help="enrollments to sample (default 5)")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('learner')}")
    with stores.override_store("content", DynamoDBContentStore()):
        smoke(args.limit)
    print(f"API operations used: {sorted(OPERATIONS)}")
    check(OPERATIONS <= READS, "only read operations were used", ", ".join(sorted(OPERATIONS - READS)))
    print(f"{len(FAILURES)} failure(s)" if FAILURES else "all checks passed")
    print(json.dumps({"failures": FAILURES}) if FAILURES else "")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
