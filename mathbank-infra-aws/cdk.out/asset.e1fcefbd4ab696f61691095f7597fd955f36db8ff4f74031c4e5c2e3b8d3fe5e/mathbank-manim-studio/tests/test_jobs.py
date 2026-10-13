import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from mathbank_manim_studio import jobs
from mathbank_manim_studio.db import connection


def test_create_and_get_research_job_round_trip():
    with connection() as conn:
        job_id = jobs.create_research_job(conn, "Vieta formulas", {"concept_code": "VIETA"})
        job = jobs.get_research_job(conn, job_id)
    assert job["status"] == "PENDING"
    assert job["topic"] == "Vieta formulas"
    assert job["context_json"] == {"concept_code": "VIETA"}
    assert job["expires_at"] > job["created_at"]
    # cleanup: this test's own row should not linger past the test run
    with connection() as conn:
        conn.execute(
            text("DELETE FROM studio.scene_research_job WHERE scene_research_job_id = :id"),
            {"id": job_id},
        )
        conn.commit()


def test_atomic_claim_marks_running_and_only_claims_once():
    with connection() as conn:
        job_id = jobs.create_research_job(conn, "claim test topic")
        first_claim = jobs.claim_pending_research_job(conn)
        second_claim = jobs.claim_pending_research_job(conn)
    assert first_claim is not None
    assert str(first_claim["scene_research_job_id"]) == job_id
    assert first_claim["status"] == "RUNNING"
    # a second immediate claim must not re-claim the same (now RUNNING) row, nor any
    # other PENDING row, since none exists
    assert second_claim is None or str(second_claim["scene_research_job_id"]) != job_id
    with connection() as conn:
        conn.execute(
            text("DELETE FROM studio.scene_research_job WHERE scene_research_job_id = :id"),
            {"id": job_id},
        )
        conn.commit()


def test_complete_and_fail_research_job():
    with connection() as conn:
        job_id = jobs.create_research_job(conn, "complete test topic")
        jobs.complete_research_job(
            conn, job_id, {"scene_key": "x", "scene_version": 1, "objects": [], "timeline": []},
            "an explanation",
        )
        job = jobs.get_research_job(conn, job_id)
    assert job["status"] == "DONE"
    assert job["result_explanation"] == "an explanation"

    with connection() as conn:
        job_id_2 = jobs.create_research_job(conn, "fail test topic")
        jobs.fail_research_job(conn, job_id_2, "boom")
        job2 = jobs.get_research_job(conn, job_id_2)
    assert job2["status"] == "FAILED"
    assert job2["error_message"] == "boom"

    with connection() as conn:
        conn.execute(
            text("DELETE FROM studio.scene_research_job WHERE scene_research_job_id IN (:a, :b)"),
            {"a": job_id, "b": job_id_2},
        )
        conn.commit()


def test_render_job_round_trip_with_source_link():
    with connection() as conn:
        research_id = jobs.create_research_job(conn, "render-link topic")
        render_id = jobs.create_render_job(
            conn, scene_spec_json={"scene_key": "x", "scene_version": 1, "objects": [],
                                     "timeline": []},
            source_research_job_id=research_id,
        )
        job = jobs.get_render_job(conn, render_id)
    assert job["status"] == "PENDING"
    assert str(job["source_research_job_id"]) == research_id

    with connection() as conn:
        conn.execute(
            text("DELETE FROM studio.video_render_job WHERE video_render_job_id = :id"),
            {"id": render_id},
        )
        conn.execute(
            text("DELETE FROM studio.scene_research_job WHERE scene_research_job_id = :id"),
            {"id": research_id},
        )
        conn.commit()
