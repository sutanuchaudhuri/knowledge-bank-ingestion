"""Inspect or explicitly apply migration 038 to the configured REST database."""
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


def missing_prerequisites(conn) -> list[str]:
    missing = []
    for relation in (
        "pedagogy.micro_course_state_asset", "pedagogy.micro_course_state_interaction",
        "pedagogy.micro_course_state_learning_item", "pedagogy.micro_course_state_activity",
    ):
        if not conn.execute(text("SELECT to_regclass(:name) IS NOT NULL"), {"name": relation}).scalar_one():
            missing.append(relation)
    return missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the additive migration.")
    parser.add_argument("--direct", action="store_true", help="Use the direct Neon host for DDL.")
    args = parser.parse_args()
    try:
        target = migration_target(args.direct, args.apply)
    except ValueError as exc:
        parser.error(str(exc))

    with target.connect() as conn:
        missing = missing_prerequisites(conn)
    if missing:
        raise SystemExit("Migration 038 prerequisites are missing: " + ", ".join(missing))

    migration_path = Path(__file__).resolve().parents[2] / "mathbank-db/sql/038_micro_course_item_sequence.sql"
    if args.apply:
        with target.begin() as conn:
            conn.exec_driver_sql(migration_path.read_text(encoding="utf-8"))
        print("Migration 038 applied transactionally.")

    with target.connect() as conn:
        present = conn.execute(text("""
            SELECT bool_and(has_col) FROM (
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema='pedagogy' AND table_name=t AND column_name='sequence_position'
                ) AS has_col
                FROM unnest(ARRAY[
                    'micro_course_state_asset', 'micro_course_state_interaction',
                    'micro_course_state_learning_item', 'micro_course_state_activity'
                ]) AS t
            ) checks
        """)).scalar_one()
    print(f"Migration 038 schema present: {present}")
    if not present:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
