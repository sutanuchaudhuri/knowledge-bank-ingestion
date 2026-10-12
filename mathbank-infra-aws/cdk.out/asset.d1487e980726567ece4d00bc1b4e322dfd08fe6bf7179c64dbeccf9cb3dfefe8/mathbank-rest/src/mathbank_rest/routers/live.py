"""Live session REST (distributed handoff 03/04/20, fluid 06/07/14/15/16).

REST is authoritative; the ``mathbank-live`` Socket.IO gateway forwards commands here and replays
``GET /events?after_sequence=`` to fan events out. Rejected commands are committed (receipt + no state
change) and then reported as HTTP 409/4xx so retries with the same ``client_command_id`` are idempotent.

Actors: admin API key → INSTRUCTOR (``X-Actor-Id`` names the person); student JWT → STUDENT participant
``student:{uuid}``; ``/v1/tutor/sessions/*`` with the admin key → AI_TUTOR (the agent service).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Literal
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from mathbank_rest import live_runtime, security, widgets
from mathbank_rest.config import settings
from mathbank_rest.db.postgres import engine

router = APIRouter(prefix="/v1", tags=["live-sessions"])
log = logging.getLogger(__name__)


def openai_responder(context: dict, message: str) -> dict:
    """Small-model live tutor reply (production). Returns ``{text, widget_intent}``; never sees solutions."""
    from mathbank_rest.tutor import _client

    response = _client.chat.completions.create(
        model=os.environ.get("LIVE_TUTOR_MODEL", "gpt-4.1-mini"),
        messages=[{"role": "system", "content": (
            "You are a concise Socratic geometry tutor in a live class. Use $...$ LaTeX for math. Never reveal a "
            "full solution. Reply in at most 4 sentences. If a diagram would help, set widget_intent to a short "
            "phrase such as 'power of a point' or 'intersecting chords', else empty.")},
                  {"role": "user", "content": json.dumps({"context": context, "student_message": message})[:12000]}],
        response_format={"type": "json_schema", "json_schema": {"name": "live_reply", "strict": True, "schema": {
            "type": "object", "additionalProperties": False, "required": ["text", "widget_intent"],
            "properties": {"text": {"type": "string"}, "widget_intent": {"type": "string"}}}}},
        temperature=0.3, max_tokens=400)
    return json.loads(response.choices[0].message.content)


RESPONDER = openai_responder  # injectable; tests replace it


def _run(fn, *args, **kwargs):
    try:
        with engine.begin() as conn:
            return fn(conn, *args, **kwargs)
    except live_runtime.LiveError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": str(exc), **exc.details}) from None


def _raise_if_rejected(result: dict) -> dict:
    if result.get("status") == "REJECTED":
        err = result["error"]
        raise HTTPException(status_code=int(err.get("http_status") or 409), detail={**err, "result": result})
    return result


def live_actor(authorization: str | None = Header(default=None), x_admin_api_key: str | None = Header(default=None),
               x_actor_id: str | None = Header(default=None)) -> dict:
    if x_admin_api_key and x_admin_api_key == settings.admin_api_key:
        return {"actor_type": "INSTRUCTOR", "actor_id": f"instructor:{x_actor_id or 'admin'}", "role": "INSTRUCTOR",
                "student_id": None}
    if authorization and authorization.lower().startswith("bearer "):
        try:
            sid = str(security.decode_access_token(authorization[7:].strip()))
            return {"actor_type": "STUDENT", "actor_id": f"student:{sid}", "role": "STUDENT", "student_id": sid}
        except (jwt.PyJWTError, ValueError, KeyError):
            pass
    raise HTTPException(status_code=401, detail="admin API key or student bearer token required")


def staff_actor(actor: dict = Depends(live_actor)) -> dict:
    if actor["role"] != "INSTRUCTOR":
        raise HTTPException(status_code=403, detail="instructor/admin only")
    return actor


def _participant_view(conn, sid: str, actor: dict) -> dict:
    if actor["role"] == "INSTRUCTOR":
        return {"role": "INSTRUCTOR", "participant_id": None, "group_id": None}
    p = live_runtime.participant(conn, sid, actor["actor_id"])
    if not p:
        raise live_runtime.LiveError(403, "NOT_A_PARTICIPANT", "join the session first")
    return {"role": "STUDENT", "participant_id": actor["actor_id"], "group_id": p.get("group_id")}


# ------------------------------------------------------------------ models

class SessionIn(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    plan_id: str | None = None
    course_limit_seconds: int | None = Field(default=None, gt=0)
    interaction_buffer_seconds: int = Field(0, ge=0)
    hard_limit: bool = False
    control_mode: Literal["AI_ACTIVE", "INSTRUCTOR_ACTIVE"] = "AI_ACTIVE"
    topics: list[dict] = Field(default_factory=list)


class JoinIn(BaseModel):
    join_code: str = Field(min_length=4, max_length=12)
    display_name: str | None = Field(default=None, max_length=80)


class CommandIn(BaseModel):
    command_type: str = Field(min_length=2, max_length=40)
    client_command_id: str = Field(default_factory=lambda: str(uuid4()), min_length=6, max_length=120)
    expected_session_version: int | None = Field(default=None, ge=1)
    payload: dict = Field(default_factory=dict)
    correlation_id: str | None = Field(default=None, max_length=120)


class VersionedIn(BaseModel):
    client_command_id: str = Field(default_factory=lambda: str(uuid4()), min_length=6, max_length=120)
    expected_session_version: int | None = Field(default=None, ge=1)


class TransitionIn(VersionedIn):
    to: Literal["NEXT", "BACK", "SKIP", "FORCE_SCENE", "COMPLETE", "START"]
    topic_index: int | None = Field(default=None, ge=0)
    scene_index: int | None = Field(default=None, ge=0)


class ActivityIn(VersionedIn):
    activity_id: str | None = None
    definition: dict | None = None
    seconds: int | None = Field(default=None, gt=0, le=3600)
    anonymous: bool = True


class ResponseIn(BaseModel):
    client_command_id: str = Field(default_factory=lambda: str(uuid4()), min_length=6, max_length=120)
    option: str | list[str] | None = None
    text: str | None = Field(default=None, max_length=4000)
    confidence: int | None = Field(default=None, ge=1, le=5)


class WidgetIn(VersionedIn):
    widget_spec_id: str | None = None
    spec: dict | None = None
    intent: str | None = Field(default=None, max_length=500)
    context: dict = Field(default_factory=dict)
    widget_instance_id: str | None = Field(default=None, max_length=80)


class WidgetStateIn(VersionedIn):
    operations: list[dict] = Field(default_factory=list)
    state: dict = Field(default_factory=dict)


class NLIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    auto_apply: bool = False
    expected_session_version: int | None = Field(default=None, ge=1)


class DecisionIn(BaseModel):
    decision: Literal["ACCEPT", "REJECT"]
    expected_session_version: int | None = Field(default=None, ge=1)


class OverrideIn(VersionedIn):
    action: Literal["TAKEOVER", "RELEASE", "LOCK_AGENT", "UNLOCK_AGENT"]
    scope: Literal["SESSION", "STUDENT", "GROUP"] = "SESSION"
    scope_id: str | None = None


class TutorActionIn(BaseModel):
    action: dict
    rationale: str = Field(default="", max_length=1000)
    based_on_version: int = Field(ge=1)
    participant_id: str | None = None


class TutorMessageIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    participant_id: str | None = None
    client_command_id: str = Field(default_factory=lambda: str(uuid4()), min_length=6, max_length=120)


def _command(sid: str, actor: dict, command: str, client_command_id: str, version: int | None, payload: dict,
             correlation_id: str | None = None) -> dict:
    return _raise_if_rejected(_run(live_runtime.execute_command, sid, command, actor["actor_type"], actor["actor_id"],
                                   client_command_id, version, payload, correlation_id))


# ------------------------------------------------------------------ sessions

@router.post("/live/sessions", status_code=201)
def create_session(body: SessionIn, actor: dict = Depends(staff_actor)) -> dict:
    return live_runtime._jsonable(_run(live_runtime.create_session, body.model_dump(), actor["actor_id"]))


@router.get("/live/sessions")
def list_sessions(limit: int = Query(50, le=200), _: dict = Depends(staff_actor)) -> dict:
    return {"items": _run(live_runtime.list_sessions, limit)}


@router.post("/live/sessions/join")
def join(body: JoinIn, actor: dict = Depends(live_actor)) -> dict:
    if actor["role"] != "STUDENT":
        raise HTTPException(status_code=403, detail="students join with their bearer token")
    return _run(live_runtime.join_session, body.join_code, actor["student_id"], body.display_name)


@router.get("/live/sessions/{sid}/state")
def state(sid: str, actor: dict = Depends(live_actor)) -> dict:
    def go(conn):
        view = _participant_view(conn, sid, actor)
        return live_runtime.snapshot(conn, sid, view["role"], view["participant_id"])
    return _run(go)


@router.get("/live/sessions/{sid}/events")
def events(sid: str, after_sequence: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=1000),
           actor: dict = Depends(live_actor)) -> dict:
    def go(conn):
        view = _participant_view(conn, sid, actor)
        return live_runtime.list_events(conn, sid, after_sequence, limit, view["role"], view["participant_id"],
                                        view["group_id"])
    return _run(go)


@router.post("/live/sessions/{sid}/commands")
def command(sid: str, body: CommandIn, actor: dict = Depends(live_actor)) -> dict:
    return _command(sid, actor, body.command_type.upper(), body.client_command_id, body.expected_session_version,
                    body.payload, body.correlation_id)


@router.post("/live/sessions/{sid}/transition")
def transition(sid: str, body: TransitionIn, actor: dict = Depends(staff_actor)) -> dict:
    payload = {k: v for k, v in (("topic_index", body.topic_index), ("scene_index", body.scene_index)) if v is not None}
    return _command(sid, actor, body.to, body.client_command_id, body.expected_session_version, payload)


@router.post("/live/sessions/{sid}/pause")
def pause(sid: str, body: VersionedIn, actor: dict = Depends(staff_actor)) -> dict:
    return _command(sid, actor, "PAUSE", body.client_command_id, body.expected_session_version, {})


@router.post("/live/sessions/{sid}/resume")
def resume(sid: str, body: VersionedIn, actor: dict = Depends(staff_actor)) -> dict:
    return _command(sid, actor, "RESUME", body.client_command_id, body.expected_session_version, {})


@router.get("/live/sessions/{sid}/time")
def time_state(sid: str, _: dict = Depends(staff_actor)) -> dict:
    return _run(lambda conn: live_runtime._jsonable(live_runtime.time_state(live_runtime.get_session(conn, sid))))


# ------------------------------------------------------------------ activities

@router.post("/activities/definitions", status_code=201)
def activity_definition(body: dict, actor: dict = Depends(staff_actor)) -> dict:
    if not body.get("prompt"):
        raise HTTPException(status_code=422, detail="prompt required")
    return _run(live_runtime.create_activity_definition, body, actor["actor_id"])


@router.post("/live/sessions/{sid}/activities")
def open_activity(sid: str, body: ActivityIn, actor: dict = Depends(staff_actor)) -> dict:
    payload = body.model_dump(exclude={"client_command_id", "expected_session_version"}, exclude_none=True)
    return _command(sid, actor, "OPEN_ACTIVITY", body.client_command_id, body.expected_session_version, payload)


@router.post("/live/sessions/{sid}/activities/{aid}/responses")
def respond(sid: str, aid: str, body: ResponseIn, actor: dict = Depends(live_actor)) -> dict:
    payload = {"activity_instance_id": aid, **body.model_dump(exclude={"client_command_id"}, exclude_none=True)}
    return _command(sid, actor, "RESPONSE_SUBMIT", body.client_command_id, None, payload)


@router.get("/live/sessions/{sid}/activities/{aid}/aggregate")
def activity_aggregate(sid: str, aid: str, actor: dict = Depends(live_actor)) -> dict:
    def go(conn):
        agg = live_runtime.aggregate(conn, aid)
        if actor["role"] != "INSTRUCTOR" and agg["status"] != "REVEALED":
            raise live_runtime.LiveError(403, "NOT_REVEALED", "results are visible after the instructor reveals them")
        return agg
    return _run(go)


@router.post("/live/sessions/{sid}/activities/{aid}/close")
def close_activity(sid: str, aid: str, body: VersionedIn, actor: dict = Depends(staff_actor)) -> dict:
    return _command(sid, actor, "CLOSE_ACTIVITY", body.client_command_id, body.expected_session_version,
                    {"activity_instance_id": aid})


@router.post("/live/sessions/{sid}/activities/{aid}/reveal")
def reveal_activity(sid: str, aid: str, body: VersionedIn, actor: dict = Depends(staff_actor)) -> dict:
    return _command(sid, actor, "REVEAL_ACTIVITY", body.client_command_id, body.expected_session_version,
                    {"activity_instance_id": aid})


# ------------------------------------------------------------------ widgets on stage

@router.post("/live/sessions/{sid}/widgets")
def show_widget(sid: str, body: WidgetIn, actor: dict = Depends(staff_actor)) -> dict:
    payload: dict = {"widget_instance_id": body.widget_instance_id}
    if body.widget_spec_id:
        payload["widget_spec_id"] = body.widget_spec_id
    elif body.spec:
        payload["spec"] = body.spec
    elif body.intent:
        composed = widgets.compose(body.intent, body.context)
        payload.update({"spec": composed["spec"], "composer_strategy": composed["strategy"]})
    else:
        raise HTTPException(status_code=422, detail="widget_spec_id, spec or intent required")
    return _command(sid, actor, "SHOW_WIDGET", body.client_command_id, body.expected_session_version, payload)


@router.patch("/live/sessions/{sid}/widgets/{wid}/state")
def widget_state(sid: str, wid: str, body: WidgetStateIn, actor: dict = Depends(staff_actor)) -> dict:
    return _command(sid, actor, "UPDATE_WIDGET", body.client_command_id, body.expected_session_version,
                    {"widget_instance_id": wid, "operations": body.operations, "state": body.state})


@router.delete("/live/sessions/{sid}/widgets/{wid}")
def hide_widget(sid: str, wid: str, expected_session_version: int | None = Query(default=None, ge=1),
                client_command_id: str | None = Query(default=None), actor: dict = Depends(staff_actor)) -> dict:
    return _command(sid, actor, "HIDE_WIDGET", client_command_id or str(uuid4()), expected_session_version,
                    {"widget_instance_id": wid})


# ------------------------------------------------------------------ instructor

@router.post("/instructor/live/{sid}/overrides")
def override(sid: str, body: OverrideIn, actor: dict = Depends(staff_actor)) -> dict:
    payload = {"scope": body.scope, "scope_id": body.scope_id} if body.action in ("TAKEOVER", "RELEASE") else {}
    return _command(sid, actor, body.action, body.client_command_id, body.expected_session_version, payload)


@router.post("/instructor/live/{sid}/commands")
def instructor_nl(sid: str, body: NLIn, actor: dict = Depends(staff_actor)) -> dict:
    return _run(live_runtime.instructor_nl, sid, body.message, actor["actor_id"], body.auto_apply,
                body.expected_session_version)


@router.get("/instructor/live/{sid}/recommendations")
def recommendations(sid: str, status: str | None = None, _: dict = Depends(staff_actor)) -> dict:
    return {"items": _run(live_runtime.list_recommendations, sid, status)}


@router.post("/instructor/live/{sid}/recommendations/{rid}")
def decide(sid: str, rid: str, body: DecisionIn, actor: dict = Depends(staff_actor)) -> dict:
    out = _run(live_runtime.decide_recommendation, sid, rid, body.decision, actor["actor_id"],
               body.expected_session_version)
    if out.get("result"):
        _raise_if_rejected(out["result"])
    return out


@router.get("/instructor/live/{sid}/handoff")
def handoff(sid: str, scope: Literal["SESSION", "STUDENT", "GROUP"] = "SESSION", scope_id: str = "*",
            _: dict = Depends(staff_actor)) -> dict:
    return _run(lambda conn: live_runtime.handoff_packet(conn, live_runtime.get_session(conn, sid), scope, scope_id))


# ------------------------------------------------------------------ tutor agent (AI_TUTOR)

@router.get("/tutor/sessions/{sid}/context", dependencies=[Depends(security.require_admin_api_key)])
def tutor_context(sid: str, participant_id: str | None = None) -> dict:
    return _run(live_runtime.tutor_context, sid, participant_id)


@router.post("/tutor/sessions/{sid}/actions", dependencies=[Depends(security.require_admin_api_key)])
def tutor_action(sid: str, body: TutorActionIn) -> dict:
    return _run(live_runtime.propose_ai_action, sid, body.action, body.rationale, body.based_on_version,
                "AI_TUTOR", body.participant_id)


@router.post("/tutor/sessions/{sid}/messages", dependencies=[Depends(security.require_admin_api_key)])
def tutor_message(sid: str, body: TutorMessageIn) -> dict:
    """Generate a live reply outside the transaction, then commit it only if the version is still current."""
    context = _run(live_runtime.tutor_context, sid, body.participant_id)
    if not context["ai_in_control"]:
        raise HTTPException(status_code=409, detail={"code": "AI_NOT_IN_CONTROL",
                                                     "message": "an instructor is in control or the agent is locked"})
    version = context["session"]["state_version"]
    reply = RESPONDER(context, body.message)
    payload = {"text": reply.get("text", ""), "participant_id": body.participant_id}
    if reply.get("widget_intent"):
        payload["widget_suggestion"] = widgets.compose(reply["widget_intent"])["spec"]
    result = _run(live_runtime.execute_command, sid, "TUTOR_MESSAGE", "AI_TUTOR", "agent:mathbank_tutor",
                  body.client_command_id, version, payload)
    if result.get("status") == "REJECTED":
        return {"delivered": False, "reason": result["error"]["code"], "result": result}
    return {"delivered": True, "reply": payload, "result": result}


@router.get("/realtime/sessions/{sid}")
def realtime_info(sid: str, actor: dict = Depends(live_actor)) -> dict:
    """Connection hints for the Socket.IO gateway (``mathbank-live``)."""
    def go(conn):
        view = _participant_view(conn, sid, actor)
        s = live_runtime.get_session(conn, sid)
        rooms = [f"session:{sid}"]
        if view["role"] == "INSTRUCTOR":
            rooms.append(f"instructor:{sid}")
        else:
            rooms.append(f"student:{view['participant_id']}")
            if view["group_id"]:
                rooms.append(f"group:{view['group_id']}")
        return {"session_id": sid, "rooms": rooms, "state_version": int(s["state_version"]),
                "last_sequence": int(s["last_sequence"]), "replay": f"/v1/live/sessions/{sid}/events?after_sequence=",
                "transport": "socket.io", "gateway_default_url": "http://127.0.0.1:5174"}
    return _run(go)
