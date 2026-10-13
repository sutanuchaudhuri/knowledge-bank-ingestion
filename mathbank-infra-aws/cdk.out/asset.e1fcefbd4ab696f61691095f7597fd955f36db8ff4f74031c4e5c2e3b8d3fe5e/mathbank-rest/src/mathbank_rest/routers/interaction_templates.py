"""Admin REST surface for the interaction template library
(requirements/41_INTERACTION_TEMPLATE_LIBRARY.md ITL-13, docs/09_API_CONTRACTS.md).
Mirrors the CLI (interactions_cli.py) via the same service-layer functions —
neither re-implements validation or persistence independently (ITL-13).
"""

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import interaction_catalog, interaction_validators, object_store
from mathbank_rest.db.postgres import engine
from mathbank_rest.scene_spec_promotion import (
    PromotionError,
    approve_scene_and_validate_asset,
    create_video_explainer_instance,
    list_promotable_candidates,
    promote_render_job,
)
from mathbank_rest.security import require_admin_api_key

router = APIRouter(
    prefix="/v1/admin/interaction-templates",
    tags=["admin-interaction-templates"],
    dependencies=[Depends(require_admin_api_key)],
)


class PublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    errors: list[str] = []


class PromoteSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    render_job_id: str
    canonical_code: str
    created_by: str = "admin"


class CreateInstanceFromSceneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    canonical_code: str
    title: str
    learning_objective: str
    created_by: str = "admin"
    concept_slugs: list[str] = []
    technique_slugs: list[str] = []


def _call(operation, *args):
    try:
        with engine.begin() as conn:
            return operation(conn, *args)
    except SQLAlchemyError as exc:
        import logging

        logging.getLogger(__name__).exception("Interaction template data unavailable")
        raise HTTPException(503, "Interaction template data unavailable.") from exc


@router.get("")
def list_templates():
    return _call(interaction_catalog.list_templates)


@router.post("/load-seed-catalog")
def load_seed_catalog():
    """Idempotently (re)loads the bundled control/icon/animation/template
    catalog vocabulary. Safe to call repeatedly — never duplicates rows."""
    return _call(interaction_catalog.load_all)


@router.post("/versions/{version_id}/validate")
def validate_template_version(version_id: UUID):
    errors = _call(interaction_validators.validate_interaction_template_version, str(version_id))
    return PublishResult(status="VALID" if not errors else "REJECTED", errors=errors)


@router.post("/versions/{version_id}/publish")
def publish_template_version(version_id: UUID):
    errors = _call(interaction_validators.validate_interaction_template_version, str(version_id))
    if errors:
        return PublishResult(status="REJECTED", errors=errors)

    def do_publish(conn):
        conn.execute(
            text("""
            UPDATE visual.interaction_template_version
            SET status='PUBLISHED', published_at=now() WHERE interaction_template_version_id=:id AND status IN ('DRAFT','REVIEWED')
        """),
            {"id": str(version_id)},
        )

    _call(do_publish)
    return PublishResult(status="PUBLISHED")


@router.post("/instances/{instance_id}/validate")
def validate_instance(instance_id: UUID):
    errors = _call(interaction_validators.validate_interaction_instance, str(instance_id))
    return PublishResult(status="VALID" if not errors else "REJECTED", errors=errors)


@router.post("/instances/{instance_id}/approve")
def approve_instance(instance_id: UUID):
    errors = _call(interaction_validators.validate_interaction_instance, str(instance_id))
    if errors:
        return PublishResult(status="REJECTED", errors=errors)

    def do_approve(conn):
        conn.execute(
            text("""
            UPDATE visual.interaction_instance SET review_status='APPROVED', approved_at=now()
            WHERE interaction_instance_id=:id AND review_status='PENDING_REVIEW'
        """),
            {"id": str(instance_id)},
        )

    _call(do_approve)
    return PublishResult(status="APPROVED")


@router.get("/scenes/promotable-candidates")
def list_promotable_candidates_endpoint():
    """DONE, unpromoted render jobs from the Manim Video Studio (requirements/60 §7) —
    the admin review queue for the "promote to canonical catalog" workflow."""
    try:
        return _call(list_promotable_candidates)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Manim Video Studio is unavailable.") from exc


@router.get("/scenes")
def list_scenes():
    return _call(
        lambda conn: [
            dict(row)
            for row in conn.execute(
                text("""
                    SELECT scene_spec_id, canonical_code, version, status,
                           rendered_video_asset_id, source_studio_job_id, created_by,
                           created_at, approved_by, approved_at
                    FROM visual.scene_spec ORDER BY created_at DESC
                """)
            ).mappings().all()
        ]
    )


