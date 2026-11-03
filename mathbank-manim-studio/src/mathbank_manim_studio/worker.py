"""In-process asyncio worker (requirements/60 §5). It claims one job at a time and runs the corresponding agent.

Two backends (``jobs_backend``, selected by ``STUDIO_JOBS_BACKEND``):

* ``postgres`` (default): polls both job tables and claims one PENDING row with ``FOR UPDATE SKIP LOCKED`` — unchanged.
* ``dynamodb``: waits on the SQS queues (long polling) and claims the job item with a conditional update and a lease that a
  heartbeat keeps extending while the agent runs. Postgres is never touched. A claim that is lost (lease expired and taken
  over, cancelled) drops the result and deletes any video this run uploaded.
"""
from __future__ import annotations

import asyncio
import logging

from mathbank_manim_studio import object_store
from mathbank_manim_studio.config import get_settings
from mathbank_manim_studio.jobs_backend import Claimed, ClaimLost, get_backend
from mathbank_manim_studio.research_agent import run_research_agent
from mathbank_manim_studio.video_render_agent import render_and_store

logger = logging.getLogger("mathbank_manim_studio.worker")

SQS_WAIT_SECONDS = 10


async def _call(backend, fn, *args):
    """Backend calls that block on the network run in a thread for the DynamoDB backend; Postgres stays as it was."""
    if backend.name == "dynamodb":
        return await asyncio.to_thread(fn, *args)
    return fn(*args)


def _start_heartbeat(backend, claimed: Claimed):
    if not backend.supports_heartbeat:
        return None
    stop = asyncio.Event()

    async def beat() -> None:
        while True:
            try:
                await asyncio.wait_for(stop.wait(), timeout=backend.heartbeat_interval)
                return
            except asyncio.TimeoutError:
                pass
            try:
                await asyncio.to_thread(backend.heartbeat, claimed)
            except ClaimLost:
                logger.warning("%s job %s: lease lost while running", claimed.kind, claimed.job_id)
                return
            except Exception:  # noqa: BLE001 -- a missed beat is retried on the next tick
                logger.warning("%s job %s: heartbeat failed", claimed.kind, claimed.job_id, exc_info=True)

    return stop, asyncio.create_task(beat())


async def _stop_heartbeat(beat) -> None:
    if beat is not None:
        beat[0].set()
        await beat[1]


async def _settle_failure(backend, claimed: Claimed, exc: Exception) -> None:
    logger.error("%s job %s failed", claimed.kind, claimed.job_id, exc_info=exc)
    try:
        await _call(backend, backend.fail, claimed, str(exc))
    except ClaimLost:
        logger.warning("%s job %s: failure not recorded, the job is no longer ours", claimed.kind, claimed.job_id)


async def _run_research_job(backend, claimed: Claimed) -> None:
    beat = _start_heartbeat(backend, claimed)
    try:
        scene_spec, explanation = await run_research_agent(
            claimed.payload["topic"], claimed.payload["context_json"]
        )
        await _call(backend, backend.complete_research, claimed, scene_spec, explanation)
    except ClaimLost:
        logger.warning("research job %s: result dropped, the job is no longer ours", claimed.job_id)
    except Exception as exc:  # noqa: BLE001 -- persisted as a user-visible job failure
        await _settle_failure(backend, claimed, exc)
    finally:
        await _stop_heartbeat(beat)
        await _call(backend, backend.ack, claimed)


async def _run_render_job(backend, claimed: Claimed) -> None:
    beat = _start_heartbeat(backend, claimed)
    object_key = None
    try:
        object_key, duration_ms = await asyncio.to_thread(
            render_and_store, claimed.payload["scene_spec_json"]
        )
        await _call(backend, backend.complete_render, claimed, object_key, duration_ms)
    except ClaimLost:
        logger.warning("render job %s: result dropped, the job is no longer ours", claimed.job_id)
        if object_key:
            await asyncio.to_thread(_discard_video, object_key)
    except Exception as exc:  # noqa: BLE001 -- persisted as a user-visible job failure
        await _settle_failure(backend, claimed, exc)
    finally:
        await _stop_heartbeat(beat)
        await _call(backend, backend.ack, claimed)


def _discard_video(object_key: str) -> None:
    try:
        object_store.delete_object(object_key)
    except Exception:  # noqa: BLE001 -- best effort; the TTL reaper removes strays
        logger.warning("could not delete orphaned video %s", object_key, exc_info=True)


async def _process_one_research_job(wait_seconds: int = 0) -> bool:
    backend = get_backend()
    claimed = await _call(backend, backend.claim, "research", wait_seconds)
    if claimed is None:
        return False
    await _run_research_job(backend, claimed)
    return True


async def _process_one_render_job(wait_seconds: int = 0) -> bool:
    backend = get_backend()
    claimed = await _call(backend, backend.claim, "render", wait_seconds)
    if claimed is None:
        return False
    await _run_render_job(backend, claimed)
    return True


async def process_message(kind: str, job_id: str) -> bool:
    """SQS-triggered path (Lambda): claim exactly the job the message names. False = duplicate/stale delivery (no-op)."""
    backend = get_backend()
    claimed = await _call(backend, backend.claim_message, kind, job_id)
    if claimed is None:
        return False
    await (_run_research_job if kind == "research" else _run_render_job)(backend, claimed)
    return True


async def run_worker_loop(*, stop_event: asyncio.Event | None = None) -> None:
    poll_seconds = get_settings().worker_poll_seconds
    stop_event = stop_event or asyncio.Event()
    backend = get_backend()
    while not stop_event.is_set():
        if backend.name == "dynamodb":
            # long polling on both queues: no Postgres, and an idle Studio costs one receive per queue per wait
            await asyncio.gather(
                _process_one_research_job(SQS_WAIT_SECONDS), _process_one_render_job(SQS_WAIT_SECONDS)
            )
            continue
        did_work = await _process_one_research_job()
        did_work = await _process_one_render_job() or did_work
        if not did_work:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
            except asyncio.TimeoutError:
                pass
