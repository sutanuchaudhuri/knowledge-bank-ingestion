"""Live, opt-in tests for the scene-spec catalog-promotion workflow (requirements/60 §7):
mathbank-rest calling the real mathbank-manim-studio REST API (requirements/60) to
promote an ephemeral render job into the canonical `visual.scene_spec` catalog.

Gated behind MANIM_STUDIO_LIVE_TEST=1 (not ROUTE_DB_TESTS=1 alone) because this needs a
real mathbank-manim-studio process reachable at MANIM_STUDIO_BASE_URL, plus a real
OpenAI call and a real manim render to produce a promotable job — genuinely slower and
more expensive than the rest of this file's rollback-only DB checks, so it stays opt-in
and separate.
"""

import os
import time

import httpx
import pytest
from sqlalchemy import text

from mathbank_rest import scene_spec_promotion
from mathbank_rest.config import settings
from mathbank_rest.db.postgres import engine


@pytest.fixture
def live_manim_studio():
    if os.environ.get("MANIM_STUDIO_LIVE_TEST") != "1":
        pytest.skip("Opt-in: requires a running mathbank-manim-studio + a real OpenAI/manim run")
    try:
        httpx.get(f"{settings.manim_studio_base_url}/v1/render-jobs", timeout=5).raise_for_status()
    except httpx.HTTPError:
        pytest.skip(f"mathbank-manim-studio is not reachable at {settings.manim_studio_base_url}")


def _create_done_render_job() -> str:
    base = settings.manim_studio_base_url
    research = httpx.post(
        f"{base}/v1/research-jobs", json={"topic": "the AM-GM inequality for two numbers"},
        timeout=10,
    ).json()
    for _ in range(60):
        research = httpx.get(f"{base}/v1/research-jobs/{research['id']}", timeout=10).json()
        if research["status"] in ("DONE", "FAILED"):
            break
        time.sleep(1)
    assert research["status"] == "DONE", research.get("error_message")

    render = httpx.post(
        f"{base}/v1/render-jobs", json={"research_job_id": research["id"]}, timeout=10
    ).json()
    for _ in range(90):
        render = httpx.get(f"{base}/v1/render-jobs/{render['id']}", timeout=10).json()
        if render["status"] in ("DONE", "FAILED"):
            break
        time.sleep(1)
    assert render["status"] == "DONE", render.get("error_message")
    return render["id"]


def test_full_promotion_round_trip(live_manim_studio):
    render_job_id = _create_done_render_job()
    canonical_code = f"TEST_PROMOTION_{render_job_id[:8]}"
    scene_spec_id = None
    try:
        with engine.connect() as conn:
            candidates = scene_spec_promotion.list_promotable_candidates(conn)
            assert any(c["id"] == render_job_id for c in candidates)

        scene_spec_id = scene_spec_promotion.promote_render_job(
            render_job_id=render_job_id, canonical_code=canonical_code, created_by="pytest",
        )
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT status, canonical_code, rendered_video_asset_id, "
                     "source_studio_job_id FROM visual.scene_spec WHERE scene_spec_id = :id"),
                {"id": scene_spec_id},
            ).mappings().one()
            assert row["status"] == "DRAFT"
            assert row["canonical_code"] == canonical_code
            assert row["source_studio_job_id"] == render_job_id
            asset_uri = conn.execute(
                text("SELECT uri FROM visual.asset WHERE asset_id = :id"),
                {"id": row["rendered_video_asset_id"]},
            ).scalar_one()
            assert asset_uri.startswith("object-store:")

        # Re-promoting the same job must fail, not silently duplicate the catalog row.
        with pytest.raises(scene_spec_promotion.PromotionError):
            scene_spec_promotion.promote_render_job(
                render_job_id=render_job_id, canonical_code=canonical_code + "_2",
                created_by="pytest",
            )

        confirm = httpx.get(
            f"{settings.manim_studio_base_url}/v1/render-jobs/{render_job_id}", timeout=10
        ).json()
        assert confirm["promoted_scene_spec_id"] == scene_spec_id
    finally:
        with engine.begin() as conn:
            conn.execute(text("SET visual.allow_purge = 'on'"))
            conn.execute(
                text("DELETE FROM studio.video_render_job WHERE video_render_job_id = :id"),
                {"id": render_job_id},
            )
            if scene_spec_id:
                asset_id = conn.execute(
                    text("SELECT rendered_video_asset_id FROM visual.scene_spec "
                         "WHERE scene_spec_id = :id"),
                    {"id": scene_spec_id},
                ).scalar_one_or_none()
                conn.execute(
                    text("DELETE FROM visual.scene_spec WHERE scene_spec_id = :id"),
                    {"id": scene_spec_id},
                )
                if asset_id:
                    conn.execute(
                        text("DELETE FROM visual.asset WHERE asset_id = :id"), {"id": asset_id}
                    )
