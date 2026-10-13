"""FastAPI app for mathbank-manim-studio (requirements/60 §5). Two job-queue resources
(research jobs, render jobs), each `POST` to enqueue + `GET` to poll; an in-process
asyncio worker is started on `startup` and cancelled on `shutdown`.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from mathbank_manim_studio import jobs, object_store
from mathbank_manim_studio.config import get_settings
from mathbank_manim_studio.db import connection
from mathbank_manim_studio.worker import run_worker_loop

_stop_event: asyncio.Event | None = None
_worker_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _stop_event, _worker_task
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(run_worker_loop(stop_event=_stop_event))
    yield
    _stop_event.set()
    if _worker_task:
        await _worker_task


app = FastAPI(title="MathBank Manim Video Studio", lifespan=lifespan)


def require_admin_api_key(x_admin_api_key: Annotated[str | None, Header()] = None) -> None:
    """Guards the one write endpoint a peer service (mathbank-rest) calls after a
    successful promotion — same shared-secret header convention as mathbank-rest's own
    `require_admin_api_key` (requirements/60 §7), not a new auth scheme."""
    settings = get_settings()
    if not settings.admin_api_key or x_admin_api_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="invalid admin API key")


class ResearchJobRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=500)
    context: dict = Field(default_factory=dict)


class RenderJobRequest(BaseModel):
    research_job_id: str | None = None
    scene_spec_json: dict | None = None


class MarkPromotedRequest(BaseModel):
    scene_spec_id: str


def _research_job_response(job: dict) -> dict:
    return {
        "id": str(job["scene_research_job_id"]),
        "status": job["status"],
        "topic": job["topic"],
        "context": job["context_json"],
        "result_scene_spec": job["result_scene_spec"],
        "result_explanation": job["result_explanation"],
        "error_message": job["error_message"],
        "created_at": job["created_at"].isoformat(),
        "expires_at": job["expires_at"].isoformat(),
    }


def _render_job_response(job: dict) -> dict:
    return {
        "id": str(job["video_render_job_id"]),
        "status": job["status"],
        "source_research_job_id": (
            str(job["source_research_job_id"]) if job["source_research_job_id"] else None
        ),
        "video_duration_ms": job["video_duration_ms"],
        "video_url": (
            f"/v1/render-jobs/{job['video_render_job_id']}/video"
            if job["video_object_key"] else None
        ),
        "promoted_scene_spec_id": (
            str(job["promoted_scene_spec_id"]) if job.get("promoted_scene_spec_id") else None
        ),
        "scene_spec_json": job.get("scene_spec_json"),
        "error_message": job["error_message"],
        "created_at": job["created_at"].isoformat(),
        "expires_at": job["expires_at"].isoformat(),
    }


@app.post("/v1/research-jobs")
def post_research_job(request: ResearchJobRequest) -> dict:
    with connection() as conn:
        job_id = jobs.create_research_job(conn, request.topic, request.context)
        job = jobs.get_research_job(conn, job_id)
    return _research_job_response(job)


@app.get("/v1/research-jobs/{job_id}")
def get_research_job(job_id: str) -> dict:
    with connection() as conn:
        job = jobs.get_research_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="research job not found")
    return _research_job_response(job)


@app.post("/v1/render-jobs")
def post_render_job(request: RenderJobRequest) -> dict:
    if not request.research_job_id and not request.scene_spec_json:
        raise HTTPException(
            status_code=422, detail="one of research_job_id or scene_spec_json is required"
        )
    with connection() as conn:
        scene_spec_json = request.scene_spec_json
        if request.research_job_id:
            research_job = jobs.get_research_job(conn, request.research_job_id)
            if research_job is None:
                raise HTTPException(status_code=404, detail="research job not found")
            if research_job["status"] != "DONE":
                raise HTTPException(
                    status_code=409,
                    detail=f"research job is {research_job['status']}, not DONE yet",
                )
            scene_spec_json = research_job["result_scene_spec"]
        job_id = jobs.create_render_job(
            conn, scene_spec_json=scene_spec_json, source_research_job_id=request.research_job_id
        )
        job = jobs.get_render_job(conn, job_id)
    return _render_job_response(job)


@app.get("/v1/render-jobs/{job_id}")
def get_render_job(job_id: str) -> dict:
    with connection() as conn:
        job = jobs.get_render_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="render job not found")
    return _render_job_response(job)


@app.get("/v1/render-jobs/{job_id}/video")
def get_render_job_video(job_id: str) -> Response:
    with connection() as conn:
        job = jobs.get_render_job(conn, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="render job not found")
    if not job.get("video_object_key"):
        raise HTTPException(status_code=409, detail=f"render job is {job['status']}, no video yet")
    data = object_store.read_bytes(job["video_object_key"])
    return Response(content=data, media_type="video/mp4")


@app.get("/v1/render-jobs")
def list_render_jobs(status: str | None = None, unpromoted_only: bool = False) -> list[dict]:
    """Lists render jobs — in particular, DONE + unpromoted ones, which is how the
    canonical-catalog promotion workflow (requirements/60 §7, mathbank-rest's
    `scene_spec_promotion.py`) discovers candidates to promote."""
    with connection() as conn:
        rows = jobs.list_render_jobs(conn, status=status, unpromoted_only=unpromoted_only)
    return [_render_job_response(row) for row in rows]


@app.post("/v1/render-jobs/{job_id}/mark-promoted", dependencies=[Depends(require_admin_api_key)])
def mark_render_job_promoted(job_id: str, request: MarkPromotedRequest) -> dict:
    with connection() as conn:
        job = jobs.get_render_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="render job not found")
        jobs.mark_render_job_promoted(conn, job_id, request.scene_spec_id)
        job = jobs.get_render_job(conn, job_id)
    return _render_job_response(job)
