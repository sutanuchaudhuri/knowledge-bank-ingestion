"""Configured geometry model adapter and learner-safe runtime context assembly."""

from __future__ import annotations

import os
from uuid import uuid4

from geometry_scene.errors import GeometryError
from geometry_scene.openai_provider import OpenAIProvider
from geometry_scene.orchestration import GeometryRequest, OrchestrationFailure, orchestrate
from geometry_scene.renderer import render

from mathbank_rest.tutor import _client


def make_provider():
    model = os.environ.get("GEOMETRY_AGENT_MODEL", "gpt-4.1-mini")
    return OpenAIProvider(_client, model)


def interpret(request: GeometryRequest, store, owner, key=None, provider=None):
    body = request.model_dump(mode="json")
    replay = store.lookup_receipt(owner, key, "interpret", body)
    if replay:
        return {
            "scene_id": replay.scene_state.scene_id,
            "version": replay.version,
            "caption": replay.visual_state.caption,
            "current_math_step": request.current_math_step,
            "validation": replay.validation.model_dump(mode="json"),
            "replayed": True,
            "operations": [{"status": "REPLAYED"}],
        }
    run_id = "run_" + uuid4().hex
    previous = store.current(request.scene_id, owner) if request.scene_id else None
    if previous and previous.version != request.expected_version:
        from geometry_scene.errors import VersionConflict

        raise VersionConflict("geometry base version changed")
    try:
        frame, evidence = orchestrate(
            request,
            provider or make_provider(),
            previous,
            max_attempts=int(os.environ.get("GEOMETRY_MAX_ATTEMPTS", "3")),
            max_calls=int(os.environ.get("GEOMETRY_MAX_CALLS", "9")),
            deadline_seconds=float(os.environ.get("GEOMETRY_DEADLINE_SECONDS", "120")),
        )
    except OrchestrationFailure as exc:
        store.save_run(owner, run_id, exc.evidence)
        exc.details["run_id"] = run_id
        raise
    lineage = {
        "problem_id": request.problem_id,
        "solution_step_id": request.solution_step_id,
        "current_math_step": request.current_math_step,
        "run_id": run_id,
    }
    if previous is None:
        scene = frame.scene_state.model_copy(update={"scene_id": "scene_" + uuid4().hex})
        frame = frame.model_copy(
            update={"scene_state": scene, "svg": render(scene, frame.visual_state)}
        )
    evidence["candidate_scene_id"] = frame.scene_state.scene_id
    evidence["publication_status"] = "REVIEWED_CANDIDATE"
    # Candidate execution is pure; only this final CAS publishes the reviewed version.
    store.save_run(owner, run_id, evidence)
    try:
        saved, replayed = store.commit_candidate(
            frame, owner, request.expected_version, key, lineage, request_body=body
        )
    except GeometryError as exc:
        exc.details["run_id"] = run_id
        raise
    return {
        "scene_id": saved.scene_state.scene_id,
        "version": saved.version,
        "caption": saved.visual_state.caption,
        "current_math_step": request.current_math_step,
        "validation": saved.validation.model_dump(mode="json"),
        "run_id": run_id,
        "replayed": replayed,
        "operations": [
            {"attempt": a["attempt"], "status": a["status"]} for a in evidence["attempts"]
        ],
    }
