"""
Bootstrap Firestore collections with schema sentinel documents.

Run via:  make setup-firestore PROJECT=mathbank-dev
Or via:   mathbank setup-firestore --project mathbank-dev

Composite indexes are declared in firestore.indexes.json and deployed with:
  make deploy-indexes PROJECT=mathbank-dev
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from google.cloud import firestore  # type: ignore
from rich.console import Console

console = Console()

SCHEMA_VERSION = "1.0.0"

COLLECTIONS: dict[str, dict] = {
    "courses": {
        "course_id": "", "display_name": "", "description": "",
        "level": "", "competition_ids": [], "created_at": "",
    },
    "competitions": {
        "competition_id": "", "course_ids": [], "display_name": "",
        "organizer": "", "competition_type": "", "level": "",
    },
    "papers": {
        "paper_id": "", "course_id": "", "test_id": "", "competition_id": "",
        "year": 0, "form_or_round": "", "session": "", "expected_questions": 0,
        "problem_url": "", "solution_url": "", "status": "raw",
        "source_tab": "", "source_row": 0,
    },
    "questions": {
        "question_id": "", "course_id": "", "paper_id": "", "competition_id": "",
        "year": 0, "q_number": 0, "primary_topic": "", "subtopic": "",
        "primary_concept_id": "", "concept_ids": [], "technique_ids": [],
        "difficulty_band": "", "correct_answer": "", "confidence": "",
        "evidence_locator": "", "notes": "", "visual_role": "none", "visual_asset_ids": [],
    },
    "concepts": {
        "canonical_topic_id": "", "course_ids": [], "domain": "",
        "topic": "", "subtopic": "", "node_type": "", "canonical_path": "",
    },
    "techniques": {
        "technique_id": "", "course_ids": [], "technique_name": "", "parent_concept_id": "",
    },
    "documents": {
        "doc_id": "", "course_id": "", "entity_type": "", "entity_id": "",
        "chunk_index": 0, "char_count": 0, "content_hash": "", "created_at": "",
    },
    "chunks": {
        "chunk_id": "", "course_id": "", "doc_id": "", "question_id": "",
        "competition_id": "", "primary_topic": "", "difficulty_band": "",
        "chunk_type": "", "token_count": 0, "embedding_model": "",
        "content_hash": "", "created_at": "",
    },
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def seed_collection(db: firestore.Client, name: str, schema: dict, dry_run: bool) -> None:
    doc = {"_type": "_schema", "collection": name, "schema_version": SCHEMA_VERSION,
           "created_at": _now_iso(), **schema}
    if dry_run:
        console.print(f"  [yellow][dry-run] would write {name}/_schema")
        return
    db.collection(name).document("_schema").set(doc, merge=True)
    console.print(f"  [green]wrote {name}/_schema")


def write_config(db: firestore.Client, dry_run: bool) -> None:
    config = {"schema_version": SCHEMA_VERSION, "collections": list(COLLECTIONS),
               "updated_at": _now_iso()}
    if dry_run:
        console.print("  [yellow][dry-run] would write __config__/corpus")
        return
    db.collection("__config__").document("corpus").set(config, merge=True)
    console.print("  [green]wrote __config__/corpus")


def run_setup(args: argparse.Namespace) -> None:
    console.rule(f"[bold]Firestore bootstrap — project={args.project}")
    db = firestore.Client(project=args.project, database=args.database)

    console.print("\n[bold]Seeding collection schema sentinels:")
    for name, schema in COLLECTIONS.items():
        seed_collection(db, name, schema, args.dry_run)

    console.print("\n[bold]Writing runtime config:")
    write_config(db, args.dry_run)

    console.print(f"\n[bold green]Done.[/] Deploy composite indexes with:")
    console.print(f"  make deploy-indexes PROJECT={args.project}")
