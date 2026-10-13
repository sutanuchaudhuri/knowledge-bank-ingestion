from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from geometry_scene.errors import GeometryError
from geometry_scene.orchestration import GeometryRequest

from mathbank_rest import step_runtime
from mathbank_rest.db.postgres import engine
from mathbank_rest.geometry_orchestration import interpret
from mathbank_rest.routers.fluid import staff_or_student
from mathbank_rest.routers.geometry_scenes import geometry_owner, get_geometry_repository

router = APIRouter(prefix="/v1/geometry-scenes", tags=["geometry-agent"])


@router.post("/interpret")
def interpret_scene(
    body: GeometryRequest,
    owner: Annotated[str, Depends(geometry_owner)],
    store: Annotated[object, Depends(get_geometry_repository)],
    actor: Annotated[dict, Depends(staff_or_student)],
    idempotency_key: str | None = Header(default=None, max_length=200),
):
    try:
        if actor["role"] != "ADMIN" and body.trusted_facts:
            raise GeometryError("learner requests cannot supply authoritative PROVEN facts")
        if body.solve_attempt_id:
            if actor["role"] != "STUDENT":
                raise GeometryError("attempt-bound geometry requires the owning learner")
            with engine.connect() as conn:
                runtime = step_runtime.get_runtime(conn, body.solve_attempt_id, UUID(owner))
            attempt = runtime["attempt"]
            current = runtime.get("current_step") or {}
            statement = attempt.get("statement_text") or body.problem_text
            step_id = current.get("solution_step_id")
            if body.solution_step_id and body.solution_step_id != step_id:
                raise GeometryError("geometry must bind to the current learner-visible step")
            if statement != body.problem_text:
                raise GeometryError("geometry problem text does not match the owned attempt")
            body = body.model_copy(
                update={
                    "problem_id": str(attempt["problem_id"]) if attempt.get("problem_id") else None,
                    "solution_step_id": step_id,
                    "current_math_step": current.get("goal") or body.current_math_step,
                }
            )
        return interpret(body, store, owner, idempotency_key)
    except GeometryError as exc:
        detail = {"code": exc.code, "message": str(exc)}
        if isinstance(exc.details.get("run_id"), str):
            detail["run_id"] = exc.details["run_id"]
        raise HTTPException(exc.status_code, detail) from exc
    except step_runtime.RuntimeError_ as exc:
        raise HTTPException(exc.status_code, {"code": exc.code, "message": str(exc)}) from exc
