"""FastAPI entry point for mathbank-ml-inference (requirements/56).

Run with `make start` (see Makefile) or directly:
    uvicorn mathbank_ml_inference.main:app --reload --port 8010
"""
from __future__ import annotations

from fastapi import FastAPI

from mathbank_ml_inference.routers import admin, student, tutor_policy

app = FastAPI(
    title="mathbank-ml-inference",
    description=(
        "Online inference service for the IntelliTutor ML/RL platform "
        "(requirements/54, requirements/56). Serves predictions/recommendations/"
        "tutor-action scores from already-trained, approved models — never trains. "
        "Every endpoint is currently scaffolded only (returns 501 MLUnavailable); "
        "see requirements/56 for the per-endpoint status table."
    ),
    version="0.1.0",
)

app.include_router(student.router)
app.include_router(admin.router)
app.include_router(tutor_policy.router)


@app.get("/health")
def health() -> dict:
    """Trivial liveness check — does not verify DB connectivity yet.
    TODO: add a real Postgres connectivity check once db.py has implemented functions to
    check against, matching mathbank-rest's own `/health` convention."""
    return {"status": "ok", "service": "mathbank-ml-inference", "implemented": False}
