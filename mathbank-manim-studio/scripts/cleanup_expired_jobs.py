#!/usr/bin/env python3
"""Deletes every expired studio.scene_research_job / studio.video_render_job row (and the
corresponding object-store video for expired render jobs) — requirements/60 §4's 1-day
TTL enforcement. Run via `make cleanup` or an external cron; intentionally not wired to
any cloud scheduler here (requirements/60 §2: no cloud resources are provisioned by this
project).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text

from mathbank_manim_studio import object_store
from mathbank_manim_studio.db import connection


def cleanup_expired_jobs() -> dict:
    deleted = {"research_jobs": 0, "render_jobs": 0, "videos": 0}
    with connection() as conn:
        expired_videos = conn.execute(
            text("""
                SELECT video_object_key FROM studio.video_render_job
                WHERE expires_at < now() AND video_object_key IS NOT NULL
            """)
        ).scalars().all()
        for key in expired_videos:
            try:
                object_store.delete_object(key)
                deleted["videos"] += 1
            except (OSError, ValueError):
                pass  # already gone or unreadable key; row deletion below still proceeds

        result = conn.execute(
            text("DELETE FROM studio.video_render_job WHERE expires_at < now()")
        )
        deleted["render_jobs"] = result.rowcount

        result = conn.execute(
            text("DELETE FROM studio.scene_research_job WHERE expires_at < now()")
        )
        deleted["research_jobs"] = result.rowcount
        conn.commit()
    return deleted


if __name__ == "__main__":
    counts = cleanup_expired_jobs()
    print(f"Deleted {counts['research_jobs']} expired research job(s), "
          f"{counts['render_jobs']} expired render job(s), {counts['videos']} video object(s)")
