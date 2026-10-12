"""Postgres connectivity via SQLAlchemy (psycopg3 driver)."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from mathbank_rest.config import settings

# pool_pre_ping avoids handing out dead connections after the dev server restarts.
engine = create_engine(settings.postgres_dsn, pool_pre_ping=True, future=True)


def check_postgres() -> dict:
    """Run a trivial query and report connectivity + server version."""
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SHOW server_version")).scalar_one()
            db = conn.execute(text("SELECT current_database()")).scalar_one()
        return {"ok": True, "server_version": version, "database": db}
    except Exception as exc:  # noqa: BLE001 - surfaced to the health endpoint, not swallowed
        return {"ok": False, "error": str(exc)}
