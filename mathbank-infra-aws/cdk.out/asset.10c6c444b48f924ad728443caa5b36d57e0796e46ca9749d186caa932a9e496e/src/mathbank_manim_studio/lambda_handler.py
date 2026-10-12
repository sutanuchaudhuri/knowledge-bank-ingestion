"""AWS Lambda entrypoints for `mathbank-manim-studio` (requirements/60, requirements/63).

Two handlers share one container image (the CDK stack overrides `cmd` per function so
both are backed by the same build — requirements/63's own planned pattern):

- `api_handler` — the existing FastAPI app (`main.app`), Mangum-wrapped, serving the
  job-queue CRUD endpoints. `lifespan="off"`: `main.py`'s own lifespan starts an
  in-process `asyncio` polling loop (`worker.run_worker_loop`) meant for a long-lived
  local-dev process — on Lambda that loop would just run once per cold start and then
  go stale the moment the execution environment is frozen between invocations. The
  actual work is done by `worker_handler` below instead, invoked on its own schedule.
- `worker_handler` — a plain (non-ASGI) Lambda handler that claims and processes
  *one* research job and *one* render job per invocation, then returns. No changes
  needed to `worker.py`/`jobs.py`: `_process_one_research_job`/`_process_one_render_job`
  were already shaped for exactly this single-claim-then-return call pattern (the
  Postgres `FOR UPDATE SKIP LOCKED` claim is what makes concurrent/repeated invocations
  safe), and the CDK stack fires this handler on an EventBridge schedule.

Secrets are fetched from SSM Parameter Store at cold start, same pattern as
mathbank-rest's own `lambda_handler.py` (requirements/63, GOTCHAS.md #42).

Manim/matplotlib/fontconfig all expect a writable `$HOME`/cache directory, which the
Lambda filesystem does not provide outside of `/tmp` — redirected below, before any of
this project's own modules (which import `manim` transitively) are imported.
"""
from __future__ import annotations

import asyncio
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


def _redirect_caches_to_tmp() -> None:
    """Manim (Cairo/Pango text layout), matplotlib (font cache) and fontconfig (font
    cache) all write to `$HOME`-relative paths by default — only `/tmp` is writable in
    Lambda's read-only filesystem. Must run before `manim`/`matplotlib` are imported by
    any transitively-imported project module."""
    os.environ.setdefault("HOME", "/tmp")
    os.environ.setdefault("XDG_CACHE_HOME", "/tmp/.cache")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/.cache/matplotlib")
    os.environ.setdefault("FONTCONFIG_PATH", "/etc/fonts")
    os.environ.setdefault("FONTCONFIG_CACHE", "/tmp/.cache/fontconfig")
    for path in ("/tmp/.cache/matplotlib", "/tmp/.cache/fontconfig", "/tmp/manim_media"):
        os.makedirs(path, exist_ok=True)


def _configure_mcp_competitions_subprocess() -> None:
    """`config.py`'s defaults for these two settings use the same
    `parents[N]`-sibling-path trick as GOTCHAS.md #40 — only valid for an editable dev
    checkout. In the Lambda image, `mathbank_mcp_competitions` is pip-installed
    (Dockerfile.lambda) as a normal package; resolve its real on-disk `__main__.py`
    location instead, and point `mcp_competitions_python` at this same interpreter
    (`sys.executable`) rather than a separate sibling `.venv` that does not exist here."""
    import sys
    from importlib.util import find_spec

    spec = find_spec("mathbank_mcp_competitions.__main__")
    if spec and spec.origin:
        os.environ.setdefault("MCP_COMPETITIONS_SCRIPT", spec.origin)
    os.environ.setdefault("MCP_COMPETITIONS_PYTHON", sys.executable)


_load_secrets_from_ssm()
_redirect_caches_to_tmp()
_configure_mcp_competitions_subprocess()

from mangum import Mangum  # noqa: E402 — must follow the setup above

from mathbank_manim_studio.main import app  # noqa: E402 — ditto
from mathbank_manim_studio.worker import (  # noqa: E402 — ditto
    _process_one_render_job,
    _process_one_research_job,
)

# `lifespan="off"`: this handler must NOT start main.py's in-process worker loop (see
# module docstring) — `worker_handler` below is the real work, on its own schedule.
api_handler = Mangum(app, lifespan="off")


def worker_handler(event, context):  # noqa: ARG001 -- EventBridge schedule event, unused
    """Claims and processes at most one research job and one render job, then returns.
    Safe to invoke repeatedly/concurrently (`FOR UPDATE SKIP LOCKED` in jobs.py)."""

    async def _run_once() -> dict:
        did_research = await _process_one_research_job()
        did_render = await _process_one_render_job()
        return {"processed_research_job": did_research, "processed_render_job": did_render}

    return asyncio.run(_run_once())
