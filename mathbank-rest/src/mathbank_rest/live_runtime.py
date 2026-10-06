"""Live session runtime (fluid widget pack 06/14/15/16 + distributed handoff 03/04/20).

PostgreSQL is authoritative. Every mutation runs as: command → authority check → expected-version check
→ one transaction (state + ordered ``live.session_event`` + ``pipeline.outbox_event``) → realtime fan-out
by the ``mathbank-live`` gateway, which replays ``session_event`` rows by sequence. Agents never mutate
state directly: AI actions become ``live.recommendation`` rows that are auto-applied only while the
session is AI_ACTIVE, the agent is unlocked and the recommendation was based on the current version.

``state_version`` changes only on control/stage changes (navigation, takeover, widgets, activities);
student responses, questions and chat messages advance ``sequence`` only, so students typing never make
an instructor command stale.
"""
from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection

from mathbank_rest import widgets

CONTROL_COMMANDS = {
    "START", "NEXT", "BACK", "PAUSE", "RESUME", "EXTEND", "SHORTEN", "SKIP", "FORCE_SCENE", "COMPLETE",
    "LOCK_AGENT", "UNLOCK_AGENT", "TAKEOVER", "RELEASE", "SHOW_WIDGET", "UPDATE_WIDGET", "HIDE_WIDGET",
    "OPEN_ACTIVITY", "CLOSE_ACTIVITY", "REVEAL_ACTIVITY", "INSTRUCTOR_MESSAGE", "SELECT_BRANCH",
}
STUDENT_COMMANDS = {"RESPONSE_SUBMIT", "HINT_REQUEST", "QUESTION_ASK", "MARK_CONFUSED", "WIDGET_INTERACT"}
AI_COMMANDS = {"TUTOR_MESSAGE"}
AUTO_APPLY = {"SHOW_WIDGET", "OPEN_ACTIVITY", "CLOSE_ACTIVITY", "REVEAL_ACTIVITY", "NEXT", "SELECT_BRANCH"}
STAFF = {"INSTRUCTOR", "ADMIN"}
BRANCHES = (("CONTINUE", 0.8), ("REINFORCE", 0.5), ("PREREQUISITE", 0.0))


