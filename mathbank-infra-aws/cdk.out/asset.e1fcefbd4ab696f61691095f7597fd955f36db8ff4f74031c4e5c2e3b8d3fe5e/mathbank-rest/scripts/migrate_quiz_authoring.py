"""Inspect or explicitly apply migration 037 to the configured REST database."""
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
    for relation in ("activity.definition", "pedagogy.micro_course_state_activity"):
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
        raise SystemExit("Migration 037 prerequisites are missing: " + ", ".join(missing))

    migration_path = Path(__file__).resolve().parents[2] / "mathbank-db/sql/037_quiz_authoring.sql"
    if args.apply:
        with target.begin() as conn:
            conn.exec_driver_sql(migration_path.read_text(encoding="utf-8"))
        print("Migration 037 applied transactionally.")

    with target.connect() as conn:
        present = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='activity' AND table_name='definition'
                  AND column_name='target_skill_id'
            )
            AND EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema='activity' AND table_name='definition'
                  AND column_name='status'
            )
            AND EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conrelid='pedagogy.micro_course_state_activity'::regclass
                  AND conname='micro_course_state_activity_purpose_check'
            )
        """)).scalar_one()
    print(f"Migration 037 schema present: {present}")
    if not present:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
