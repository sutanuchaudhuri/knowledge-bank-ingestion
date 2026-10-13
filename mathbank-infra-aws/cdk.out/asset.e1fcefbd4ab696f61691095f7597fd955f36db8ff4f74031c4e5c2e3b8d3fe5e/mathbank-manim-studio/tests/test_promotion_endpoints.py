from fastapi.testclient import TestClient
from sqlalchemy import text

from mathbank_manim_studio import jobs
from mathbank_manim_studio.config import get_settings
from mathbank_manim_studio.db import connection
from mathbank_manim_studio.main import app


def _cleanup_render_job(job_id: str) -> None:
    with connection() as conn:
        conn.execute(
            text("DELETE FROM studio.video_render_job WHERE video_render_job_id = :id"),
            {"id": job_id},
        )
        conn.commit()


def test_list_render_jobs_filters_by_status_and_unpromoted():
    with connection() as conn:
        done_id = jobs.create_render_job(
            conn, scene_spec_json={"scene_key": "x", "scene_version": 1, "objects": [],
                                     "timeline": []},
        )
        jobs.complete_render_job(conn, done_id, "fakekey.mp4", 1000)
        pending_id = jobs.create_render_job(
            conn, scene_spec_json={"scene_key": "y", "scene_version": 1, "objects": [],
                                     "timeline": []},
        )
    try:
        with TestClient(app) as client:
            done_jobs = client.get("/v1/render-jobs", params={"status": "DONE"}).json()
            assert any(j["id"] == done_id for j in done_jobs)
            assert not any(j["id"] == pending_id for j in done_jobs)

            unpromoted = client.get(
                "/v1/render-jobs", params={"status": "DONE", "unpromoted_only": True}
            ).json()
            assert any(j["id"] == done_id for j in unpromoted)
    finally:
        _cleanup_render_job(done_id)
        _cleanup_render_job(pending_id)


def test_mark_promoted_requires_admin_key():
    with connection() as conn:
        job_id = jobs.create_render_job(
            conn, scene_spec_json={"scene_key": "x", "scene_version": 1, "objects": [],
                                     "timeline": []},
        )
    try:
        with TestClient(app) as client:
            no_key = client.post(
                f"/v1/render-jobs/{job_id}/mark-promoted",
                json={"scene_spec_id": "00000000-0000-0000-0000-000000000000"},
            )
            assert no_key.status_code == 401

            wrong_key = client.post(
                f"/v1/render-jobs/{job_id}/mark-promoted",
                json={"scene_spec_id": "00000000-0000-0000-0000-000000000000"},
                headers={"X-Admin-Api-Key": "wrong"},
            )
            assert wrong_key.status_code == 401
    finally:
        _cleanup_render_job(job_id)


def test_mark_promoted_succeeds_with_correct_key():
    settings = get_settings()
    with connection() as conn:
        job_id = jobs.create_render_job(
            conn, scene_spec_json={"scene_key": "x", "scene_version": 1, "objects": [],
                                     "timeline": []},
        )
        # promoted_scene_spec_id has a real FK into visual.scene_spec (migration 045),
        # so this test needs one real (throwaway) row to point at.
        scene_spec_id = conn.execute(
            text("""
                INSERT INTO visual.scene_spec
                    (canonical_code, version, scene_schema_version, scene_json,
                     content_hash, created_by)
                VALUES ('TEST_PROMO_ENDPOINT', 1, 'v1', '{}'::jsonb, 'deadbeef', 'test')
                RETURNING scene_spec_id
            """)
        ).scalar_one()
        conn.commit()
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/v1/render-jobs/{job_id}/mark-promoted",
                json={"scene_spec_id": str(scene_spec_id)},
                headers={"X-Admin-Api-Key": settings.admin_api_key},
            )
            assert response.status_code == 200
            assert response.json()["promoted_scene_spec_id"] == str(scene_spec_id)
    finally:
        _cleanup_render_job(job_id)
        with connection() as conn:
            conn.execute(
                text("DELETE FROM visual.scene_spec WHERE scene_spec_id = :id"),
                {"id": scene_spec_id},
            )
            conn.commit()
