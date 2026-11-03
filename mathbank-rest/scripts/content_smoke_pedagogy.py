"""Read-only smoke check of the pedagogy area of the DynamoDB content store against a real environment (requirement 71 WP4).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/content_smoke_pedagogy.py [--problems 60] [--video-id ID]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject); nothing is written (the cached-hint write is not exercised) and
PostgreSQL is never touched. Exits 1 when a shape or consistency check fails; every check prints one line with the measured counts.
Problem codes are taken from the catalogue listing (no scans); the first problem with a solution DAG / published route is used.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest.config import settings
from mathbank_rest.stores import ddb
from mathbank_rest.stores.content import DynamoDBContentStore

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity"}
STEP_KEYS = {"solution_step_id", "source_step_id", "occurrence", "solution_id", "solution_part_id", "part_label", "global_step_index",
             "step_index_in_part", "step_text", "step_type", "tutor_role", "concept_node_id", "subconcept_node_id", "skill_node_id",
             "skill_name", "hint_level", "is_checkpoint"}
TAXONOMY_KEYS = {"taxonomy_node_id", "node_type", "name", "parent_node_id", "parent_name", "chapter_number", "section_number", "slug",
                 "slug_kind", "problem_count", "example_problem_codes"}


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


def timed(label: str, fn, *args, **kwargs):
    t0 = time.perf_counter()
    out = fn(*args, **kwargs)
    print(f"     {label}: {(time.perf_counter() - t0) * 1000:.0f} ms")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problems", type=int, default=60, help="problems examined from the catalogue listing")
    parser.add_argument("--competition", help="competition code to sample (default: every competition; only some books have solution DAGs)")
    parser.add_argument("--video-id", help="a video_asset_id with an approved transcript (the video tables were empty at migration)")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('content')}")
    store = DynamoDBContentStore()

    codes = [r["canonical_code"] for r in timed("list_problems", store.list_problems, competition=args.competition, limit=args.problems)]
    check(bool(codes), "catalogue listing returned problem codes", f"{len(codes)} codes")

    dag, dag_code = None, None
    for code in codes:
        dag = store.get_solution_dag(code)
        if dag["steps"]:
            dag_code = code
            break
    check(dag is not None and bool(dag["steps"]), "A14 a solution DAG exists", f"problem {dag_code}")
    if dag and dag["steps"]:
        steps = dag["steps"]
        check(all(set(s) == STEP_KEYS for s in steps), "A14 step rows have the Postgres column set", f"{len(steps)} steps")
        check([s["global_step_index"] for s in steps] == sorted(s["global_step_index"] for s in steps), "A14 steps ordered by global_step_index")
        check(all(s["step_text"] and s["part_label"] for s in steps), "A14 step_text resolved (inline or S3) and part labels joined")
        ids = {s["solution_step_id"] for s in steps}
        check(all(d["from_step_id"] in ids and d["to_step_id"] in ids and d["review_status"] != "REJECTED" for d in dag["dependencies"]),
              "A14 dependencies reference the DAG's steps and exclude REJECTED", f"{len(dag['dependencies'])} edges")
        check(all(t["review_status"] == "APPROVED" for t in dag["step_techniques"]), "A14 step techniques are APPROVED only",
              f"{len(dag['step_techniques'])} rows")
        pid = dag["problem_id"]
        by_id = timed("get_solution_dag(problem_id)", store.get_solution_dag, problem_id=pid)
        check(by_id["problem_code"] == dag_code and len(by_id["steps"]) == len(steps), "A14 problem_id resolves through GSI1 PID#")

        details = timed("get_step_details", store.get_step_details, [s["solution_step_id"] for s in steps[:5]] + ["__missing__"])
        check(len(details) == min(5, len(steps)) and all(r["eligible"] for r in details.values()), "A15 step details + eligibility",
              f"{len(details)} rows")
        check(all("step_text" not in r for r in details.values()), "A15 step text omitted unless asked")
        with_text = store.get_step_details([steps[0]["solution_step_id"]], include_step_text=True)
        check(with_text[steps[0]["solution_step_id"]]["step_text"] == steps[0]["step_text"], "A15 step text equals the DAG's")
        first = steps[0]["solution_step_id"]
        ctx = timed("get_step_tutor_context", store.get_step_tutor_context, first)
        check(bool(ctx["statement_text"]) and ctx["part_label"] == steps[0]["part_label"] and ctx["previous_steps"] == [],
              "A14 tutor context (statement, part label, no earlier steps for step 1)")
        last = steps[-1]["solution_step_id"]
        check(len(store.get_step_tutor_context(last)["previous_steps"]) == len(steps) - 1, "A14 tutor context lists every earlier step")
        origin = store.get_step_origin(first)
        check(origin["canonical_code"] == dag_code and origin["part_label"] == steps[0]["part_label"], "A14 step origin")
        target = store.get_step_recovery_target(first)
        check(bool(target["skill_node_id"]) and bool(target["label"]), "A14 recovery target", str(target["label"]))
        hint = store.get_cached_step_hint(first, 1, "step-hint-v1")      # a miss is normal: the cache fills as students ask
        check(hint is None or isinstance(hint, str), "A27 cached-hint strong read", "hit" if hint else "miss")
        check(isinstance(store.list_cached_step_hints(first, 4, "step-hint-v1"), list), "A27 lower cached hints read")

    route, route_code = None, None
    for code in codes:
        route = store.find_published_route(code)
        if route:
            route_code = code
            break
    if route is None:
        print("skip A21/A22: none of the examined problems has a published route (raise --problems)")
    else:
        rid = route["route_release_id"]
        print(f"     published route for {route_code}: {rid}")
        check(route["status"] == "PUBLISHED" and route["canonical_code"] == route_code and bool(route["approach_summary"]),
              "A21 find_published_route row")
        instructions = timed("list_route_instructions", store.list_route_instructions, rid)
        check(bool(instructions) and "expected_response" not in json.dumps(instructions), "A22 learner instructions carry no expected_response",
              f"{len(instructions)} steps")
        view = store.load_route_learner_view(rid)
        check("expected_response" not in json.dumps(view), "A22 learner snapshot carries no expected_response")
        check(store.get_route_step_hint(rid, 1, 1) is not None, "A22 opening hint level 1 exists")
        program = timed("load_route_program", store.load_route_program, rid)
        check(len(program.steps) == len(instructions) and all(s.instruction.expected_response for s in program.steps),
              "A22 server-side program rebuilt with expected_response", f"{len(program.steps)} steps")
        check(all(len(s.hints) == 4 for s in program.steps), "A22 four default hints per step")
        check(store.get_published_route(route_code, rid) is not None, "A21 get_published_route by release id")

    concepts = timed("list_taxonomy_nodes", store.list_taxonomy_nodes, ("CONCEPT", "SUBCONCEPT", "SKILL", "TECHNIQUE"))
    check(bool(concepts) and all(set(n) == {"taxonomy_node_id", "name", "node_type"} for n in concepts), "A24 taxonomy listing via GSI2 TAXTYPE#",
          f"{len(concepts)} nodes")
    nodes = store.get_taxonomy_nodes([n["taxonomy_node_id"] for n in concepts[:5]])
    check(len(nodes) == min(5, len(concepts)) and all(set(n) == TAXONOMY_KEYS for n in nodes.values()), "A24 taxonomy details shape")
    parent_ids = {n["parent_node_id"] for n in nodes.values() if n["parent_node_id"]}
    if parent_ids:
        parent = min(parent_ids)
        kids = timed("list_taxonomy_children", store.list_taxonomy_children, parent)
        check(bool(kids) and all(k["parent_node_id"] == parent for k in kids), "A24 children via GSI1 TAXCHILD#", f"{len(kids)} children of {parent}")
    skill = next((n for n in concepts if n["node_type"] == "SKILL"), None)
    if skill:
        cands = timed("list_topic_candidates", store.list_topic_candidates, skill["taxonomy_node_id"], limit=20)
        check(all({"canonical_code", "node_type", "confidence", "difficulty", "skill_ids", "structure_key"} == set(c) for c in cands)
              and [c["canonical_code"] for c in cands] == sorted(c["canonical_code"] for c in cands), "A24 topic candidates shape and order",
              f"{len(cands)} candidates for {skill['taxonomy_node_id']}")

    if args.video_id:
        doc = timed("get_video_transcript", store.get_video_transcript, args.video_id)
        check(doc is not None and bool(doc["segments"]), "A26 transcript loaded and checksum-verified")
        if doc and doc["segments"]:
            seg = doc["segments"][len(doc["segments"]) // 2]
            check(store.find_video_segment_at(args.video_id, seg["start_ms"]) == seg, "A26 binary search finds the segment at start_ms")
    else:
        print("skip A26: pass --video-id to check a transcript (video tables were empty at migration)")

    check(OPERATIONS <= READS, "only read operations were issued", ", ".join(sorted(OPERATIONS)))
    print(f"{'ALL CHECKS PASSED' if not FAILURES else 'FAILED: ' + '; '.join(FAILURES)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
