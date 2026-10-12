"""AWS Lambda entrypoint for `mathbank-agent` (requirements/62 §4, requirements/63).

Not a thin Mangum wrapper alone — `server.py`'s own `main()` does real startup work
(verify Postgres `agent_sessions` schema/connectivity, register a custom ADK session
service) before building the FastAPI app; this handler replicates exactly that sequence
once at cold start, then wraps the resulting app in Mangum. Deliberately does **not**
import `server.py` directly — that module's `sys.path.insert(...)` sibling-`project_env`
import only works for a real monorepo checkout (GOTCHAS.md #40), which this Lambda image
is not. `OPENAI_API_KEY` arrives already set from `_load_secrets_from_ssm()` below, so
that import is never needed here.
"""
from __future__ import annotations

import os


def _load_secrets_from_ssm() -> None:
    prefix = os.environ.pop("MATHBANK_SSM_PREFIX", "")
    secret_map = os.environ.pop("MATHBANK_SECRET_MAP", "")
    if not prefix or not secret_map:
        return  # local/non-Lambda run — nothing to do
    import boto3

    client = boto3.client("ssm")
    for pair in secret_map.split(","):
        ssm_suffix, _, target_env_var = pair.partition("=")
        if not ssm_suffix or not target_env_var:
            continue
        name = f"{prefix}/{ssm_suffix}"
        resp = client.get_parameter(Name=name, WithDecryption=True)
        os.environ[target_env_var] = resp["Parameter"]["Value"]


_load_secrets_from_ssm()

import asyncio  # noqa: E402

from google.adk.cli.fast_api import get_fast_api_app  # noqa: E402
from google.adk.cli.service_registry import get_service_registry  # noqa: E402
from google.adk.sessions import DatabaseSessionService  # noqa: E402
from mangum import Mangum  # noqa: E402
from session_config import (  # noqa: E402
    ROOT,
    create_session_service,
    prepare_session_schema,
    session_database_url,
)


async def _check_session_storage(service: DatabaseSessionService) -> None:
    try:
        await service.list_sessions(app_name="mathbank_tutor", user_id="startup-check")
    finally:
        await service.close()


_url = session_database_url()
prepare_session_schema(_url)
asyncio.run(_check_session_storage(create_session_service(_url)))
get_service_registry().register_session_service(
    "mathbank-postgres", lambda uri, **kwargs: create_session_service(_url)
)

app = get_fast_api_app(
    agents_dir=str(ROOT / "agents"),
    session_service_uri="mathbank-postgres://sessions",
    allow_origins=["*"],
    web=False,
)

handler = Mangum(app)
