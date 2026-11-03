"""OpenAPI tag descriptions shared by every app profile (main.py, app_runtime.py, app_admin.py)."""
from __future__ import annotations

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
    {"name": "admin-content", "description": "Reconcile the DynamoDB content read model against PostgreSQL (requirement 70 C6, requirement 71 WP4). Admin profile only. X-Admin-Api-Key or staff session."},
]
