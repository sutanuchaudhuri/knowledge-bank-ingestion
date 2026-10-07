"""Authenticated artifact commands. Mount this router in the service's main application.

Requests accept ArtifactPlan (subject/topic/title and typed elements, optional overlays/frames).
Generation returns a bundle ID; assets return authenticated content_path values, never store keys.
Frames are reset-to-base declarative actions with stable element IDs and step/explanation metadata.
Students own requests and read published bundles; staff alone generate, publish and index bundles.
Semantic calls accept a supplied 1536-vector or explicit generate_embedding=true. Missing eligible
index vectors/provider output are reported UNAVAILABLE, never replaced with lexical results.
"""

from __future__ import annotations

import json
import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import Field

from mathbank_rest import artifact_runtime as runtime
from mathbank_rest import object_store, security
from mathbank_rest.db.postgres import engine
from mathbank_rest.routers.fluid import staff_or_student

router = APIRouter(prefix="/v1/artifacts", tags=["artifacts"])
Actor = Annotated[dict, Depends(staff_or_student)]


class GeometryPreview(runtime.ArtifactPlan):
    incircle_triangles: list[
        Annotated[list[runtime.Identifier], Field(min_length=3, max_length=3)]
    ] = Field(default_factory=list, max_length=8)


@router.post("/preview")
def preview(body: runtime.ArtifactPlan, actor: Actor) -> dict:
    try:
        generated = runtime.generate(body)
    except runtime.ArtifactError as exc:
        raise HTTPException(
            exc.status_code, detail={"code": exc.code, "message": str(exc)}
        ) from None
    return {
        "validation": generated["validation"],
        "rule_profile_id": generated["rule_profile_id"],
        "markdown_block": "```artifact-preview\n"
        + json.dumps(body.model_dump(mode="json"))
        + "\n```",
    }


@router.post("/preview/content")
def preview_content(body: runtime.ArtifactPlan, actor: Actor) -> Response:
    try:
        generated = runtime.generate(body)
    except runtime.ArtifactError as exc:
        raise HTTPException(
            exc.status_code, detail={"code": exc.code, "message": str(exc)}
        ) from None
    svg = next(
        asset["data"] for asset in generated["assets"] if asset["mime_type"] == "image/svg+xml"
    )
    return Response(
        svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


def _geometry_preview(body: GeometryPreview) -> dict:
    if body.subject != "GEOMETRY":
        raise HTTPException(422, detail={"code": "GEOMETRY_REQUIRED"})
    points = {p.id: p for p in body.elements if isinstance(p, runtime.Point)}
    elements = list(body.elements)
    for index, triangle in enumerate(body.incircle_triangles):
        if len(set(triangle)) != 3 or any(identifier not in points for identifier in triangle):
            raise HTTPException(422, detail={"code": "INVALID_INCIRCLE_TRIANGLE"})
        a, b, c = [points[identifier] for identifier in triangle]
        sides = [
            math.hypot(b.x - c.x, b.y - c.y),
            math.hypot(a.x - c.x, a.y - c.y),
            math.hypot(a.x - b.x, a.y - b.y),
        ]
        perimeter = sum(sides)
        twice_area = abs((b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x))
        if twice_area < 1 or perimeter == 0:
            raise HTTPException(422, detail={"code": "DEGENERATE_INCIRCLE_TRIANGLE"})
        elements.append(
            runtime.Circle(
                kind="CIRCLE",
                id=f"incircle_{index + 1}",
                cx=sum(p.x * s for p, s in zip((a, b, c), sides)) / perimeter,
                cy=sum(p.y * s for p, s in zip((a, b, c), sides)) / perimeter,
                radius=twice_area / perimeter,
            )
        )
    payload = body.model_dump(exclude={"incircle_triangles"})
    payload["elements"] = [element.model_dump() for element in elements]
    try:
        return runtime.generate(runtime.ArtifactPlan.model_validate(payload))
    except runtime.ArtifactError as exc:
        raise HTTPException(
            exc.status_code, detail={"code": exc.code, "message": str(exc)}
        ) from None


@router.post("/geometry-preview")
def geometry_preview(body: GeometryPreview, actor: Actor) -> dict:
    """Private, ephemeral drawing; never publishes, stores, or calls a paid provider."""
    generated = _geometry_preview(body)
    return {
        "validation": generated["validation"],
        "rule_profile_id": generated["rule_profile_id"],
        "markdown_block": "```geometry-artifact\n"
        + json.dumps(body.model_dump(mode="json"))
        + "\n```",
    }


@router.post("/geometry-preview/content")
def geometry_preview_content(body: GeometryPreview, actor: Actor) -> Response:
    generated = _geometry_preview(body)
    svg = next(
        asset["data"] for asset in generated["assets"] if asset["mime_type"] == "image/svg+xml"
    )
    return Response(
        svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.get("/embedding-profile")
def embedding_profile(actor: Actor) -> dict:
    try:
        return {"status": "AVAILABLE", **runtime.embedding_profile()}
    except runtime.ArtifactError as exc:
        return {"status": "UNAVAILABLE", "reason": exc.code}


def _run(fn, *args, object_keys: list[str] | None = None, **kwargs):
    try:
        with engine.begin() as conn:
            return fn(conn, *args, **kwargs)
    except Exception as exc:
        # SQL rollback cannot roll back a filesystem write. Remove only this command's objects.
        for key in object_keys or []:
            try:
                object_store.delete_object(key)
            except OSError:
                pass
        if isinstance(exc, runtime.ArtifactError):
            raise HTTPException(
                status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}
            ) from None
        if isinstance(exc, object_store.ObjectStoreError):
            raise HTTPException(
                status_code=503, detail={"code": "OBJECT_STORE_UNAVAILABLE", "message": str(exc)}
            ) from None
        raise


@router.post("/requests", status_code=201)
def request_artifact(body: runtime.ArtifactPlan, actor: Actor) -> dict:
    return _run(runtime.create_request, body, actor)


@router.get("/requests/{request_id}")
def get_request(request_id: UUID, actor: Actor) -> dict:
    return _run(runtime.get_request, request_id, actor)


@router.post(
    "/requests/{request_id}/generate", dependencies=[Depends(security.require_admin_api_key)]
)
def generate(request_id: UUID, body: runtime.GenerateBody) -> dict:
    keys: list[str] = []
    return _run(
        runtime.generate_request,
        request_id,
        {"role": "ADMIN", "student_id": None},
        body.publish,
        keys,
        object_keys=keys,
    )


@router.get("/bundles/{bundle_id}")
def get_bundle(bundle_id: UUID, actor: Actor) -> dict:
    return _run(runtime.get_bundle, bundle_id, actor)


@router.get("/bundles/{bundle_id}/assets")
def assets(bundle_id: UUID, actor: Actor) -> dict:
    rows = _run(runtime.list_assets, bundle_id, actor)
    for row in rows:
        row["content_path"] = (
            f"/v1/artifacts/bundles/{bundle_id}/assets/{row['artifact_asset_id']}/content"
        )
    return {"assets": rows}


@router.get("/bundles/{bundle_id}/assets/{asset_id}/content")
def asset_content(bundle_id: UUID, asset_id: UUID, actor: Actor) -> Response:
    metadata, data = _run(runtime.asset_bytes, bundle_id, asset_id, actor)
    return Response(
        content=data,
        media_type=metadata["mime_type"],
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Content-Disposition": f'inline; filename="{asset_id}.{metadata["render_format"].lower()}"',
        },
    )


