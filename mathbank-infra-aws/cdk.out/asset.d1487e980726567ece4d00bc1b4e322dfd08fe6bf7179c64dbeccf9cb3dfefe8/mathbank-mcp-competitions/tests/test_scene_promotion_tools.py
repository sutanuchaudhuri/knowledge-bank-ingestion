"""Live, opt-in tests for the requirements/60 §7 scene-catalog-promotion MCP tools —
exercises the real MCP protocol path against a real, running mathbank-manim-studio +
mathbank-rest (the same two-service round trip proven directly in
mathbank-rest/tests/test_scene_spec_promotion.py, now through the MCP tool layer that an
actual agent would use).

Gated behind MANIM_STUDIO_LIVE_TEST=1, same convention as mathbank-rest's own opt-in test
for this feature, since it needs a real OpenAI call + a real manim render + both services
reachable.
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
import psycopg
import pytest
from fastmcp import Client

from mathbank_mcp_competitions.server import mcp

MANIM_STUDIO_BASE_URL = "http://localhost:8020"
REST_ENV_PATH = Path(__file__).resolve().parents[2] / "mathbank-rest" / ".env"


def _read_rest_env() -> dict:
    env = {}
    if REST_ENV_PATH.is_file():
        for line in REST_ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip()
    return env


@pytest.fixture
async def live_manim_studio():
    if os.environ.get("MANIM_STUDIO_LIVE_TEST") != "1":
        pytest.skip("Opt-in: requires a running mathbank-manim-studio + a real OpenAI/manim run")
    try:
        httpx.get(f"{MANIM_STUDIO_BASE_URL}/v1/render-jobs", timeout=5).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(f"mathbank-manim-studio is not reachable at {MANIM_STUDIO_BASE_URL}")


def _create_done_render_job() -> str:
    research = httpx.post(
        f"{MANIM_STUDIO_BASE_URL}/v1/research-jobs",
        json={"topic": "the triangle inequality"}, timeout=10,
    ).json()
    for _ in range(60):
        research = httpx.get(f"{MANIM_STUDIO_BASE_URL}/v1/research-jobs/{research['id']}", timeout=10).json()
        if research["status"] in ("DONE", "FAILED"):
            break
        time.sleep(1)
    assert research["status"] == "DONE", research.get("error_message")

    render = httpx.post(
        f"{MANIM_STUDIO_BASE_URL}/v1/render-jobs", json={"research_job_id": research["id"]}, timeout=10
    ).json()
    for _ in range(90):
        render = httpx.get(f"{MANIM_STUDIO_BASE_URL}/v1/render-jobs/{render['id']}", timeout=10).json()
        if render["status"] in ("DONE", "FAILED"):
            break
        time.sleep(1)
    assert render["status"] == "DONE", render.get("error_message")
    return render["id"]


async def test_promotion_tools_full_round_trip(live_manim_studio):
    rest_env = _read_rest_env()
    admin_key = rest_env.get("ADMIN_API_KEY")
    if not admin_key:
        pytest.skip("mathbank-rest/.env has no ADMIN_API_KEY to test against")

    render_job_id = _create_done_render_job()
    canonical_code = f"TEST_MCP_PROMOTION_{render_job_id[:8]}"
    scene_spec_id = None
    try:
        async with Client(mcp) as client:
            candidates = (await client.call_tool(
                "list_promotable_scenes", {"admin_api_key": admin_key}
            )).data
            assert any(c["id"] == render_job_id for c in candidates)

            promoted = (await client.call_tool(
                "promote_scene_to_catalog",
                {"render_job_id": render_job_id, "canonical_code": canonical_code,
                 "admin_api_key": admin_key},
            )).data
            assert promoted["status"] == "DRAFT"
            scene_spec_id = promoted["scene_spec_id"]

            validated = (await client.call_tool(
                "validate_scene_in_catalog",
                {"scene_spec_id": scene_spec_id, "admin_api_key": admin_key},
            )).data
            assert validated["status"] == "VALID"

            approved = (await client.call_tool(
                "approve_scene_in_catalog",
                {"scene_spec_id": scene_spec_id, "admin_api_key": admin_key},
            )).data
            assert approved["status"] == "APPROVED"
    finally:
        conninfo = (
            f"host={rest_env.get('POSTGRES_HOST')} port={rest_env.get('POSTGRES_PORT')} "
            f"dbname={rest_env.get('POSTGRES_DB')} user={rest_env.get('POSTGRES_USER')} "
            f"password={rest_env.get('POSTGRES_PASSWORD')} "
            f"sslmode={rest_env.get('POSTGRES_SSLMODE') or 'prefer'}"
        )
        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SET visual.allow_purge = 'on'")
                cur.execute(
                    "DELETE FROM studio.video_render_job WHERE video_render_job_id = %s",
                    (render_job_id,),
                )
                if scene_spec_id:
                    cur.execute(
                        "SELECT rendered_video_asset_id FROM visual.scene_spec "
                        "WHERE scene_spec_id = %s", (scene_spec_id,),
                    )
                    row = cur.fetchone()
                    cur.execute(
                        "DELETE FROM visual.scene_spec WHERE scene_spec_id = %s",
                        (scene_spec_id,),
                    )
                    if row and row[0]:
                        cur.execute(
                            "DELETE FROM visual.asset WHERE asset_id = %s", (row[0],)
                        )
            conn.commit()
