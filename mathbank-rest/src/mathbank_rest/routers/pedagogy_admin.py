"""Authenticated operator review; decisions never imply automatic publishing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from psycopg import Error as PsycopgError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.db import pedagogy_admin as db
from mathbank_rest.db import topic_pedagogy
from mathbank_rest.security import require_admin_api_key

logger = logging.getLogger(__name__)
Kind = Literal[
    "skill",
    "skill_concept",
    "skill_relation",
    "concept_relation",
    "problem_skill",
    "problem_pedagogy",
    "problem_concept",
    "problem_technique",
]
Status = Literal["PENDING", "REVIEWED", "REJECTED"]
router = APIRouter(
    prefix="/v1/admin/pedagogy",
    tags=["admin pedagogy"],
    dependencies=[Depends(require_admin_api_key)],
)


def validate_note(value: str) -> str:
    if len(value.strip()) < 10:
        raise ValueError("Explain the review decision in at least 10 characters.")
    return value.strip()


class EntityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Kind
    key: dict[str, str]


class FeedbackDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_id: UUID
    status: Literal["RESOLVED", "DISMISSED"]
    note: str = Field(min_length=10, max_length=2000)
    retrieval_verdict: Literal["UNCLASSIFIED", "IRRELEVANT", "RELEVANT"] = "UNCLASSIFIED"
    error_kind: Literal["UNCLASSIFIED", "METADATA", "RETRIEVAL", "INSUFFICIENT_EVIDENCE"] = "UNCLASSIFIED"
    _trimmed_note = field_validator("note")(validate_note)


@router.get("/feedback")
def feedback_queue(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    return call(topic_pedagogy.feedback_queue, limit, offset)


@router.post("/feedback-review")
def feedback_review(body: FeedbackDecision) -> dict:
    result = call(topic_pedagogy.resolve_feedback, body.feedback_id, body.status, body.note,
                  body.retrieval_verdict, body.error_kind)
    if result is None:
        raise HTTPException(409, "Feedback is missing or already reviewed.")
    return {
        **result,
        "message": "Feedback reviewed only. Correct annotations through the revision-checked review workflow and publish explicitly.",
    }


@router.get("/retrieval-examples")
def retrieval_examples(limit: int = Query(100, ge=1, le=500)) -> dict:
    return call(topic_pedagogy.reviewed_retrieval_examples, limit)


class ReviewRequest(EntityRequest):
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_status: Status
    note: str = Field(min_length=10, max_length=2000)

    _trimmed_note = field_validator("note")(validate_note)


class EditRequest(EntityRequest):
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    changes: dict[str, Any]
    note: str = Field(min_length=10, max_length=2000)
    _trimmed_note = field_validator("note")(validate_note)


class ReclassifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_code: str = Field(min_length=1, max_length=200)


class PublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class BulkItem(EntityRequest):
    expected_revision: str = Field(pattern=r"^[a-f0-9]{64}$")


class BulkReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[BulkItem] = Field(min_length=1, max_length=100)
    review_status: Status
    note: str = Field(min_length=10, max_length=2000)

    _trimmed_note = field_validator("note")(validate_note)


class StarterReviewRequest(PublishRequest):
    note: str = Field(min_length=10, max_length=2000)

    _trimmed_note = field_validator("note")(validate_note)


def call(operation: Callable[..., dict], *args: Any) -> dict:
    try:
        return operation(*args)
    except db.MissingMetadata as exc:
        raise HTTPException(404, str(exc)) from exc
    except db.ReviewConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except (
        SQLAlchemyError,
        PsycopgError,
        Neo4jError,
        ServiceUnavailable,
        SessionExpired,
        RuntimeError,
        OSError,
    ) as exc:
        logger.exception("Pedagogy review or publication failed")
        raise HTTPException(
            503,
            (
                "Review/publication failed. Check database connectivity and migrations 006/007. "
                "A Postgres decision does not update Neo4j until publish succeeds; "
                "reload and retry publication if its recording failed after graph commit."
            ),
        ) from exc


@router.get("/queue")
def queue(
    kind: Kind = "skill",
    status: Literal["ALL", "PENDING", "REVIEWED", "REJECTED"] = "PENDING",
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    return call(db.queue, kind, status, limit, offset)


@router.post("/review")
def review(body: ReviewRequest) -> dict:
    return call(
        db.decide, body.kind, body.key, body.expected_revision, body.review_status, body.note
    )


@router.post("/history")
def history(body: EntityRequest) -> dict:
    return call(db.history, body.kind, body.key)


@router.post("/publish")
def publish(body: PublishRequest) -> dict:
    return call(db.publish, body.expected_fingerprint)


@router.post("/bulk-review")
def bulk_review(body: BulkReviewRequest) -> dict:
    return call(
        db.bulk_decide, [item.model_dump() for item in body.items], body.review_status, body.note
    )


@router.post("/approve-starter")
def approve_starter(body: StarterReviewRequest) -> dict:
    return call(db.approve_starter, body.expected_fingerprint, body.note)


@router.post("/edit")
def edit(body: EditRequest) -> dict:
    return call(db.edit, body.kind, body.key, body.expected_revision, body.changes, body.note)


@router.post("/reclassify")
def reclassify(body: ReclassifyRequest) -> dict:
    from mathbank_rest.enrichment import EnrichmentUnavailable, enrich_problem

    try:
        result = enrich_problem(body.problem_code, force=True)
    except EnrichmentUnavailable as exc:
        logger.exception("Admin reclassification failed")
        raise HTTPException(502, str(exc)) from exc
    return {
        **result,
        "message": "Automatic teaching metadata regenerated; human edits and rejected records preserved. Publish to update graph.",
    }
