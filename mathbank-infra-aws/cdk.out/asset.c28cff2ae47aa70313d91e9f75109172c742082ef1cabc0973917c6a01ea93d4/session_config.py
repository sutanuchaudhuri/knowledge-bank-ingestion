"""Postgres session storage, separate from the corpus schemas."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from google.adk.sessions import DatabaseSessionService
from sqlalchemy import URL, Connection, event
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parent
SESSION_SCHEMA = "agent_sessions"


def session_database_url() -> URL:
    settings = {
        **dotenv_values(ROOT.parent / "mathbank-rest" / ".env"),
        **dotenv_values(ROOT.parent / ".env"),
        **dotenv_values(ROOT / ".env"),
        **os.environ,
    }
    required = ("POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")
    if any(not settings.get(key) for key in required):
        raise RuntimeError(
            "Agent sessions require POSTGRES_HOST, POSTGRES_DB, POSTGRES_USER and "
            "POSTGRES_PASSWORD in the shell, agent .env or root .env."
        )
    return URL.create(
        "postgresql+psycopg",
        username=settings["POSTGRES_USER"],
        password=settings["POSTGRES_PASSWORD"],
        host=settings["POSTGRES_HOST"],
        port=int(settings.get("POSTGRES_PORT") or "5432"),
        database=settings["POSTGRES_DB"],
        query={"sslmode": settings.get("POSTGRES_SSLMODE") or "require"},
    )


def prepare_session_schema(url: URL) -> None:
    with psycopg.connect(
        host=url.host, port=url.port, dbname=url.database,
        user=url.username, password=url.password, **dict(url.query),
    ) as connection:
        connection.execute(f"CREATE SCHEMA IF NOT EXISTS {SESSION_SCHEMA}")


def create_session_service(url: URL) -> DatabaseSessionService:
    engine = create_async_engine(url, pool_pre_ping=True)

    @event.listens_for(engine.sync_engine, "begin")
    def set_schema(connection: Connection) -> None:
        # SET LOCAL works with Neon transaction pooling, unlike startup options.
        connection.exec_driver_sql(f"SET LOCAL search_path TO {SESSION_SCHEMA}")

    return DatabaseSessionService(db_engine=engine)
