"""Backfill rich display properties (title/description/symptom/etc.) onto existing
Claim/Misconception/TheoryItem/diagnostic-LearningItem nodes, without touching any
relationship or doing a destructive delete-then-recreate (requirements/51 ENR-7).

mathbank_rest.route_projection.project() is the canonical full projector and now also
writes these properties (see _display_properties there) — but running its full
delete-then-recreate cycle against the current ~1M-edge 'tutoring_routes' layer exceeds
this AuraDB instance's per-transaction memory budget (confirmed live:
Neo.TransientError.General.MemoryPoolOutOfMemoryError on the bulk DELETE alone, which
rolled back cleanly with zero data loss). This script is a much smaller, purely additive,
batched SET-only operation — reads pedagogy.route_asset directly and updates only the
four scalar/text properties per node, safe to run on this instance today. The canonical
full projector remains correct for whenever the instance is upgraded or the graph is
pruned; this script is the pragmatic interim backfill, not a replacement for it.
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_from_postgres import _load_env, chunks, graph_target, pg_conninfo  # noqa: E402

LABELS = {
    "CLAIM": "Claim",
    "MISCONCEPTION": "Misconception",
    "THEORY": "TheoryItem",
    "LEARNING_ITEM": "LearningItem",
}
BATCH_SIZE = 500


def display_properties(kind: str, content: dict) -> dict:
    if kind == "LEARNING_ITEM":
        return {"title": content.get("title"), "question": content.get("question"),
                "expected_answer": content.get("expected_answer")}
    if kind == "CLAIM":
        return {"title": content.get("title"), "description": content.get("description"),
                "canonical_expression": content.get("canonical_expression")}
    if kind == "MISCONCEPTION":
        return {"title": content.get("title"), "description": content.get("description"),
                "symptom": content.get("symptom"), "why_wrong": content.get("why_wrong"),
                "correct_model": content.get("correct_model")}
    return {"title": content.get("title"), "description": content.get("description")}


def main() -> None:
    env = _load_env()
    target = graph_target(env)
    updated_by_label: dict[str, int] = {}
    try:
        with psycopg.connect(pg_conninfo(env)) as pg_conn, pg_conn.cursor() as cur:
            cur.execute("SELECT asset_id, content FROM pedagogy.route_asset")
            rows = [
                {"id": str(asset_id), "kind": content["kind"],
                 "properties": display_properties(content["kind"], content)}
                for asset_id, content in cur.fetchall()
            ]
        rows_by_kind: dict[str, list[dict]] = {}
        for row in rows:
            rows_by_kind.setdefault(row.pop("kind"), []).append(row)

        with target.session() as session:
            for kind, kind_rows in rows_by_kind.items():
                label = LABELS[kind]
                for batch in chunks(kind_rows, BATCH_SIZE):
                    session.run(
                        f"""
                        UNWIND $rows AS row
                        MATCH (n:{label} {{canonical_id: row.id}})
                        SET n += row.properties
                        """,
                        rows=batch,
                    ).consume()
                updated_by_label[label] = updated_by_label.get(label, 0) + len(kind_rows)
    finally:
        target.close()
    for label, count in updated_by_label.items():
        print(f"{label}: {count} nodes updated")


if __name__ == "__main__":
    main()
