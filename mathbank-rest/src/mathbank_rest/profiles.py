"""App profiles (requirement 71 §2.1).

``main.py`` stays the **combined** app: it mounts every router and is the local-dev default (product decision
2026-11-03). ``app_runtime.py`` and ``app_admin.py`` are built here from the same router objects:

* ``runtime``  learners, agents and live traffic. Never has PostgreSQL access (``db/postgres.py`` hands out a
               guard that raises). Routers are added to RUNTIME_ROUTERS as their work package replaces SQL
               with a store; until then they sit in RUNTIME_PENDING.
* ``admin``    the authoring plane: admin, import, review and release routers (PostgreSQL).
* ``socratic`` the Socratic Studio has its own app (``socratic_app.py``); it is listed only so the
               partition below is complete.

Every router object must belong to exactly one group; ``tests/test_profiles.py`` enforces that, so a router can
never be silently dropped from a profile.
"""
from __future__ import annotations

import importlib
from collections.abc import Iterable

from fastapi import FastAPI

from mathbank_rest.openapi_tags import OPENAPI_TAGS

# name -> (module, attribute). Order is the mount order used by main.py.
ROUTERS: dict[str, tuple[str, str]] = {
    "v1": ("mathbank_rest.routers.v1", "router"),
    "learner": ("mathbank_rest.routers.learner", "router"),
    "admin": ("mathbank_rest.routers.admin", "router"),
    "socratic": ("mathbank_rest.routers.socratic", "router"),
    "admin_corpus": ("mathbank_rest.routers.admin_corpus", "router"),
    "tutor": ("mathbank_rest.routers.tutor", "router"),
    "tutoring_routes": ("mathbank_rest.routers.tutoring_routes", "router"),
    "pedagogy": ("mathbank_rest.routers.pedagogy", "router"),
    "pedagogy_admin": ("mathbank_rest.routers.pedagogy_admin", "router"),
    "step_runtime": ("mathbank_rest.routers.step_runtime", "router"),
    "agent_sessions": ("mathbank_rest.routers.agent_sessions", "router"),
    "admin_textbooks": ("mathbank_rest.routers.admin_textbooks", "router"),
    "admin_imports": ("mathbank_rest.routers.admin_imports", "router"),
    "fluid": ("mathbank_rest.routers.fluid", "router"),
    "live": ("mathbank_rest.routers.live", "router"),
    "attempt_media": ("mathbank_rest.routers.attempt_media", "router"),
    "artifacts": ("mathbank_rest.routers.artifacts", "router"),
    "geometry_interpretation": ("mathbank_rest.routers.geometry_interpretation", "router"),
    "geometry_scenes": ("mathbank_rest.routers.geometry_scenes", "router"),
    "interaction_templates": ("mathbank_rest.routers.interaction_templates", "router"),
    "micro_course_admin": ("mathbank_rest.routers.micro_courses", "admin_router"),
    "micro_course_student": ("mathbank_rest.routers.micro_courses", "student_router"),
    "admin_taxonomy": ("mathbank_rest.routers.admin_taxonomy", "router"),
    "admin_activities": ("mathbank_rest.routers.admin_activities", "router"),
    "admin_activity_bindings": ("mathbank_rest.routers.admin_activities", "binding_router"),
    "quiz_runtime": ("mathbank_rest.routers.quiz_runtime", "router"),
    "exam_integration": ("mathbank_rest.routers.exam_integration", "router"),
    "notifications": ("mathbank_rest.routers.notifications", "router"),
    "theorems_admin": ("mathbank_rest.routers.theorems", "admin_router"),
    "theorems_student": ("mathbank_rest.routers.theorems", "student_router"),
}

# Authoring plane: stays on PostgreSQL (requirement 70 C7).
ADMIN_ROUTERS: tuple[str, ...] = (
    "admin", "admin_corpus", "admin_imports", "admin_textbooks", "admin_taxonomy", "admin_activities",
    "admin_activity_bindings", "pedagogy_admin", "interaction_templates", "micro_course_admin", "theorems_admin",
    "tutoring_routes",
)

# Served by app_socratic (socratic_app.py), not by the runtime/admin apps.
SOCRATIC_ROUTERS: tuple[str, ...] = ("socratic",)

# Runtime routers whose SQL has been replaced by stores. Each work package appends here when its gate passes.
RUNTIME_ROUTERS: tuple[str, ...] = ()

# Runtime-facing routers still on PostgreSQL SQL, with the work package that moves them.
RUNTIME_PENDING: dict[str, str] = {
    "v1": "WP4", "tutor": "WP4", "pedagogy": "WP4", "theorems_student": "WP4", "micro_course_student": "WP4/WP5",
    "learner": "WP5", "step_runtime": "WP5",
    "quiz_runtime": "WP6", "exam_integration": "WP6",
    "live": "WP7", "fluid": "WP7",
    "attempt_media": "WP8", "artifacts": "WP8", "geometry_interpretation": "WP8", "geometry_scenes": "WP8",
    "agent_sessions": "WP9", "notifications": "WP3",
}

PROFILES: dict[str, tuple[str, ...]] = {
    "combined": tuple(ROUTERS),
    "runtime": RUNTIME_ROUTERS,
    "admin": ADMIN_ROUTERS,
}


def partition() -> dict[str, set[str]]:
    """Every router name by group; used by the invariant test."""
    return {"runtime": set(RUNTIME_ROUTERS), "runtime_pending": set(RUNTIME_PENDING), "admin": set(ADMIN_ROUTERS),
            "socratic": set(SOCRATIC_ROUTERS)}


def load_router(name: str):
    module, attr = ROUTERS[name]
    return getattr(importlib.import_module(module), attr)


def install_common(app: FastAPI) -> FastAPI:
    """Pieces every profile shares: store error mapping and the stores health endpoint."""
    from mathbank_rest import stores
    from mathbank_rest.stores.errors import install_error_handlers

    install_error_handlers(app)

    @app.get("/health/stores", tags=["ops"])
    def health_stores() -> dict:
        return {"profile": stores.settings.app_profile, "stores": stores.describe()}

    return app


def create_app(profile: str, *, extra: Iterable[str] = ()) -> FastAPI:
    """Build the FastAPI app for `profile` ("runtime" or "admin"; "combined" is main.py)."""
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}; expected one of {sorted(PROFILES)}")
    from mathbank_rest.config import settings

    app = FastAPI(
        title=f"mathbank-rest ({profile})",
        version="0.1.0",
        summary={"runtime": "Learner/agent/live runtime — no PostgreSQL access.",
                 "admin": "Authoring plane — PostgreSQL.",
                 "combined": "Every router (local dev)."}[profile],
        openapi_tags=OPENAPI_TAGS,
    )
    install_common(app)
    for name in (*PROFILES[profile], *extra):
        app.include_router(load_router(name))

    @app.get("/health", tags=["ops"])
    def health() -> dict:
        out: dict = {"profile": profile, "stores": stores_describe()}
        if profile != "runtime":
            from mathbank_rest.db.postgres import check_postgres

            out["postgres"] = check_postgres()
        return out

    def stores_describe() -> dict:
        from mathbank_rest import stores

        return stores.describe()

    assert settings.app_profile in ("combined", profile) or profile == "combined", (
        f"MB_APP_PROFILE={settings.app_profile!r} does not match the {profile!r} app")
    return app
