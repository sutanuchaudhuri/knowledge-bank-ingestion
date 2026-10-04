"""
Bridge OpenAI classification results (scripts/classify_crawled.py, written to
the local SQLite mathbank.db) into the CSV corpus mirror that
mathbank-db/etl/load_corpus.py actually reads — so new concepts/techniques
and problem->concept/technique mappings flow into Postgres (and from there,
the Neo4j graph projection).

Without this bridge, classify_crawled.py's output lives only in SQLite and
is invisible to Postgres/Neo4j.

Routing (by concepts.node_type on the classified concept):
  node_type != 'Technique'  -> topic_taxonomy.csv + question_taxonomy_map.csv
  node_type == 'Technique'  -> technique_catalog.csv + question_technique_map.csv

Idempotent: every write is an append, skipping rows whose primary key already
exists in the target CSV (by Concept_ID / Technique_ID / Mapping_ID), so this
is safe to re-run as classification continues in batches. A duplicate-key
audit runs both before (reports pre-existing corpus issues, doesn't block)
and after (hard-fails if THIS run introduced a duplicate) each write.

Usage:
    python scripts/export_classifications_to_csv.py              # real run
    python scripts/export_classifications_to_csv.py --dry-run     # report only
"""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mathbank.db import DB_PATH  # noqa: E402
from mathbank.db.tracking import IngestionRun  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

console = Console()

CORPUS_DIR = ROOT / "src" / "mathbank" / "data" / "maths_corpus"
TOPIC_TAXONOMY_CSV = CORPUS_DIR / "topic_taxonomy.csv"
CANONICAL_HIERARCHY_CSV = CORPUS_DIR / "canonical_topic_hierarchy.csv"
TECHNIQUE_CATALOG_CSV = CORPUS_DIR / "technique_catalog.csv"
QUESTION_TAXONOMY_MAP_CSV = CORPUS_DIR / "question_taxonomy_map.csv"
QUESTION_TECHNIQUE_MAP_CSV = CORPUS_DIR / "question_technique_map.csv"


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames or [], list(reader)


def _find_duplicate_keys(path: Path, key_column: str, normalize: bool = False) -> list[str]:
    """Returns any key values that appear more than once in `path`'s `key_column`
    (blank keys are ignored — some CSVs have optional/legacy rows without one)."""
    _, rows = _read_csv_rows(path)
    counts: dict[str, int] = {}
    for row in rows:
        key = row.get(key_column, "")
        if not key:
            continue
        key = _slugify(key) if normalize else key
        counts[key] = counts.get(key, 0) + 1
    return [k for k, n in counts.items() if n > 1]


def _check_for_duplicates() -> dict[str, list[str]]:
    """Pre/post-flight duplicate-key audit across all four target CSVs — run
    both before writing (catches pre-existing corpus issues) and after
    (catches anything this script itself introduced)."""
    return {
        "topic_taxonomy.csv (Concept_ID)": _find_duplicate_keys(TOPIC_TAXONOMY_CSV, "Concept_ID", normalize=True),
        "technique_catalog.csv (Technique_ID)": _find_duplicate_keys(
            TECHNIQUE_CATALOG_CSV, "Technique_ID", normalize=True
        ),
        "question_taxonomy_map.csv (Mapping_ID)": _find_duplicate_keys(QUESTION_TAXONOMY_MAP_CSV, "Mapping_ID"),
        "question_technique_map.csv (Technique_Map_ID)": _find_duplicate_keys(
            QUESTION_TECHNIQUE_MAP_CSV, "Technique_Map_ID"
        ),
    }


def _append_rows(path: Path, fieldnames: list[str], new_rows: list[dict], dry_run: bool) -> None:
    if not new_rows:
        return
    if dry_run:
        return
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        for row in new_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def export_concepts_and_techniques(conn: sqlite3.Connection, dry_run: bool) -> dict[str, int]:
    taxonomy_fields, taxonomy_rows = _read_csv_rows(TOPIC_TAXONOMY_CSV)
    hierarchy_fields, hierarchy_rows = _read_csv_rows(CANONICAL_HIERARCHY_CSV)
    technique_fields, technique_rows = _read_csv_rows(TECHNIQUE_CATALOG_CSV)

    known_concept_slugs = {_slugify(r.get("Concept_ID", "")) for r in taxonomy_rows} | {
        _slugify(r.get("Canonical_Topic_ID", "")) for r in hierarchy_rows
    }
    known_technique_slugs = {_slugify(r.get("Technique_ID", "")) for r in technique_rows}

    new_concept_rows: list[dict] = []
    new_technique_rows: list[dict] = []

    conn.row_factory = sqlite3.Row
    for r in conn.execute("SELECT * FROM concepts"):
        slug = _slugify(r["canonical_topic_id"])
        if r["node_type"] == "Technique":
            if slug in known_technique_slugs:
                continue
            known_technique_slugs.add(slug)
            new_technique_rows.append(
                {
                    "Technique_ID": r["canonical_topic_id"],
                    "Parent_Concept_ID": "",
                    "Technique_Name": r["concept_or_technique"],
                    "Canonical_Path": r["canonical_path"],
                    "Definition": r["definition"],
                    "Notes": "Added by export_classifications_to_csv.py from OpenAI classification",
                }
            )
        else:
            if slug in known_concept_slugs:
                continue
            known_concept_slugs.add(slug)
            new_concept_rows.append(
                {
                    "Concept_ID": r["canonical_topic_id"],
                    "Domain": r["domain"],
                    "Concept": r["concept_or_technique"],
                    "Concept_Type": r["node_type"] or "Mathematical Concept",
                    "Evidence_Basis": r["definition"],
                    "Agent_Search_Terms": "",
                }
            )

    _append_rows(TOPIC_TAXONOMY_CSV, taxonomy_fields, new_concept_rows, dry_run)
    _append_rows(TECHNIQUE_CATALOG_CSV, technique_fields, new_technique_rows, dry_run)
    return {"new_concepts": len(new_concept_rows), "new_techniques": len(new_technique_rows)}


