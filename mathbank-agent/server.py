"""Launch ADK without exposing the database URL in process arguments."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import psycopg
import uvicorn
from dotenv import load_dotenv
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.service_registry import get_service_registry
from google.adk.sessions import DatabaseSessionService
from session_config import (
    ROOT,
    create_session_service,
    prepare_session_schema,
    session_database_url,
)
from sqlalchemy.exc import SQLAlchemyError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from project_env import load_project_openai  # noqa: E402


async def check_session_storage(service: DatabaseSessionService) -> None:
    try:
        await service.list_sessions(app_name="mathbank_tutor", user_id="startup-check")
    finally:
        await service.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--allow_origins", action="append", default=[])
    parser.add_argument("--web", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    load_project_openai(ROOT / ".env")
    url = session_database_url()
    try:
        prepare_session_schema(url)
        asyncio.run(check_session_storage(create_session_service(url)))
    except (psycopg.Error, SQLAlchemyError):
        # Driver exceptions can include connection details. Never print them.
        raise SystemExit(
            "Postgres session storage initialization failed. Check connectivity, "
            "credentials, SSL settings and CREATE permission for agent_sessions."
        ) from None
    print("Agent sessions: Postgres / agent_sessions (connection verified)", flush=True)
    get_service_registry().register_session_service(
        "mathbank-postgres", lambda uri, **kwargs: create_session_service(url)
    )
    app = get_fast_api_app(
        agents_dir=str(ROOT / "agents"),
        session_service_uri="mathbank-postgres://sessions",
        allow_origins=args.allow_origins,
        web=args.web,
        port=args.port,
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
