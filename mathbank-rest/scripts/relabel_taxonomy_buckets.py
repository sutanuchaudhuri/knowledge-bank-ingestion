"""ENR-8 item 1 (requirements/51): regenerate misleading labels on fixed-code curriculum
"bucket" taxonomy nodes.

Confirmed live: 127 of pedagogy.taxonomy_node's 897 fixed-code rows (matching
`[A-Z]+\\.C\\d+\\.[A-Z_]+`, e.g. GEO.C04.AREA) are each referenced by >=10
solution_step_requirement rows -- real, intentional curriculum-category concentration, not
a bug (see requirements/51 Section 3.1). But the node's own `name`/`description` is whichever
specific instance happened to populate it FIRST (e.g. GEO.C04.AREA is named "Calculating Area
of Triangle BPC" despite being used 2,342 times as a general area-calculation bucket), which
reads as misleadingly narrow.

This does NOT invent a "better" category name (the domain-prefix scheme is too ad hoc --
confirmed live: 70+ distinct, inconsistent prefixes -- to decode reliably). Instead it
appends a purely factual, auditable suffix: the real usage count and, where more than one
distinct non-blank proposed_name was ever recorded against this code, a short list of them --
so a reader sees "this is a recurring category," not an isolated specific instance, without
this script asserting any new semantic claim it cannot support.

Idempotent: matches and strips any previously-appended suffix of this script's own format
before reapplying, so re-running with updated usage counts does not grow the string forever.
"""
from __future__ import annotations

import argparse
import re

from sqlalchemy import text

from mathbank_rest.db.postgres import engine

_SUFFIX_RE = re.compile(r"\s*\(recurring category, [\d,]+ uses.*?\)\s*$")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run.")
    parser.add_argument("--min-usage", type=int, default=10, help="Usage-count threshold to treat as a bucket.")
    args = parser.parse_args()

    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT tn.taxonomy_node_id, tn.name,
                   count(req.*) AS usage_count,
                   array_agg(DISTINCT req.proposed_name) FILTER (WHERE req.proposed_name != '') AS proposals
            FROM pedagogy.taxonomy_node tn
            JOIN pedagogy.solution_step_requirement req ON req.taxonomy_node_id = tn.taxonomy_node_id
            WHERE tn.taxonomy_node_id ~ '^[A-Z]+\\.C\\d+\\.[A-Z_]+$'
            GROUP BY tn.taxonomy_node_id, tn.name
            HAVING count(req.*) >= :min_usage
            ORDER BY usage_count DESC
        """), {"min_usage": args.min_usage}).mappings().all()

    print(f"Fixed-code bucket nodes with >= {args.min_usage} uses: {len(rows)}")

    updates = []
    for row in rows:
        base_name = _SUFFIX_RE.sub("", row["name"]).strip()
        proposals = sorted(row["proposals"] or [])
        detail = f"includes: {', '.join(proposals)}" if len(proposals) > 1 else None
        count_str = f"{row['usage_count']:,}"
        suffix = f" (recurring category, {count_str} uses" + (f"; {detail})" if detail else ")")
        new_name = base_name + suffix
        if new_name != row["name"]:
            updates.append({"id": row["taxonomy_node_id"], "name": new_name})

    print(f"Nodes whose label actually changes: {len(updates)}")
    for u in updates[:5]:
        print(f"  {u['id']}: {u['name']}")

    if not args.apply:
        print("Dry run only -- pass --apply to write. No changes made.")
        return

    with engine.begin() as conn:
        for u in updates:
            conn.execute(text("""
                UPDATE pedagogy.taxonomy_node SET name = :name WHERE taxonomy_node_id = :id
            """), u)
    print(f"Updated {len(updates)} taxonomy_node labels.")


if __name__ == "__main__":
    main()
