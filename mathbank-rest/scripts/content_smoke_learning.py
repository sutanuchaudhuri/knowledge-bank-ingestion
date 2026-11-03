"""Read-only smoke check of the learning area of the DynamoDB content store against a real environment (requirement 71 WP4).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/content_smoke_learning.py

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject). Nothing is written and PostgreSQL is never touched. Exits 1
when a shape or consistency check fails; every check prints one line with the measured counts. Checks that need data the
environment does not hold yet (published courses, theorem items) are reported as SKIP, not FAIL.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest.config import settings
from mathbank_rest.stores import ddb
from mathbank_rest.stores.content.learning import (
    LearningDynamoDB,
    _published_mc,
    snapshot_asset_ids,
)
from mathbank_rest.stores.content.snapshots import snapshots

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity"}
FORBIDDEN_KEYS = {"correctness_policy", "correct_answer", "answer_or_solution_seed", "canonical_policy", "expected_response"}
READER_KEYS = {"micro_course_id", "canonical_code", "title", "description", "metadata", "estimated_minutes", "difficulty_level",
               "release_id", "version", "learning_objectives", "prerequisite_summary", "primary_targets", "prerequisite_targets",
               "modules", "states", "transitions"}
STATE_KEYS = {"state_id", "module_id", "module_key", "state_key", "ordinal", "state_type", "title", "objective",
              "student_instruction", "estimated_seconds", "required", "skippable", "assets", "qa_contexts", "learning_items",
              "transcript_segments", "interactions", "activities", "items"}
LIST_KEYS = {"canonical_code", "title", "description", "metadata", "estimated_minutes", "difficulty_level", "release_id", "version",
             "state_count", "primary_targets"}


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


def smoke_courses(store: LearningDynamoDB) -> None:
    rows = timed("list_published_micro_courses", store.list_published_micro_courses, None, 200)
    if not rows:
        return skip("A18/A19/A20 micro-courses", "no published course in GSI2 CATALOG#MC")
    check(all(set(r) == LIST_KEYS for r in rows), "A18 list shape", f"{len(rows)} courses")
    check([(r["title"], r["canonical_code"]) for r in rows] == sorted((r["title"], r["canonical_code"]) for r in rows),
          "A18 ordered by title, code")
    check(store.list_published_micro_courses(None, 1, 1) == rows[1:2], "A18 offset/limit window equals slice")
    check(not any(leaked_keys(r) for r in rows), "A18 list has no answer keys")
    code = rows[0]["canonical_code"]
    reader = timed(f"get_micro_course_reader({code})", store.get_micro_course_reader, None, code)
    check(set(reader) == READER_KEYS, "A19 reader top-level shape", f"{len(reader['states'])} states")
    check(all(set(s) == STATE_KEYS for s in reader["states"]), "A19 state shape")
    check(not leaked_keys(reader), "A19 reader has no answer keys")
    check("uri" not in json.dumps(reader), "A19 reader has no storage uri")
    check(reader["release_id"] == rows[0]["release_id"], "A19 reader release equals the catalogue's")
    before = len(snapshots._lru)
    timed("get_micro_course_reader (LRU hit)", store.get_micro_course_reader, None, code)
    check(len(snapshots._lru) == before, "A19 second read served from the snapshot LRU")
    check(store.get_pinned_micro_course_reader(None, reader["release_id"]) == reader, "A19 pinned release equals the current reader")

    ids = sorted(snapshot_asset_ids(snapshots.get_json(_published_mc(code).current_s3_key)))
    print(f"     A20 snapshot lists {len(ids)} assets")
    for asset_id in ids[:3]:
        try:
            asset = store.get_course_asset(None, code, asset_id)
            check(set(asset) == {"object_key", "mime_type", "content_hash", "object_size_bytes"}, "A20 asset route data",
                  f"{asset_id}: {asset['mime_type']}")
        except Exception as exc:  # noqa: BLE001 - an external (non object-store) asset is a 409 by design
            print(f"     A20 asset {asset_id}: {type(exc).__name__}: {exc}")
    try:
        store.get_course_asset(None, code, "00000000-0000-4000-8000-00000000dead")
        check(False, "A20 asset outside the snapshot is refused")
    except Exception as exc:  # noqa: BLE001
        check(type(exc).__name__ == "MicroCourseNotFound", "A20 asset outside the snapshot is refused", type(exc).__name__)

    for state in reader["states"]:
        for item in state["learning_items"][:1]:
            key = store.get_learning_item_key(None, item["learning_item_id"])
            check(key is not None and set(key) == {"learning_item_id", "correct_answer", "answer_or_solution_seed"},
                  "A16 learning-item key (strong read)", item["learning_item_id"])
            graded = store.get_grading_item(None, reader["release_id"], state["state_id"], item["learning_item_id"])
            check(graded is not None and graded["choices"] == item["choices"], "A16 grading item from the pinned release")
            break
        for activity in state["activities"][:1]:
            akey = store.get_activity_key(None, activity["activity_id"])
            check(akey is None or set(akey) == {"activity_id", "correctness_policy", "canonical_policy"}, "A17 activity key shape",
                  "mirrored" if akey else "activity not mirrored (not STATIC/PRECOMPILED)")
            definition = store.get_activity_definition(None, activity["activity_id"])
            check(definition is None or not leaked_keys(definition), "A17 activity definition carries no key")
            break


def smoke_theorems(store: LearningDynamoDB) -> None:
    check(store.get_theorems_for_technique(None, "does-not-exist") == {"items": []}, "A23 unknown technique is empty")
    try:
        store.get_theorem_by_slug(None, "does-not-exist")
        check(False, "A23 unknown theorem is refused")
    except Exception as exc:  # noqa: BLE001
        check(type(exc).__name__ == "TheoremNotFound", "A23 unknown theorem is refused", type(exc).__name__)
    pointer = ddb.get_item("content", "CATALOG#THEOREM", "SNAPSHOT")
    if pointer is None:
        return skip("A23 theorems", "no CATALOG#THEOREM snapshot yet")
    items = snapshots.get_json(pointer["s3_key"])["items"]
    if not items:
        return skip("A23 theorems", "empty theorem catalogue")
    slug = items[0]["slug"]
    theorem = timed(f"get_theorem_by_slug({slug})", store.get_theorem_by_slug, None, slug)
    check({"theorem_id", "slug", "name", "kind", "field", "statement_text", "assets", "sources", "taxonomy_links"} <= set(theorem),
          "A23 theorem shape", f"{len(items)} theorems in the catalogue")
    check("uri" not in json.dumps(theorem, default=str), "A23 theorem has no raw uri")
    lineage = timed("get_theorem_prerequisites", store.get_theorem_prerequisites, None, slug)
    check(all(r["depth"] <= 4 for r in lineage["prerequisites"]), "A23 prerequisites respect max_depth 4",
          f"{len(lineage['prerequisites'])} rows")
    shallow = store.get_theorem_prerequisites(None, slug, max_depth=1)
    check(all(r["depth"] == 1 for r in shallow["prerequisites"]), "A23 max_depth=1")
    for link in theorem["taxonomy_links"][:1]:
        by_node = store.list_theorems_for_taxonomy_node(None, link["taxonomy_node_id"])
        check(any(r["slug"] == slug for r in by_node["items"]), "A23 by-taxonomy contains the theorem", link["taxonomy_node_id"])


def smoke_interactions(store: LearningDynamoDB) -> None:
    library = timed("get_widget_library", store.get_widget_library, None)
    check(set(library) == {"templates", "controls", "icons", "animations"}, "A31 widget library shape",
          ", ".join(f"{k}={len(v)}" for k, v in library.items()))
    row = next((t for t in library["templates"] if t["interaction_template_version_id"]), None)
    if row is None:
        return skip("A31 template version", "no template with a version id")
    version = store.get_interaction_template_version(None, row["template_key"], row["version"])
    check(version is not None and version["template_key"] == row["template_key"] and version["version"] == row["version"],
          "A31 template version", f"{row['template_key']} v{row['version']}")
    check(store.get_interaction_template_version(None, row["template_key"], 9999) is None, "A31 unknown version is None")


def main() -> int:
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('content')}")
    store = LearningDynamoDB()
    smoke_courses(store)
    smoke_theorems(store)
    smoke_interactions(store)
    print(f"API operations used: {sorted(OPERATIONS)}")
    check(OPERATIONS <= READS, "only read operations were used", ", ".join(sorted(OPERATIONS - READS)))
    print(f"{len(FAILURES)} failure(s)" if FAILURES else "all checks passed")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
