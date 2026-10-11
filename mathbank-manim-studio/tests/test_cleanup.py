from pathlib import Path

from sqlalchemy import text

from mathbank_manim_studio import jobs, object_store
from mathbank_manim_studio.db import connection

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cleanup_expired_jobs import cleanup_expired_jobs  # noqa: E402


def _backdate_research_job(job_id: str) -> None:
    with connection() as conn:
        conn.execute(
            text("""
                UPDATE studio.scene_research_job
                SET expires_at = now() - interval '1 hour'
                WHERE scene_research_job_id = :id
            """),
            {"id": job_id},
        )
        conn.commit()


def _backdate_render_job(job_id: str) -> None:
    with connection() as conn:
        conn.execute(
            text("""
                UPDATE studio.video_render_job
                SET expires_at = now() - interval '1 hour'
                WHERE video_render_job_id = :id
            """),
            {"id": job_id},
        )
        conn.commit()


def test_cleanup_deletes_expired_research_job_but_not_a_fresh_one():
    with connection() as conn:
        expired_id = jobs.create_research_job(conn, "expired topic")
        fresh_id = jobs.create_research_job(conn, "fresh topic")
    _backdate_research_job(expired_id)

    counts = cleanup_expired_jobs()
    assert counts["research_jobs"] >= 1

    with connection() as conn:
        assert jobs.get_research_job(conn, expired_id) is None
        assert jobs.get_research_job(conn, fresh_id) is not None
        conn.execute(
            text("DELETE FROM studio.scene_research_job WHERE scene_research_job_id = :id"),
            {"id": fresh_id},
        )
        conn.commit()


def test_cleanup_deletes_expired_render_job_and_its_video_object():
    # Write a tiny real file into the object store, as a real render job would.
    tmp = Path("/tmp/mathbank_manim_studio_cleanup_test.mp4")
    tmp.write_bytes(b"not a real video but a real file")
    object_key = object_store.put_file(tmp, "mp4")
    tmp.unlink()

    with connection() as conn:
        render_id = jobs.create_render_job(
            conn, scene_spec_json={"scene_key": "x", "scene_version": 1, "objects": [],
                                     "timeline": []},
        )
        jobs.complete_render_job(conn, render_id, object_key, 1000)
    _backdate_render_job(render_id)

    # Sanity check before cleanup: the object is actually readable.
    assert object_store.read_bytes(object_key) == b"not a real video but a real file"

    counts = cleanup_expired_jobs()
    assert counts["render_jobs"] >= 1
    assert counts["videos"] >= 1

    with connection() as conn:
        assert jobs.get_render_job(conn, render_id) is None
    try:
        object_store.read_bytes(object_key)
        assert False, "expected the video object to have been deleted"
    except object_store.ObjectStoreError:
        pass
