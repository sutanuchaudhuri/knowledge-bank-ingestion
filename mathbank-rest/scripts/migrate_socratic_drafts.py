"""Inspect or explicitly apply additive Socratic draft migration 053."""
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
    path = Path(__file__).resolve().parents[2] / "mathbank-db/sql/053_socratic_drafts.sql"
    if args.apply:
        with target.begin() as conn:
            conn.execute(text("SET LOCAL lock_timeout = '5s'"))
            conn.execute(text("SET LOCAL statement_timeout = '60s'"))
            conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('socratic-migration-053',0))"))
            conn.exec_driver_sql(path.read_text())
        print("Applied additive migration 053; no canonical or learner row writes.")
    with target.connect() as conn:
        for name in ("socratic_strategy", "socratic_workflow", "socratic_revision", "socratic_command"):
            present = conn.execute(text("SELECT to_regclass(:name) IS NOT NULL"),
                                   {"name": "orchestration." + name}).scalar_one()
            print(f"orchestration.{name}: {'EXISTS' if present else 'MISSING'}")


if __name__ == "__main__":
    main()
