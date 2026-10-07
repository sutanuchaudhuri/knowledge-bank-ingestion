"""Student-scoped artifact tools: deterministic REST only, never generation or paid indexing."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from google.adk.tools.tool_context import ToolContext

from .step_runtime_tools import _call


def search_artifacts(
    query: str, tool_context: ToolContext, subject: str = "", limit: int = 10
) -> dict[str, Any]:
    """Find published reusable SVG/LaTeX artifacts by lexical query, without paid embeddings."""
    if len(query) > 2000 or not 1 <= limit <= 100:
        return {
            "error": "INVALID_SEARCH",
            "message": "query max 2000 characters; limit 1–100",
        }
    body: dict[str, Any] = {"query": query, "limit": limit}
    if subject:
        if subject not in ("GEOMETRY", "ALGEBRA", "COMBINATORICS", "NUMBER_THEORY"):
            return {"error": "INVALID_SUBJECT"}
        body["subject"] = subject
    return _call(tool_context, "POST", "/v1/artifacts/search", json=body)


def get_artifact_bundle(bundle_id: str, tool_context: ToolContext) -> dict[str, Any]:
    """Read a published bundle, its mediated private asset paths and ordered instructional frames."""
    try:
        identifier = str(UUID(bundle_id))
    except ValueError:
        return {"error": "INVALID_BUNDLE_ID"}
    path = f"/v1/artifacts/bundles/{identifier}"
    bundle = _call(tool_context, "GET", path)
    if "error" in bundle:
        return bundle
    assets = _call(tool_context, "GET", path + "/assets")
    if "error" in assets:
        return assets
    frames = _call(tool_context, "GET", path + "/frames")
    if "error" in frames:
        return frames
    return {"bundle": bundle, "assets": assets["assets"], "frame_sequence": frames}


def request_artifact(plan_json: str, tool_context: ToolContext) -> dict[str, Any]:
    """Submit a structured flat ArtifactPlan for staff generation; never claim a bundle was generated.

    The JSON requires subject, topic, title and typed elements. Staff must explicitly generate and
    publish the request before students can reuse its assets. This tool never calls a model.
    """
    if len(plan_json) > 128000:
        return {"error": "PLAN_TOO_LARGE"}
    try:
        plan = json.loads(plan_json)
    except ValueError:
        return {"error": "INVALID_PLAN_JSON"}
    if not isinstance(plan, dict):
        return {"error": "INVALID_PLAN_JSON"}
    return _call(tool_context, "POST", "/v1/artifacts/requests", json=plan)


def draw_geometry_diagram(plan_json: str, tool_context: ToolContext) -> dict[str, Any]:
    """Draw a generated illustrative diagram now using the geometry artifact capability.

    No staff publication or paid provider is needed. Return markdown_block verbatim to display it.
    plan_json is a flat geometry ArtifactPlan: subject GEOMETRY, topic, title, width/height,
    elements with POINT {kind,id,x,y,label}, SEGMENT {kind,id,start,end,auxiliary},
    CIRCLE {kind,id,cx,cy,radius}. Points need generous margins and label spacing.
    Optional incircle_triangles [[A,B,C],...] computes TRUE incircles from named vertices;
    never guess their centers/radii. Draw triangle sides/diagonals as segments too.
    summary explains that this is GENERATED, not the source figure; arbitrary sketches need
    not satisfy every hypothesis and are not proof. Do not draw the conclusion (e.g. rectangle,
    right-angle marks) as though given. Light circles, vertex dots, offset labels and dashed
    auxiliary segments are rendered by the shared geometry rule profile.
    """
    if len(plan_json) > 128000:
        return {"error": "PLAN_TOO_LARGE", "message": "Use a smaller geometry plan"}
    try:
        plan = json.loads(plan_json)
    except ValueError:
        return {
            "error": "INVALID_PLAN_JSON",
            "message": "A geometry plan must be a JSON object",
        }
    if not isinstance(plan, dict):
        return {
            "error": "INVALID_PLAN_JSON",
            "message": "A geometry plan must be a JSON object",
        }
    return _call(tool_context, "POST", "/v1/artifacts/geometry-preview", json=plan)


ARTIFACT_TOOLS = [
    search_artifacts,
    get_artifact_bundle,
    request_artifact,
    draw_geometry_diagram,
]


def validate_artifact_plan(plan_json: str, tool_context: ToolContext) -> dict[str, Any]:
    """Validate an exact flat ArtifactPlan using authoritative REST rules; no model or writes."""
    return _plan_command(plan_json, tool_context, "/v1/artifacts/validate")


def preview_artifact(plan_json: str, tool_context: ToolContext) -> dict[str, Any]:
    """Render a validated algebra/combinatorics/number-theory plan without staff publication.

    Return the exact markdown_block for chat. Rendering is private and deterministic.
    """
    return _plan_command(plan_json, tool_context, "/v1/artifacts/preview")


def _plan_command(plan_json: str, tool_context: ToolContext, path: str) -> dict[str, Any]:
    if len(plan_json) > 128000:
        return {"error": "PLAN_TOO_LARGE", "message": "Use a smaller structured plan."}
    try:
        plan = json.loads(plan_json)
    except ValueError:
        return {"error": "INVALID_PLAN_JSON", "message": "An artifact plan must be a JSON object."}
    if not isinstance(plan, dict):
        return {"error": "INVALID_PLAN_JSON", "message": "An artifact plan must be a JSON object."}
    return _call(tool_context, "POST", path, json=plan)