def export_problem_mappings(conn: sqlite3.Connection, dry_run: bool) -> dict[str, int]:
    concept_node_type = {r["canonical_topic_id"]: r["node_type"] for r in conn.execute("SELECT * FROM concepts")}

    concept_map_fields, concept_map_rows = _read_csv_rows(QUESTION_TAXONOMY_MAP_CSV)
    technique_map_fields, technique_map_rows = _read_csv_rows(QUESTION_TECHNIQUE_MAP_CSV)
    known_mapping_ids = {r.get("Mapping_ID", "") for r in concept_map_rows}
    known_technique_map_ids = {r.get("Technique_Map_ID", "") for r in technique_map_rows}

    new_concept_map_rows: list[dict] = []
    new_technique_map_rows: list[dict] = []

    for r in conn.execute("SELECT * FROM question_taxonomy_maps"):
        node_type = concept_node_type.get(r["concept_id"])
        if node_type == "Technique":
            if r["mapping_id"] in known_technique_map_ids:
                continue
            known_technique_map_ids.add(r["mapping_id"])
            new_technique_map_rows.append(
                {
                    "Technique_Map_ID": r["mapping_id"],
                    "Question_ID": r["question_id"],
                    "Parent_Concept_ID": "",
                    "Technique_ID": r["concept_id"],
                    "Technique_Name": "",
                    "Role": r["association_type"] or "Required",
                    "Evidence_Source": r["evidence_source"],
                    "Evidence_Confidence": r["confidence"],
                    "Evidence_Snippet_or_Reason": r["notes"],
                    "Classification_Status": "AGENT_INFERRED",
                    "Canonical_Paper_ID": r["canonical_paper_id"] or "",
                }
            )
        else:
            if r["mapping_id"] in known_mapping_ids:
                continue
            known_mapping_ids.add(r["mapping_id"])
            new_concept_map_rows.append(
                {
                    "Mapping_ID": r["mapping_id"],
                    "Question_ID": r["question_id"],
                    "Test_ID": r["test_id"],
                    "Exam_Level": r["exam_level"],
                    "Concept_ID": r["concept_id"],
                    "Association_Type": r["association_type"],
                    "Evidence_Source": r["evidence_source"],
                    "Confidence": r["confidence"],
                    "Notes": r["notes"],
                    "Canonical_Paper_ID": r["canonical_paper_id"] or "",
                }
            )

    _append_rows(QUESTION_TAXONOMY_MAP_CSV, concept_map_fields, new_concept_map_rows, dry_run)
    _append_rows(QUESTION_TECHNIQUE_MAP_CSV, technique_map_fields, new_technique_map_rows, dry_run)
    return {"new_concept_maps": len(new_concept_map_rows), "new_technique_maps": len(new_technique_map_rows)}


def main() -> None:
    p = argparse.ArgumentParser(description="Export SQLite classification results into the CSV corpus mirror")
    p.add_argument("--dry-run", action="store_true", help="Report counts only, write nothing")
    args = p.parse_args()

    conn = sqlite3.connect(DB_PATH)
    run = IngestionRun(conn, "export_classifications_to_csv", params={"dry_run": args.dry_run})
    run.__enter__()

    pre_existing_dupes = {k: v for k, v in _check_for_duplicates().items() if v}
    if pre_existing_dupes:
        console.print("[bold red]Pre-existing duplicate keys found (not caused by this run):[/]")
        for csv_name, keys in pre_existing_dupes.items():
            console.print(f"  {csv_name}: {keys[:10]}{' ...' if len(keys) > 10 else ''}")

    concept_counts = export_concepts_and_techniques(conn, args.dry_run)
    mapping_counts = export_problem_mappings(conn, args.dry_run)

    table = Table(title=f"Export {'(dry run)' if args.dry_run else ''}".strip())
    table.add_column("Target CSV")
    table.add_column("New rows", justify="right")
    table.add_row("topic_taxonomy.csv", str(concept_counts["new_concepts"]))
    table.add_row("technique_catalog.csv", str(concept_counts["new_techniques"]))
    table.add_row("question_taxonomy_map.csv", str(mapping_counts["new_concept_maps"]))
    table.add_row("question_technique_map.csv", str(mapping_counts["new_technique_maps"]))
    console.print(table)

    new_rows = (
        concept_counts["new_concepts"] + concept_counts["new_techniques"]
        + mapping_counts["new_concept_maps"] + mapping_counts["new_technique_maps"]
    )
    run.update(processed=new_rows, succeeded=new_rows)

    if args.dry_run:
        run.__exit__(None, None, None)
        conn.close()
        return

    post_dupes = {k: v for k, v in _check_for_duplicates().items() if v}
    new_dupes = {
        csv_name: [k for k in keys if k not in pre_existing_dupes.get(csv_name, [])]
        for csv_name, keys in post_dupes.items()
    }
    new_dupes = {k: v for k, v in new_dupes.items() if v}
    if new_dupes:
        console.print("[bold red]This run introduced duplicate keys:[/]")
        for csv_name, keys in new_dupes.items():
            console.print(f"  {csv_name}: {keys}")
        run.update(failed=sum(len(v) for v in new_dupes.values()))
        run.__exit__(SystemExit, SystemExit("duplicate keys introduced"), None)
        conn.close()
        raise SystemExit(1)
    console.print("[green]Post-export duplicate check: clean (no new duplicate keys introduced).[/]")
    run.__exit__(None, None, None)
    conn.close()


if __name__ == "__main__":
    main()
