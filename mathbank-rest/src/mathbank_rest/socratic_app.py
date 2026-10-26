"""Isolated Socratic API and same-origin SPA; no legacy admin/learner routes."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest import socratic_auth
from mathbank_rest.db.postgres import engine
from mathbank_rest.routers.socratic import router

app = FastAPI(title="MathBank Socratic Studio", version="0.1.0", docs_url=None, redoc_url=None,
              description="Prototype draft persistence only. No evaluation, model jobs or publication.")
app.include_router(router)


@app.middleware("http")
async def response_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    )
    if request.url.path.startswith("/v1/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/health")
def health():
    """Check configured auth and exact isolated tables, not user data or provider login."""
    socratic_auth.configured()
    try:
        with engine.begin() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '5s'"))
            ready = conn.execute(text("""
                SELECT bool_and(to_regclass(name) IS NOT NULL)
                FROM unnest(ARRAY[
                    'orchestration.socratic_strategy','orchestration.socratic_workflow',
                    'orchestration.socratic_revision','orchestration.socratic_command',
                    'orchestration.socratic_preview','orchestration.socratic_preview_event'
                ]) AS names(name)
            """)).scalar_one()
        if not ready:
            raise HTTPException(503, "Socratic schema is not ready.")
    except SQLAlchemyError:
        raise socratic_auth.fail(503, "SOCRATIC_STORAGE_UNAVAILABLE", "Draft storage is unavailable.") from None
    return {"ok": True, "prototype_only": True, "evaluation_available": True,
            "evaluation_scope": "SYNTHETIC_PREVIEW_DETERMINISTIC", "model_jobs_available": False}


static_dir = Path(os.environ.get("SOCRATIC_STATIC_DIR", "/var/task/studio"))
if static_dir.is_dir():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="studio")