@router.get("/scenes/{scene_spec_id}")
def get_scene(scene_spec_id: UUID):
    def do_get(conn):
        row = conn.execute(
            text("SELECT * FROM visual.scene_spec WHERE scene_spec_id = :id"),
            {"id": str(scene_spec_id)},
        ).mappings().one_or_none()
        if row is None:
            raise HTTPException(404, "scene not found")
        result = dict(row)
        if result.get("rendered_video_asset_id"):
            asset = conn.execute(
                text("SELECT uri, mime_type, object_size_bytes FROM visual.asset "
                     "WHERE asset_id = :id"),
                {"id": result["rendered_video_asset_id"]},
            ).mappings().one_or_none()
            result["rendered_video"] = dict(asset) if asset else None
        return result

    return _call(do_get)


@router.get("/scenes/{scene_spec_id}/video")
def get_scene_video(scene_spec_id: UUID):
    def do_get(conn):
        asset = conn.execute(
            text("""
                SELECT a.uri FROM visual.scene_spec s
                JOIN visual.asset a ON a.asset_id = s.rendered_video_asset_id
                WHERE s.scene_spec_id = :id
            """),
            {"id": str(scene_spec_id)},
        ).scalar_one_or_none()
        if asset is None:
            raise HTTPException(404, "scene has no rendered video")
        key = asset.removeprefix("object-store:")
        return object_store.read_bytes(key)

    data = _call(do_get)
    return Response(content=data, media_type="video/mp4")


@router.post("/scenes/promote")
def promote_scene(request: PromoteSceneRequest):
    try:
        scene_spec_id = promote_render_job(
            render_job_id=request.render_job_id, canonical_code=request.canonical_code,
            created_by=request.created_by,
        )
    except PromotionError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (httpx.HTTPError, SQLAlchemyError) as exc:
        raise HTTPException(503, "Manim Video Studio or its data is unavailable.") from exc
    return {"scene_spec_id": scene_spec_id, "status": "DRAFT"}


@router.post("/scenes/{scene_spec_id}/validate")
def validate_scene(scene_spec_id: UUID):
    errors = _call(interaction_validators.validate_scene_spec, str(scene_spec_id))
    return PublishResult(status="VALID" if not errors else "REJECTED", errors=errors)


@router.post("/scenes/{scene_spec_id}/approve")
def approve_scene(scene_spec_id: UUID, approved_by: str = "admin"):
    errors = _call(interaction_validators.validate_scene_spec, str(scene_spec_id))
    if errors:
        return PublishResult(status="REJECTED", errors=errors)

    def do_approve(conn):
        conn.execute(
            text("""
                UPDATE visual.scene_spec SET status='APPROVED', approved_by=:approved_by,
                       approved_at=now()
                WHERE scene_spec_id=:id AND status='DRAFT'
            """),
            {"id": str(scene_spec_id), "approved_by": approved_by},
        )
        approve_scene_and_validate_asset(conn, str(scene_spec_id), approved_by)

    _call(do_approve)
    return PublishResult(status="APPROVED")


@router.post("/scenes/{scene_spec_id}/create-instance")
def create_instance_from_scene(scene_spec_id: UUID, request: CreateInstanceFromSceneRequest):
    try:
        instance_id = _call(
            lambda conn: create_video_explainer_instance(
                conn, scene_spec_id=str(scene_spec_id), canonical_code=request.canonical_code,
                title=request.title, learning_objective=request.learning_objective,
                created_by=request.created_by, concept_slugs=request.concept_slugs,
                technique_slugs=request.technique_slugs,
            )
        )
    except PromotionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"interaction_instance_id": instance_id, "review_status": "PENDING_REVIEW"}


@router.post("/graph/rebuild")
def rebuild_graph():
    from neo4j.exceptions import Neo4jError

    from mathbank_rest import interaction_template_projection as itp

    try:
        return itp.project()
    except (SQLAlchemyError, Neo4jError, ValueError) as exc:
        import logging

        logging.getLogger(__name__).exception("Interaction-template graph rebuild failed")
        raise HTTPException(503, f"Graph rebuild failed: {type(exc).__name__}") from exc


@router.get("/graph/verify")
def verify_graph():
    from mathbank_rest import interaction_template_projection as itp

    return itp.verify()