@router.get("/bundles/{bundle_id}/frames")
def frames(bundle_id: UUID, actor: Actor) -> dict:
    return _run(runtime.get_frames, bundle_id, actor)


@router.get("/bundles/{bundle_id}/frames/{ordinal}/content")
def frame_content(
    bundle_id: UUID, ordinal: Annotated[int, Path(ge=0, le=127)], actor: Actor
) -> Response:
    data = _run(runtime.frame_svg, bundle_id, ordinal, actor)
    return Response(
        content=data,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.post("/validate")
def validate(body: runtime.ArtifactPlan, actor: Actor) -> dict:
    return runtime.validate_plan(body)


@router.post("/bundles/{bundle_id}/validate")
def validate_bundle(bundle_id: UUID, actor: Actor) -> dict:
    return _run(runtime.validate_bundle, bundle_id, actor)


@router.post("/bundles/{bundle_id}/publish", dependencies=[Depends(security.require_admin_api_key)])
def publish(bundle_id: UUID) -> dict:
    return _run(runtime.publish_bundle, bundle_id, {"role": "ADMIN", "student_id": None})


@router.post("/bundles/{bundle_id}/index", dependencies=[Depends(security.require_admin_api_key)])
def index(bundle_id: UUID, body: runtime.IndexBody) -> dict:
    return _run(runtime.index_bundle, bundle_id, body, {"role": "ADMIN", "student_id": None})


@router.post("/search")
def search(body: runtime.SearchBody, actor: Actor) -> dict:
    return _run(runtime.search, body, actor)


@router.post("/search/semantic")
def semantic_search(body: runtime.SearchBody, actor: Actor) -> dict:
    return _run(runtime.search, body, actor, semantic=True)


@router.post("/bundles/{bundle_id}/similar")
def similar(bundle_id: UUID, body: runtime.SearchBody, actor: Actor) -> dict:
    return _run(runtime.similar, bundle_id, body, actor)
