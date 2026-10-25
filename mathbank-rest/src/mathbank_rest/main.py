"""FastAPI app: health + per-database connectivity checks."""
from __future__ import annotations

from fastapi import FastAPI, Response, status

from mathbank_rest.db.graph import check_neo4j
from mathbank_rest.db.postgres import check_postgres
from mathbank_rest.routers.admin import router as admin_router
from mathbank_rest.routers.admin_corpus import router as admin_corpus_router
from mathbank_rest.routers.admin_imports import router as admin_imports_router
from mathbank_rest.routers.admin_textbooks import router as admin_textbooks_router
from mathbank_rest.routers.agent_sessions import router as agent_sessions_router
from mathbank_rest.routers.fluid import router as fluid_router
from mathbank_rest.routers.geometry_scenes import router as geometry_scenes_router
from mathbank_rest.routers.geometry_interpretation import router as geometry_interpretation_router
from mathbank_rest.routers.interaction_templates import router as interaction_templates_router
from mathbank_rest.routers.micro_courses import admin_router as micro_course_admin_router
from mathbank_rest.routers.micro_courses import student_router as micro_course_student_router
from mathbank_rest.routers.learner import router as learner_router
from mathbank_rest.routers.live import router as live_router
from mathbank_rest.routers.attempt_media import router as attempt_media_router
from mathbank_rest.routers.artifacts import router as artifacts_router
from mathbank_rest.routers.pedagogy import router as pedagogy_router
from mathbank_rest.routers.pedagogy_admin import router as pedagogy_admin_router
from mathbank_rest.routers.step_runtime import router as step_runtime_router
from mathbank_rest.routers.tutor import router as tutor_router
from mathbank_rest.routers.tutoring_routes import router as tutoring_routes_router
from mathbank_rest.routers.v1 import router as v1_router
from mathbank_rest.routers.admin_taxonomy import router as admin_taxonomy_router
from mathbank_rest.routers.admin_activities import router as admin_activities_router
from mathbank_rest.routers.admin_activities import binding_router as admin_activity_bindings_router
from mathbank_rest.routers.quiz_runtime import router as quiz_runtime_router
from mathbank_rest.routers.exam_integration import router as exam_integration_router
from mathbank_rest.routers.notifications import router as notifications_router
from mathbank_rest.routers.theorems import admin_router as theorems_admin_router
from mathbank_rest.routers.theorems import student_router as theorems_student_router
from mathbank_rest.routers.socratic import router as socratic_router

