"""Reviewed instructional routes: protected draft review and learner-owned assets."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import route_runtime
from mathbank_rest.db.postgres import engine
from mathbank_rest.route_contracts import RouteProgram
from mathbank_rest.security import get_current_student_id, require_admin_api_key
from mathbank_rest.step_runtime import RuntimeError_

router = APIRouter(prefix="/v1", tags=["tutoring-routes"])


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewer: str = Field(min_length=3, max_length=200, pattern=r"^\S.*\S$")
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    mathematical_review_confirmed: Literal[True]


class EditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    program: RouteProgram


class StartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{2,119}$")
    route_release_id: UUID | None = None


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    hint_level: int = Field(ge=1, le=5, strict=True)
    advance: bool = False


def call(operation, *args):
    try:
        with engine.begin() as conn:
            return operation(conn, *args)
    except RuntimeError_ as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from exc
    except SQLAlchemyError as exc:
        import logging

        logging.getLogger(__name__).exception("Instructional route data unavailable")
        raise HTTPException(503, "Instructional route data unavailable.") from exc
    except ValueError as exc:
        raise HTTPException(
            422, "Route validation failed; reload the draft before review."
        ) from exc


@router.get("/admin/tutoring-routes", dependencies=[Depends(require_admin_api_key)])
def drafts(limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)):
    def load(conn):
        return {
            "releases": [
                dict(row)
                for row in conn.execute(
                    text("""
            SELECT r.route_release_id,r.solution_id,p.canonical_code,r.release_version,
                   r.status,r.content_hash,r.approach_name,r.created_at,r.reviewed_by,
                   (SELECT count(*) FROM pedagogy.route_step st WHERE st.route_release_id=r.route_release_id) AS steps
            FROM pedagogy.solution_route_release r JOIN core.problem p USING(problem_id)
            ORDER BY r.created_at DESC,r.route_release_id LIMIT :limit OFFSET :offset
        """),
                    {"limit": limit, "offset": offset},
                ).mappings()
            ],
            "total": conn.execute(
                text("SELECT count(*) FROM pedagogy.solution_route_release")
            ).scalar_one(),
        }

    return call(load)


@router.get("/admin/tutoring-routes/{release_id}", dependencies=[Depends(require_admin_api_key)])
def preview(release_id: UUID):
    def load(conn):
        row = (
            conn.execute(
                text("""
            SELECT * FROM pedagogy.solution_route_release WHERE route_release_id=:id
        """),
                {"id": release_id},
            )
            .mappings()
            .first()
        )
        if not row:
            from mathbank_rest.step_runtime import NotFound

            raise NotFound("Route release not found.")
        source = (
            conn.execute(
                text("""
            SELECT p.canonical_code,p.statement_text,s.verification_status,
                   coalesce(nullif(trim(s.body_markdown),''),s.body_latex) AS solution
            FROM core.solution s JOIN core.problem p USING(problem_id) WHERE s.solution_id=:sid
        """),
                {"sid": row["solution_id"]},
            )
            .mappings()
            .one()
        )
        return {
            "release": dict(row),
            "source": dict(source),
            "program": route_runtime.load_program(conn, str(release_id)).model_dump(),
            "step_generation_metadata": [
                dict(step)
                for step in conn.execute(
                    text("""
                    SELECT step_index,generation_metadata FROM pedagogy.route_step
                    WHERE route_release_id=:r ORDER BY step_index
                """),
                    {"r": release_id},
                ).mappings()
            ],
        }

    return call(load)


@router.post(
    "/admin/tutoring-routes/{release_id}/review", dependencies=[Depends(require_admin_api_key)]
)
def review(release_id: UUID, body: ReviewRequest):
    return call(route_runtime.review, release_id, body.reviewer, body.expected_hash)


@router.post(
    "/admin/tutoring-routes/{release_id}/publish", dependencies=[Depends(require_admin_api_key)]
)
def publish(release_id: UUID):
    return call(route_runtime.publish, release_id)


@router.post(
    "/admin/tutoring-routes/{release_id}/edit", dependencies=[Depends(require_admin_api_key)]
)
def edit(release_id: UUID, body: EditRequest):
    return call(route_runtime.edit, release_id, body.expected_hash, body.program)


@router.post("/admin/tutoring-routes/refresh-graph", dependencies=[Depends(require_admin_api_key)])
def refresh_graph():
    from neo4j.exceptions import Neo4jError

    from mathbank_rest.route_projection import project

    try:
        return project()
    except (SQLAlchemyError, Neo4jError, ValueError) as exc:
        import logging

        logging.getLogger(__name__).exception("Instructional route graph refresh failed")
        raise HTTPException(503, "Graph refresh failed; publication is not graph parity.") from exc


@router.post("/tutor/route-attempts", status_code=201)
def start(body: StartRequest, student: Annotated[UUID, Depends(get_current_student_id)]):
    return call(route_runtime.start_attempt, student, body.problem_code, body.route_release_id)


@router.get("/tutor/route-attempts/{attempt_id}")
def current(attempt_id: UUID, student: Annotated[UUID, Depends(get_current_student_id)]):
    def load(conn):
        return route_runtime.current_view(
            conn, route_runtime.owned_attempt(conn, student, attempt_id)
        )

    return call(load)


@router.post("/tutor/route-attempts/{attempt_id}/assist")
def assist(
    attempt_id: UUID, body: AssistRequest, student: Annotated[UUID, Depends(get_current_student_id)]
):
    return call(
        route_runtime.assist,
        student,
        attempt_id,
        body.expected_version,
        body.hint_level,
        body.advance,
    )
