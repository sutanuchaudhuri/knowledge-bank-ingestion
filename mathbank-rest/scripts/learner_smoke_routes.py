"""Read-only smoke check of the routes area of the DynamoDB learner store against a real environment (requirement 71 WP5).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/learner_smoke_routes.py [--students 40] [--links 20]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject): learners are sampled from the admin directory index
(GSI2 ``STUDENT_DIR``), feedback from the per-status index (GSI1 ``FEEDBACK#<status>``) and agent links from GSI1 ``AGENTLINKS``,
never by a scan; nothing is written. PostgreSQL is never touched: the ADK session store (``agent_sessions`` schema until WP9) is
replaced by an empty stub, so the session lists are checked at the link level only.

Checks: every migrated ROUTE / FEEDBACK / AGENTLINK item parses into its refined model; at most one IN_PROGRESS attempt per learner
and release, each with its open-route sentinel; finished attempts carry ``finished_at``; the learner view is the documented shape and
never carries an answer key; another learner's attempt id is refused; paging with a one-item page returns exactly the list; reports
have their owner pointer and duplicate-check sentinel, resolved IRRELEVANT ones are in the retrieval exclusion, the admin queue
orders PENDING first; every link has its sentinel with the same owner. Exits 1 when a check fails; checks that need data the
environment does not hold (the live copy has 2 route attempts, 0 reports, 77 links) are reported as SKIP, not FAIL.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import agent_transcripts as at
from mathbank_rest import stores
from mathbank_rest.config import settings
from mathbank_rest.models.ddb.learner import LearnerProfile
from mathbank_rest.models.manual.learner_routes import (
    AgentLinkItem,
    FeedbackItem,
    FeedbackOwner,
    RetrievalExclusion,
    RouteItem,
    UniqueAgentSession,
    UniqueFeedback,
    UniqueOpenRoute,
)
from mathbank_rest.step_runtime import NotFound
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner.routes import RoutesDynamoDB

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity"}
FORBIDDEN_KEYS = {"expected_response", "correctness_policy", "correct_answer", "full_explanation"}
VIEW_KEYS = {"route_attempt_id", "route_release_id", "version", "current_step", "status", "goal", "student_prompt",
             "tutor_explained_steps", "mastery_recorded"}
LIST_KEYS = {"route_attempt_id", "route_release_id", "problem_code", "status", "current_step", "tutor_explained_steps", "version",
             "created_at", "updated_at", "finished_at"}
QUEUE_KEYS = {"feedback_id", "canonical_code", "topic", "reason", "status", "created_at", "review_note", "reviewed_at", "audit",
              "retrieval_verdict", "error_kind", "related_report_count"}
STATUSES = ("PENDING", "RESOLVED", "DISMISSED")


class Spy:
    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        attr = getattr(self._inner, name)
        if callable(attr) and not name.startswith("_"):
            OPERATIONS.add(name)
        return attr


class NoAdk:
    """Stands in for the PostgreSQL ADK session store: no sessions, so only the link level is exercised."""

    def available(self) -> bool:
        return True

    def facts(self, keys):
        return {}

    def unlinked_count(self, linked) -> int:
        return 0


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


def directory(limit: int) -> list[str]:
    """Student ids from the admin directory index (GSI2 ``STUDENT_DIR``); the projection carries ``student_id``."""
    page = ddb.query_page("learner", "STUDENT_DIR", index="GSI2", limit=limit)
    return [item["student_id"] for item in page["items"] if "student_id" in item]


def smoke_routes(store: RoutesDynamoDB, students: list[str]) -> None:
    total, strangers = 0, [s for s in students if s]
    for sid in students:
        routes = typed.query(RouteItem, ddb.student_pk(sid), sk_begins="ROUTE#", limit=200).items
        if not routes:
            continue
        label = f"learner {sid[:8]}"
        total += len(routes)
        open_by_release: dict[str, list[RouteItem]] = {}
        for r in routes:
            check((r.status == "FINISHED") == (r.finished_at is not None) and r.version >= 1 and r.current_step >= 1,
                  f"{label} route {str(r.route_attempt_id)[:8]}: item shape", f"{r.status} step {r.current_step} v{r.version}")
            if r.status == "IN_PROGRESS":
                open_by_release.setdefault(str(r.route_release_id), []).append(r)
        for release, items in open_by_release.items():
            marker = typed.get(UniqueOpenRoute, ddb.student_pk(sid), f"UNIQUE#open_route#{release}")
            check(len(items) == 1, f"{label}: one open attempt for release {release[:8]}", f"{len(items)} open")
            check(marker is not None and str(marker.route_attempt_id) == str(items[0].route_attempt_id),
                  f"{label}: open-route sentinel points at the open attempt")
        first = routes[0]
        view = timed(f"{label}: get_route_attempt_view", store.get_route_attempt_view, sid, str(first.route_attempt_id))
        check(set(view) == VIEW_KEYS and view["mastery_recorded"] is False, f"{label}: A33 view shape", view["status"])
        check(not leaked_keys(view), f"{label}: WP1 no answer key in the learner view")
        other = next((s for s in strangers if s != sid), None)
        if other:
            try:
                store.get_route_attempt_view(other, str(first.route_attempt_id))
                check(False, f"{label}: another learner's id is refused")
            except NotFound:
                check(True, f"{label}: another learner's id is refused")
        everything = store.list_route_attempts(sid, limit=200)
        check({i["route_attempt_id"] for i in everything["items"]} == {str(r.route_attempt_id) for r in routes}
              and all(set(i) == LIST_KEYS for i in everything["items"]), f"{label}: A34 list shape and content",
              f"{len(everything['items'])} attempt(s)")
        paged, token = [], None
        while True:
            page = store.list_route_attempts(sid, limit=1, next_token=token)
            paged += page["items"]
            token = page["next_token"]
            if not token:
                break
        check([i["route_attempt_id"] for i in paged] == [i["route_attempt_id"] for i in everything["items"]],
              f"{label}: one-item pages return the same list")
    if not total:
        skip("route attempts", f"none among the {len(students)} sampled learners")


def smoke_feedback(store: RoutesDynamoDB) -> None:
    counts = {}
    for status in STATUSES:
        items = typed.query(FeedbackItem, f"FEEDBACK#{status}", index="GSI1", limit=50, forward=False).items
        counts[status] = len(items)
        for f in items:
            sid, fid = str(f.student_id), str(f.feedback_id)
            label = f"feedback {fid[:8]} ({status})"
            check(f.status == status and f.GSI1SK.endswith(f"#{fid}"), f"{label}: item shape")
            owner = typed.get(FeedbackOwner, f"FEEDBACK#{fid}", "OWNER")
            check(owner is not None and str(owner.student_id) == sid, f"{label}: owner pointer")
            sentinels = [u for u in typed.query(UniqueFeedback, ddb.student_pk(sid), sk_begins="UNIQUE#feedback#", limit=200).items
                         if str(u.feedback_id) == fid]
            check(len(sentinels) == 1, f"{label}: duplicate-check sentinel")
            if status == "RESOLVED" and f.retrieval_verdict == "IRRELEVANT" and f.requested_node_id:
                row = typed.get(RetrievalExclusion, f"RETRIEVAL_EXCLUSION#{f.requested_node_id}", f"PROBLEM#{f.problem_id}")
                check(row is not None and fid in row.feedback_ids, f"{label}: retrieval exclusion lists the report")
    if not any(counts.values()):
        return skip("feedback", "no report in any status (the migrated copy holds none)")
    queue = timed("list_feedback_queue", store.list_feedback_queue, 100, 0)
    check(queue["total"] >= sum(counts.values()) and all(set(i) == QUEUE_KEYS for i in queue["items"]),
          "A36 queue shape", f"{queue['total']} report(s)")
    statuses = [i["status"] for i in queue["items"]]
    check(statuses == sorted(statuses, key=lambda s: s != "PENDING"), "A36 PENDING first")
    examples = store.list_retrieval_examples(50)
    check(all(e["retrieval_verdict"] != "UNCLASSIFIED" for e in examples), "A36 retrieval examples are classified",
          f"{len(examples)} example(s)")


def smoke_links(store: RoutesDynamoDB, limit: int) -> None:
    links = typed.query(AgentLinkItem, "AGENTLINKS", index="GSI1", limit=limit, forward=False).items
    if not links:
        return skip("agent links", "no link in GSI1 AGENTLINKS")
    emails = store._agent_emails(link.student_id for link in links)
    for link in links:
        sid, label = str(link.student_id), f"link {link.agent_session_id[:8]}"
        sentinel = typed.get(UniqueAgentSession, *ddb.unique_key("agent_session", f"{link.agent_app_name}#{link.agent_session_id}"))
        check(sentinel is not None and str(sentinel.student_id) == sid, f"{label}: A38 sentinel carries the owner")
        found = store.get_agent_link(link.agent_app_name, link.agent_session_id)
        check(found is not None and found["student_id"] == sid and found["agent_user_id"] == str(link.agent_user_id),
              f"{label}: get_agent_link")
        check(store.get_link_owner(link.agent_app_name, link.agent_session_id) == sid, f"{label}: get_link_owner")
        check(sid in emails, f"{label}: the owner has a profile")
    mine = timed("list_student_sessions", store.list_student_sessions, str(links[0].student_id))
    check({m["agent_session_id"] for m in mine} >= {links[0].agent_session_id} and all(m["session_missing"] for m in mine),
          "A39 own sessions listed (ADK facts stubbed)", f"{len(mine)} session(s)")
    page = timed("list_all_sessions", store.list_all_sessions, None, 5)
    check(len(page["linked"]) == min(5, len(links)) or len(links) < 5, "A40 admin list page")
    seen, token = [], page.get("next_token")
    seen += [m["agent_session_id"] for m in page["linked"]]
    for _ in range(50):
        if not token:
            break
        nxt = store.list_all_sessions(None, 5, token)
        seen += [m["agent_session_id"] for m in nxt["linked"]]
        token = nxt.get("next_token")
    check(len(seen) == len(set(seen)), "A40 signed-token paging has no repeats", f"{len(seen)} link(s) walked")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--students", type=int, default=40, help="learners sampled from the directory for route attempts")
    parser.add_argument("--links", type=int, default=20, help="agent links sampled")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    at.adk_sessions = NoAdk()
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('learner')}")
    store = RoutesDynamoDB()
    with stores.override_store("content", DynamoDBContentStore()):
        students = directory(args.students)
        print(f"sampled {len(students)} learner(s) from the directory; profiles parse: "
              f"{len(typed.batch_get(LearnerProfile, [(ddb.student_pk(s), 'PROFILE') for s in students]))}")
        smoke_routes(store, students)
        smoke_feedback(store)
        smoke_links(store, args.links)
    print(f"API operations used: {sorted(OPERATIONS)}")
    check(OPERATIONS <= READS, "only read operations were used", ", ".join(sorted(OPERATIONS - READS)))
    print(f"{len(FAILURES)} failure(s)" if FAILURES else "all checks passed")
    print(json.dumps({"failures": FAILURES}) if FAILURES else "")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
