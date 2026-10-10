"""Admin REST surface for the interaction template library
(requirements/41_INTERACTION_TEMPLATE_LIBRARY.md ITL-13, docs/09_API_CONTRACTS.md).
Mirrors the CLI (interactions_cli.py) via the same service-layer functions —
neither re-implements validation or persistence independently (ITL-13).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import interaction_catalog, interaction_validators
from mathbank_rest.db.postgres import engine
from mathbank_rest.security import require_admin_api_key

router = APIRouter(
    prefix="/v1/admin/interaction-templates",
    tags=["interaction-templates"],
    dependencies=[Depends(require_admin_api_key)],
)


class PublishResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    errors: list[str] = []


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
