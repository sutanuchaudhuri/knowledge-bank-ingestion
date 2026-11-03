"""Read-only smoke check of the catalog area of the DynamoDB content store against a real environment (requirement 71 WP4).

    MB_AWS_PROFILE=aws-sutanu-admin DDB_ENV=dev .venv/bin/python scripts/content_smoke_catalog.py [--problems 40]

Only DynamoDB/S3 reads (GetItem, Query, BatchGetItem, GetObject). Nothing is written and PostgreSQL is never touched. Exits 1
when a shape or consistency check fails; every check prints one line with the measured counts.
"""
from __future__ import annotations

import argparse
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


def has_keys(rows: list[dict], keys: set[str]) -> bool:
    return all(set(r) == keys for r in rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problems", type=int, default=40, help="problems scanned for one with diagrams")
    args = parser.parse_args()
    real = ddb.client
    ddb.client = lambda service="dynamodb": Spy(real(service))      # records every API operation used
    print(f"env={settings.ddb_env} profile={settings.aws_profile or '(default chain)'} table={ddb.table_name('content')}")
    store = DynamoDBContentStore()

    comps = timed("list_competitions", store.list_competitions)
    check(bool(comps) and has_keys(comps, {"competition_id", "external_code", "name", "level"}), "A1 competitions shape", f"{len(comps)} rows")
    check([c["name"] for c in comps] == sorted(c["name"] for c in comps), "A1 competitions ordered by name")

    list_keys = {"canonical_code", "problem_number", "official_answer", "source_url", "paper_code", "year", "competition"}
    page = timed("list_problems(limit=10)", store.list_problems, limit=10)
    check(len(page) == 10 and has_keys(page, list_keys), "A5 list_problems shape", f"{len(page)} rows")
    order = [(r["competition"], r["year"] or 0, r["paper_code"], r["problem_number"]) for r in page]
    check(order == sorted(order), "A5 ordering comp.name, year, paper_code, problem_number")
    check(store.list_problems(limit=5, offset=5) == page[5:10], "A5 offset/limit window equals slice")
    first = comps[0]["external_code"]
    only = store.list_problems(competition=first, limit=50)
    check(all(r["competition"] == comps[0]["name"] for r in only) and bool(only), "A5 competition filter", f"{first}: {len(only)} rows")
    years = sorted({r["year"] for r in only if r["year"]})
    if len(years) >= 2:
        lo, hi = years[0], years[1]
        ranged = store.list_problems(competition=first, year_min=lo, year_max=hi, limit=200)
        check(bool(ranged) and {r["year"] for r in ranged} <= set(years[:2]), "A5 year range", f"{lo}-{hi}: {len(ranged)} rows")

    concepts = timed("list_concepts", store.list_concepts, limit=200)
    check(bool(concepts) and has_keys(concepts, {"slug", "name", "level", "description"}), "A8 concepts shape", f"{len(concepts)} (page of 200)")
    levels = [c["level"] for c in concepts if c["level"] is not None]
    check(levels == sorted(levels), "A8 concepts ordered by level, NULLs last")
    techniques = timed("list_techniques", store.list_techniques, limit=200)
    check(bool(techniques) and has_keys(techniques, {"slug", "name", "description"}), "A8 techniques shape", f"{len(techniques)} (page of 200)")

    broad = timed("get_concept_problems(broadest)", store.get_concept_problems, concepts[0]["slug"], limit=25)
    cp_keys = {"canonical_code", "problem_number", "competition", "year", "role", "confidence", "matched_concept_slug"}
    probe = next((c["slug"] for c in concepts if store.get_concept_problems(c["slug"], limit=1)), None)
    rows = store.get_concept_problems(probe, limit=30) if probe else []
    check(has_keys(rows, cp_keys) and bool(rows), "A6 concept problems shape", f"{probe}: {len(rows)} rows, broad={len(broad)}")
    check(len({r["canonical_code"] for r in rows}) == len(rows), "A6 one row per problem")
    keys = [(r["year"] or 0, r["problem_number"], r["canonical_code"]) for r in rows]
    check(keys == sorted(keys), "A6 ordered by year, problem_number, code")
    check(store.get_concept_problems(probe, limit=5, offset=5) == rows[5:10], "A6 offset/limit window equals slice")
    if probe:
        filtered = store.list_problems(concept=probe, limit=50)
        check(has_keys(filtered, list_keys), "A5 concept filter shape", f"{probe}: {len(filtered)} rows")
        neighbours = timed("get_concept_neighbors", store.get_concept_neighbors, probe)
        check(has_keys(neighbours, {"slug", "name", "relation_type", "strength", "direction"}), "A10 neighbours shape", f"{len(neighbours)} rows")

    tech = next((t["slug"] for t in techniques if store.get_technique_problems(t["slug"], limit=1)), None)
    trows = store.get_technique_problems(tech, limit=30) if tech else []
    check(bool(trows) and has_keys(trows, {"canonical_code", "problem_number", "competition", "year", "role", "confidence"}),
          "A7 technique problems shape", f"{tech}: {len(trows)} rows")
    if tech:
        check(has_keys(store.list_problems(technique=tech, limit=20), list_keys), "A5 technique filter shape")

    code = page[0]["canonical_code"]
    problem = timed("get_problem_by_code", store.get_problem_by_code, code)
    want = {"canonical_code", "problem_number", "statement_text", "official_answer", "source_url", "difficulty_band",
            "classification_status", "paper_code", "year", "competition", "concepts", "techniques", "solutions", "diagrams"}
    check(problem is not None and set(problem) == want, "A2 problem detail shape", code)
    check(store.get_problem_by_code("NO_SUCH_CODE_XYZ") is None, "A2 unknown code -> None")
    batch = timed("get_problems_by_codes(10)", store.get_problems_by_codes, [r["canonical_code"] for r in page])
    check([r["canonical_code"] for r in batch] == [r["canonical_code"] for r in page], "A4 batch keeps input order", f"{len(batch)} rows")
    tags = store.get_problem_tags(code=code)
    check(set(tags) == {"concept_ids", "technique_ids"}, "A11 tags shape", f"{len(tags['concept_ids'])} concepts, {len(tags['technique_ids'])} techniques")

    coverage = timed("get_corpus_coverage", store.get_corpus_coverage)
    check(bool(coverage) and has_keys(coverage, {"competition", "papers", "problems", "problems_with_concept", "problems_with_technique"}),
          "A12 coverage shape", f"{len(coverage)} competitions, {sum(r['problems'] for r in coverage)} problems")

    shown = 0
    for row in store.list_problems(limit=min(args.problems, 200)):
        diagrams = store.list_problem_diagrams(row["canonical_code"])
        if not diagrams:
            continue
        shown += 1
        image = store.get_student_image(diagrams[0]["problem_image_id"])
        check(image is not None and bool(image["data"]) and image["media_type"].startswith("image/"), "A13 student image bytes",
              f"{row['canonical_code']}: {len(image['data']) if image else 0} bytes {image['media_type'] if image else ''}")
        if shown >= 3:
            break
    if not shown:
        print(f"     no problem with diagrams among the first {args.problems}; raise --problems to exercise A13")

    check(OPERATIONS <= READS, "only read operations were used", ", ".join(sorted(OPERATIONS)))
    check("scan" not in OPERATIONS, "no scan")
    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
