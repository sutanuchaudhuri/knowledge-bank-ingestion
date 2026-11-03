#!/usr/bin/env python3
"""Findings ledger check (requirement 71 §4).

    python scripts/findings_check.py                 # report + validate rows; exit 1 on an invalid row
    python scripts/findings_check.py --wp WP5        # also require every ID routed to WP5 to be DONE/DECLINED
    python scripts/findings_check.py --strict        # merge gate: EVERY ID must be DONE or DECLINED

The ledger is documentation/database/findings_register.csv. Row rules:
  status is one of PLANNED, IN_PROGRESS, DONE, DECLINED
  DONE      needs `pr` (commit/PR reference) and `tests` (test id or file)
  DECLINED  needs a reason in `routing_note` (and ideally the replacement)
"""
from __future__ import annotations

import argparse
import collections
import csv
import sys
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "documentation" / "database" / "findings_register.csv"
STATUSES = ("PLANNED", "IN_PROGRESS", "DONE", "DECLINED")
CLOSED = ("DONE", "DECLINED")


def load(path: Path = LEDGER) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def validate(rows: list[dict]) -> list[str]:
    problems: list[str] = []
    seen: set[str] = set()
    for r in rows:
        i, st = r["id"], r["status"]
        if i in seen:
            problems.append(f"{i}: duplicate id")
        seen.add(i)
        if st not in STATUSES:
            problems.append(f"{i}: status {st!r} not in {STATUSES}")
        elif st == "DONE" and not (r["pr"].strip() and r["tests"].strip()):
            problems.append(f"{i}: DONE needs both `pr` and `tests`")
        elif st == "DECLINED" and not r["routing_note"].strip():
            problems.append(f"{i}: DECLINED needs a reason in `routing_note`")
        if not r["primary_wp"].startswith("WP"):
            problems.append(f"{i}: primary_wp {r['primary_wp']!r} is not a work package")
    return problems


def report(rows: list[dict]) -> dict[str, collections.Counter]:
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r["primary_wp"]][r["status"]] += 1
    print(f"{'WP':5} {'total':>5} " + " ".join(f"{s:>11}" for s in STATUSES))
    for wp in sorted(by, key=lambda w: int(w[2:])):
        c = by[wp]
        print(f"{wp:5} {sum(c.values()):5d} " + " ".join(f"{c[s]:11d}" for s in STATUSES))
    tot = collections.Counter(r["status"] for r in rows)
    print(f"{'all':5} {len(rows):5d} " + " ".join(f"{tot[s]:11d}" for s in STATUSES))
    return by


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--wp", action="append", default=[], help="require this work package to be fully closed")
    ap.add_argument("--strict", action="store_true", help="require every ID to be DONE or DECLINED (merge to main)")
    a = ap.parse_args(argv)
    rows = load(a.ledger)
    problems = validate(rows)
    report(rows)
    if problems:
        print(f"\n{len(problems)} invalid row(s):", file=sys.stderr)
        for p in problems[:50]:
            print("  " + p, file=sys.stderr)
        return 1
    open_rows = [r for r in rows if r["status"] not in CLOSED]
    scope = [r for r in open_rows if a.strict or r["primary_wp"] in a.wp]
    if scope:
        what = "everything" if a.strict else ", ".join(a.wp)
        print(f"\nNOT COMPLETE ({what}): {len(scope)} open id(s), e.g. " + ", ".join(r["id"] for r in scope[:8]), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
