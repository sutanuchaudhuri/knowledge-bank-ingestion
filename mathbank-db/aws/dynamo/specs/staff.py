"""C5 staff context: Socratic Studio, notifications, ADK agent sessions and runtime audit.

Design: documentation/requirements/70_DYNAMODB_AND_S3_VECTORS_ADOPTION_PLAN.md §13 (C5).

Tables: mb-socratic, mb-notify, mb-agent-sessions, mb-audit.
- orchestration.socratic_* (6 tables) → mb-socratic (+ derived DOMAIN and META#SCHEMA items).
- agent_sessions.* (5 ADK 2.11 tables) → mb-agent-sessions.
- audit.action_log rows with entity_type SOCRATIC_WORKFLOW / STAFF_USER → mb-audit copies (migrated_from='pg').
- notification.event was never created in Neon (migration 043 superseded): mb-notify is declared but has
  no mapping. STRATEGY_REVIEW / REVIEW_HEAD (socratic) are new item types with no source rows.
"""
from __future__ import annotations

import datetime as dt
import json
from typing import Any

from ..spec import Mapping, Table, iso, ttl_after

PREVIEW_RETENTION_DAYS = 30      # SOCRATIC_PREVIEW_RETENTION_DAYS
AUDIT_RETENTION_DAYS = 400
ADK_VERSION = "2.11.0"

# Engine offload policy: listed attributes > MB_OFFLOAD_THRESHOLD (16 KiB) go to S3 as <attr>_ref.
OFFLOAD = {
    ("socratic", "STRATEGY"): ("phases",),
    ("socratic", "REVISION"): ("program", "dependencies"),
    ("socratic", "PREVIEW"): ("activity_snapshot", "feedback"),
    ("socratic", "PREVIEW_EVENT"): ("response", "evidence", "result"),
    ("notify", "NOTIFICATION"): ("payload", "body"),
    ("agent-sessions", "SESSION"): ("state",),
    ("agent-sessions", "EVENT"): ("event_json",),
    ("agent-sessions", "APP_STATE"): ("state",),
    ("agent-sessions", "USER_STATE"): ("state",),
    ("audit", "AUDIT"): ("before_state", "after_state"),
}

TABLES = [
    # GSI2 never projects activity_snapshot / response / evidence / result.
    Table("socratic", gsis=("GSI1", "GSI2"), stream=True, ttl=True,
          include_gsis=(("GSI1", ("code", "domain", "label", "status", "phases", "title", "revision",
                                  "content_hash", "updated_at", "archived_at")),
                        ("GSI2", ("workflow_revision", "status", "state_version", "created_at", "updated_at",
                                  "content_hash"))),
          description="Socratic Studio: strategies, domains, workflows, revisions, commands, previews"),
    Table("notify", gsis=("GSI1",), stream=True, ttl=True,
          description="Notifications (built natively; notification.event never existed in Neon, no mapping)"),
    Table("agent-sessions", gsis=("GSI1", "GSI2"), stream=True, ttl=True, keys_only_gsis=("GSI2",),
          include_gsis=(("GSI1", ("update_time", "create_time", "event_count", "first_user_text",
                                  "linked_student_id")),),
          description="ADK DynamoDBSessionService store (app mathbank_tutor)"),
    # TTL stays off on mb-audit until the daily export job is green; items still carry ttl (created+400d).
    Table("audit", gsis=("GSI1", "GSI2", "GSI3"), stream=True, ttl=False, keys_only_gsis=("GSI2", "GSI3"),
          description="Runtime audit for DynamoDB-backed contexts"),
]


# ---------------------------------------------------------------- helpers

def _canon_json(v: Any) -> str:
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _utc(v: dt.datetime) -> dt.datetime:
    return v.replace(tzinfo=dt.timezone.utc) if v.tzinfo is None else v.astimezone(dt.timezone.utc)


_EPOCH = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