class LiveError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status_code, self.code, self.details = status, code, details or {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _row(result) -> dict | None:
    row = result.mappings().first()
    return dict(row) if row else None


def _jsonable(value):
    return json.loads(json.dumps(value, default=str))


# ------------------------------------------------------------------ events

def emit(conn: Connection, sid: str, event_type: str, actor_type: str, actor_id: str | None, payload: dict,
         audience: str = "SESSION", audience_id: str | None = None, bump: bool = False,
         correlation_id: str | None = None, causation_id: str | None = None) -> dict:
    """Append one ordered event (and its outbox row). Must run inside the command transaction."""
    seq_row = conn.execute(text(
        "UPDATE live.session SET last_sequence = last_sequence + 1, "
        "state_version = state_version + CASE WHEN :b THEN 1 ELSE 0 END, updated_at = now() "
        "WHERE live_session_id = CAST(:s AS uuid) RETURNING last_sequence, state_version"),
        {"s": sid, "b": bump}).one()
    sequence, version = int(seq_row[0]), int(seq_row[1])
    event_id = str(uuid4())
    body = _jsonable(payload or {})
    conn.execute(text(
        "INSERT INTO live.session_event (live_session_id, sequence, event_id, event_type, session_version, "
        "correlation_id, causation_id, actor_type, actor_id, audience, audience_id, payload) VALUES "
        "(CAST(:s AS uuid), :q, CAST(:e AS uuid), :t, :v, :c, :ca, :at, :aid, :au, :auid, CAST(:p AS jsonb))"),
        {"s": sid, "q": sequence, "e": event_id, "t": event_type, "v": version, "c": correlation_id,
         "ca": causation_id, "at": actor_type, "aid": actor_id, "au": audience, "auid": audience_id,
         "p": json.dumps(body)})
    envelope = {"event_id": event_id, "event_type": event_type, "session_id": sid, "sequence": sequence,
                "session_version": version, "correlation_id": correlation_id, "causation_id": causation_id,
                "actor_type": actor_type, "actor_id": actor_id, "audience": audience, "audience_id": audience_id,
                "timestamp": _now().isoformat(), "payload": body}
    conn.execute(text(
        "INSERT INTO pipeline.outbox_event (event_type, aggregate_type, aggregate_id, payload) "
        "VALUES ('LIVE_EVENT', 'live_session', :s, CAST(:p AS jsonb))"),
        {"s": sid, "p": json.dumps({"event_type": event_type, "sequence": sequence, "event_id": event_id})})
    return envelope


def list_events(conn: Connection, sid: str, after_sequence: int = 0, limit: int = 500,
                role: str = "INSTRUCTOR", participant_id: str | None = None, group_id: str | None = None) -> dict:
    rows = conn.execute(text(
        "SELECT event_id::text, event_type, live_session_id::text AS session_id, sequence, session_version, "
        "correlation_id, causation_id, actor_type, actor_id, audience, audience_id, payload, created_at AS timestamp "
        "FROM live.session_event WHERE live_session_id = CAST(:s AS uuid) AND sequence > :a "
        "ORDER BY sequence LIMIT :l"), {"s": sid, "a": after_sequence, "l": limit}).mappings().all()
    events = []
    for r in rows:
        e = dict(r)
        if role not in STAFF and not _visible(e, participant_id, group_id):
            continue
        events.append(_jsonable(e))
    last = conn.execute(text("SELECT last_sequence FROM live.session WHERE live_session_id = CAST(:s AS uuid)"),
                        {"s": sid}).scalar()
    return {"events": events, "last_sequence": int(last or 0),
            "next_after": int(rows[-1]["sequence"]) if rows else after_sequence}


def _visible(event: dict, participant_id: str | None, group_id: str | None) -> bool:
    audience = event["audience"]
    if audience == "SESSION":
        return True
    if audience == "STUDENT":
        return event.get("audience_id") == participant_id
    if audience == "GROUP":
        return group_id is not None and event.get("audience_id") == group_id
    return False


# ------------------------------------------------------------------ sessions

_SESSION_COLS = (
    "live_session_id::text AS session_id, plan_id::text AS plan_id, title, join_code, status, control_mode, "
    "controller, agent_locked, state_version, last_sequence, current_topic_index, current_scene_index, "
    "course_limit_seconds, interaction_buffer_seconds, hard_limit, extension_seconds, started_at, paused_at, "
    "paused_total_seconds, topic_started_at, completed_at, stage, topics, created_by, created_at, updated_at")


def get_session(conn: Connection, sid: str, lock: bool = False) -> dict:
    row = _row(conn.execute(text(f"SELECT {_SESSION_COLS} FROM live.session WHERE live_session_id = CAST(:s AS uuid)"
                                 + (" FOR UPDATE" if lock else "")), {"s": sid}))
    if row is None:
        raise LiveError(404, "SESSION_NOT_FOUND", "live session not found")
    return row


def _join_code(conn: Connection) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(20):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if not conn.execute(text("SELECT 1 FROM live.session WHERE join_code = :c"), {"c": code}).first():
            return code
    raise LiveError(503, "JOIN_CODE_EXHAUSTED", "could not allocate a join code")


def create_session(conn: Connection, body: dict, actor: str = "admin") -> dict:
    topics = body.get("topics") or []
    plan_id = body.get("plan_id")
    limits = {"course_limit_seconds": int(body.get("course_limit_seconds") or 0),
              "interaction_buffer_seconds": int(body.get("interaction_buffer_seconds") or 0),
              "hard_limit": bool(body.get("hard_limit", False))}
    if plan_id:
        plan = _row(conn.execute(text(
            "SELECT plan_id::text AS plan_id, title, status, course_limit_seconds, interaction_buffer_seconds, "
            "hard_limit FROM authoring.presentation_plan WHERE plan_id = CAST(:p AS uuid)"), {"p": plan_id}))
        if plan is None:
            raise LiveError(404, "PLAN_NOT_FOUND", "presentation plan not found")
        if plan["status"] not in ("APPROVED", "PUBLISHED"):
            raise LiveError(409, "PLAN_NOT_APPROVED", "only approved or published plans can run live")
        topics = [dict(r) for r in conn.execute(text(
            "SELECT ordinal, title, concept, problem_ref, planned_seconds, min_seconds, max_seconds, required, scenes "
            "FROM authoring.plan_topic WHERE plan_id = CAST(:p AS uuid) ORDER BY ordinal"),
            {"p": plan_id}).mappings().all()]
        limits = {k: plan[k] for k in limits}
        body.setdefault("title", plan["title"])
    if not topics:
        topics = [{"ordinal": 0, "topic_key": "main", "title": body.get("title") or "Live session",
                   "planned_seconds": limits["course_limit_seconds"] or 1800, "required": True, "scenes": []}]
    for i, t in enumerate(topics):
        t.setdefault("ordinal", i)
        t.setdefault("scenes", [])
        t.setdefault("required", True)
        t["planned_seconds"] = int(t.get("planned_seconds") or 300)
    if limits["course_limit_seconds"] <= 0:
        limits["course_limit_seconds"] = sum(t["planned_seconds"] for t in topics)
    sid = conn.execute(text(
        "INSERT INTO live.session (plan_id, title, join_code, course_limit_seconds, interaction_buffer_seconds, "
        "hard_limit, topics, created_by, control_mode) VALUES (CAST(:p AS uuid), :t, :j, :c, :b, :h, "
        "CAST(:tp AS jsonb), :by, :m) RETURNING live_session_id::text"),
        {"p": plan_id, "t": body.get("title") or "Live session", "j": _join_code(conn),
         "c": limits["course_limit_seconds"], "b": limits["interaction_buffer_seconds"], "h": limits["hard_limit"],
         "tp": json.dumps(_jsonable(topics)), "by": actor,
         "m": body.get("control_mode") or "AI_ACTIVE"}).scalar_one()
    for t in topics:
        conn.execute(text(
            "INSERT INTO live.topic_run (live_session_id, topic_index, title, planned_seconds) "
            "VALUES (CAST(:s AS uuid), :i, :t, :p)"), {"s": sid, "i": t["ordinal"], "t": t["title"],
                                                      "p": t["planned_seconds"]})
    conn.execute(text(
        "INSERT INTO live.participant (live_session_id, participant_id, role, display_name) "
        "VALUES (CAST(:s AS uuid), :p, 'INSTRUCTOR', :n) ON CONFLICT DO NOTHING"),
        {"s": sid, "p": f"instructor:{actor}", "n": actor})
    emit(conn, sid, "session.created", "INSTRUCTOR", actor, {"title": body.get("title"), "topics": len(topics)})
    return get_session(conn, sid)


def list_sessions(conn: Connection, limit: int = 50) -> list[dict]:
    return [_jsonable(dict(r)) for r in conn.execute(text(
        f"SELECT {_SESSION_COLS} FROM live.session ORDER BY created_at DESC LIMIT :l"), {"l": limit}).mappings()]


def join_session(conn: Connection, join_code: str, student_id: str, display_name: str | None = None) -> dict:
    row = _row(conn.execute(text(
        "SELECT live_session_id::text AS sid, status FROM live.session WHERE join_code = :c"),
        {"c": (join_code or "").strip().upper()}))
    if row is None:
        raise LiveError(404, "JOIN_CODE_NOT_FOUND", "no live session with that join code")
    if row["status"] in ("COMPLETED", "CANCELLED"):
        raise LiveError(409, "SESSION_ENDED", "that live session has ended")
    pid = f"student:{student_id}"
    name = display_name or conn.execute(text(
        "SELECT COALESCE(display_name, 'Student') FROM learner.student_profile WHERE student_id = CAST(:s AS uuid)"),
        {"s": student_id}).scalar() or "Student"
    inserted = conn.execute(text(
        "INSERT INTO live.participant (live_session_id, participant_id, role, student_id, display_name) "
        "VALUES (CAST(:s AS uuid), :p, 'STUDENT', CAST(:st AS uuid), :n) "
        "ON CONFLICT (live_session_id, participant_id) DO UPDATE SET last_seen_at = now() "
        "RETURNING (xmax = 0) AS fresh"), {"s": row["sid"], "p": pid, "st": student_id, "n": name}).scalar()
    if inserted:
        emit(conn, row["sid"], "participant.joined", "STUDENT", pid, {"participant_id": pid, "display_name": name})
    return {"session_id": row["sid"], "participant_id": pid, "display_name": name}


def participant(conn: Connection, sid: str, participant_id: str) -> dict | None:
    return _row(conn.execute(text(
        "SELECT participant_id, role, student_id::text AS student_id, display_name, group_id, control_mode, confused "
        "FROM live.participant WHERE live_session_id = CAST(:s AS uuid) AND participant_id = :p"),
        {"s": sid, "p": participant_id}))


# ------------------------------------------------------------------ time orchestrator (fluid 06)

def _elapsed(s: dict, now: datetime | None = None) -> int:
    now = now or _now()
    if not s.get("started_at"):
        return 0
    end = s.get("completed_at") or now
    paused = int(s.get("paused_total_seconds") or 0)
    if s.get("paused_at") and not s.get("completed_at"):
        paused += int((now - s["paused_at"]).total_seconds())
    return max(0, int((end - s["started_at"]).total_seconds()) - paused)


def time_state(s: dict, now: datetime | None = None) -> dict:
    now = now or _now()
    topics = s.get("topics") or []
    idx = int(s.get("current_topic_index") or 0)
    elapsed = _elapsed(s, now)
    limit = int(s["course_limit_seconds"]) + int(s.get("extension_seconds") or 0)
    remaining_planned = sum(int(t["planned_seconds"]) for t in topics[idx + 1:])
    topic_elapsed = 0
    if s.get("topic_started_at") and s.get("status") in ("ACTIVE", "PAUSED"):
        topic_elapsed = max(0, int(((s.get("paused_at") or now) - s["topic_started_at"]).total_seconds()))
    current_planned = int(topics[idx]["planned_seconds"]) if idx < len(topics) else 0
    projected = elapsed + max(0, current_planned - topic_elapsed) + remaining_planned
    remaining = limit - elapsed
    status = "OVER" if remaining < 0 else "BEHIND" if projected > limit else "ON_TRACK"
    optional = [{"topic_index": int(t["ordinal"]), "title": t["title"], "planned_seconds": int(t["planned_seconds"])}
                for t in topics[idx + 1:] if not t.get("required", True)]
    recs: list[dict] = []
    if status != "ON_TRACK":
        over = projected - limit
        for o in optional:
            if over <= 0:
                break
            recs.append({"action": {"command_type": "SKIP", "payload": {"topic_index": o["topic_index"]}},
                         "rationale": f"Skip optional topic “{o['title']}” to recover {o['planned_seconds'] // 60} min"})
            over -= o["planned_seconds"]
        if over > 0 and not s.get("hard_limit"):
            recs.append({"action": {"command_type": "EXTEND", "payload": {"seconds": int(over)}},
                         "rationale": f"Extend by {max(1, over // 60)} min (soft limit)"})
        elif over > 0:
            recs.append({"action": {"command_type": "SHORTEN", "payload": {"seconds": int(over)}},
                         "rationale": "Hard limit: compress the remaining required topics"})
    return {"elapsed_seconds": elapsed, "limit_seconds": limit, "remaining_seconds": remaining,
            "hard_limit": bool(s.get("hard_limit")), "extension_seconds": int(s.get("extension_seconds") or 0),
            "current_topic_index": idx, "topic_elapsed_seconds": topic_elapsed,
            "topic_planned_seconds": current_planned, "topic_variance_seconds": topic_elapsed - current_planned,
            "remaining_planned_seconds": remaining_planned, "projected_total_seconds": projected,
            "status": status, "optional_topics_remaining": optional, "recommendations": recs}


# ------------------------------------------------------------------ widgets in a session

def _ref_checker(conn: Connection):
    def check(kind: str, value: str) -> str | None:
        if kind == "problem_image_id":
            ok = conn.execute(text("SELECT 1 FROM core.problem_image WHERE problem_image_id::text = :v"), {"v": value}).first()
            return None if ok else "unknown problem image"
        if kind == "problem_id":
            ok = conn.execute(text("SELECT 1 FROM core.problem WHERE problem_id::text = :v OR canonical_code = :v"),
                              {"v": value}).first()
            return None if ok else "unknown problem"
        return None
    return check


def store_widget_spec(conn: Connection, spec: dict, source_type: str, actor: str, sid: str | None = None,
                      audience: str = "STUDENT") -> dict:
    result = widgets.validate(spec, _ref_checker(conn), audience)
    if not result["valid"]:
        raise LiveError(422, "WIDGET_INVALID", "widget spec failed validation", {"errors": result["errors"]})
    normalized = result["normalized"]
    persistence = normalized["persistence"]
    spec_id = conn.execute(text(
        "INSERT INTO visual.widget_spec (widget_type, spec_version, title, spec, lifecycle, persistence, "
        "live_session_id, source_type, source_lineage, validation, content_hash, created_by, expires_at) VALUES "
        "(:t, :v, :ti, CAST(:s AS jsonb), 'VALIDATED', :p, CAST(:sid AS uuid), :st, CAST(:l AS jsonb), "
        "CAST(:val AS jsonb), :h, :by, CASE WHEN :p = 'EPHEMERAL' THEN now() + interval '1 day' END) "
        "RETURNING widget_spec_id::text"),
        {"t": normalized["widget_type"], "v": normalized["version"], "ti": normalized["title"],
         "s": json.dumps(normalized), "p": persistence, "sid": sid, "st": source_type,
         "l": json.dumps(normalized.get("source_lineage") or {}),
         "val": json.dumps({"errors": [], "warnings": result["warnings"]}),
         "h": widgets.content_hash(normalized), "by": actor}).scalar_one()
    return {"widget_spec_id": spec_id, "spec": normalized, "warnings": result["warnings"]}


def _show_widget(conn, s, payload, actor_type, actor_id) -> dict:
    sid = s["session_id"]
    if payload.get("widget_spec_id"):
        row = _row(conn.execute(text(
            "SELECT widget_spec_id::text AS widget_spec_id, spec, lifecycle FROM visual.widget_spec "
            "WHERE widget_spec_id = CAST(:w AS uuid)"), {"w": payload["widget_spec_id"]}))
        if row is None or row["lifecycle"] in ("REJECTED", "EXPIRED"):
            raise LiveError(404, "WIDGET_NOT_FOUND", "widget spec not found or not showable")
        stored = row
    else:
        source = {"AI_TUTOR": "LIVE_AGENT_CREATED"}.get(actor_type, "INSTRUCTOR_CREATED")
        stored = store_widget_spec(conn, payload.get("spec") or {}, payload.get("source_type") or source,
                                   actor_id or actor_type, sid)
    instance_id = payload.get("widget_instance_id") or f"w-{uuid4().hex[:10]}"
    conn.execute(text(
        "INSERT INTO visual.widget_state (live_session_id, widget_instance_id, widget_spec_id, state) "
        "VALUES (CAST(:s AS uuid), :i, CAST(:w AS uuid), '{}'::jsonb) ON CONFLICT (live_session_id, widget_instance_id) "
        "DO UPDATE SET widget_spec_id = EXCLUDED.widget_spec_id, visible = true, state_version = "
        "visual.widget_state.state_version + 1, updated_at = now()"),
        {"s": sid, "i": instance_id, "w": stored["widget_spec_id"]})
    conn.execute(text("UPDATE visual.widget_spec SET lifecycle = 'SHOWN' WHERE widget_spec_id = CAST(:w AS uuid) "
                      "AND lifecycle IN ('VALIDATED', 'READY')"), {"w": stored["widget_spec_id"]})
    stage = s.get("stage") or {}
    stage.setdefault("widgets", {})[instance_id] = {"widget_spec_id": stored["widget_spec_id"], "spec": stored["spec"],
                                                    "state": {}, "visible": True}
    _save_stage(conn, sid, stage)
    return {"event": "widget.shown", "bump": True,
            "payload": {"widget_instance_id": instance_id, "widget_spec_id": stored["widget_spec_id"],
                        "spec": stored["spec"]}}


def _update_widget(conn, s, payload) -> dict:
    sid, instance_id = s["session_id"], payload.get("widget_instance_id")
    stage = s.get("stage") or {}
    current = (stage.get("widgets") or {}).get(instance_id)
    if not current:
        raise LiveError(404, "WIDGET_INSTANCE_NOT_FOUND", "widget instance is not on stage")
    operations = payload.get("operations") or []
    errors = widgets.validate_operations(current["spec"], operations)
    if errors:
        raise LiveError(422, "WIDGET_OPERATIONS_INVALID", "widget operations failed validation", {"errors": errors})
    state = dict(current.get("state") or {})
    state.setdefault("operations", []).extend(operations)
    state.update(payload.get("state") or {})
    current["state"] = state
    _save_stage(conn, sid, stage)
    conn.execute(text("UPDATE visual.widget_state SET state = CAST(:st AS jsonb), state_version = state_version + 1, "
                      "updated_at = now() WHERE live_session_id = CAST(:s AS uuid) AND widget_instance_id = :i"),
                 {"st": json.dumps(_jsonable(state)), "s": sid, "i": instance_id})
    return {"event": "widget.updated", "bump": True,
            "payload": {"widget_instance_id": instance_id, "operations": operations, "state": state}}


def _hide_widget(conn, s, payload) -> dict:
    sid, instance_id = s["session_id"], payload.get("widget_instance_id")
    stage = s.get("stage") or {}
    if instance_id not in (stage.get("widgets") or {}):
        raise LiveError(404, "WIDGET_INSTANCE_NOT_FOUND", "widget instance is not on stage")
    stage["widgets"].pop(instance_id)
    _save_stage(conn, sid, stage)
    conn.execute(text("UPDATE visual.widget_state SET visible = false, updated_at = now() "
                      "WHERE live_session_id = CAST(:s AS uuid) AND widget_instance_id = :i"), {"s": sid, "i": instance_id})
    return {"event": "widget.hidden", "bump": True, "payload": {"widget_instance_id": instance_id}}


def _save_stage(conn, sid: str, stage: dict) -> None:
    conn.execute(text("UPDATE live.session SET stage = CAST(:st AS jsonb) WHERE live_session_id = CAST(:s AS uuid)"),
                 {"st": json.dumps(_jsonable(stage)), "s": sid})


# ------------------------------------------------------------------ activities (fluid 07/14)

ACTIVITY_TYPES = ("MCQ", "MULTISELECT", "NUMERIC", "SHORT_RESPONSE", "SUBPROBLEM", "STEP_ORDERING",
                  "ERROR_DIAGNOSIS", "CONFIDENCE_CHECK", "LIVE_POLL")  # mirrors activity.definition CHECK (020)


def create_activity_definition(conn: Connection, body: dict, actor: str) -> dict:
    options = body.get("options") or []
    if body.get("activity_type") and body["activity_type"] not in ACTIVITY_TYPES:
        raise LiveError(422, "ACTIVITY_INVALID", f"activity_type must be one of {', '.join(ACTIVITY_TYPES)}")
    if body.get("activity_type") in ("MCQ", "MULTISELECT", "LIVE_POLL", "CONFIDENCE_CHECK") and len(options) < 2:
        raise LiveError(422, "ACTIVITY_INVALID", "choice activities need at least two options")
    for o in options:
        problems: list[str] = []
        widgets._walk(o, "option", problems)
        if problems:
            raise LiveError(422, "ACTIVITY_INVALID", "unsafe option content", {"errors": problems})
    row = _row(conn.execute(text(
        "INSERT INTO activity.definition (activity_type, prompt, options, correctness_policy, target_skill, "
        "estimated_seconds, source_type, source_lineage, persistence_mode, created_by) VALUES (:t, :p, "
        "CAST(:o AS jsonb), CAST(:c AS jsonb), :sk, :e, :st, CAST(:l AS jsonb), :pm, :by) "
        "RETURNING activity_id::text AS activity_id, activity_type, prompt, options, correctness_policy"),
        {"t": body.get("activity_type") or "LIVE_POLL", "p": body["prompt"], "o": json.dumps(options),
         "c": json.dumps(body.get("correctness_policy") or {}), "sk": body.get("target_skill"),
         "e": int(body.get("estimated_seconds") or 60), "st": body.get("source_type") or "INSTRUCTOR_CREATED",
         "l": json.dumps(body.get("source_lineage") or {}), "pm": body.get("persistence_mode") or "SESSION",
         "by": actor}))
    return _jsonable(row)


def _option_key(option) -> str:
    return str(option.get("key") or option.get("id") or option.get("label")) if isinstance(option, dict) else str(option)


def aggregate(conn: Connection, instance_id: str) -> dict:
    inst = _row(conn.execute(text(
        "SELECT i.activity_instance_id::text AS instance_id, i.status, d.activity_type, d.prompt, d.options, "
        "d.correctness_policy FROM activity.instance i JOIN activity.definition d USING (activity_id) "
        "WHERE i.activity_instance_id = CAST(:i AS uuid)"), {"i": instance_id}))
    if inst is None:
        raise LiveError(404, "ACTIVITY_NOT_FOUND", "activity instance not found")
    keys = [_option_key(o) for o in inst["options"]]
    counts = {k: 0 for k in keys}
    rows = conn.execute(text("SELECT response, confidence, is_correct FROM activity.response "
                             "WHERE activity_instance_id = CAST(:i AS uuid)"), {"i": instance_id}).mappings().all()
    confidences, correct = [], []
    for r in rows:
        choice = (r["response"] or {}).get("option")
        chosen = choice if isinstance(choice, list) else [choice]
        for c in chosen:
            if c is not None:
                counts[str(c)] = counts.get(str(c), 0) + 1
        if r["confidence"] is not None:
            confidences.append(int(r["confidence"]))
        if r["is_correct"] is not None:
            correct.append(bool(r["is_correct"]))
    total = len(rows)
    pct = {k: round(100.0 * v / total, 1) if total else 0.0 for k, v in counts.items()}
    rate = (sum(correct) / len(correct)) if correct else None
    branch = None
    if rate is not None:
        branch = next(name for name, floor in BRANCHES if rate >= floor)
    return {"activity_instance_id": instance_id, "status": inst["status"], "prompt": inst["prompt"],
            "activity_type": inst["activity_type"], "response_count": total, "option_counts": counts,
            "option_percentages": pct,
            "average_confidence": round(sum(confidences) / len(confidences), 2) if confidences else None,
            "correct_rate": round(rate, 3) if rate is not None else None, "recommended_branch": branch,
            "correct_option": (inst["correctness_policy"] or {}).get("correct_option")}


def _open_activity(conn, s, payload, actor_id) -> dict:
    sid = s["session_id"]
    activity_id = payload.get("activity_id")
    if not activity_id:
        activity_id = create_activity_definition(conn, payload.get("definition") or {}, actor_id or "instructor")["activity_id"]
    stage = s.get("stage") or {}
    if stage.get("activity"):
        conn.execute(text("UPDATE activity.instance SET status = 'CLOSED', closed_at = now() "
                          "WHERE activity_instance_id = CAST(:i AS uuid) AND status = 'OPEN'"),
                     {"i": stage["activity"]["activity_instance_id"]})
    defn = _row(conn.execute(text(
        "SELECT activity_id::text AS activity_id, activity_type, prompt, options, estimated_seconds "
        "FROM activity.definition WHERE activity_id = CAST(:a AS uuid)"), {"a": activity_id}))
    if defn is None:
        raise LiveError(404, "ACTIVITY_DEFINITION_NOT_FOUND", "activity definition not found")
    instance_id = conn.execute(text(
        "INSERT INTO activity.instance (live_session_id, activity_id, anonymous, opened_by, closes_at) VALUES "
        "(CAST(:s AS uuid), CAST(:a AS uuid), :an, :by, now() + make_interval(secs => :sec)) "
        "RETURNING activity_instance_id::text"),
        {"s": sid, "a": activity_id, "an": bool(payload.get("anonymous", True)), "by": actor_id or "instructor",
         "sec": int(payload.get("seconds") or defn["estimated_seconds"])}).scalar_one()
    public = {"activity_instance_id": instance_id, "activity_id": activity_id, "activity_type": defn["activity_type"],
              "prompt": defn["prompt"], "options": defn["options"], "status": "OPEN"}
    stage["activity"] = public
    _save_stage(conn, sid, stage)
    return {"event": "activity.opened", "bump": True, "payload": public}


def _close_activity(conn, s, payload, reveal: bool) -> dict:
    sid = s["session_id"]
    stage = s.get("stage") or {}
    current = stage.get("activity") or {}
    instance_id = payload.get("activity_instance_id") or current.get("activity_instance_id")
    if not instance_id:
        raise LiveError(409, "NO_OPEN_ACTIVITY", "no activity is on stage")
    status = "REVEALED" if reveal else "CLOSED"
    conn.execute(text("UPDATE activity.instance SET status = :st, closed_at = COALESCE(closed_at, now()) "
                      "WHERE activity_instance_id = CAST(:i AS uuid) AND live_session_id = CAST(:s AS uuid)"),
                 {"st": status, "i": instance_id, "s": sid})
    agg = aggregate(conn, instance_id)
    result: dict = {"activity_instance_id": instance_id, "status": status}
    if current.get("activity_instance_id") == instance_id:
        current["status"] = status
        stage["activity"] = current
    if reveal:
        spec = widgets.poll_result_spec(agg["prompt"], agg, agg.get("correct_option"), instance_id)
        stored = store_widget_spec(conn, spec, "PRECOMPILED", "system", sid)
        wid = f"poll-{instance_id[:8]}"
        conn.execute(text(
            "INSERT INTO visual.widget_state (live_session_id, widget_instance_id, widget_spec_id) "
            "VALUES (CAST(:s AS uuid), :i, CAST(:w AS uuid)) ON CONFLICT (live_session_id, widget_instance_id) "
            "DO UPDATE SET widget_spec_id = EXCLUDED.widget_spec_id, visible = true, updated_at = now()"),
            {"s": sid, "i": wid, "w": stored["widget_spec_id"]})
        stage.setdefault("widgets", {})[wid] = {"widget_spec_id": stored["widget_spec_id"], "spec": stored["spec"],
                                                "state": {}, "visible": True}
        result.update({"aggregate": agg, "widget_instance_id": wid, "spec": stored["spec"]})
    _save_stage(conn, sid, stage)
    return {"event": "activity.revealed" if reveal else "activity.closed", "bump": True, "payload": result,
            "aggregate": agg}


def _submit_response(conn, s, payload, participant_id, client_command_id) -> dict:
    sid = s["session_id"]
    current = (s.get("stage") or {}).get("activity") or {}
    instance_id = payload.get("activity_instance_id") or current.get("activity_instance_id")
    inst = _row(conn.execute(text(
        "SELECT i.status, i.closes_at, d.correctness_policy FROM activity.instance i JOIN activity.definition d "
        "USING (activity_id) WHERE i.activity_instance_id = CAST(:i AS uuid) AND i.live_session_id = CAST(:s AS uuid)"),
        {"i": instance_id, "s": sid})) if instance_id else None
    if inst is None:
        raise LiveError(404, "ACTIVITY_NOT_FOUND", "activity instance not found")
    if inst["status"] != "OPEN":
        raise LiveError(409, "ACTIVITY_CLOSED", "this activity is no longer accepting responses")
    response = {"option": payload.get("option"), "text": payload.get("text")}
    policy = inst["correctness_policy"] or {}
    is_correct = None
    if policy.get("correct_option") is not None and payload.get("option") is not None:
        is_correct = str(payload["option"]) == str(policy["correct_option"])
    elif policy.get("numeric_answer") is not None and payload.get("text") not in (None, ""):
        try:
            is_correct = abs(float(payload["text"]) - float(policy["numeric_answer"])) <= float(policy.get("tolerance", 1e-6))
        except ValueError:
            is_correct = False
    confidence = payload.get("confidence")
    conn.execute(text(
        "INSERT INTO activity.response (activity_instance_id, participant_id, response, confidence, is_correct, "
        "client_command_id) VALUES (CAST(:i AS uuid), :p, CAST(:r AS jsonb), :c, :ok, :cc) "
        "ON CONFLICT (activity_instance_id, participant_id) DO UPDATE SET response = EXCLUDED.response, "
        "confidence = EXCLUDED.confidence, is_correct = EXCLUDED.is_correct, "
        "client_command_id = EXCLUDED.client_command_id, submitted_at = now()"),
        {"i": instance_id, "p": participant_id, "r": json.dumps(response),
         "c": int(confidence) if confidence else None, "ok": is_correct, "cc": client_command_id})
    return {"event": "activity.response.accepted", "bump": False, "audience": "STUDENT",
            "audience_id": participant_id, "payload": {"activity_instance_id": instance_id, "accepted": True},
            "instance_id": instance_id}


# ------------------------------------------------------------------ navigation

def _close_topic(conn, sid: str, idx: int, status: str = "DONE") -> None:
    conn.execute(text(
        "UPDATE live.topic_run SET ended_at = now(), status = :st, actual_seconds = "
        "GREATEST(0, EXTRACT(EPOCH FROM now() - started_at)::int) WHERE live_session_id = CAST(:s AS uuid) "
        "AND topic_index = :i AND status = 'ACTIVE'"), {"s": sid, "i": idx, "st": status})


def _enter_topic(conn, sid: str, idx: int) -> None:
    conn.execute(text("UPDATE live.topic_run SET started_at = COALESCE(started_at, now()), status = 'ACTIVE', "
                      "ended_at = NULL WHERE live_session_id = CAST(:s AS uuid) AND topic_index = :i"), {"s": sid, "i": idx})
    conn.execute(text("UPDATE live.session SET current_topic_index = :i, current_scene_index = 0, "
                      "topic_started_at = now() WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid, "i": idx})


def _goto(conn, s: dict, idx: int, reason: str) -> dict:
    topics = s.get("topics") or []
    if not 0 <= idx < len(topics):
        raise LiveError(409, "NO_SUCH_TOPIC", f"topic index {idx} is outside 0..{len(topics) - 1}")
    _close_topic(conn, s["session_id"], int(s["current_topic_index"]))
    _enter_topic(conn, s["session_id"], idx)
    return {"event": "scene.changed", "bump": True,
            "payload": {"topic_index": idx, "scene_index": 0, "topic": topics[idx], "reason": reason}}


def _navigate(conn, s: dict, command: str, payload: dict) -> dict:
    sid, idx = s["session_id"], int(s["current_topic_index"])
    topics = s.get("topics") or []
    if command == "START":
        if s["status"] != "SCHEDULED":
            raise LiveError(409, "ALREADY_STARTED", "session already started")
        conn.execute(text("UPDATE live.session SET status = 'ACTIVE', started_at = now() "
                          "WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid})
        _enter_topic(conn, sid, 0)
        return {"event": "session.started", "bump": True, "payload": {"topic_index": 0, "topic": topics[0] if topics else None}}
    if s["status"] in ("COMPLETED", "CANCELLED"):
        raise LiveError(409, "SESSION_ENDED", "session has ended")
    if s["status"] == "SCHEDULED":
        raise LiveError(409, "NOT_STARTED", "start the session first")
    if command == "PAUSE":
        if s["status"] == "PAUSED":
            raise LiveError(409, "ALREADY_PAUSED", "session already paused")
        conn.execute(text("UPDATE live.session SET status = 'PAUSED', paused_at = now() "
                          "WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid})
        return {"event": "session.paused", "bump": True, "payload": {}}
    if command == "RESUME":
        if s["status"] != "PAUSED":
            raise LiveError(409, "NOT_PAUSED", "session is not paused")
        conn.execute(text(
            "UPDATE live.session SET status = 'ACTIVE', paused_total_seconds = paused_total_seconds + "
            "GREATEST(0, EXTRACT(EPOCH FROM now() - paused_at)::int), topic_started_at = topic_started_at + "
            "(now() - paused_at), paused_at = NULL WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid})
        return {"event": "session.resumed", "bump": True, "payload": {}}
    if command == "NEXT":
        if idx + 1 >= len(topics):
            raise LiveError(409, "LAST_TOPIC", "already on the last topic; use COMPLETE")
        return _goto(conn, s, idx + 1, "next")
    if command == "BACK":
        if idx == 0:
            raise LiveError(409, "FIRST_TOPIC", "already on the first topic")
        return _goto(conn, s, idx - 1, "back")
    if command == "FORCE_SCENE":
        target = int(payload.get("topic_index", idx))
        if target != idx:
            out = _goto(conn, s, target, "forced")
        else:
            out = {"event": "scene.changed", "bump": True, "payload": {"topic_index": idx, "topic": topics[idx]}}
        scene = int(payload.get("scene_index") or 0)
        conn.execute(text("UPDATE live.session SET current_scene_index = :c WHERE live_session_id = CAST(:s AS uuid)"),
                     {"c": scene, "s": sid})
        out["payload"]["scene_index"] = scene
        return out
    if command == "SKIP":
        target = int(payload.get("topic_index", idx))
        if target == idx:
            _close_topic(conn, sid, idx, "SKIPPED")
            if idx + 1 < len(topics):
                out = _goto(conn, s, idx + 1, "skipped")
                out["payload"]["skipped_topic_index"] = idx
                return out
            return _complete(conn, s)
        conn.execute(text("UPDATE live.topic_run SET status = 'SKIPPED' WHERE live_session_id = CAST(:s AS uuid) "
                          "AND topic_index = :i AND status = 'PENDING'"), {"s": sid, "i": target})
        return {"event": "topic.skipped", "bump": True, "payload": {"topic_index": target}}
    if command in ("EXTEND", "SHORTEN"):
        seconds = int(payload.get("seconds") or 0)
        if seconds <= 0:
            raise LiveError(422, "INVALID_SECONDS", "seconds must be positive")
        delta = seconds if command == "EXTEND" else -seconds
        conn.execute(text("UPDATE live.session SET extension_seconds = extension_seconds + :d "
                          "WHERE live_session_id = CAST(:s AS uuid)"), {"d": delta, "s": sid})
        return {"event": "time.adjusted", "bump": True, "payload": {"delta_seconds": delta,
                                                                    "extension_seconds": int(s["extension_seconds"]) + delta}}
    if command == "COMPLETE":
        return _complete(conn, s)
    raise LiveError(400, "UNKNOWN_COMMAND", command)


def _complete(conn, s: dict) -> dict:
    sid = s["session_id"]
    _close_topic(conn, sid, int(s["current_topic_index"]))
    conn.execute(text("UPDATE live.session SET status = 'COMPLETED', completed_at = now(), "
                      "paused_total_seconds = paused_total_seconds + CASE WHEN paused_at IS NULL THEN 0 ELSE "
                      "GREATEST(0, EXTRACT(EPOCH FROM now() - paused_at)::int) END, paused_at = NULL "
                      "WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid})
    conn.execute(text("UPDATE live.takeover SET ended_at = now() WHERE live_session_id = CAST(:s AS uuid) "
                      "AND ended_at IS NULL"), {"s": sid})
    return {"event": "session.completed", "bump": True, "payload": {}}


# ------------------------------------------------------------------ takeover (dist 20)

def handoff_packet(conn: Connection, s: dict, scope: str, scope_id: str) -> dict:
    sid = s["session_id"]
    topics = s.get("topics") or []
    idx = int(s["current_topic_index"])
    who = "" if scope == "SESSION" else " AND actor_id = :who"
    params = {"s": sid, "who": scope_id}
    recent = [dict(r) for r in conn.execute(text(
        "SELECT event_type, actor_type, actor_id, payload, created_at FROM live.session_event "
        "WHERE live_session_id = CAST(:s AS uuid) AND event_type IN ('student.question', 'student.hint_requested', "
        "'student.confused', 'tutor.message', 'activity.response.accepted')" + who +
        " ORDER BY sequence DESC LIMIT 12"), params).mappings()]
    hints = sum(1 for r in recent if r["event_type"] == "student.hint_requested")
    confused = [r["actor_id"] for r in recent if r["event_type"] == "student.confused"]
    tried = [r["payload"].get("text", "")[:160] for r in recent if r["event_type"] == "tutor.message"][:3]
    agg = None
    activity = (s.get("stage") or {}).get("activity")
    if activity:
        agg = aggregate(conn, activity["activity_instance_id"])
    likely_gap = None
    if agg and agg.get("correct_rate") is not None and agg["correct_rate"] < 0.5:
        likely_gap = f"Most of the class missed “{agg['prompt'][:80]}”"
    elif hints >= 2 or confused:
        likely_gap = "Repeated hint requests / confusion on the current topic"
    move = "Continue the plan"
    if likely_gap:
        move = "Revisit the prerequisite idea with a worked example, then re-poll"
    return _jsonable({
        "scope": scope, "scope_id": scope_id,
        "topic": topics[idx] if idx < len(topics) else None, "scene_index": s["current_scene_index"],
        "recent_activity": list(reversed(recent)), "hints_used": hints, "confused_participants": confused,
        "poll_aggregate": agg, "likely_gap": likely_gap, "already_tried": tried, "recommended_next_move": move,
        "time": time_state(s)})


def _takeover(conn, s: dict, payload: dict, actor_id: str) -> dict:
    sid = s["session_id"]
    scope = (payload.get("scope") or "SESSION").upper()
    scope_id = str(payload.get("scope_id") or "*") if scope != "SESSION" else "*"
    if scope == "SESSION":
        changed = conn.execute(text(
            "UPDATE live.session SET control_mode = 'INSTRUCTOR_ACTIVE', controller = :c "
            "WHERE live_session_id = CAST(:s AS uuid) AND control_mode = 'AI_ACTIVE' RETURNING 1"),
            {"c": actor_id, "s": sid}).first()
    elif scope == "STUDENT":
        changed = conn.execute(text(
            "UPDATE live.participant SET control_mode = 'INSTRUCTOR_ACTIVE' WHERE live_session_id = CAST(:s AS uuid) "
            "AND participant_id = :p AND control_mode = 'AI_ACTIVE' RETURNING 1"), {"s": sid, "p": scope_id}).first()
    else:
        changed = conn.execute(text(
            "UPDATE live.participant SET control_mode = 'INSTRUCTOR_ACTIVE' WHERE live_session_id = CAST(:s AS uuid) "
            "AND group_id = :g AND control_mode = 'AI_ACTIVE' RETURNING 1"), {"s": sid, "g": scope_id}).first()
    if not changed:
        raise LiveError(409, "ALREADY_TAKEN_OVER", f"{scope.lower()} is not under AI control")
    packet = handoff_packet(conn, s, scope, scope_id)
    takeover_id = conn.execute(text(
        "INSERT INTO live.takeover (live_session_id, scope, scope_id, instructor, handoff_packet) VALUES "
        "(CAST(:s AS uuid), :sc, :id, :by, CAST(:p AS jsonb)) RETURNING takeover_id::text"),
        {"s": sid, "sc": scope, "id": scope_id, "by": actor_id, "p": json.dumps(packet)}).scalar_one()
    stale = conn.execute(text("UPDATE live.recommendation SET status = 'STALE', decided_at = now(), "
                              "decided_by = 'takeover' WHERE live_session_id = CAST(:s AS uuid) AND status = 'PROPOSED' "
                              "AND source = 'AI_TUTOR'"), {"s": sid}).rowcount
    return {"event": "instructor.takeover.started", "bump": True,
            "payload": {"takeover_id": takeover_id, "scope": scope, "scope_id": scope_id, "instructor": actor_id,
                        "stale_recommendations": stale},
            "private": {"handoff_packet": packet, "takeover_id": takeover_id}}


def _release(conn, s: dict, payload: dict, actor_id: str) -> dict:
    sid = s["session_id"]
    scope = (payload.get("scope") or "SESSION").upper()
    scope_id = str(payload.get("scope_id") or "*") if scope != "SESSION" else "*"
    ended = conn.execute(text("UPDATE live.takeover SET ended_at = now() WHERE live_session_id = CAST(:s AS uuid) "
                              "AND scope = :sc AND scope_id = :id AND ended_at IS NULL RETURNING takeover_id::text"),
                         {"s": sid, "sc": scope, "id": scope_id}).scalar()
    if not ended:
        raise LiveError(409, "NO_ACTIVE_TAKEOVER", "no active takeover for that scope")
    if scope == "SESSION":
        conn.execute(text("UPDATE live.session SET control_mode = 'AI_ACTIVE', controller = NULL "
                          "WHERE live_session_id = CAST(:s AS uuid)"), {"s": sid})
    elif scope == "STUDENT":
        conn.execute(text("UPDATE live.participant SET control_mode = 'AI_ACTIVE' WHERE live_session_id = "
                          "CAST(:s AS uuid) AND participant_id = :p"), {"s": sid, "p": scope_id})
    else:
        conn.execute(text("UPDATE live.participant SET control_mode = 'AI_ACTIVE' WHERE live_session_id = "
                          "CAST(:s AS uuid) AND group_id = :g"), {"s": sid, "g": scope_id})
    return {"event": "instructor.takeover.ended", "bump": True,
            "payload": {"takeover_id": ended, "scope": scope, "scope_id": scope_id, "instructor": actor_id}}


def _ai_in_control(conn, s: dict, participant_id: str | None) -> bool:
    if s["control_mode"] != "AI_ACTIVE" or s["agent_locked"]:
        return False
    if participant_id:
        p = participant(conn, s["session_id"], participant_id)
        if p and p["control_mode"] != "AI_ACTIVE":
            return False
        if p and p.get("group_id") and conn.execute(text(
                "SELECT 1 FROM live.takeover WHERE live_session_id = CAST(:s AS uuid) AND scope = 'GROUP' "
                "AND scope_id = :g AND ended_at IS NULL"), {"s": s["session_id"], "g": p["group_id"]}).first():
            return False
    return True


# ------------------------------------------------------------------ command pipeline

def _dispatch(conn, s: dict, command: str, actor_type: str, actor_id: str | None, payload: dict,
              client_command_id: str) -> dict:
    if command in ("START", "NEXT", "BACK", "PAUSE", "RESUME", "EXTEND", "SHORTEN", "SKIP", "FORCE_SCENE", "COMPLETE"):
        return _navigate(conn, s, command, payload)
    if command == "SELECT_BRANCH":
        branch = (payload.get("branch") or "CONTINUE").upper()
        if branch == "CONTINUE" and int(s["current_topic_index"]) + 1 < len(s.get("topics") or []):
            out = _goto(conn, s, int(s["current_topic_index"]) + 1, "branch:CONTINUE")
            out["payload"]["branch"] = branch
            return out
        return {"event": "branch.selected", "bump": True, "payload": {"branch": branch,
                                                                       "activity_instance_id": payload.get("activity_instance_id")}}
    if command in ("LOCK_AGENT", "UNLOCK_AGENT"):
        locked = command == "LOCK_AGENT"
        conn.execute(text("UPDATE live.session SET agent_locked = :l WHERE live_session_id = CAST(:s AS uuid)"),
                     {"l": locked, "s": s["session_id"]})
        if locked:
            conn.execute(text("UPDATE live.recommendation SET status = 'STALE', decided_at = now(), decided_by = 'lock' "
                              "WHERE live_session_id = CAST(:s AS uuid) AND status = 'PROPOSED' AND source = 'AI_TUTOR'"),
                         {"s": s["session_id"]})
        return {"event": "agent.locked" if locked else "agent.unlocked", "bump": True, "payload": {}}
    if command == "TAKEOVER":
        return _takeover(conn, s, payload, actor_id or "instructor")
    if command == "RELEASE":
        return _release(conn, s, payload, actor_id or "instructor")
    if command == "SHOW_WIDGET":
        return _show_widget(conn, s, payload, actor_type, actor_id)
    if command == "UPDATE_WIDGET":
        return _update_widget(conn, s, payload)
    if command == "HIDE_WIDGET":
        return _hide_widget(conn, s, payload)
    if command == "OPEN_ACTIVITY":
        return _open_activity(conn, s, payload, actor_id)
    if command in ("CLOSE_ACTIVITY", "REVEAL_ACTIVITY"):
        out = _close_activity(conn, s, payload, command == "REVEAL_ACTIVITY")
        agg = out.pop("aggregate")
        if agg.get("recommended_branch") and command == "CLOSE_ACTIVITY":
            _recommend(conn, s, "POLL_BRANCH", {"command_type": "SELECT_BRANCH",
                                                "payload": {"branch": agg["recommended_branch"],
                                                            "activity_instance_id": agg["activity_instance_id"]}},
                       f"{round(100 * agg['correct_rate'])}% correct → {agg['recommended_branch']}",
                       int(s["state_version"]) + 1)
        return out
    if command == "INSTRUCTOR_MESSAGE":
        msg = (payload.get("text") or "").strip()
        if not msg:
            raise LiveError(422, "EMPTY_MESSAGE", "message text required")
        target = payload.get("participant_id")
        return {"event": "instructor.message", "bump": False, "payload": {"text": msg[:4000]},
                "audience": "STUDENT" if target else "SESSION", "audience_id": target}
    if command == "TUTOR_MESSAGE":
        target = payload.get("participant_id")
        if not _ai_in_control(conn, s, target):
            raise LiveError(409, "AI_NOT_IN_CONTROL", "the AI tutor is not in control of this scope")
        return {"event": "tutor.message", "bump": False,
                "payload": {"text": (payload.get("text") or "")[:6000], "widget_suggestion": payload.get("widget_suggestion")},
                "audience": "STUDENT" if target else "SESSION", "audience_id": target}
    if command == "RESPONSE_SUBMIT":
        return _submit_response(conn, s, payload, actor_id, client_command_id)
    if command in ("HINT_REQUEST", "QUESTION_ASK", "MARK_CONFUSED", "WIDGET_INTERACT"):
        if command == "MARK_CONFUSED":
            conn.execute(text("UPDATE live.participant SET confused = :c, last_seen_at = now() WHERE live_session_id = "
                              "CAST(:s AS uuid) AND participant_id = :p"),
                         {"c": bool(payload.get("confused", True)), "s": s["session_id"], "p": actor_id})
        names = {"HINT_REQUEST": "student.hint_requested", "QUESTION_ASK": "student.question",
                 "MARK_CONFUSED": "student.confused", "WIDGET_INTERACT": "student.widget_interaction"}
        body = {k: payload.get(k) for k in ("text", "widget_instance_id", "interaction", "confused") if k in payload}
        if "text" in body:
            body["text"] = str(body["text"])[:4000]
        return {"event": names[command], "bump": False, "payload": body, "audience": "INSTRUCTOR"}
    raise LiveError(400, "UNKNOWN_COMMAND", f"unknown command {command}")


def _authorise(conn, s: dict, command: str, actor_type: str, actor_id: str | None) -> None:
    if actor_type in STAFF:
        if command not in CONTROL_COMMANDS:
            raise LiveError(403, "FORBIDDEN_COMMAND", f"{actor_type} cannot issue {command}")
        return
    if actor_type == "STUDENT":
        if command not in STUDENT_COMMANDS:
            raise LiveError(403, "FORBIDDEN_COMMAND", "students may only respond, ask, request hints or interact")
        p = participant(conn, s["session_id"], actor_id or "")
        if not p or p["role"] != "STUDENT":
            raise LiveError(403, "NOT_A_PARTICIPANT", "join the session first")
        if s["status"] not in ("ACTIVE", "PAUSED"):
            raise LiveError(409, "SESSION_NOT_ACTIVE", "session is not running")
        return
    if actor_type == "AI_TUTOR":
        if command not in AI_COMMANDS:
            raise LiveError(403, "AI_PROPOSES_ONLY", "AI actions must go through recommendations")
        return
    raise LiveError(403, "FORBIDDEN_COMMAND", f"unknown actor {actor_type}")


def execute_command(conn: Connection, sid: str, command_type: str, actor_type: str, actor_id: str | None,
                    client_command_id: str, expected_session_version: int | None, payload: dict | None = None,
                    correlation_id: str | None = None) -> dict:
    """Idempotent, version-checked command. Returns the stored result; REJECTED results carry ``error``."""
    command = (command_type or "").upper()
    payload = payload or {}
    receipt = _row(conn.execute(text(
        "SELECT status, result FROM live.command_receipt WHERE live_session_id = CAST(:s AS uuid) "
        "AND client_command_id = :c"), {"s": sid, "c": client_command_id}))
    if receipt:
        return {**receipt["result"], "duplicate": True}
    s = get_session(conn, sid, lock=True)
    savepoint = conn.begin_nested()  # a rejection mid-dispatch must not leave partial writes behind
    try:
        _authorise(conn, s, command, actor_type, actor_id)
        version_bound = actor_type != "STUDENT"
        if version_bound and expected_session_version is not None and int(expected_session_version) != int(s["state_version"]):
            raise LiveError(409, "STALE_VERSION", "session changed since you last looked",
                            {"expected": expected_session_version, "current": s["state_version"]})
        if version_bound and expected_session_version is None and actor_type == "AI_TUTOR":
            raise LiveError(409, "STALE_VERSION", "AI commands must carry expected_session_version")
        out = _dispatch(conn, s, command, actor_type, actor_id, payload, client_command_id)
        event = emit(conn, sid, out["event"], actor_type, actor_id, out.get("payload") or {},
                     out.get("audience", "SESSION"), out.get("audience_id"), bool(out.get("bump")),
                     correlation_id=correlation_id or client_command_id, causation_id=client_command_id)
        if out.get("private"):
            emit(conn, sid, "instructor.handoff_packet", "SYSTEM", None, out["private"], "INSTRUCTOR",
                 correlation_id=correlation_id or client_command_id, causation_id=event["event_id"])
        if out.get("instance_id"):
            agg = aggregate(conn, out["instance_id"])
            emit(conn, sid, "activity.aggregate.updated", "SYSTEM", None, agg, "INSTRUCTOR",
                 correlation_id=correlation_id or client_command_id, causation_id=event["event_id"])
        fresh = get_session(conn, sid)
        result = {"status": "ACCEPTED", "command_type": command, "client_command_id": client_command_id,
                  "event": event, "session_version": int(fresh["state_version"]),
                  "last_sequence": int(fresh["last_sequence"])}
        if out.get("private"):
            result["handoff_packet"] = out["private"]["handoff_packet"]
        status = "ACCEPTED"
        savepoint.commit()
    except LiveError as exc:
        savepoint.rollback()
        result = {"status": "REJECTED", "command_type": command, "client_command_id": client_command_id,
                  "error": {"code": exc.code, "message": str(exc), "http_status": exc.status_code, **exc.details},
                  "session_version": int(s["state_version"])}
        status = "REJECTED"
    conn.execute(text(
        "INSERT INTO live.command_receipt (live_session_id, client_command_id, command_type, actor_type, actor_id, "
        "status, result) VALUES (CAST(:s AS uuid), :c, :t, :at, :aid, :st, CAST(:r AS jsonb))"),
        {"s": sid, "c": client_command_id, "t": command, "at": actor_type, "aid": actor_id, "st": status,
         "r": json.dumps(_jsonable(result))})
    return _jsonable(result)


# ------------------------------------------------------------------ recommendations

def _recommend(conn, s: dict, source: str, action: dict, rationale: str, based_on_version: int) -> str:
    return conn.execute(text(
        "INSERT INTO live.recommendation (live_session_id, source, action, rationale, based_on_version) VALUES "
        "(CAST(:s AS uuid), :src, CAST(:a AS jsonb), :r, :v) RETURNING recommendation_id::text"),
        {"s": s["session_id"], "src": source, "a": json.dumps(_jsonable(action)), "r": rationale,
         "v": based_on_version}).scalar_one()


def propose_ai_action(conn: Connection, sid: str, action: dict, rationale: str, based_on_version: int,
                      source: str = "AI_TUTOR", participant_id: str | None = None) -> dict:
    """Agents propose; this either auto-applies (AI_ACTIVE, unlocked, fresh, allow-listed) or queues."""
    s = get_session(conn, sid, lock=True)
    command = (action.get("command_type") or "").upper()
    if command not in CONTROL_COMMANDS:
        raise LiveError(422, "UNKNOWN_ACTION", f"{command} is not a session action")
    if command == "EXTEND" and s["hard_limit"]:
        raise LiveError(409, "HARD_LIMIT", "the AI can never extend past a hard time limit")
    rid = _recommend(conn, s, source, {**action, "command_type": command}, rationale, based_on_version)
    stale = int(based_on_version) != int(s["state_version"])
    if stale:
        conn.execute(text("UPDATE live.recommendation SET status = 'STALE', decided_at = now(), decided_by = 'system' "
                          "WHERE recommendation_id = CAST(:r AS uuid)"), {"r": rid})
        return {"recommendation_id": rid, "status": "STALE", "applied": False, "session_version": s["state_version"]}
    if command in AUTO_APPLY and _ai_in_control(conn, s, participant_id):
        result = execute_command(conn, sid, command, "INSTRUCTOR", f"auto:{source.lower()}", f"rec:{rid}",
                                 int(s["state_version"]), action.get("payload") or {})
        accepted = result["status"] == "ACCEPTED"
        conn.execute(text("UPDATE live.recommendation SET status = :st, decided_at = now(), decided_by = 'policy:auto' "
                          "WHERE recommendation_id = CAST(:r AS uuid)"),
                     {"st": "ACCEPTED" if accepted else "REJECTED", "r": rid})
        return {"recommendation_id": rid, "status": "ACCEPTED" if accepted else "REJECTED", "applied": accepted,
                "result": result}
    emit(conn, sid, "recommendation.proposed", "SYSTEM", None,
         {"recommendation_id": rid, "source": source, "action": action, "rationale": rationale}, "INSTRUCTOR")
    return {"recommendation_id": rid, "status": "PROPOSED", "applied": False}


def list_recommendations(conn: Connection, sid: str, status: str | None = None) -> list[dict]:
    return [_jsonable(dict(r)) for r in conn.execute(text(
        "SELECT recommendation_id::text, source, action, rationale, based_on_version, status, decided_by, decided_at, "
        "created_at FROM live.recommendation WHERE live_session_id = CAST(:s AS uuid) "
        "AND (CAST(:st AS text) IS NULL OR status = :st) ORDER BY created_at DESC LIMIT 100"),
        {"s": sid, "st": status}).mappings()]


def decide_recommendation(conn: Connection, sid: str, rid: str, decision: str, actor: str,
                          expected_session_version: int | None) -> dict:
    rec = _row(conn.execute(text(
        "SELECT recommendation_id::text AS rid, action, status, based_on_version FROM live.recommendation "
        "WHERE recommendation_id = CAST(:r AS uuid) AND live_session_id = CAST(:s AS uuid) FOR UPDATE"),
        {"r": rid, "s": sid}))
    if rec is None:
        raise LiveError(404, "RECOMMENDATION_NOT_FOUND", "recommendation not found")
    if rec["status"] != "PROPOSED":
        raise LiveError(409, "RECOMMENDATION_DECIDED", f"recommendation is {rec['status']}")
    if decision.upper() == "REJECT":
        conn.execute(text("UPDATE live.recommendation SET status = 'REJECTED', decided_by = :a, decided_at = now() "
                          "WHERE recommendation_id = CAST(:r AS uuid)"), {"a": actor, "r": rid})
        return {"recommendation_id": rid, "status": "REJECTED"}
    action = rec["action"]
    result = execute_command(conn, sid, action["command_type"], "INSTRUCTOR", actor, f"rec:{rid}",
                             expected_session_version, action.get("payload") or {})
    status = "ACCEPTED" if result["status"] == "ACCEPTED" else "PROPOSED"
    if status == "ACCEPTED":
        conn.execute(text("UPDATE live.recommendation SET status = 'ACCEPTED', decided_by = :a, decided_at = now() "
                          "WHERE recommendation_id = CAST(:r AS uuid)"), {"a": actor, "r": rid})
    return {"recommendation_id": rid, "status": status, "result": result}


# ------------------------------------------------------------------ instructor natural language (fluid 16)

def compile_instructor_command(message: str, s: dict) -> list[dict]:
    low = (message or "").strip().lower()
    acts: list[dict] = []
    poll = re.search(r"(?:open|run|start)\s+(?:a\s+)?poll\s*[:\-]?\s*[\"“]?(.+?\?)[\"”]?\s*(.*)$", message or "", re.I | re.S)
    if poll:
        rest = poll.group(2)
        correct = re.search(r"[\s,;.]*\bcorrect\s*(?:answer)?\s*(?:is|=|:)?\s*([A-F])\b\.?\s*$", rest, re.I)
        if correct:
            rest = rest[:correct.start()]
        parts = re.split(r"(?:^|\s)([A-F])\)\s*", rest)
        opts = [(parts[i], parts[i + 1].strip().rstrip(",;")) for i in range(1, len(parts) - 1, 2)]
        options = [{"key": k.upper(), "label": v} for k, v in opts if v] or \
                  [{"key": "A", "label": "Yes"}, {"key": "B", "label": "No"}, {"key": "C", "label": "Not sure"}]
        acts.append({"command_type": "OPEN_ACTIVITY", "payload": {"definition": {
            "activity_type": "LIVE_POLL", "prompt": poll.group(1).strip(), "options": options,
            "correctness_policy": {"correct_option": correct.group(1).upper()} if correct else {}}}})
        return acts
    minutes = re.search(r"(\d+)\s*(?:min|minute)", low)
    topic = re.search(r"\btopic\s*#?\s*(\d+)", low)
    if re.search(r"\b(take over|takeover|i'?ll take it|my turn)\b", low):
        student = re.search(r"student:[0-9a-f-]{36}", low)
        acts.append({"command_type": "TAKEOVER", "payload": {"scope": "STUDENT", "scope_id": student.group(0)}
                     if student else {"scope": "SESSION"}})
    elif re.search(r"\b(hand back|give back|release|resume ai|ai take over)\b", low):
        acts.append({"command_type": "RELEASE", "payload": {"scope": "SESSION"}})
    elif re.search(r"\b(unlock)\b.*\b(agent|ai|tutor)\b", low):
        acts.append({"command_type": "UNLOCK_AGENT", "payload": {}})
    elif re.search(r"\b(lock|freeze|mute)\b.*\b(agent|ai|tutor)\b", low):
        acts.append({"command_type": "LOCK_AGENT", "payload": {}})
    elif re.search(r"\b(reveal|show (the )?results?)\b", low):
        acts.append({"command_type": "REVEAL_ACTIVITY", "payload": {}})
    elif re.search(r"\bclose\b.*\b(poll|activity|question)\b", low):
        acts.append({"command_type": "CLOSE_ACTIVITY", "payload": {}})
    elif re.search(r"\b(extend|add|more time)\b", low) and minutes:
        acts.append({"command_type": "EXTEND", "payload": {"seconds": int(minutes.group(1)) * 60}})
    elif re.search(r"\b(shorten|cut|less time)\b", low) and minutes:
        acts.append({"command_type": "SHORTEN", "payload": {"seconds": int(minutes.group(1)) * 60}})
    elif re.search(r"\bskip\b", low):
        acts.append({"command_type": "SKIP", "payload": {"topic_index": int(topic.group(1)) - 1} if topic else {}})
    elif re.search(r"\b(go to|jump to|switch to)\b", low) and topic:
        acts.append({"command_type": "FORCE_SCENE", "payload": {"topic_index": int(topic.group(1)) - 1}})
    elif re.search(r"\b(next|move on|continue)\b", low):
        acts.append({"command_type": "NEXT", "payload": {}})
    elif re.search(r"\b(back|previous)\b", low):
        acts.append({"command_type": "BACK", "payload": {}})
    elif re.search(r"\bpause\b", low):
        acts.append({"command_type": "PAUSE", "payload": {}})
    elif re.search(r"\b(resume|unpause)\b", low):
        acts.append({"command_type": "RESUME", "payload": {}})
    elif re.search(r"\b(show|draw|display)\b", low):
        intent = re.sub(r"^\s*(please\s+)?(show|draw|display)\s+(me\s+|them\s+|a\s+|the\s+)*", "", message or "", flags=re.I)
        composed = widgets.compose(intent)
        acts.append({"command_type": "SHOW_WIDGET", "payload": {"spec": composed["spec"],
                                                                "composer_strategy": composed["strategy"]}})
    elif re.search(r"\b(end|finish|complete)\b.*\b(session|class|lesson)\b", low):
        acts.append({"command_type": "COMPLETE", "payload": {}})
    return acts


def instructor_nl(conn: Connection, sid: str, message: str, actor: str, auto_apply: bool = False,
                  expected_session_version: int | None = None) -> dict:
    s = get_session(conn, sid, lock=True)
    actions = compile_instructor_command(message, s)
    if not actions:
        return {"understood": False, "actions": [],
                "message": "Try: next, back, pause, extend 5 minutes, skip topic 3, open poll \"Q? A) .. B) ..\", "
                           "show power of a point, reveal results, take over, lock agent."}
    out = []
    for i, action in enumerate(actions):
        rid = _recommend(conn, s, "INSTRUCTOR_NL", action, message[:500], int(s["state_version"]))
        if auto_apply:
            out.append(decide_recommendation(conn, sid, rid, "ACCEPT", actor,
                                             expected_session_version if i == 0 else None))
        else:
            out.append({"recommendation_id": rid, "status": "PROPOSED", "action": action})
    return {"understood": True, "actions": out}


# ------------------------------------------------------------------ snapshots / context

def snapshot(conn: Connection, sid: str, role: str = "INSTRUCTOR", participant_id: str | None = None) -> dict:
    s = get_session(conn, sid)
    topics = s.get("topics") or []
    idx = int(s["current_topic_index"])
    stage = s.get("stage") or {}
    me = participant(conn, sid, participant_id) if participant_id else None
    view = {"session_id": sid, "title": s["title"], "status": s["status"], "join_code": s["join_code"],
            "control_mode": s["control_mode"], "agent_locked": s["agent_locked"],
            "state_version": int(s["state_version"]), "last_sequence": int(s["last_sequence"]),
            "current_topic_index": idx, "current_scene_index": int(s["current_scene_index"]),
            "topic": topics[idx] if idx < len(topics) else None,
            "topics": [{"ordinal": t["ordinal"], "title": t["title"], "planned_seconds": t["planned_seconds"],
                        "required": t.get("required", True)} for t in topics],
            "widgets": [{"widget_instance_id": k, **v} for k, v in (stage.get("widgets") or {}).items()],
            "activity": stage.get("activity"), "time": time_state(s), "me": me}
    if role in STAFF:
        view["participants"] = [_jsonable(dict(r)) for r in conn.execute(text(
            "SELECT participant_id, role, display_name, group_id, control_mode, confused, last_seen_at "
            "FROM live.participant WHERE live_session_id = CAST(:s AS uuid) ORDER BY joined_at"), {"s": sid}).mappings()]
        view["recommendations"] = list_recommendations(conn, sid, "PROPOSED")
        if stage.get("activity"):
            view["activity_aggregate"] = aggregate(conn, stage["activity"]["activity_instance_id"])
        view["takeovers"] = [_jsonable(dict(r)) for r in conn.execute(text(
            "SELECT takeover_id::text, scope, scope_id, instructor, started_at FROM live.takeover "
            "WHERE live_session_id = CAST(:s AS uuid) AND ended_at IS NULL"), {"s": sid}).mappings()]
        view["topic_runs"] = [_jsonable(dict(r)) for r in conn.execute(text(
            "SELECT topic_index, title, planned_seconds, actual_seconds, status FROM live.topic_run "
            "WHERE live_session_id = CAST(:s AS uuid) ORDER BY topic_index"), {"s": sid}).mappings()]
    elif stage.get("activity") and stage["activity"].get("status") == "REVEALED":
        view["activity_aggregate"] = aggregate(conn, stage["activity"]["activity_instance_id"])
    return _jsonable(view)


def tutor_context(conn: Connection, sid: str, participant_id: str | None = None) -> dict:
    """Minimal, permission-filtered context for the tutor agent (fluid 15). No solutions, no identities."""
    snap = snapshot(conn, sid, "STUDENT", participant_id)
    recent = [dict(r) for r in conn.execute(text(
        "SELECT event_type, actor_type, payload FROM live.session_event WHERE live_session_id = CAST(:s AS uuid) "
        "AND event_type IN ('student.question', 'tutor.message', 'instructor.message', 'scene.changed', "
        "'activity.opened', 'activity.revealed') AND (audience = 'SESSION' OR audience_id = :p) "
        "ORDER BY sequence DESC LIMIT 10"), {"s": sid, "p": participant_id}).mappings()]
    s = get_session(conn, sid)
    return {"session": {k: snap[k] for k in ("session_id", "title", "status", "state_version", "current_topic_index",
                                             "topic", "activity", "time")},
            "widgets_on_stage": [{"widget_instance_id": w["widget_instance_id"], "widget_type": w["spec"]["widget_type"],
                                  "title": w["spec"].get("title")} for w in snap["widgets"]],
            "ai_in_control": _ai_in_control(conn, s, participant_id),
            "agent_locked": snap["agent_locked"], "control_mode": snap["control_mode"],
            "recent": _jsonable(list(reversed(recent))),
            "allowed_actions": sorted(AUTO_APPLY | {"TUTOR_MESSAGE"}),
            "rules": ["Never reveal hidden solutions", "Instructor actions outrank the tutor",
                      "Send expected_session_version; stale actions are discarded"]}
