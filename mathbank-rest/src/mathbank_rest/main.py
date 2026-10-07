"""FastAPI app: health + per-database connectivity checks."""
from __future__ import annotations

from fastapi import FastAPI, Response, status

from mathbank_rest.db.graph import check_neo4j
from mathbank_rest.db.postgres import check_postgres
from mathbank_rest.routers.admin import router as admin_router
from mathbank_rest.routers.admin_imports import router as admin_imports_router
from mathbank_rest.routers.admin_textbooks import router as admin_textbooks_router
from mathbank_rest.routers.agent_sessions import router as agent_sessions_router
from mathbank_rest.routers.fluid import router as fluid_router
from mathbank_rest.routers.learner import router as learner_router
from mathbank_rest.routers.live import router as live_router
from mathbank_rest.routers.attempt_media import router as attempt_media_router
from mathbank_rest.routers.artifacts import router as artifacts_router
from mathbank_rest.routers.pedagogy import router as pedagogy_router
from mathbank_rest.routers.pedagogy_admin import router as pedagogy_admin_router
from mathbank_rest.routers.step_runtime import router as step_runtime_router
from mathbank_rest.routers.tutor import router as tutor_router
from mathbank_rest.routers.v1 import router as v1_router

app = FastAPI(title="mathbank-rest", version="0.1.0")
app.include_router(v1_router)
app.include_router(learner_router)
app.include_router(admin_router)
app.include_router(tutor_router)
app.include_router(pedagogy_router)
app.include_router(pedagogy_admin_router)
app.include_router(step_runtime_router)
app.include_router(agent_sessions_router)
app.include_router(admin_textbooks_router)
app.include_router(admin_imports_router)
app.include_router(fluid_router)
app.include_router(live_router)
app.include_router(attempt_media_router)
app.include_router(artifacts_router)


@app.get("/health")
def health(response: Response) -> dict:
    postgres = check_postgres()
    neo4j = check_neo4j()
    if not (postgres["ok"] and neo4j["ok"]):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"postgres": postgres, "neo4j": neo4j}


@app.get("/health/postgres")
def health_postgres(response: Response) -> dict:
    result = check_postgres()
    if not result["ok"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@app.get("/health/neo4j")
def health_neo4j(response: Response) -> dict:
    result = check_neo4j()
    if not result["ok"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
