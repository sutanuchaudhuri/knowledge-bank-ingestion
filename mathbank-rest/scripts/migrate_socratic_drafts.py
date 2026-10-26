"""Inspect or explicitly apply additive Socratic migrations 053 (drafts) and 054 (previews)."""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text

from mathbank_rest.db.postgres import engine


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--direct", action="store_true", help="Use configured Neon direct endpoint for DDL.")
    args = parser.parse_args()
    target = engine
    host = engine.url.host or ""
    if "-pooler" in host:
        if args.apply and not args.direct:
            parser.error("DDL requires --direct for the configured pooled Neon target.")
        if args.direct:
            if not host.endswith(".neon.tech"):
                parser.error("--direct supports only the configured Neon target.")
            target = create_engine(engine.url.set(host=host.replace("-pooler", "")),
                                   pool_pre_ping=True)
    sql = Path(__file__).resolve().parents[2] / "mathbank-db/sql"
    if args.apply:
        for number, name in (("053", "053_socratic_drafts.sql"), ("054", "054_socratic_previews.sql")):
            with target.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text("SET LOCAL statement_timeout = '60s'"))
                conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:scope,0))"),
                             {"scope": f"socratic-migration-{number}"})
                conn.exec_driver_sql((sql / name).read_text())
            print(f"Applied additive migration {number}; no canonical or learner row writes.")
    with target.connect() as conn:
        for name in ("socratic_strategy", "socratic_workflow", "socratic_revision", "socratic_command",
                     "socratic_preview", "socratic_preview_event"):
            present = conn.execute(text("SELECT to_regclass(:name) IS NOT NULL"),
                                   {"name": "orchestration." + name}).scalar_one()
            print(f"orchestration.{name}: {'EXISTS' if present else 'MISSING'}")


if __name__ == "__main__":
    main()
