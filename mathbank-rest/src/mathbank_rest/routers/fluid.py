"""Fluid widget + authoring REST (fluid widget pack 03/04/05/08/10/11/12/17/19/20).

* ``/v1/widgets/*`` — registry, validation, deterministic composition (FAST path), stored specs and the
  EPHEMERAL → PROMOTION_CANDIDATE → admin review → STATIC promotion lifecycle.
* ``/v1/tutor/format-math`` — LaTeX formatting for student input (deterministic, or agentic with a
  deterministic fallback). Available to students (JWT) and staff (admin key).
* ``/v1/authoring/*`` — presentation plans and the admin chat that proposes structured patches.
"""
from __future__ import annotations

from typing import Literal

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from mathbank_rest import authoring, live_runtime, math_format, security, widgets
from mathbank_rest.config import settings
from mathbank_rest.db.postgres import engine

router = APIRouter(prefix="/v1", tags=["fluid-widgets"])
FORMATTER = math_format.openai_formatter  # injectable; tests replace it
PLAN_LLM_PARSER = None  # optional NL → patch fallback; deterministic parser is the default


def _run(fn, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return fn(conn, *args, **kwargs)
    except (authoring.AuthoringError, live_runtime.LiveError) as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": str(exc), **exc.details}) from None


def staff_or_student(authorization: str | None = Header(default=None),
                     x_admin_api_key: str | None = Header(default=None)) -> dict:
    """Accept either the admin API key (staff) or a student bearer token."""
    if x_admin_api_key and x_admin_api_key == settings.admin_api_key:
        return {"role": "ADMIN", "student_id": None}
    if authorization and authorization.lower().startswith("bearer "):
        try:
            return {"role": "STUDENT", "student_id": str(security.decode_access_token(authorization[7:].strip()))}
        except (jwt.PyJWTError, ValueError, KeyError):
            pass
    raise HTTPException(status_code=401, detail="admin API key or student bearer token required")


# ------------------------------------------------------------------ widgets

class SpecBody(BaseModel):
    spec: dict
    audience: Literal["STUDENT", "INSTRUCTOR"] = "STUDENT"


class GenerateBody(BaseModel):
    intent: str = Field(min_length=1, max_length=1000)
    context: dict = Field(default_factory=dict)
    store: bool = False
    source_type: Literal["PRECOMPILED", "CORPUS_DERIVED", "LIVE_AGENT_CREATED", "INSTRUCTOR_CREATED"] = "LIVE_AGENT_CREATED"


class StoreBody(BaseModel):
    spec: dict
    source_type: Literal["PRECOMPILED", "CORPUS_DERIVED", "LIVE_AGENT_CREATED", "INSTRUCTOR_CREATED"] = "INSTRUCTOR_CREATED"
    live_session_id: str | None = None


class ReviewBody(BaseModel):
    decision: Literal["NOMINATE", "PROMOTE", "REJECT"]
    reviewer: str = "admin"


@router.get("/widgets/registry")
def widget_registry() -> dict:
    return {"version": widgets.SPEC_VERSION, "widget_types": widgets.registry()}


@router.post("/widgets/validate")
def widget_validate(body: SpecBody, _: dict = Depends(staff_or_student)) -> dict:
    def go(conn):
        return widgets.validate(body.spec, live_runtime._ref_checker(conn), body.audience)
    return _run(go)


@router.post("/widgets/generate")
def widget_generate(body: GenerateBody, caller: dict = Depends(staff_or_student)) -> dict:
    """Deterministic FAST-path composition (never calls a model); optionally stores the result.

    Students (e.g. the tutor agent acting with the learner's token) may compose for display only;
    persisting a spec (``store``) stays staff-only."""
    if body.store and caller["role"] != "ADMIN":
        raise HTTPException(status_code=403, detail="storing widget specs requires the admin API key")
    composed = widgets.compose(body.intent, body.context)

    def go(conn):
        check = widgets.validate(composed["spec"], live_runtime._ref_checker(conn))
        out = {**composed, "validation": {k: check[k] for k in ("valid", "errors", "warnings")}}
        if body.store and check["valid"]:
            out["stored"] = live_runtime.store_widget_spec(conn, composed["spec"], body.source_type, "composer")
        return out
    return _run(go)


@router.post("/widgets/specs", status_code=201)
def widget_store(body: StoreBody, x_actor_id: str | None = Header(default=None),
                 _: None = Depends(security.require_admin_api_key)) -> dict:
    return _run(live_runtime.store_widget_spec, body.spec, body.source_type, x_actor_id or "admin",
                body.live_session_id)


_SPEC_COLS = ("widget_spec_id::text AS widget_spec_id, widget_type, spec_version, title, spec, lifecycle, persistence, "
              "live_session_id::text AS live_session_id, source_type, source_lineage, validation, content_hash, "
              "created_by, created_at, expires_at, reviewed_by, reviewed_at")


@router.get("/widgets/specs")
def widget_specs(lifecycle: str | None = None, persistence: str | None = None, limit: int = Query(50, le=200),
                 _: None = Depends(security.require_admin_api_key)) -> dict:
    def go(conn):
        rows = conn.execute(text(
            f"SELECT {_SPEC_COLS} FROM visual.widget_spec WHERE (CAST(:l AS text) IS NULL OR lifecycle = :l) "
            "AND (CAST(:p AS text) IS NULL OR persistence = :p) ORDER BY created_at DESC LIMIT :n"),
            {"l": lifecycle, "p": persistence, "n": limit}).mappings().all()
        return {"items": [live_runtime._jsonable(dict(r)) for r in rows]}
    return _run(go)


@router.get("/widgets/specs/{spec_id}")
def widget_spec(spec_id: str, _: dict = Depends(staff_or_student)) -> dict:
    def go(conn):
        row = conn.execute(text(f"SELECT {_SPEC_COLS} FROM visual.widget_spec WHERE widget_spec_id::text = :i"),
                           {"i": spec_id}).mappings().first()
        if not row:
            raise live_runtime.LiveError(404, "WIDGET_NOT_FOUND", "widget spec not found")
        return live_runtime._jsonable(dict(row))
    return _run(go)


@router.post("/widgets/specs/{spec_id}/review")
def widget_review(spec_id: str, body: ReviewBody, _: None = Depends(security.require_admin_api_key)) -> dict:
    """Persistence promotion (fluid 19/20): agent-created → candidate → admin-approved STATIC template."""
    transitions = {"NOMINATE": ("PROMOTION_CANDIDATE", None), "PROMOTE": ("PROMOTED_TO_TEMPLATE", "STATIC"),
                   "REJECT": ("REJECTED", None)}

    def go(conn):
        row = conn.execute(text("SELECT lifecycle FROM visual.widget_spec WHERE widget_spec_id::text = :i FOR UPDATE"),
                           {"i": spec_id}).first()
        if not row:
            raise live_runtime.LiveError(404, "WIDGET_NOT_FOUND", "widget spec not found")
        if body.decision == "PROMOTE" and row[0] != "PROMOTION_CANDIDATE":
            raise live_runtime.LiveError(409, "NOT_A_CANDIDATE", "nominate the widget before promoting it")
        lifecycle, persistence = transitions[body.decision]
        conn.execute(text(
            "UPDATE visual.widget_spec SET lifecycle = :l, persistence = COALESCE(:p, persistence), "
            "expires_at = CASE WHEN :p = 'STATIC' THEN NULL ELSE expires_at END, reviewed_by = :r, reviewed_at = now() "
            "WHERE widget_spec_id::text = :i"), {"l": lifecycle, "p": persistence, "r": body.reviewer, "i": spec_id})
        return {"widget_spec_id": spec_id, "lifecycle": lifecycle, "persistence": persistence or "unchanged"}
    return _run(go)


# ------------------------------------------------------------------ LaTeX formatting for student input

class FormatBody(BaseModel):
    text: str = Field(min_length=1, max_length=math_format.MAX_CHARS)
    mode: Literal["deterministic", "agentic"] = "deterministic"


@router.post("/tutor/format-math")
def format_math(body: FormatBody, _: dict = Depends(staff_or_student)) -> dict:
    return math_format.format_math(body.text, body.mode, FORMATTER if body.mode == "agentic" else None)


# ------------------------------------------------------------------ authoring: presentation plans

class TopicIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    concept: str | None = None
    problem_ref: str | None = None
    planned_seconds: int = Field(gt=0)
    min_seconds: int | None = Field(default=None, gt=0)
    max_seconds: int | None = Field(default=None, gt=0)
    required: bool = True
    scenes: list[dict] = Field(default_factory=list)


class PlanIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    plan_key: str | None = None
    course_limit_seconds: int = Field(gt=0)
    interaction_buffer_seconds: int = Field(0, ge=0)
    hard_limit: bool = False
    topics: list[TopicIn] = Field(default_factory=list)


class TopicsIn(BaseModel):
    topics: list[TopicIn]


class TimingIn(BaseModel):
    course_limit_seconds: int | None = Field(default=None, gt=0)
    interaction_buffer_seconds: int | None = Field(default=None, ge=0)
    hard_limit: bool | None = None


class ChatIn(BaseModel):
    plan_id: str


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class PatchDecision(BaseModel):
    action: Literal["APPLY", "MODIFY", "REJECT", "ASK_FOR_ALTERNATIVE"]
    operations: list[dict] | None = None


AdminOnly = Depends(security.require_admin_api_key)


@router.get("/authoring/presentation-plans", dependencies=[AdminOnly])
def plans(limit: int = Query(100, le=500)) -> dict:
    return {"items": _run(authoring.list_plans, limit)}


@router.post("/authoring/presentation-plans", status_code=201, dependencies=[AdminOnly])
def create_plan(body: PlanIn, x_actor_id: str | None = Header(default=None)) -> dict:
    return _run(authoring.create_plan, body.model_dump(), x_actor_id or "admin")


@router.get("/authoring/presentation-plans/{plan_id}", dependencies=[AdminOnly])
def plan(plan_id: str) -> dict:
    return _run(authoring.get_plan, plan_id)


@router.put("/authoring/presentation-plans/{plan_id}/topics", dependencies=[AdminOnly])
def plan_topics(plan_id: str, body: TopicsIn) -> dict:
    return _run(authoring.update_topics, plan_id, [t.model_dump() for t in body.topics])


@router.patch("/authoring/presentation-plans/{plan_id}/timing", dependencies=[AdminOnly])
def plan_timing(plan_id: str, body: TimingIn) -> dict:
    return _run(authoring.update_timing, plan_id, body.model_dump(exclude_none=True))


@router.post("/authoring/presentation-plans/{plan_id}/validate", dependencies=[AdminOnly])
def plan_validate(plan_id: str) -> dict:
    return _run(lambda conn: authoring.validate_plan(authoring.get_plan(conn, plan_id)))


@router.post("/authoring/presentation-plans/{plan_id}/approve", dependencies=[AdminOnly])
def plan_approve(plan_id: str) -> dict:
    return _run(authoring.approve_plan, plan_id)


@router.post("/authoring/presentation-plans/{plan_id}/publish", dependencies=[AdminOnly])
def plan_publish(plan_id: str) -> dict:
    return _run(authoring.publish_plan, plan_id)


@router.post("/authoring/presentation-plans/{plan_id}/new-version", status_code=201, dependencies=[AdminOnly])
def plan_new_version(plan_id: str, x_actor_id: str | None = Header(default=None)) -> dict:
    return _run(authoring.new_version, plan_id, x_actor_id or "admin")


@router.post("/authoring/chat/sessions", status_code=201, dependencies=[AdminOnly])
def chat_create(body: ChatIn, x_actor_id: str | None = Header(default=None)) -> dict:
    return _run(authoring.create_chat, body.plan_id, x_actor_id or "admin")


@router.get("/authoring/chat/sessions/{chat_id}", dependencies=[AdminOnly])
def chat_get(chat_id: str) -> dict:
    return _run(authoring.get_chat, chat_id)


@router.post("/authoring/chat/sessions/{chat_id}/messages", dependencies=[AdminOnly])
def chat_message(chat_id: str, body: MessageIn) -> dict:
    return _run(authoring.post_message, chat_id, body.content, PLAN_LLM_PARSER)


@router.get("/authoring/chat/sessions/{chat_id}/proposed-patches", dependencies=[AdminOnly])
def chat_patches(chat_id: str) -> dict:
    return {"items": _run(authoring.list_patches, chat_id)}


@router.post("/authoring/chat/sessions/{chat_id}/proposed-patches/{patch_id}/apply", dependencies=[AdminOnly])
def chat_patch_decide(chat_id: str, patch_id: str, body: PatchDecision,
                      x_actor_id: str | None = Header(default=None)) -> dict:
    return _run(authoring.decide_patch, chat_id, patch_id, body.action, x_actor_id or "admin", body.operations)