# One line per tag actually used by any operation (doc 45 APID-2): what it covers + which auth
# scheme applies. Admin-gated tags are prefixed `admin-`; everything else is anonymous or learner
# JWT, named in the description below rather than inferred from the prefix.
OPENAPI_TAGS = [
    {"name": "admin-socratic", "description": "Socratic Studio staff sessions. HttpOnly cookies, Cognito identity/groups by default or explicit loopback-only local testing; origin and CSRF on mutations. Not the legacy shared admin-key boundary."},
    {"name": "ops", "description": "Health/connectivity checks. Anonymous."},
    {"name": "corpus", "description": "Public read-only competitions/problems. Anonymous."},
    {"name": "taxonomy", "description": "Public read-only concepts/techniques. Anonymous."},
    {"name": "search", "description": "Public hybrid semantic/lexical/graph search. Anonymous."},
    {"name": "analytics", "description": "Public cohort-level (no PII) analytics. Anonymous."},
    {"name": "learner", "description": "Student auth, mastery, progress. Learner JWT."},
    {"name": "agent-sessions", "description": "Agent conversation transcripts. Learner JWT; two admin-key-gated review endpoints."},
    {"name": "pedagogy", "description": "Anonymous read-only teaching context and provisional coaching. Anonymous + optional learner JWT."},
    {"name": "tutor", "description": "Scoped tutor Q&A/feedback. Learner JWT."},
    {"name": "step-runtime", "description": "Guided step attempts, hints, recovery routes. Learner JWT."},
    {"name": "tutoring-routes", "description": "Precompiled tutoring-route runtime. Learner JWT."},
    {"name": "micro-courses", "description": "Published micro-course catalog and enrollment runtime. Anonymous (preview) or learner JWT (enrolled)."},
    {"name": "theorems", "description": "Approved-only theorem/axiom/lemma/corollary catalog: detail, sources, diagrams, prerequisite lineage, hybrid search. Anonymous."},
    {"name": "geometry-agent", "description": "Geometry-scene interpretation for staff/student. Mixed staff-or-student auth."},
    {"name": "geometry-scenes", "description": "Independent deterministic geometry scene engine, mounted as a sub-API. Mixed staff-or-student auth; debug evidence is staff-only."},
    {"name": "fluid-widgets", "description": "Live-session widget proposals and activities. Session-scoped auth."},
    {"name": "live-sessions", "description": "Live classroom session/event log relayed by mathbank-live. Session-scoped auth."},
    {"name": "multimodal-attempts", "description": "Private multimodal student attempt review. Learner JWT."},
    {"name": "artifacts", "description": "Generated diagram/artifact bundles. Learner JWT."},
    {"name": "admin-pipeline", "description": "Register competitions/papers; pipeline run/job status. X-Admin-Api-Key."},
    {"name": "admin-corpus", "description": "Reviewed corpus authoring (text/image drafts). X-Admin-Api-Key."},
    {"name": "admin-imports", "description": "Admin solution-step import review/approval. X-Admin-Api-Key."},
    {"name": "admin-textbooks", "description": "Admin textbook import dashboard. X-Admin-Api-Key."},
    {"name": "admin-pedagogy", "description": "Revision-gated skill/concept/technique governance review/edit/publish workflow. X-Admin-Api-Key."},
    {"name": "admin-interaction-templates", "description": "Interaction/animation/feedback template catalog authoring. X-Admin-Api-Key."},
    {"name": "admin-micro-courses", "description": "Micro-course authoring, release lifecycle, activity, preview. X-Admin-Api-Key."},
    {"name": "admin-taxonomy", "description": "Concept/technique/skill/misconception list, update, alias, activate/deactivate (doc 45). X-Admin-Api-Key."},
    {"name": "admin-activities", "description": "Quiz/activity authoring bank (doc 46). X-Admin-Api-Key."},
    {"name": "admin-theorems", "description": "Theorem/axiom/lemma/corollary catalog authoring: CRUD, prerequisite relations (cycle-checked), technique/taxonomy linking, sources, diagrams, dedup search (doc 61). X-Admin-Api-Key."},
]

app = FastAPI(
    title="mathbank-rest",
    version="0.1.0",
    summary="The only direct PostgreSQL/Neo4j boundary in the MathBank platform.",
    description=(
        "FastAPI service backing mathbank-web, mathbank-live and mathbank-agent. Three auth "
        "boundaries: a shared `X-Admin-Api-Key` header (configured via `ADMIN_API_KEY`) for legacy "
        "`/v1/admin/*` operations, staff cookies for `/v1/admin/socratic/*` "
        "(Cognito by default; explicit loopback-only local testing available), "
        "and a learner `Authorization: Bearer` JWT (obtained from "
        "`POST /v1/learner/login`) for student-owned operations. Most of `/v1` is anonymous "
        "read access. See `documentation/requirements/reference/REST_API.md` for the prose "
        "reference and `documentation/requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md` "
        "for known documentation/CRUD gaps and their tracked fixes."
    ),
    openapi_tags=OPENAPI_TAGS,
)
app.include_router(v1_router)
app.include_router(learner_router)
app.include_router(admin_router)
app.include_router(socratic_router)
app.include_router(admin_corpus_router)
app.include_router(tutor_router)
app.include_router(tutoring_routes_router)
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
app.include_router(geometry_interpretation_router)
app.include_router(geometry_scenes_router, tags=["geometry-scenes"])
app.include_router(interaction_templates_router)
app.include_router(micro_course_admin_router)
app.include_router(micro_course_student_router)
app.include_router(admin_taxonomy_router)
app.include_router(admin_activities_router)
app.include_router(admin_activity_bindings_router)
app.include_router(quiz_runtime_router)
app.include_router(exam_integration_router)
app.include_router(notifications_router)
app.include_router(theorems_admin_router)
app.include_router(theorems_student_router)


@app.get("/health", tags=["ops"])
def health(response: Response) -> dict:
    postgres = check_postgres()
    neo4j = check_neo4j()
    if not (postgres["ok"] and neo4j["ok"]):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"postgres": postgres, "neo4j": neo4j}


@app.get("/health/postgres", tags=["ops"])
def health_postgres(response: Response) -> dict:
    result = check_postgres()
    if not result["ok"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


@app.get("/health/neo4j", tags=["ops"])
def health_neo4j(response: Response) -> dict:
    result = check_neo4j()
    if not result["ok"]:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result
