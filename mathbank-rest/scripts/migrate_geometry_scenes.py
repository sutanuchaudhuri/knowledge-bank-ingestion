"""Explicitly install geometry storage migration 026; no runtime auto-migration."""
import argparse
from importlib.resources import files

from sqlalchemy import create_engine,text

from mathbank_rest.db.postgres import engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Authorize additive schema migration")
    parser.add_argument("--direct",action="store_true",
                        help="Use the corresponding direct Neon host for migration only")
    args = parser.parse_args()
    target=engine
    if "-pooler" in (engine.url.host or ""):
        if args.apply and not args.direct:
            parser.error("pooled Neon connections are not used for DDL; supply --direct")
        if args.direct:
            if not engine.url.host.endswith(".neon.tech"):
                parser.error("--direct supports only the configured Neon endpoint")
            target=create_engine(engine.url.set(host=engine.url.host.replace("-pooler","")),pool_pre_ping=True)
    if args.apply:
        migration = files("mathbank_rest").joinpath("migrations/026_geometry_scenes.sql").read_text()
        with target.begin() as conn:
            conn.exec_driver_sql(migration)
        print("Geometry migration 026 applied transactionally.")
    with target.connect() as conn:
        present = conn.execute(text(
            "SELECT to_regclass('geometry_scene.versions') IS NOT NULL "
            "AND to_regclass('geometry_scene.receipts') IS NOT NULL "
            "AND to_regclass('geometry_scene.runs') IS NOT NULL"
        )).scalar_one()
    print(f"Geometry storage schema present: {present}")
    if not present:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
