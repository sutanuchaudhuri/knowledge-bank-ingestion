"""Owner-authorized geometry orchestration; credentials stay in invocation temp state."""

from __future__ import annotations

import json
import os
import re

import httpx
from google.adk.tools.tool_context import ToolContext

REST_BASE_URL = os.environ.get("MATHBANK_REST_BASE_URL", "http://127.0.0.1:8000")


def _client():
    return httpx.Client(base_url=REST_BASE_URL, timeout=150)


def generate_geometry_scene(
    problem_text: str,
    goal: str,
    tool_context: ToolContext,
    scene_id: str = "",
    expected_version: int = -1,
    current_math_step: str = "",
    context_json: str = "[]",
    solve_attempt_id: str = "",
    solution_step_id: str = "",
) -> dict:
    """Interpret learner-safe geometry intent with reasoning/presentation roles and bounded review.

    Supply exact problem text, current goal and only already-disclosed context facts. Reuse
    the returned scene_id/version for cumulative updates. Does not complete solution steps.
    Paste markdown_block unchanged; do not replace it with invented diagram JSON.
    """
    token = tool_context.state.get("temp:student_token")
    if not token:
        return {
            "error": "SIGN_IN_REQUIRED",
            "message": "Sign in to use saved geometry scenes.",
        }
    if len(context_json) > 20000 or len(problem_text) > 20000 or len(goal) > 2000:
        return {
            "error": "INVALID_GEOMETRY_REQUEST",
            "message": "Geometry context exceeds size limits.",
        }
    try:
        context = json.loads(context_json)
        if (
            not isinstance(context, list)
            or len(context) > 128
            or not all(isinstance(c, dict) for c in context)
        ):
            raise ValueError("Context must be a bounded list of fact objects.")
        if scene_id and (
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", scene_id)
            or expected_version < 0
        ):
            raise ValueError("Use a valid scene ID and expected version.")
    except ValueError as exc:
        return {"error": "INVALID_GEOMETRY_REQUEST", "message": str(exc)}
    body = {
        "problem_text": problem_text,
        "goal": goal,
        "context": context,
        "current_math_step": current_math_step,
    }
    if scene_id:
        body.update(scene_id=scene_id, expected_version=expected_version)
    if solve_attempt_id:
        body["solve_attempt_id"] = solve_attempt_id
    if solution_step_id:
        body["solution_step_id"] = solution_step_id
    headers = {"Authorization": "Bearer " + token}
    call_id = getattr(tool_context, "function_call_id", None)
    if call_id:
        headers["Idempotency-Key"] = "geometry:" + str(call_id)[:180]
    try:
        with _client() as client:
            response = client.post(
                "/v1/geometry-scenes/interpret", json=body, headers=headers
            )
    except httpx.HTTPError as exc:
        return {"error": "GEOMETRY_TRANSPORT_ERROR", "message": type(exc).__name__}
    try:
        result = response.json()
    except ValueError:
        return {
            "error": "GEOMETRY_RESPONSE_INVALID",
            "message": "Geometry service returned a non-JSON response.",
        }
    if not isinstance(result,dict):
        return {"error":"GEOMETRY_RESPONSE_INVALID","message":"Geometry service returned a non-object response."}
    if response.status_code >= 400:
        detail = result.get("detail")
        return {
            "error": detail.get("code", "GEOMETRY_FAILED")
            if isinstance(detail, dict)
            else "GEOMETRY_FAILED",
            "message": detail.get("message")
            if isinstance(detail, dict)
            else str(detail),
            "run_id": detail.get("run_id") if isinstance(detail, dict) else None,
            "status": response.status_code,
        }
    validation=result.get("validation")
    if not isinstance(validation,dict) or validation.get("valid") is not True:
        return {
            "error": "GEOMETRY_NOT_ACCEPTED",
            "message": "No validated frame was accepted.",
        }
    scene=result.get("scene_id")
    version=result.get("version")
    if (
        not isinstance(scene,str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}",scene)
        or not isinstance(version,int) or isinstance(version,bool) or version<0
        or not isinstance(result.get("caption"),str) or len(result["caption"])>2000
        or not isinstance(result.get("current_math_step"),str) or len(result["current_math_step"])>200
    ):
        return {"error":"GEOMETRY_RESPONSE_INVALID","message":"Geometry service returned an invalid accepted-scene reference."}
    block = {
        key: result[key]
        for key in ("scene_id", "version", "caption", "current_math_step")
    }
    tool_context.state["geometry:last_scene"] = {
        "scene_id": result["scene_id"],
        "version": result["version"],
    }
    return {
        **result,
        "markdown_block": "```geometry-scene\n" + json.dumps(block) + "\n```",
    }


GEOMETRY_SCENE_TOOLS = [generate_geometry_scene]
