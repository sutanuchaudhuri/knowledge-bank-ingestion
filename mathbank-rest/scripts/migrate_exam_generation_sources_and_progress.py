"""Inspect or explicitly apply migration 050 (exam-agent question sources + generation
progress log) to the configured REST database."""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text

from mathbank_rest.db.postgres import engine


def migration_target(direct: bool, apply: bool):
    if "-pooler" not in (engine.url.host or ""):
        return engine
    if apply and not direct:
        raise ValueError("pooled Neon connections are not used for DDL; supply --direct")
    if not direct:
        return engine
    if not engine.url.host.endswith(".neon.tech"):
        raise ValueError("--direct supports only the configured Neon endpoint")
    return create_engine(
        engine.url.set(host=engine.url.host.replace("-pooler", "")),
        pool_pre_ping=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the additive migration.")
    parser.add_argument("--direct", action="store_true", help="Use the direct Neon host for DDL.")
    args = parser.parse_args()
    try:
        target = migration_target(args.direct, args.apply)
    except ValueError as exc:
        parser.error(str(exc))

    migration_path = (
        Path(__file__).resolve().parents[2]
        / "mathbank-db/sql/050_exam_generation_sources_and_progress.sql"
    )
    if args.apply:
        with target.begin() as conn:
            conn.exec_driver_sql(migration_path.read_text(encoding="utf-8"))
        print("Applied migration 050_exam_generation_sources_and_progress.sql")

    with target.connect() as conn:
        for schema, table in (
            ("quiz", "question_source"),
            ("quiz", "generation_event"),
        ):
            exists = conn.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"),
                {"name": f"{schema}.{table}"},
            ).scalar()
            print(f"{schema}.{table}: {'EXISTS' if exists else 'MISSING'}")
        for schema, table, column in (
            ("quiz", "solution", "solution_steps"),
            ("quiz", "solution", "step_count"),
            ("quiz", "question", "complexity_signals"),
        ):
            exists = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                     "WHERE table_schema=:s AND table_name=:t AND column_name=:c)"),
                {"s": schema, "t": table, "c": column},
            ).scalar()
            print(f"{schema}.{table}.{column}: {'EXISTS' if exists else 'MISSING'}")


if __name__ == "__main__":
    main()
