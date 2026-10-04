"""Anonymous read-only teaching context and provisional coaching contracts."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import pedagogy

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/tutor", tags=["pedagogy"])


def _call(operation: Callable[..., dict], *args: Any) -> dict:
    try:
        return operation(*args)
    except pedagogy.UnknownLearningEntity as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except pedagogy.CoachingUnavailable as exc:
        logger.exception("Provisional coaching unavailable")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (Neo4jError, ServiceUnavailable, SessionExpired, SQLAlchemyError) as exc:
        logger.exception("Pedagogical data service unavailable")
        raise HTTPException(
            status_code=503, detail="Learning data is unavailable; check database connectivity."
        ) from exc


@router.get("/learning-context/{problem_code}")
def learning_context(problem_code: str) -> dict:
    return _call(pedagogy.learning_context, problem_code)


@router.get("/prerequisites/{skill_slug}")
def prerequisites(skill_slug: str, max_depth: int = Query(default=4, ge=1, le=8)) -> dict:
    return _call(pedagogy.prerequisite_path, skill_slug, max_depth)


@router.get("/practice/{problem_code}")
def practice(problem_code: str, limit: int = Query(default=5, ge=1, le=20)) -> dict:
    return _call(pedagogy.easier_practice, problem_code, limit)


@router.post("/coach")
def coach(body: pedagogy.CoachRequest) -> dict:
    return _call(pedagogy.coach, body)
