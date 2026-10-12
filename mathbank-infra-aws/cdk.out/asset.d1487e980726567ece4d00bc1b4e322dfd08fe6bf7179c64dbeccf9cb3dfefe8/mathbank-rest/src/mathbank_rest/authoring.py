"""Presentation plans, timing validation and admin-chat patches (fluid 04/05/06).

The admin chat never edits a plan directly: each message is compiled into a structured patch
(``{op, target, before, after}`` operations + impact + validation) that the admin APPLIES, REJECTS,
MODIFIES or asks an ALTERNATIVE for. A whole patch is validated and applied in one transaction.
Published plans are immutable (DB trigger); applying a patch to one creates the next DRAFT version.
The deterministic parser covers the common timing/structure edits; an optional model parser can be
injected but its output passes the same operation validation.
"""
from __future__ import annotations

import copy
import json
import re
import secrets
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection

SCENE_KINDS = ("EXPLAIN", "WIDGET", "ACTIVITY", "POLL", "PRACTICE", "DISCUSSION")
PATCH_OPS = ("UPDATE_TOPIC_TIME", "UPDATE_COURSE_LIMIT", "UPDATE_BUFFER", "SET_HARD_LIMIT", "SET_TOPIC_REQUIRED",
             "REMOVE_TOPIC", "ADD_TOPIC", "MOVE_TOPIC", "RENAME_TOPIC", "ADD_SCENE")


class AuthoringError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.status_code, self.code, self.details = status_code, code, details or {}


# ------------------------------------------------------------------ pure plan logic

def timing_summary(plan: dict) -> dict:
    topics = plan.get("topics", [])
    planned = sum(int(t.get("planned_seconds", 0)) for t in topics)
    optional = sum(int(t.get("planned_seconds", 0)) for t in topics if not t.get("required", True))
    limit = int(plan["course_limit_seconds"])
    buffer = int(plan.get("interaction_buffer_seconds", 0))
    return {"course_limit_seconds": limit, "planned_content_seconds": planned, "interaction_buffer_seconds": buffer,
            "available_content_seconds": limit - buffer, "slack_seconds": limit - buffer - planned,
            "optional_content_seconds": optional, "hard_limit": bool(plan.get("hard_limit"))}


def validate_plan(plan: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    topics = plan.get("topics", [])
    if not plan.get("title"):
        errors.append("plan needs a title")
    if not topics:
        errors.append("plan needs at least one topic")
    if int(plan.get("course_limit_seconds") or 0) <= 0:
        errors.append("course_limit_seconds must be positive")
    if int(plan.get("interaction_buffer_seconds") or 0) < 0:
        errors.append("interaction_buffer_seconds cannot be negative")
    if sorted(int(t.get("ordinal", -1)) for t in topics) != list(range(len(topics))):
        errors.append("topic ordinals must be contiguous from 0")
    for t in topics:
        name = f"topic {int(t.get('ordinal', 0)) + 1} ({t.get('title') or 'untitled'})"
        secs = int(t.get("planned_seconds") or 0)
        if not t.get("title"):
            errors.append(f"{name}: needs a title")
        if secs <= 0:
            errors.append(f"{name}: planned time must be positive")
        if t.get("min_seconds") and secs < int(t["min_seconds"]):
            errors.append(f"{name}: planned {secs}s is below its minimum {t['min_seconds']}s")
        if t.get("max_seconds") and secs > int(t["max_seconds"]):
            errors.append(f"{name}: planned {secs}s exceeds its maximum {t['max_seconds']}s")
        scenes = t.get("scenes") or []
        if not isinstance(scenes, list):
            errors.append(f"{name}: scenes must be a list")
            continue
        for s in scenes:
            if not isinstance(s, dict) or s.get("kind") not in SCENE_KINDS:
                errors.append(f"{name}: scene kind must be one of {', '.join(SCENE_KINDS)}")
        scene_total = sum(int(s.get("planned_seconds") or 0) for s in scenes if isinstance(s, dict))
        if scene_total > secs:
            warnings.append(f"{name}: scenes plan {scene_total}s but the topic has {secs}s")
    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings, "timing": None}
    timing = timing_summary(plan)
    if timing["slack_seconds"] < 0:
        message = (f"planned content {timing['planned_content_seconds']}s exceeds the "
                   f"{timing['available_content_seconds']}s available after the interaction buffer")
        (errors if timing["hard_limit"] else warnings).append(message)
    return {"valid": not errors, "errors": errors, "warnings": warnings, "timing": timing}


