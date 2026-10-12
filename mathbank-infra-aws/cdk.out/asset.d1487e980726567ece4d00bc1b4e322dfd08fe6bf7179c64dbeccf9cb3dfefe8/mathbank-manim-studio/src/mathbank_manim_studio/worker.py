"""In-process asyncio worker (requirements/60 §5): polls both job tables, atomically
claims one PENDING row at a time, and runs the corresponding agent. Deliberately not a
separate process/queue technology — the Postgres `FOR UPDATE SKIP LOCKED` claim already
makes this safe to run from multiple processes/machines if the workload ever needs that,
without changing the job-table contract (requirements/60 §2).
"""
from __future__ import annotations

import asyncio
import logging

from mathbank_manim_studio import jobs
from mathbank_manim_studio.config import get_settings
from mathbank_manim_studio.db import connection
from mathbank_manim_studio.research_agent import run_research_agent
from mathbank_manim_studio.video_render_agent import render_and_store

logger = logging.getLogger("mathbank_manim_studio.worker")


async def _process_one_research_job() -> bool:
    with connection() as conn:
        job = jobs.claim_pending_research_job(conn)
    if job is None:
        return False
    job_id = str(job["scene_research_job_id"])
    try:
        scene_spec, explanation = await run_research_agent(job["topic"], job["context_json"])
        with connection() as conn:
            jobs.complete_research_job(conn, job_id, scene_spec, explanation)
    except Exception as exc:  # noqa: BLE001 -- persisted as a user-visible job failure
        logger.exception("research job %s failed", job_id)
        with connection() as conn:
            jobs.fail_research_job(conn, job_id, str(exc))
    return True


async def _process_one_render_job() -> bool:
    with connection() as conn:
        job = jobs.claim_pending_render_job(conn)
    if job is None:
        return False
    job_id = str(job["video_render_job_id"])
    try:
        object_key, duration_ms = await asyncio.to_thread(
            render_and_store, job["scene_spec_json"]
        )
        with connection() as conn:
            jobs.complete_render_job(conn, job_id, object_key, duration_ms)
    except Exception as exc:  # noqa: BLE001 -- persisted as a user-visible job failure
        logger.exception("render job %s failed", job_id)
        with connection() as conn:
            jobs.fail_render_job(conn, job_id, str(exc))
    return True


async def run_worker_loop(*, stop_event: asyncio.Event | None = None) -> None:
    poll_seconds = get_settings().worker_poll_seconds
    stop_event = stop_event or asyncio.Event()
    while not stop_event.is_set():
        did_work = await _process_one_research_job()
        did_work = await _process_one_render_job() or did_work
        if not did_work:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass
