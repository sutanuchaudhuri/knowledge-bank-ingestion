"""Mount the independent seven-path API; debug evidence is explicitly staff-only."""

from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Path, Query, Request
from geometry_scene.api import make_router
from geometry_scene.errors import GeometryError
from geometry_scene.schemas import SceneInput, StateDelta
from pydantic import BaseModel, Field

from mathbank_rest.geometry_storage import get_geometry_repository
from mathbank_rest.routers.fluid import staff_or_student

Actor = Annotated[dict, Depends(staff_or_student)]


def geometry_owner(actor: Actor) -> str:
    return "admin" if actor["role"] == "ADMIN" else str(actor["student_id"])


def staff(actor: Actor):
    if actor["role"] != "ADMIN":
        raise HTTPException(403, "geometry debug evidence requires staff access")
    return actor


async def authorize_math_status(request: Request, actor: Actor):
    if actor["role"] == "ADMIN" or request.method != "POST":
        return
    if request.url.path != "/v1/geometry-scenes" and not request.url.path.endswith("/deltas"):
        return
    try:
        body = await request.json()
        parsed = (
            SceneInput.model_validate(body)
            if request.url.path == "/v1/geometry-scenes"
            else StateDelta.model_validate(body)
        )
    except ValueError as exc:
        raise HTTPException(
            422, {"code": "INVALID_GEOMETRY", "message": "Invalid structured geometry request."}
        ) from exc
    claims = (
        parsed.relations
        if isinstance(parsed, SceneInput)
        else (*parsed.add_relations, *parsed.change_status)
    )
    if any(claim.status in ("PROVEN", "DISPROVEN") for claim in claims):
        raise HTTPException(
            422,
            {
                "code": "UNTRUSTED_GEOMETRY_STATUS",
                "message": "Learners cannot submit authoritative proof/disproof status; use reviewed interpretation.",
            },
        )


router = make_router(
    geometry_owner,
    get_geometry_repository,
    authorize_math_status,
    expose_solver_diagnostics=False,
)
Store = Annotated[object, Depends(get_geometry_repository)]
RunID = Annotated[str, Path(min_length=1, max_length=200)]
Owner = Annotated[str, Query(min_length=1, max_length=200)]
Staff = Annotated[dict, Depends(staff)]


class Review(BaseModel):
    decision: Literal["ACCEPTED", "REJECTED", "NEEDS_REVISION"]
    note: str = Field(default="", max_length=4000)


def _call(fn, *args):
    try:
        return fn(*args)
    except GeometryError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from None


@router.get("/debug/runs/{run_id}")
def read_run(run_id: RunID, owner: Owner, _: Staff, store: Store):
    return _call(store.read_run, owner, run_id)


@router.get("/debug/runs")
def list_runs(
    owner: Owner, _: Staff, store: Store, limit: Annotated[int, Query(ge=1, le=100)] = 50
):
    return {"runs": _call(store.list_runs, owner, limit)}


@router.post("/debug/runs/{run_id}/review")
def review_run(run_id: RunID, owner: Owner, body: Review, _: Staff, store: Store):
    return _call(store.review_run, owner, run_id, body.model_dump())
