"""Apply only migration 025 to the database explicitly configured for REST."""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import text

from mathbank_rest.db.postgres import engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Explicitly authorize this schema migration.")
    args = parser.parse_args()
    if args.apply:
        migration = Path(__file__).resolve().parents[2] / "mathbank-db/sql/025_corpus_authoring.sql"
        with engine.begin() as conn:
            conn.exec_driver_sql(migration.read_text())
        print("Migration 025 applied transactionally to the configured REST database.")
    with engine.connect() as conn:
        present = conn.execute(text("SELECT to_regclass('ingest.corpus_draft') IS NOT NULL")).scalar_one()
    print(f"Corpus authoring schema present: {present}")
    if not present:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