def _find_topic(plan: dict, ref) -> dict | None:
    topics = plan["topics"]
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        idx = int(ref)
        return next((t for t in topics if int(t["ordinal"]) == idx), None)
    needle = str(ref or "").lower().strip()
    return next((t for t in topics if needle and needle in (t.get("title") or "").lower()), None)


def _renumber(plan: dict) -> None:
    for i, t in enumerate(plan["topics"]):
        t["ordinal"] = i


def apply_operations(plan: dict, operations: list[dict]) -> dict:
    """Apply patch operations to a plan dict copy; raises AuthoringError on an invalid operation."""
    plan = copy.deepcopy(plan)
    plan["topics"] = sorted(plan["topics"], key=lambda t: int(t["ordinal"]))
    for i, op in enumerate(operations):
        kind = op.get("op")
        if kind not in PATCH_OPS:
            raise AuthoringError(422, "INVALID_PATCH", f"operation {i}: unknown op {kind!r}")
        target = op.get("target")
        topic = _find_topic(plan, target) if kind in ("UPDATE_TOPIC_TIME", "SET_TOPIC_REQUIRED", "REMOVE_TOPIC",
                                                       "MOVE_TOPIC", "RENAME_TOPIC", "ADD_SCENE") else None
        if kind in ("UPDATE_TOPIC_TIME", "SET_TOPIC_REQUIRED", "REMOVE_TOPIC", "MOVE_TOPIC", "RENAME_TOPIC",
                    "ADD_SCENE") and topic is None:
            raise AuthoringError(422, "INVALID_PATCH", f"operation {i}: topic {target!r} not found")
        after = op.get("after")
        if kind == "UPDATE_TOPIC_TIME":
            topic["planned_seconds"] = int(after)
        elif kind == "UPDATE_COURSE_LIMIT":
            plan["course_limit_seconds"] = int(after)
        elif kind == "UPDATE_BUFFER":
            plan["interaction_buffer_seconds"] = int(after)
        elif kind == "SET_HARD_LIMIT":
            plan["hard_limit"] = bool(after)
        elif kind == "SET_TOPIC_REQUIRED":
            topic["required"] = bool(after)
        elif kind == "RENAME_TOPIC":
            topic["title"] = str(after)[:200]
        elif kind == "REMOVE_TOPIC":
            plan["topics"].remove(topic)
            _renumber(plan)
        elif kind == "MOVE_TOPIC":
            plan["topics"].remove(topic)
            plan["topics"].insert(max(0, min(int(after), len(plan["topics"]))), topic)
            _renumber(plan)
        elif kind == "ADD_TOPIC":
            new = after if isinstance(after, dict) else {}
            if not new.get("title") or int(new.get("planned_seconds") or 0) <= 0:
                raise AuthoringError(422, "INVALID_PATCH", f"operation {i}: ADD_TOPIC needs title and planned_seconds")
            position = int(op.get("position", len(plan["topics"])))
            plan["topics"].insert(max(0, min(position, len(plan["topics"]))),
                                  {"title": str(new["title"])[:200], "planned_seconds": int(new["planned_seconds"]),
                                   "required": bool(new.get("required", True)), "concept": new.get("concept"),
                                   "problem_ref": new.get("problem_ref"), "scenes": new.get("scenes", []),
                                   "min_seconds": None, "max_seconds": None, "ordinal": -1})
            _renumber(plan)
        elif kind == "ADD_SCENE":
            scene = after if isinstance(after, dict) else {}
            if scene.get("kind") not in SCENE_KINDS:
                raise AuthoringError(422, "INVALID_PATCH", f"operation {i}: scene kind must be one of {SCENE_KINDS}")
            topic.setdefault("scenes", []).append({"scene_id": scene.get("scene_id") or f"sc_{secrets.token_hex(4)}",
                                                   "kind": scene["kind"], "title": scene.get("title") or scene["kind"].title(),
                                                   "planned_seconds": int(scene.get("planned_seconds") or 60),
                                                   "optional": bool(scene.get("optional", False))})
    return plan