def _micros(v: dt.datetime) -> int:
    d = _utc(v) - _EPOCH
    return (d.days * 86400 + d.seconds) * 1_000_000 + d.microseconds


def _epoch_f(v: dt.datetime | None) -> float | None:
    """Epoch seconds with microsecond precision (ADK timestamps; naive values are UTC)."""
    return None if v is None else _micros(v) / 1_000_000


def _state_map(state: dict | None) -> dict:
    """ADK state as M of key → JSON string (floats survive without Decimal drift)."""
    return {str(k): _canon_json(v) for k, v in (state or {}).items()}


# ---------------------------------------------------------------- mb-socratic

def strategy(r: dict):
    yield {"PK": f"STRATEGY#{r['code']}", "SK": "STRATEGY", "type": "STRATEGY",
           "GSI1PK": "STRATEGIES", "GSI1SK": f"DOMAIN#{r['domain']}#CODE#{r['code']}",
           "code": r["code"], "domain": r["domain"], "label": r["label"], "status": r["status"],
           "phases": r["phases"], "provenance": r["provenance"]}


def domain(r: dict):
    yield {"PK": f"DOMAIN#{r['domain']}", "SK": "DOMAIN", "type": "DOMAIN",
           "GSI1PK": "DOMAINS", "GSI1SK": r["domain"], "code": r["domain"], "label": r["domain"]}


def socratic_meta(r: dict):
    yield {"PK": "META#SCHEMA", "SK": "META", "type": "META", "schema": "dynamodb-v1",
           "seeded_strategies": r["seeded_strategies"], "domains": r["domains"]}


def workflow(r: dict):
    wf = str(r["workflow_id"])
    yield {"PK": f"WF#{wf}", "SK": "WF", "type": "WORKFLOW",
           "GSI1PK": f"OWNER#{r['owner_id']}", "GSI1SK": f"ACTIVE#{iso(r['updated_at'])}#{wf}",
           "workflow_id": wf, "owner_id": r["owner_id"], "title": r["title"], "domain": r["domain"],
           "revision": r["revision"], "content_hash": r["content_hash"], "prototype_only": r["prototype_only"],
           "created_at": r["created_at"], "updated_at": r["updated_at"], "version": r["revision"]}


def revision(r: dict):
    wf = str(r["workflow_id"])
    yield {"PK": f"WF#{wf}", "SK": f"REV#{r['revision']:010d}", "type": "REVISION",
            "workflow_id": wf, "revision": r["revision"], "content_hash": r["content_hash"],
            "author_id": r["author_id"], "strategy_code": r["strategy_code"], "program": r["program"],
            "dependencies": r["dependencies"], "problem_id": r["problem_id"], "solution_id": r["solution_id"],
            "solution_revision": r["solution_revision"], "route_release_id": r["route_release_id"],
            "created_at": r["created_at"]}


def command(r: dict):
    op, key = r["operation"], r["idempotency_key"]
    if op == "CREATE":
        sk = f"CMD#CREATE#{key}"
    elif op.startswith("UPDATE:"):
        sk = f"CMD#UPDATE#{op.split(':', 1)[1]}#{key}"
    else:
        raise ValueError(f"socratic_command: unsupported operation {op!r}")
    yield {"PK": f"OWNER#{r['owner_id']}", "SK": sk, "type": "COMMAND",
           "owner_id": r["owner_id"], "operation": op, "idempotency_key": key, "request_hash": r["request_hash"],
           "workflow_id": str(r["workflow_id"]), "revision": r["revision"], "content_hash": r["content_hash"],
           "created_at": r["created_at"]}


