"""Inspect or explicitly apply migration 043 (notification schema) to the configured
REST database. Mirrors scripts/migrate_micro_course_item_sequence.py's pattern.

STATUS: scaffolded. NOT RUN against any database in this pass (requirements/59 NOTIF-6) —
this script exists so applying the migration later is a one-command action, not a reason
to hand-write SQL at that point.
"""
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

    migration_path = Path(__file__).resolve().parents[2] / "mathbank-db/sql/043_notifications.sql"
    if args.apply:
        with target.begin() as conn:
            conn.exec_driver_sql(migration_path.read_text(encoding="utf-8"))
        print("Migration 043 applied transactionally.")

    with target.connect() as conn:
        present = conn.execute(
            text("SELECT to_regclass('notification.event') IS NOT NULL")
        ).scalar_one()
    print(f"Migration 043 schema present: {present}")
    if not present:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