def patch_impact(before: dict, after: dict) -> dict:
    a, b = timing_summary(before), timing_summary(after)
    validation = validate_plan(after)
    return {"planned_content_seconds": {"before": a["planned_content_seconds"], "after": b["planned_content_seconds"]},
            "course_limit_seconds": {"before": a["course_limit_seconds"], "after": b["course_limit_seconds"]},
            "slack_seconds": {"before": a["slack_seconds"], "after": b["slack_seconds"]},
            "topic_count": {"before": len(before["topics"]), "after": len(after["topics"])},
            "valid": validation["valid"], "errors": validation["errors"], "warnings": validation["warnings"]}


_DURATION = re.compile(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b", re.I)


def _seconds(match: re.Match) -> int:
    value, unit = float(match.group(1)), match.group(2).lower()
    return int(round(value * (3600 if unit.startswith("h") else 1 if unit.startswith("s") else 60)))


def _topic_ref(message: str, plan: dict):
    m = re.search(r"\btopic\s*#?\s*(\d+)", message, re.I)
    if m:
        return int(m.group(1)) - 1  # humans count from 1
    lowered = message.lower()
    for t in sorted(plan["topics"], key=lambda t: -len(t.get("title") or "")):
        if t.get("title") and t["title"].lower() in lowered:
            return int(t["ordinal"])
    m = re.search(r"[\"“']([^\"”']+)[\"”']", message)
    return m.group(1) if m else None


def parse_admin_message(message: str, plan: dict) -> tuple[list[dict], str]:
    """Deterministic NL → operations. Returns (operations, assistant summary); empty ops if not understood."""
    msg = message.strip()
    low = msg.lower()
    ops: list[dict] = []
    duration = _DURATION.search(msg)
    ref = _topic_ref(msg, plan)
    topic = _find_topic(plan, ref) if ref is not None else None
    if re.search(r"\b(course|session|class|whole|total)\b.*\b(limit|length|long|duration)\b|\b(limit|length)\b.*\b(course|session|class)\b", low) and duration:
        ops.append({"op": "UPDATE_COURSE_LIMIT", "target": "plan", "before": plan["course_limit_seconds"],
                    "after": _seconds(duration)})
    elif "buffer" in low and duration:
        ops.append({"op": "UPDATE_BUFFER", "target": "plan", "before": plan.get("interaction_buffer_seconds", 0),
                    "after": _seconds(duration)})
    elif re.search(r"\bhard\s+limit\b", low):
        ops.append({"op": "SET_HARD_LIMIT", "target": "plan", "before": bool(plan.get("hard_limit")),
                    "after": not re.search(r"\b(no|remove|soft|disable|off)\b", low)})
    elif re.search(r"\b(remove|delete|drop)\b", low) and topic:
        ops.append({"op": "REMOVE_TOPIC", "target": int(topic["ordinal"]), "before": topic["title"], "after": None})
    elif re.search(r"\b(optional|required|mandatory)\b", low) and topic:
        ops.append({"op": "SET_TOPIC_REQUIRED", "target": int(topic["ordinal"]), "before": topic.get("required", True),
                    "after": "optional" not in low})
    elif re.search(r"\b(move|put)\b", low) and topic:
        m = re.search(r"\b(?:to|before|after)\s+(?:position|topic)?\s*#?\s*(\d+)", low)
        first = re.search(r"\b(first|start|beginning)\b", low)
        last = re.search(r"\b(last|end)\b", low)
        position = 0 if first else len(plan["topics"]) - 1 if last else (int(m.group(1)) - 1 if m else None)
        if m and "after" in m.group(0):
            position = int(m.group(1))
        if position is not None:
            ops.append({"op": "MOVE_TOPIC", "target": int(topic["ordinal"]), "before": int(topic["ordinal"]),
                        "after": position})
    elif re.search(r"\brename\b", low) and topic:
        m = re.search(r"\bto\s+[\"“']?([^\"”']+)[\"”']?\s*$", msg, re.I)
        if m:
            ops.append({"op": "RENAME_TOPIC", "target": int(topic["ordinal"]), "before": topic["title"],
                        "after": m.group(1).strip()})
    elif re.search(r"\badd\b.*\b(poll|activity|widget|practice|discussion)\b", low) and topic:
        kind = next(k for k in ("POLL", "ACTIVITY", "WIDGET", "PRACTICE", "DISCUSSION") if k.lower() in low)
        ops.append({"op": "ADD_SCENE", "target": int(topic["ordinal"]), "before": None,
                    "after": {"kind": kind, "title": f"{kind.title()} check",
                              "planned_seconds": _seconds(duration) if duration else 120}})
    elif re.search(r"\badd\b.*\btopic\b", low) and duration and not re.search(r"\btopic\s*#?\s*\d", low):
        m = re.search(r"[\"“']([^\"”']+)[\"”']", msg) or re.search(r"\btopic\s+(?:on|about|called)?\s*([A-Za-z][\w\s-]{2,60}?)\s+(?:for|of|with)\b", msg, re.I)
        if m:
            ops.append({"op": "ADD_TOPIC", "target": "plan", "before": None,
                        "after": {"title": m.group(1).strip(), "planned_seconds": _seconds(duration)}})
    elif topic and duration:
        current = int(topic["planned_seconds"])
        delta = _seconds(duration)
        if re.search(r"\b(add|extend|increase|more|longer)\b|\+", low) and not re.search(r"\bto\s+\d", low):
            new = current + delta
        elif re.search(r"\b(cut|reduce|shorten|less|shorter|decrease)\b|-", low) and not re.search(r"\bto\s+\d", low):
            new = max(30, current - delta)
        else:
            new = delta
        ops.append({"op": "UPDATE_TOPIC_TIME", "target": int(topic["ordinal"]), "before": current, "after": new})
    if not ops:
        return [], ("I couldn't map that to a plan change. Try e.g. \"set topic 2 to 8 minutes\", \"make topic 3 "
                    "optional\", \"add a poll to topic 1\", \"set the course limit to 45 minutes\" or \"add a 5 minute buffer\".")
    return ops, "; ".join(_describe(op, plan) for op in ops)


def _describe(op: dict, plan: dict) -> str:
    name = lambda ref: next((f"topic {int(t['ordinal']) + 1} “{t['title']}”" for t in plan["topics"]  # noqa: E731
                             if int(t["ordinal"]) == ref), str(ref))
    kind = op["op"]
    if kind == "UPDATE_TOPIC_TIME":
        return f"Change {name(op['target'])} from {op['before'] // 60}m{op['before'] % 60:02d}s to {op['after'] // 60}m{op['after'] % 60:02d}s"
    if kind == "UPDATE_COURSE_LIMIT":
        return f"Set the course limit to {op['after'] // 60} minutes"
    if kind == "UPDATE_BUFFER":
        return f"Set the interaction buffer to {op['after'] // 60}m{op['after'] % 60:02d}s"
    if kind == "SET_HARD_LIMIT":
        return "Make the time limit hard" if op["after"] else "Make the time limit soft"
    if kind == "SET_TOPIC_REQUIRED":
        return f"Mark {name(op['target'])} as {'required' if op['after'] else 'optional'}"
    if kind == "REMOVE_TOPIC":
        return f"Remove {name(op['target'])}"
    if kind == "MOVE_TOPIC":
        return f"Move {name(op['target'])} to position {op['after'] + 1}"
    if kind == "RENAME_TOPIC":
        return f"Rename {name(op['target'])} to “{op['after']}”"
    if kind == "ADD_SCENE":
        return f"Add a {op['after']['kind'].lower()} scene to {name(op['target'])}"
    if kind == "ADD_TOPIC":
        return f"Add topic “{op['after']['title']}” ({op['after']['planned_seconds'] // 60} min)"
    return kind


def alternative_operations(plan: dict, operations: list[dict]) -> list[dict] | None:
    """Offer a budget-neutral alternative: fund extra topic time from optional topics."""
    extra = sum(int(op["after"]) - int(op["before"]) for op in operations
                if op["op"] == "UPDATE_TOPIC_TIME" and int(op["after"]) > int(op["before"]))
    if extra <= 0:
        return None
    targets = {op["target"] for op in operations}
    donors = [t for t in sorted(plan["topics"], key=lambda t: -int(t["planned_seconds"]))
              if not t.get("required", True) and int(t["ordinal"]) not in targets]
    alt = list(operations)
    for donor in donors:
        if extra <= 0:
            break
        give = min(extra, int(donor["planned_seconds"]) - 60)
        if give > 0:
            alt.append({"op": "UPDATE_TOPIC_TIME", "target": int(donor["ordinal"]), "before": int(donor["planned_seconds"]),
                        "after": int(donor["planned_seconds"]) - give})
            extra -= give
    return alt if len(alt) > len(operations) else None


# ------------------------------------------------------------------ persistence

_PLAN_COLS = ("plan_id::text AS plan_id, plan_key, version, parent_plan_id::text AS parent_plan_id, title, description, "
              "status, course_limit_seconds, interaction_buffer_seconds, hard_limit, created_by, created_at, "
              "updated_at, approved_at, published_at")


def get_plan(conn: Connection, plan_id: str, lock: bool = False) -> dict:
    row = conn.execute(text(f"SELECT {_PLAN_COLS} FROM authoring.presentation_plan WHERE plan_id = CAST(:p AS uuid)"
                            + (" FOR UPDATE" if lock else "")), {"p": plan_id}).mappings().first()
    if not row:
        raise AuthoringError(404, "NOT_FOUND", "presentation plan not found")
    plan = dict(row)
    plan["topics"] = [dict(t) for t in conn.execute(text(
        "SELECT topic_id::text AS topic_id, ordinal, title, concept, problem_ref, planned_seconds, min_seconds, "
        "max_seconds, required, scenes FROM authoring.plan_topic WHERE plan_id = CAST(:p AS uuid) ORDER BY ordinal"),
        {"p": plan_id}).mappings()]
    plan["timing"] = timing_summary(plan)
    return plan


def list_plans(conn: Connection, limit: int = 100) -> list[dict]:
    return [dict(r) for r in conn.execute(text(
        f"SELECT {_PLAN_COLS}, (SELECT count(*) FROM authoring.plan_topic t WHERE t.plan_id = p.plan_id) AS topic_count "
        "FROM authoring.presentation_plan p ORDER BY updated_at DESC LIMIT :n"), {"n": limit}).mappings()]


def _write_topics(conn: Connection, plan_id: str, topics: list[dict]) -> None:
    conn.execute(text("DELETE FROM authoring.plan_topic WHERE plan_id = CAST(:p AS uuid)"), {"p": plan_id})
    for i, t in enumerate(sorted(topics, key=lambda t: int(t.get("ordinal", 0)))):
        conn.execute(text(
            "INSERT INTO authoring.plan_topic (plan_id, ordinal, title, concept, problem_ref, planned_seconds, "
            "min_seconds, max_seconds, required, scenes) VALUES (CAST(:p AS uuid), :o, :t, :c, :pr, :s, :mn, :mx, :r, "
            "CAST(:sc AS jsonb))"),
            {"p": plan_id, "o": i, "t": t["title"], "c": t.get("concept"), "pr": t.get("problem_ref"),
             "s": int(t["planned_seconds"]), "mn": t.get("min_seconds"), "mx": t.get("max_seconds"),
             "r": bool(t.get("required", True)),
             "sc": json.dumps([{**s, "scene_id": s.get("scene_id") or f"sc_{secrets.token_hex(4)}"}
                               for s in (t.get("scenes") or [])])})


def create_plan(conn: Connection, body: dict, actor: str = "admin") -> dict:
    candidate = {**body, "topics": [{**t, "ordinal": i} for i, t in enumerate(body.get("topics", []))]}
    structural = [e for e in validate_plan(candidate)["errors"] if "exceeds the" not in e]
    if structural:
        raise AuthoringError(422, "INVALID_PLAN", "; ".join(structural))
    slug = re.sub(r"[^a-z0-9]+", "-", body["title"].lower()).strip("-")[:40] or "plan"
    plan_id = conn.execute(text(
        "INSERT INTO authoring.presentation_plan (plan_key, title, description, course_limit_seconds, "
        "interaction_buffer_seconds, hard_limit, created_by) VALUES (:k, :t, :d, :l, :b, :h, :a) RETURNING plan_id::text"),
        {"k": body.get("plan_key") or f"{slug}-{secrets.token_hex(3)}", "t": body["title"], "d": body.get("description"),
         "l": int(body["course_limit_seconds"]), "b": int(body.get("interaction_buffer_seconds", 0)),
         "h": bool(body.get("hard_limit", False)), "a": actor}).scalar_one()
    _write_topics(conn, plan_id, candidate["topics"])
    return get_plan(conn, plan_id)


def _ensure_editable(plan: dict) -> None:
    if plan["status"] in ("PUBLISHED", "SUPERSEDED"):
        raise AuthoringError(409, "PLAN_IMMUTABLE", "published plans are immutable; create a new version first")


def save_plan_state(conn: Connection, plan: dict) -> dict:
    """Persist a (validated) edited plan dict onto its DRAFT/APPROVED row; APPROVED drops back to DRAFT."""
    conn.execute(text(
        "UPDATE authoring.presentation_plan SET title = :t, course_limit_seconds = :l, interaction_buffer_seconds = :b, "
        "hard_limit = :h, status = 'DRAFT', approved_at = NULL, updated_at = now() WHERE plan_id = CAST(:p AS uuid)"),
        {"t": plan["title"], "l": int(plan["course_limit_seconds"]), "b": int(plan.get("interaction_buffer_seconds", 0)),
         "h": bool(plan.get("hard_limit")), "p": plan["plan_id"]})
    _write_topics(conn, plan["plan_id"], plan["topics"])
    return get_plan(conn, plan["plan_id"])


def update_topics(conn: Connection, plan_id: str, topics: list[dict]) -> dict:
    plan = get_plan(conn, plan_id, lock=True)
    _ensure_editable(plan)
    plan["topics"] = [{**t, "ordinal": i} for i, t in enumerate(topics)]
    structural = [e for e in validate_plan(plan)["errors"] if "exceeds the" not in e]
    if structural:
        raise AuthoringError(422, "INVALID_PLAN", "; ".join(structural))
    return save_plan_state(conn, plan)


def update_timing(conn: Connection, plan_id: str, body: dict) -> dict:
    plan = get_plan(conn, plan_id, lock=True)
    _ensure_editable(plan)
    for key in ("course_limit_seconds", "interaction_buffer_seconds", "hard_limit"):
        if body.get(key) is not None:
            plan[key] = body[key]
    for ordinal, secs in (body.get("topic_seconds") or {}).items():
        topic = _find_topic(plan, int(ordinal))
        if topic is None:
            raise AuthoringError(422, "INVALID_PLAN", f"topic ordinal {ordinal} not found")
        topic["planned_seconds"] = int(secs)
    structural = [e for e in validate_plan(plan)["errors"] if "exceeds the" not in e]
    if structural:
        raise AuthoringError(422, "INVALID_PLAN", "; ".join(structural))
    return save_plan_state(conn, plan)


def approve_plan(conn: Connection, plan_id: str) -> dict:
    plan = get_plan(conn, plan_id, lock=True)
    _ensure_editable(plan)
    result = validate_plan(plan)
    if not result["valid"]:
        raise AuthoringError(422, "INVALID_PLAN", "; ".join(result["errors"]), result)
    conn.execute(text("UPDATE authoring.presentation_plan SET status = 'APPROVED', approved_at = now(), updated_at = now() "
                      "WHERE plan_id = CAST(:p AS uuid)"), {"p": plan_id})
    return get_plan(conn, plan_id)


def publish_plan(conn: Connection, plan_id: str) -> dict:
    plan = get_plan(conn, plan_id, lock=True)
    if plan["status"] != "APPROVED":
        raise AuthoringError(409, "NOT_APPROVED", "approve the plan before publishing")
    conn.execute(text("UPDATE authoring.presentation_plan SET status = 'SUPERSEDED' WHERE plan_key = :k "
                      "AND status = 'PUBLISHED'"), {"k": plan["plan_key"]})
    conn.execute(text("UPDATE authoring.presentation_plan SET status = 'PUBLISHED', published_at = now(), "
                      "updated_at = now() WHERE plan_id = CAST(:p AS uuid)"), {"p": plan_id})
    return get_plan(conn, plan_id)


def new_version(conn: Connection, plan_id: str, actor: str = "admin") -> dict:
    source = get_plan(conn, plan_id)
    existing = conn.execute(text("SELECT plan_id::text FROM authoring.presentation_plan WHERE plan_key = :k "
                                 "AND status IN ('DRAFT', 'APPROVED') ORDER BY version DESC LIMIT 1"),
                            {"k": source["plan_key"]}).scalar()
    if existing:
        return get_plan(conn, existing)
    version = conn.execute(text("SELECT max(version) + 1 FROM authoring.presentation_plan WHERE plan_key = :k"),
                           {"k": source["plan_key"]}).scalar_one()
    new_id = conn.execute(text(
        "INSERT INTO authoring.presentation_plan (plan_key, version, parent_plan_id, title, description, "
        "course_limit_seconds, interaction_buffer_seconds, hard_limit, created_by) VALUES (:k, :v, CAST(:parent AS uuid), "
        ":t, :d, :l, :b, :h, :a) RETURNING plan_id::text"),
        {"k": source["plan_key"], "v": version, "parent": plan_id, "t": source["title"], "d": source["description"],
         "l": source["course_limit_seconds"], "b": source["interaction_buffer_seconds"], "h": source["hard_limit"],
         "a": actor}).scalar_one()
    _write_topics(conn, new_id, source["topics"])
    return get_plan(conn, new_id)


# ------------------------------------------------------------------ admin chat

def create_chat(conn: Connection, plan_id: str, actor: str = "admin") -> dict:
    get_plan(conn, plan_id)
    chat_id = conn.execute(text("INSERT INTO authoring.chat_session (plan_id, actor) VALUES (CAST(:p AS uuid), :a) "
                                "RETURNING chat_session_id::text"), {"p": plan_id, "a": actor}).scalar_one()
    return get_chat(conn, chat_id)


def get_chat(conn: Connection, chat_id: str) -> dict:
    row = conn.execute(text("SELECT chat_session_id::text AS chat_session_id, plan_id::text AS plan_id, actor, created_at "
                            "FROM authoring.chat_session WHERE chat_session_id = CAST(:c AS uuid)"), {"c": chat_id}).mappings().first()
    if not row:
        raise AuthoringError(404, "NOT_FOUND", "chat session not found")
    chat = dict(row)
    chat["messages"] = [dict(r) for r in conn.execute(text(
        "SELECT message_id, role, content, patch_id::text AS patch_id, created_at FROM authoring.chat_message "
        "WHERE chat_session_id = CAST(:c AS uuid) ORDER BY message_id"), {"c": chat_id}).mappings()]
    chat["patches"] = list_patches(conn, chat_id)
    return chat


def list_patches(conn: Connection, chat_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(text(
        "SELECT patch_id::text AS patch_id, plan_id::text AS plan_id, summary, operations, impact, validation, proposer, "
        "status, result_plan_id::text AS result_plan_id, decided_by, decided_at, created_at FROM authoring.proposed_patch "
        "WHERE chat_session_id = CAST(:c AS uuid) ORDER BY created_at"), {"c": chat_id}).mappings()]


def _store_patch(conn: Connection, chat_id: str, plan: dict, ops: list[dict], summary: str, proposer: str) -> str:
    after = apply_operations(plan, ops)
    impact = patch_impact(plan, after)
    return conn.execute(text(
        "INSERT INTO authoring.proposed_patch (chat_session_id, plan_id, summary, operations, impact, validation, proposer) "
        "VALUES (CAST(:c AS uuid), CAST(:p AS uuid), :s, CAST(:o AS jsonb), CAST(:i AS jsonb), CAST(:v AS jsonb), :pr) "
        "RETURNING patch_id::text"),
        {"c": chat_id, "p": plan["plan_id"], "s": summary, "o": json.dumps(ops), "i": json.dumps(impact),
         "v": json.dumps({"valid": impact["valid"], "errors": impact["errors"], "warnings": impact["warnings"]}),
         "pr": proposer}).scalar_one()


def post_message(conn: Connection, chat_id: str, content: str,
                 llm_parser: Callable[[str, dict], list[dict]] | None = None) -> dict:
    chat = get_chat(conn, chat_id)
    plan = get_plan(conn, chat["plan_id"])
    conn.execute(text("INSERT INTO authoring.chat_message (chat_session_id, role, content) VALUES (CAST(:c AS uuid), 'ADMIN', :t)"),
                 {"c": chat_id, "t": content[:4000]})
    ops, summary = parse_admin_message(content, plan)
    proposer = "DETERMINISTIC_PARSER"
    if not ops and llm_parser is not None:
        try:
            ops = llm_parser(content, plan) or []
            summary = "; ".join(_describe(op, plan) for op in ops) if ops else summary
            proposer = "LLM_PARSER"
        except Exception:  # noqa: BLE001 — the deterministic reply stands
            ops = []
    patch_id = None
    if ops:
        try:
            patch_id = _store_patch(conn, chat_id, plan, ops, summary, proposer)
            reply = f"Proposed change: {summary}. Review the impact and Apply, Modify, Reject or ask for an alternative."
        except AuthoringError as exc:
            reply = f"I understood that as “{summary}” but it is not valid: {exc}"
    else:
        reply = summary
    conn.execute(text("INSERT INTO authoring.chat_message (chat_session_id, role, content, patch_id) VALUES "
                      "(CAST(:c AS uuid), 'ASSISTANT', :t, CAST(:p AS uuid))"), {"c": chat_id, "t": reply, "p": patch_id})
    return get_chat(conn, chat_id)


def decide_patch(conn: Connection, chat_id: str, patch_id: str, action: str, actor: str = "admin",
                 operations: list[dict] | None = None) -> dict:
    row = conn.execute(text("SELECT patch_id::text AS patch_id, plan_id::text AS plan_id, operations, status, summary "
                            "FROM authoring.proposed_patch WHERE patch_id = CAST(:p AS uuid) AND chat_session_id = CAST(:c AS uuid) "
                            "FOR UPDATE"), {"p": patch_id, "c": chat_id}).mappings().first()
    if not row:
        raise AuthoringError(404, "NOT_FOUND", "patch not found")
    if row["status"] != "PROPOSED":
        raise AuthoringError(409, "PATCH_DECIDED", f"patch is already {row['status']}")
    plan = get_plan(conn, row["plan_id"], lock=True)
    note = None
    if action == "REJECT":
        conn.execute(text("UPDATE authoring.proposed_patch SET status = 'REJECTED', decided_by = :a, decided_at = now() "
                          "WHERE patch_id = CAST(:p AS uuid)"), {"a": actor, "p": patch_id})
        note = "Patch rejected; the plan is unchanged."
    elif action == "ASK_FOR_ALTERNATIVE":
        alt = alternative_operations(plan, row["operations"])
        conn.execute(text("UPDATE authoring.proposed_patch SET status = 'SUPERSEDED', decided_by = :a, decided_at = now() "
                          "WHERE patch_id = CAST(:p AS uuid)"), {"a": actor, "p": patch_id})
        if alt:
            summary = "; ".join(_describe(op, plan) for op in alt)
            new_id = _store_patch(conn, chat_id, plan, alt, summary, "DETERMINISTIC_ALTERNATIVE")
            note = f"Alternative: {summary} (keeps the total within budget by using optional topics)."
            conn.execute(text("INSERT INTO authoring.chat_message (chat_session_id, role, content, patch_id) VALUES "
                              "(CAST(:c AS uuid), 'ASSISTANT', :t, CAST(:p AS uuid))"), {"c": chat_id, "t": note, "p": new_id})
            return get_chat(conn, chat_id)
        note = "No budget-neutral alternative is available (no optional topics to borrow time from)."
    elif action in ("APPLY", "MODIFY"):
        ops = operations if action == "MODIFY" else row["operations"]
        if action == "MODIFY" and not ops:
            raise AuthoringError(422, "INVALID_PATCH", "MODIFY needs replacement operations")
        target = plan
        if plan["status"] in ("PUBLISHED", "SUPERSEDED"):
            target = new_version(conn, plan["plan_id"], actor)
        updated = apply_operations(target, ops)
        result = validate_plan(updated)
        if not result["valid"]:
            raise AuthoringError(422, "INVALID_PLAN", "; ".join(result["errors"]), result)
        saved = save_plan_state(conn, updated)
        conn.execute(text("UPDATE authoring.proposed_patch SET status = 'APPLIED', operations = CAST(:o AS jsonb), "
                          "result_plan_id = CAST(:r AS uuid), decided_by = :a, decided_at = now() WHERE patch_id = CAST(:p AS uuid)"),
                     {"o": json.dumps(ops), "r": saved["plan_id"], "a": actor, "p": patch_id})
        note = (f"Applied to plan version {saved['version']} ({saved['status'].lower()})."
                + (" The published version is unchanged." if target is not plan else ""))
    else:
        raise AuthoringError(422, "INVALID_ACTION", "action must be APPLY, REJECT, MODIFY or ASK_FOR_ALTERNATIVE")
    conn.execute(text("INSERT INTO authoring.chat_message (chat_session_id, role, content, patch_id) VALUES "
                      "(CAST(:c AS uuid), 'SYSTEM', :t, CAST(:p AS uuid))"), {"c": chat_id, "t": note, "p": patch_id})
    return get_chat(conn, chat_id)