def preview(r: dict):
    pid, wf = str(r["preview_id"]), str(r["workflow_id"])
    yield {"PK": f"PREVIEW#{pid}", "SK": "PREVIEW", "type": "PREVIEW",
            "GSI2PK": f"OWNER#{r['owner_id']}#WF#{wf}", "GSI2SK": f"CREATED#{iso(r['created_at'])}#{pid}",
            "preview_id": pid, "owner_id": r["owner_id"], "workflow_id": wf,
            "workflow_revision": r["workflow_revision"], "content_hash": r["content_hash"],
            "activity_snapshot": r["activity_snapshot"], "state_version": r["state_version"],
            "current_node_key": r["current_node_key"], "status": r["status"],
            "transitions_used": r["transitions_used"], "hint_level": r["hint_level"], "revealed": r["revealed"],
            "feedback": r["feedback"], "synthetic": r["synthetic"], "created_at": r["created_at"],
            "updated_at": r["updated_at"], "ttl": ttl_after(r["cutover_at"], PREVIEW_RETENTION_DAYS)}


def preview_event(r: dict):
    pid, n = str(r["preview_id"]), r["state_version"]
    ttl = ttl_after(r["cutover_at"], PREVIEW_RETENTION_DAYS)
    yield {"PK": f"PREVIEW#{pid}", "SK": f"EV#{n:010d}", "type": "PREVIEW_EVENT",
            "preview_id": pid, "state_version": n, "action": r["action"], "idempotency_key": r["idempotency_key"],
            "request_hash": r["request_hash"], "node_key": r["node_key"], "from_key": r["from_key"],
            "to_key": r["to_key"], "outcome": r["outcome"], "rule_id": r["rule_id"],
            "decision_source": r["decision_source"], "reason": r["reason"], "assisted": r["assisted"],
            "response": r["response"], "evidence": r["evidence"], "result": r["result"],
            "created_at": r["created_at"], "ttl": ttl}
    if r["idempotency_key"] is not None:
        yield {"PK": f"PREVIEW#{pid}", "SK": f"IDEMP#{r['idempotency_key']}", "type": "PREVIEW_IDEMP",
                    "preview_id": pid, "idempotency_key": r["idempotency_key"], "request_hash": r["request_hash"],
                    "state_version": n, "created_at": r["created_at"], "ttl": ttl}


# ---------------------------------------------------------------- mb-agent-sessions

def adk_session(r: dict):
    app, uid, sid = r["app_name"], r["user_id"], r["id"]
    yield {"PK": f"APP#{app}#USER#{uid}", "SK": f"SESSION#{sid}", "type": "SESSION",
           "GSI1PK": f"APP#{app}", "GSI1SK": f"UPD#{iso(r['update_time'])}#{uid}#{sid}",
           "GSI2PK": f"SID#{app}#{sid}", "GSI2SK": f"USER#{uid}",
           "app_name": app, "user_id": uid, "session_id": sid, "state": _state_map(r["state"]),
           "create_time": _epoch_f(r["create_time"]), "update_time": _epoch_f(r["update_time"]),
           "update_marker": "v1", "version": 1, "event_count": r["event_count"],
           "first_user_text": r["first_user_text"], "linked_student_id": r["linked_student_id"],
           "linked_at": r["linked_at"]}


def adk_event(r: dict):
    app, uid, sid, eid = r["app_name"], r["user_id"], r["session_id"], r["id"]
    data = r["event_data"] or {}
    yield {"PK": f"SESS#{app}#{uid}#{sid}", "SK": f"EVT#{_micros(r['timestamp']):017d}#{eid}", "type": "EVENT",
            "app_name": app, "user_id": uid, "session_id": sid, "event_id": eid,
            "invocation_id": r["invocation_id"], "timestamp": _epoch_f(r["timestamp"]),
            "author": data.get("author"), "partial": bool(data.get("partial") or False),
            "event_json": None if r["event_data"] is None else _canon_json(r["event_data"])}


def adk_app_state(r: dict):
    yield {"PK": f"APP#{r['app_name']}", "SK": "APP_STATE", "type": "APP_STATE", "app_name": r["app_name"],
           "state": _state_map(r["state"]), "update_time": _epoch_f(r["update_time"]), "version": 1}


