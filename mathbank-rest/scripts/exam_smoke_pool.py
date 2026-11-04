"""Read-only smoke check of the question pool of the DynamoDB exam store against a real environment (requirement 71 WP6, C2 A12-A15, A21).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/exam_smoke_pool.py [--sample 25] [--vectors] [--match TOPIC]

Only reads: DynamoDB GetItem / Query / BatchGetItem and, with ``--vectors`` or ``--match``, S3 Vectors GetVectors / QueryVectors (``--match`` also
embeds the topic, one paid OpenAI call). Nothing is written and PostgreSQL is never touched. In ``dev`` the pool is empty (``quiz.question_pool`` had
0 rows), so most checks then reduce to shapes on an empty partition; the per-entry checks run as soon as the pool has rows. Exits 1 when a check fails.
"""
from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mathbank_rest import vector_store
from mathbank_rest.config import settings
from mathbank_rest.models.manual.exam_pool import PoolConcept, PoolUniqueHash, concept_sk
from mathbank_rest.stores import ddb, typed
from mathbank_rest.stores.exam.pool import PoolDynamoDB
from mathbank_rest.vector_catalog import Family

FAILURES: list[str] = []
OPERATIONS: set[str] = set()
READS = {"get_item", "query", "batch_get_item", "get_object", "get_caller_identity", "get_vectors", "query_vectors"}
VIEW_KEYS = {"pool_question_id", "content_hash", "style", "question_type", "difficulty_band", "topic_key", "concept_slugs", "technique_slugs",
             "source_quiz_id", "generated_by", "times_served", "last_served_at", "created_at", "status", "retired_at", "retired_reason",
             "near_duplicate_of", "vector_state", "version"}
ROW_KEYS = {"pool_question_id", "style", "question_type", "difficulty_band", "topic_key", "concept_slugs", "times_served", "created_at", "status"}


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


def all_rows(store: PoolDynamoDB, **kw) -> list[dict]:
    rows, token = [], None
    while True:
        page = store.list_pool_questions(limit=100, next_token=token, **kw)
        rows += page["items"]
        token = page["next_token"]
        if not token:
            return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=25, help="pool entries inspected in detail")
    parser.add_argument("--vectors", action="store_true", help="also check that INDEXED entries have vectors (needs VECTOR_STORE=s3vectors)")
    parser.add_argument("--match", metavar="TOPIC", help="run one topic match (embeds TOPIC: a paid call) for the first sampled style/type/band")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('exam')}")
    store = PoolDynamoDB()

    active, retired = timed("list ACTIVE", all_rows, store, status="ACTIVE"), timed("list RETIRED", all_rows, store, status="RETIRED")
    check(all(set(r) == ROW_KEYS for r in active + retired), "A21 row shape", f"{len(active)} active, {len(retired)} retired")
    check(all(r["status"] == "ACTIVE" for r in active) and all(r["status"] == "RETIRED" for r in retired), "A21 status partitions are pure")
    both = all_rows(store, status=None)
    check(len(both) == len(active) + len(retired), "A21 status=None lists both partitions", f"{len(both)} rows")
    check(store.get_pool_question(str(uuid.uuid4())) is None, "get unknown id -> None")
    check(store.match_pool_questions(None, style="AIME", question_types=["MCQ"], difficulty_band=None, topic=None, concept_slugs=[]) == [],
          "A12 nothing to match on -> []")
    probe = store.match_pool_questions(str(uuid.uuid4()), style="AIME", question_types=["MCQ"], difficulty_band="medium", topic=None,
                                       concept_slugs=["__no_such_concept__"])
    check(probe == [], "A13 unknown concept -> [] (reads one empty POOLCONCEPT partition)")

    sample = both[:args.sample]
    if not sample:
        print("     the pool is empty: per-entry checks skipped")
    states = {"PENDING": 0, "INDEXED": 0}
    for row in sample:
        pid = row["pool_question_id"]
        full = store.get_pool_question(pid)
        check(full is not None and set(full) == VIEW_KEYS | {"question"}, f"E05 {pid[:8]} view shape")
        if full is None:
            continue
        states[full["vector_state"]] += 1
        check(full["status"] == row["status"] and full["times_served"] == row["times_served"], f"A21 {pid[:8]} GSI row equals the base item")
        sentinel = typed.get(PoolUniqueHash, *ddb.unique_key("content_hash", full["content_hash"]))
        check(sentinel is not None and str(sentinel.pool_question_id) == pid, f"A16 {pid[:8]} sentinel points back")
        for slug in full["concept_slugs"]:
            c = typed.get(PoolConcept, f"POOLCONCEPT#{slug}", concept_sk(full["style"], full["question_type"], full["difficulty_band"], pid))
            check(c is not None and c.status == full["status"], f"A13 {pid[:8]} concept {slug} in sync")
        if args.vectors and full["vector_state"] == "INDEXED":
            found = vector_store.get_vector_store().get(Family.QUIZ_QUESTION, [f"{pid}#prompt"], with_data=False)
            check(bool(found) and found[0].metadata.get("status") == full["status"], f"A12 {pid[:8]} prompt vector present, status in sync")
    if sample:
        print(f"     vector_state of the sample: {states}")

    if args.match and sample:
        first = sample[0]
        out = timed("A12-A15 match", store.match_pool_questions, str(uuid.uuid4()), style=first["style"], question_types=[first["question_type"]],
                    difficulty_band=first["difficulty_band"], topic=args.match, concept_slugs=first["concept_slugs"][:1], limit=5)
        check(all(set(m) == {"pool_question_id", "question_type", "question", "topic_similarity"} for m in out), "match response shape",
              f"{len(out)} rows")
        check(all(0.0 <= m["topic_similarity"] <= 1.0 for m in out), "match similarity within [0, 1]")

    bad = OPERATIONS - READS
    check(not bad, "only read operations were used", ", ".join(sorted(OPERATIONS)))
    print(f"{'FAILED: ' + ', '.join(FAILURES) if FAILURES else 'all checks passed'}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    raise SystemExit(main())
