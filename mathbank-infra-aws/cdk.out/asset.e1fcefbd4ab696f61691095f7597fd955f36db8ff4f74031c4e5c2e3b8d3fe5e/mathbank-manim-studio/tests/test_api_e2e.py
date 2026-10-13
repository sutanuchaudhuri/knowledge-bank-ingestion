"""Full, live round trip through the real FastAPI app + worker loop: enqueue a research
job, poll until DONE, enqueue a render job from its result, poll until DONE, download the
video. This is the single strongest piece of evidence for requirements/60 — it exercises
every layer (API, Postgres job queue, OpenAI-driven research agent via a real MCP
subprocess, and a real `manim` render) exactly as a real caller would. Slow (~30-90s):
a live OpenAI call plus a live manim render are both genuinely executed.
"""
from __future__ import annotations

import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_manim_studio.db import connection
from mathbank_manim_studio.main import app


def _poll_until(client: TestClient, url: str, *, timeout_s: float = 90) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        body = client.get(url).json()
        if body["status"] in ("DONE", "FAILED"):
            return body
        time.sleep(1.0)
    raise TimeoutError(f"{url} did not reach a terminal status within {timeout_s}s")


def test_full_research_to_render_round_trip():
    with TestClient(app) as client:
        research = client.post(
            "/v1/research-jobs",
            json={"topic": "Vieta's formulas for a quadratic", "context": {}},
        ).json()
        assert research["status"] == "PENDING"

        research_done = _poll_until(client, f"/v1/research-jobs/{research['id']}")
        assert research_done["status"] == "DONE", research_done.get("error_message")
        assert research_done["result_scene_spec"]["objects"]
        assert research_done["result_explanation"]

        render = client.post(
            "/v1/render-jobs", json={"research_job_id": research["id"]}
        ).json()
        assert render["status"] == "PENDING"
        assert render["source_research_job_id"] == research["id"]

        render_done = _poll_until(client, f"/v1/render-jobs/{render['id']}", timeout_s=120)
        assert render_done["status"] == "DONE", render_done.get("error_message")
        assert render_done["video_duration_ms"] > 500
        assert render_done["video_url"]

        video_response = client.get(render_done["video_url"])
        assert video_response.status_code == 200
        assert video_response.headers["content-type"] == "video/mp4"
        assert len(video_response.content) > 1000

    # Clean up both rows (and the stored video) so this test leaves nothing behind.
    with connection() as conn:
        video_key = conn.execute(
            text("SELECT video_object_key FROM studio.video_render_job WHERE video_render_job_id = :id"),
            {"id": render["id"]},
        ).scalar_one_or_none()
        conn.execute(
            text("DELETE FROM studio.video_render_job WHERE video_render_job_id = :id"),
            {"id": render["id"]},
        )
        conn.execute(
            text("DELETE FROM studio.scene_research_job WHERE scene_research_job_id = :id"),
            {"id": research["id"]},
        )
        conn.commit()
    if video_key:
        from mathbank_manim_studio import object_store
        object_store.delete_object(video_key)


def test_render_job_requires_research_job_id_or_scene_spec():
    with TestClient(app) as client:
        response = client.post("/v1/render-jobs", json={})
    assert response.status_code == 422


def test_get_unknown_job_returns_404():
    with TestClient(app) as client:
        assert client.get("/v1/research-jobs/00000000-0000-0000-0000-000000000000").status_code == 404
        assert client.get("/v1/render-jobs/00000000-0000-0000-0000-000000000000").status_code == 404