def adk_user_state(r: dict):
    yield {"PK": f"APP#{r['app_name']}#USER#{r['user_id']}", "SK": "USER_STATE", "type": "USER_STATE",
           "app_name": r["app_name"], "user_id": r["user_id"], "state": _state_map(r["state"]),
           "update_time": _epoch_f(r["update_time"]), "version": 1}


def adk_metadata(r: dict):
    if r["key"] == "schema_version":
        yield {"PK": "META#SCHEMA", "SK": "META", "type": "META", "schema": "dynamodb-v1",
               "adk_version": ADK_VERSION, "pg_schema_version": r["value"]}
    else:
        yield {"PK": "META#ADK", "SK": f"KEY#{r['key']}", "type": "META", "key": r["key"], "value": r["value"]}


# ---------------------------------------------------------------- mb-audit

def audit(r: dict):
    aid, at = str(r["action_log_id"]), f"AT#{_micros(r['created_at']):017d}#{r['action_log_id']}"
    yield {"PK": f"ENTITY#{r['entity_type']}#{r['entity_id']}", "SK": at, "type": "AUDIT",
           "GSI1PK": f"ACTOR#{r['actor_type']}#{r['actor_id']}", "GSI1SK": at,
           "GSI2PK": f"REQ#{r['request_id']}" if r["request_id"] else None,
           "GSI2SK": at if r["request_id"] else None,
           "GSI3PK": f"AUDIT#{aid}", "GSI3SK": "AUDIT",
           "audit_id": aid, "actor_type": r["actor_type"], "actor_id": r["actor_id"], "action": r["action"],
           "entity_type": r["entity_type"], "entity_id": r["entity_id"], "before_state": r["before_state"],
           "after_state": r["after_state"], "request_id": r["request_id"], "source_table": "audit.action_log",
           "created_at": r["created_at"], "migrated_from": "pg",
           "ttl": ttl_after(r["created_at"], AUDIT_RETENTION_DAYS)}


# ---------------------------------------------------------------- mappings

_CUTOVER = "date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS cutover_at"
_AUDIT_TYPES = "('SOCRATIC_WORKFLOW', 'STAFF_USER')"

