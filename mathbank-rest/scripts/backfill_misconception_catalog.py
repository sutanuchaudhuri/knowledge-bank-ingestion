"""ENR-1 Phase A (requirements/51): deduplicate pedagogy.route_asset's MISCONCEPTION rows
by exact `description` text into real knowledge.misconception catalog rows, and link each
canonical misconception to every taxonomy_node_id any of its duplicate instances recorded.

Confirmed live before writing this script: 80,242 MISCONCEPTION rows, ~70,018 distinct
description values (12.7 percent exact-duplicate rows -- a free, zero-risk merge). This is
Phase A only (exact-text dedup); Phase B (embedding-based near-duplicate clustering) needs
ENR-2's pgvector infrastructure and is a separate, later script.

The per-checkpoint route_asset rows are left completely untouched (confirmed live:
pedagogy.guard_route_snapshot() blocks ANY write to a route_asset row once its release
leaves DRAFT status, and virtually all existing rows already have) -- the asset-to-canonical
link lives in the separate, purely additive knowledge.route_asset_misconception_link table
instead (migration 039).

Performance note (learned the hard way): one-row-at-a-time INSERTs over the network to Neon
took ~4 minutes per 1,000 groups (projected 4+ hours for the full 70,018 groups). Rewritten
to compute each misconception_id deterministically client-side (uuid5 of its canonical_code
-- no RETURNING round trip needed) and batch every INSERT as one multi-row VALUES statement
per table per batch, cutting network round trips by roughly three orders of magnitude.

Idempotent: re-running with the same source data produces the same canonical_code -> the
same uuid5 id -> ON CONFLICT DO NOTHING everywhere; existing rows are never duplicated or
altered.
"""
from __future__ import annotations

import argparse
import hashlib
import uuid
from collections import defaultdict

from sqlalchemy import text

from mathbank_rest.db.postgres import engine

_NAMESPACE = uuid.UUID("c6f8b1d2-3a4e-4b8a-9f2c-7e1d5a6b8c9d")  # fixed, arbitrary, stable


def _canonical_code(description: str) -> str:
    digest = hashlib.sha256(description.encode("utf-8")).hexdigest()[:16]
    return f"MIS-AUTO-{digest}"


def _deterministic_id(canonical_code: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, canonical_code)


def _short_name(description: str, max_len: int = 120) -> str:
    flat = " ".join(description.split())
    return flat if len(flat) <= max_len else flat[: max_len - 1].rstrip() + "…"


def _bulk_insert(conn, insert_clause: str, conflict_clause: str, rows: list[dict]) -> None:
    """One multi-row `INSERT ... VALUES (:a_0,:b_0), (:a_1,:b_1), ...` statement for `rows`
    (each a flat param dict with globally-unique keys already assigned by the caller) --
    avoids a network round trip per row, which is what made the first version of this
    script impractically slow (confirmed live: ~4 min/1000 groups one-row-at-a-time)."""
    if not rows:
        return
    placeholders = ", ".join("(" + ", ".join(f":{key}" for key in row) + ")" for row in rows)
    params = {key: value for row in rows for key, value in row.items()}
    conn.execute(text(f"{insert_clause} VALUES {placeholders} {conflict_clause}"), params)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes; default is dry-run.")
    parser.add_argument("--batch-size", type=int, default=2000, help="Groups committed per transaction.")
    parser.add_argument("--limit-groups", type=int, default=None,
                         help="Only process the first N groups (for a small safe test run).")
    args = parser.parse_args()

    with engine.connect() as conn:
        asset_rows_db = conn.execute(text("""
            SELECT asset_id, content
            FROM pedagogy.route_asset
            WHERE content->>'kind' = 'MISCONCEPTION'
        """)).mappings().all()

    groups: dict[str, list[dict]] = defaultdict(list)
    for row in asset_rows_db:
        content = row["content"]
        description = (content.get("description") or "").strip()
        if not description:
            continue
        groups[description].append({"asset_id": row["asset_id"], "content": content})

    print(f"Total MISCONCEPTION rows: {len(asset_rows_db)}")
    print(f"Distinct non-blank descriptions (canonical groups): {len(groups)}")
    duplicate_groups = sum(1 for members in groups.values() if len(members) > 1)
    print(f"Groups with more than one duplicate row: {duplicate_groups}")

    if not args.apply:
        print("Dry run only -- pass --apply to write. No changes made.")
        return

    group_items = list(groups.items())
    if args.limit_groups:
        group_items = group_items[: args.limit_groups]
        print(f"--limit-groups set: processing only {len(group_items)} groups")

    misconceptions_written = 0
    taxonomy_links_written = 0
    asset_links_written = 0
    for batch_start in range(0, len(group_items), args.batch_size):
        batch = group_items[batch_start:batch_start + args.batch_size]

        misconception_rows: list[dict] = []
        taxonomy_rows: list[dict] = []
        asset_link_rows: list[dict] = []
        for i, (description, members) in enumerate(batch):
            code = _canonical_code(description)
            mid = str(_deterministic_id(code))
            representative = members[0]["content"]
            misconception_rows.append({
                f"mid_{i}": mid, f"code_{i}": code, f"name_{i}": _short_name(description),
                f"desc_{i}": description,
                f"symptom_{i}": representative.get("symptom") or None,
                f"why_{i}": representative.get("why_wrong") or None,
                f"model_{i}": representative.get("correct_model") or None,
                f"src_{i}": "route_enrichment:dedup-exact-text-v1",
                f"rs_{i}": "APPROVED",
                f"am_{i}": "automatic",
            })
            taxonomy_ids = sorted({
                taxonomy_id
                for member in members
                for taxonomy_id in (member["content"].get("taxonomy_node_ids") or [])
            })
            for j, taxonomy_id in enumerate(taxonomy_ids):
                taxonomy_rows.append({
                    f"tmid_{i}_{j}": mid, f"tid_{i}_{j}": taxonomy_id,
                    f"dv_{i}_{j}": "route_asset.taxonomy_node_ids",
                })
            for k, member in enumerate(members):
                asset_link_rows.append({f"aid_{i}_{k}": str(member["asset_id"]), f"amid_{i}_{k}": mid})

        with engine.begin() as conn:
            _bulk_insert(
                conn,
                "INSERT INTO knowledge.misconception "
                "(misconception_id, canonical_code, name, description, symptom, why_wrong, "
                " correct_model, source, review_status, approval_method)",
                "ON CONFLICT (canonical_code) DO NOTHING",
                misconception_rows,
            )
            misconceptions_written += len(misconception_rows)

            _bulk_insert(
                conn,
                "INSERT INTO knowledge.misconception_taxonomy_link "
                "(misconception_id, taxonomy_node_id, derived_via)",
                "ON CONFLICT (misconception_id, taxonomy_node_id) DO NOTHING",
                taxonomy_rows,
            )
            taxonomy_links_written += len(taxonomy_rows)

            _bulk_insert(
                conn,
                "INSERT INTO knowledge.route_asset_misconception_link (asset_id, misconception_id)",
                "ON CONFLICT (asset_id) DO NOTHING",
                asset_link_rows,
            )
            asset_links_written += len(asset_link_rows)

        print(f"  batch {batch_start}-{batch_start + len(batch)}/{len(group_items)} committed "
              f"(misconceptions: {misconceptions_written}, taxonomy links: {taxonomy_links_written}, "
              f"asset links: {asset_links_written})")

    print(f"Done. Misconceptions upserted: {misconceptions_written}; "
          f"taxonomy links: {taxonomy_links_written}; asset links: {asset_links_written}")


if __name__ == "__main__":
    main()
