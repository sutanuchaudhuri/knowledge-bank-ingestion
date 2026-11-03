"""Postgres connectivity via SQLAlchemy (psycopg3 driver)."""
from __future__ import annotations

from sqlalchemy import create_engine, text

from mathbank_rest.config import settings



class RuntimeProfileHasNoPostgres:
    """Stands in for the engine in the runtime profile (requirement 71 §2.1): any use fails loudly, so a code
    path that still reaches PostgreSQL is found by a test or a 500, never by silently connecting."""

    def _fail(self, *_a, **_k):
        raise RuntimeError(
            "PostgreSQL is not available in the runtime profile (MB_APP_PROFILE=runtime): "
            "this code path must use a store (mathbank_rest.stores) instead of SQL"
        )

    connect = begin = execute = dispose = raw_connection = _fail

    def __getattr__(self, name: str):
        return self._fail


# pool_pre_ping avoids handing out dead connections after the dev server restarts.
engine = (
    RuntimeProfileHasNoPostgres()
    if settings.app_profile == "runtime"
    else create_engine(settings.postgres_dsn, pool_pre_ping=True, future=True)
)


def check_postgres() -> dict:
    """Run a trivial query and report connectivity + server version."""
    if settings.app_profile == "runtime":
        return {"ok": False, "error": "disabled in the runtime profile"}
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SHOW server_version")).scalar_one()
            db = conn.execute(text("SELECT current_database()")).scalar_one()
        return {"ok": True, "server_version": version, "database": db}
    except Exception as exc:  # noqa: BLE001 - surfaced to the health endpoint, not swallowed
        return {"ok": False, "error": str(exc)}