MAPPINGS = [
    Mapping("orchestration.socratic_strategy", "socratic",
            "SELECT code, domain, label, status, phases, provenance FROM orchestration.socratic_strategy ORDER BY code",
            strategy, expected_source="orchestration.socratic_strategy"),
    Mapping("socratic.domain", "socratic",
            "SELECT DISTINCT domain FROM orchestration.socratic_strategy ORDER BY domain", domain,
            note="derived DOMAIN items (label = code)"),
    Mapping("socratic.meta", "socratic",
            "SELECT count(*)::int AS seeded_strategies, count(DISTINCT domain)::int AS domains "
            "FROM orchestration.socratic_strategy", socratic_meta, note="META#SCHEMA for /health"),
    Mapping("orchestration.socratic_workflow", "socratic",
            "SELECT workflow_id, owner_id, title, domain, revision, content_hash, prototype_only, created_at, "
            "updated_at FROM orchestration.socratic_workflow ORDER BY workflow_id",
            workflow, expected_source="orchestration.socratic_workflow"),
    Mapping("orchestration.socratic_revision", "socratic",
            "SELECT workflow_id, revision, content_hash, author_id, strategy_code, program, dependencies, problem_id, "
            "solution_id, solution_revision, route_release_id, created_at FROM orchestration.socratic_revision "
            "ORDER BY workflow_id, revision",
            revision, expected_source="orchestration.socratic_revision"),
    Mapping("orchestration.socratic_command", "socratic",
            "SELECT c.owner_id, c.operation, c.idempotency_key, c.request_hash, c.workflow_id, c.revision, "
            "r.content_hash, c.created_at FROM orchestration.socratic_command c "
            "LEFT JOIN orchestration.socratic_revision r ON r.workflow_id = c.workflow_id AND r.revision = c.revision "
            "ORDER BY c.owner_id, c.operation, c.idempotency_key",
            command, expected_source="orchestration.socratic_command"),
    Mapping("orchestration.socratic_preview", "socratic",
            "SELECT preview_id, owner_id, workflow_id, workflow_revision, content_hash, activity_snapshot, "
            "state_version, current_node_key, status, transitions_used, hint_level, revealed, feedback, synthetic, "
            f"created_at, updated_at, {_CUTOVER} FROM orchestration.socratic_preview ORDER BY preview_id",
            preview, expected_source="orchestration.socratic_preview"),
    Mapping("orchestration.socratic_preview_event", "socratic",
            "SELECT preview_id, state_version, action, idempotency_key, request_hash, node_key, from_key, to_key, "
            "outcome, rule_id, decision_source, reason, assisted, response, evidence, result, created_at, "
            f"{_CUTOVER} FROM orchestration.socratic_preview_event ORDER BY preview_id, state_version",
            preview_event, expected_source="orchestration.socratic_preview_event",
            note="PREVIEW_EVENT + PREVIEW_IDEMP sentinel per non-null idempotency_key"),

    Mapping("agent_sessions.sessions", "agent-sessions",
            "SELECT s.app_name, s.user_id, s.id, s.state, s.create_time, s.update_time, "
            "  (SELECT count(*)::int FROM agent_sessions.events e WHERE e.app_name = s.app_name "
            "     AND e.user_id = s.user_id AND e.session_id = s.id "
            "     AND COALESCE((e.event_data->>'partial')::boolean, false) = false) AS event_count, "
            "  (SELECT left(e.event_data->'content'->'parts'->0->>'text', 160) FROM agent_sessions.events e "
            "     WHERE e.app_name = s.app_name AND e.user_id = s.user_id AND e.session_id = s.id "
            "       AND e.event_data->>'author' = 'user' ORDER BY e.timestamp, e.id LIMIT 1) AS first_user_text, "
            "  l.student_id AS linked_student_id, l.created_at AS linked_at "
            "FROM agent_sessions.sessions s "
            "LEFT JOIN LATERAL (SELECT student_id, created_at FROM learner.agent_session_link l "
            "  WHERE l.agent_app_name = s.app_name AND l.agent_session_id = s.id "
            "  ORDER BY l.created_at, l.agent_session_link_id LIMIT 1) l ON true "
            "ORDER BY s.app_name, s.user_id, s.id",
            adk_session, expected_source="agent_sessions.sessions"),
    Mapping("agent_sessions.events", "agent-sessions",
            "SELECT app_name, user_id, session_id, id, invocation_id, timestamp, event_data "
            "FROM agent_sessions.events ORDER BY app_name, user_id, session_id, timestamp, id",
            adk_event, expected_source="agent_sessions.events"),
    Mapping("agent_sessions.app_states", "agent-sessions",
            "SELECT app_name, state, update_time FROM agent_sessions.app_states ORDER BY app_name",
            adk_app_state, expected_source="agent_sessions.app_states"),
    Mapping("agent_sessions.user_states", "agent-sessions",
            "SELECT app_name, user_id, state, update_time FROM agent_sessions.user_states ORDER BY app_name, user_id",
            adk_user_state, expected_source="agent_sessions.user_states"),
    Mapping("agent_sessions.adk_internal_metadata", "agent-sessions",
            "SELECT key, value FROM agent_sessions.adk_internal_metadata ORDER BY key",
            adk_metadata, expected_source="agent_sessions.adk_internal_metadata"),

    Mapping("audit.action_log", "audit",
            "SELECT action_log_id, actor_type, actor_id, action, entity_type, entity_id, before_state, after_state, "
            f"request_id, created_at FROM audit.action_log WHERE entity_type IN {_AUDIT_TYPES} "
            "ORDER BY created_at, action_log_id",
            audit, expected_source=f"audit.action_log WHERE entity_type IN {_AUDIT_TYPES}",
            note="only Socratic/Studio rows; PG originals stay (C7)"),
]
