"""CRUD + atomic job-claim helpers against `studio.scene_research_job` and
`studio.video_render_job` (requirements/60 §4, migration 044). Plain SQLAlchemy `text()`
statements — no ORM models, matching mathbank-rest's own convention.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection


def create_research_job(conn: Connection, topic: str, context: dict | None = None) -> str:
    row = conn.execute(
        text("""
            INSERT INTO studio.scene_research_job (topic, context_json)
            VALUES (:topic, :context_json)
            RETURNING scene_research_job_id
        """),
        {"topic": topic, "context_json": json.dumps(context or {})},
    ).mappings().one()
    conn.commit()
    return str(row["scene_research_job_id"])


def get_research_job(conn: Connection, job_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text("SELECT * FROM studio.scene_research_job WHERE scene_research_job_id = :id"),
        {"id": job_id},
    ).mappings().one_or_none()
    return dict(row) if row else None


def claim_pending_research_job(conn: Connection) -> dict[str, Any] | None:
    """Atomically claims one PENDING row (sets it RUNNING) so two worker instances can
    safely poll the same table concurrently without double-processing a job."""
    row = conn.execute(
        text("""
            UPDATE studio.scene_research_job
            SET status = 'RUNNING', updated_at = now()
            WHERE scene_research_job_id = (
                SELECT scene_research_job_id FROM studio.scene_research_job
                WHERE status = 'PENDING'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
        """)
    ).mappings().one_or_none()
    conn.commit()
    return dict(row) if row else None


def complete_research_job(conn: Connection, job_id: str, scene_spec: dict, explanation: str
                           ) -> None:
    conn.execute(
        text("""
            UPDATE studio.scene_research_job
            SET status = 'DONE', result_scene_spec = :scene_spec,
                result_explanation = :explanation, updated_at = now()
            WHERE scene_research_job_id = :id
        """),
        {"id": job_id, "scene_spec": json.dumps(scene_spec), "explanation": explanation},
    )
    conn.commit()


def fail_research_job(conn: Connection, job_id: str, error_message: str) -> None:
    conn.execute(
        text("""
            UPDATE studio.scene_research_job
            SET status = 'FAILED', error_message = :error, updated_at = now()
            WHERE scene_research_job_id = :id
        """),
        {"id": job_id, "error": error_message[:4000]},
    )
    conn.commit()


def create_render_job(conn: Connection, *, scene_spec_json: dict,
                       source_research_job_id: str | None = None) -> str:
    row = conn.execute(
        text("""
            INSERT INTO studio.video_render_job (scene_spec_json, source_research_job_id)
            VALUES (:scene_spec_json, :source_id)
            RETURNING video_render_job_id
        """),
        {"scene_spec_json": json.dumps(scene_spec_json), "source_id": source_research_job_id},
    ).mappings().one()
    conn.commit()
    return str(row["video_render_job_id"])


def get_render_job(conn: Connection, job_id: str) -> dict[str, Any] | None:
    row = conn.execute(
        text("SELECT * FROM studio.video_render_job WHERE video_render_job_id = :id"),
        {"id": job_id},
    ).mappings().one_or_none()
    return dict(row) if row else None


def list_render_jobs(conn: Connection, *, status: str | None = None,
                      unpromoted_only: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    clauses = []
    params: dict[str, Any] = {"limit": limit}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    if unpromoted_only:
        clauses.append("promoted_scene_spec_id IS NULL")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        text(f"""
            SELECT * FROM studio.video_render_job
            {where}
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        params,
    ).mappings().all()
    return [dict(row) for row in rows]


def mark_render_job_promoted(conn: Connection, job_id: str, scene_spec_id: str) -> None:
    conn.execute(
        text("""
            UPDATE studio.video_render_job
            SET promoted_scene_spec_id = :scene_spec_id, updated_at = now()
            WHERE video_render_job_id = :id
        """),
        {"id": job_id, "scene_spec_id": scene_spec_id},
    )
    conn.commit()


def claim_pending_render_job(conn: Connection) -> dict[str, Any] | None:
    row = conn.execute(
        text("""
            UPDATE studio.video_render_job
            SET status = 'RUNNING', updated_at = now()
            WHERE video_render_job_id = (
                SELECT video_render_job_id FROM studio.video_render_job
                WHERE status = 'PENDING'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING *
        """)
    ).mappings().one_or_none()
    conn.commit()
    return dict(row) if row else None


def complete_render_job(conn: Connection, job_id: str, video_object_key: str,
                         video_duration_ms: int) -> None:
    conn.execute(
        text("""
            UPDATE studio.video_render_job
            SET status = 'DONE', video_object_key = :key, video_duration_ms = :duration_ms,
                updated_at = now()
            WHERE video_render_job_id = :id
        """),
        {"id": job_id, "key": video_object_key, "duration_ms": video_duration_ms},
    )
    conn.commit()


def fail_render_job(conn: Connection, job_id: str, error_message: str) -> None:
    conn.execute(
        text("""
            UPDATE studio.video_render_job
            SET status = 'FAILED', error_message = :error, updated_at = now()
            WHERE video_render_job_id = :id
        """),
        {"id": job_id, "error": error_message[:4000]},
    )
    conn.commit()
