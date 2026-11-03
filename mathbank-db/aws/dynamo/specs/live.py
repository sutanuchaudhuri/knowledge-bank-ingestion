"""C3 Live classroom, activities, widgets and lesson authoring → `mb-live-<env>` (single table).

Design: documentation/requirements/70_DYNAMODB_AND_S3_VECTORS_ADOPTION_PLAN.md §13 (C3), §3 key schema and
§7 data migration. Source tables: live.* (7), activity.instance, activity.response, visual.widget_spec
(session-scoped/runtime rows only; the library subset stays in PostgreSQL), visual.widget_state,
authoring.* (5).

Notable shapes:
- SESSION META drops `stage.widgets` (now authoritative WIDGET items) and keeps `stage_activity` (public
  projection; answer-key fields stripped defensively).
- SEQ (per-session atomic event counter) is computed from live.session_event (max sequence).
- CMD receipts are re-keyed by actor: `CMD#<actor_id|unknown>#<client_command_id>`.
- ACT snapshots the definition at migration time: `public` (activity_type, prompt, options) and the server-only
  `answer_key` (correctness_policy) + `definition_sha256`.
- Participant ids `instructor:instructor:<x>` are rewritten to `instructor:<x>` (LIV-S08) unless that would
  collide inside the session; the source id is kept as `source_participant_id`.
- Large attributes (event payloads, responses, receipts, specs, topics, …) are offloaded by the engine via
  OFFLOAD (> 16 KiB → S3, `<attr>_ref`); no hand-rolled S3 references.
- ttl on EVT/CMD/WIDGET/session WSPEC is NOT set here: `mb-live-archiver` sets it after archiving
  (its nightly sweep picks up completed sessions without `archived_at`).
"""
from __future__ import annotations

import datetime as dt

from ...common import json_bytes, sha256
from ..spec import Mapping, Table, epoch, iso, s, ttl_after

CTX = "live"
WSPEC_LIFECYCLES = {"VALIDATED", "SHOWN", "PROMOTION_CANDIDATE", "PROMOTED_TO_TEMPLATE", "REJECTED"}
ANSWER_KEY_FIELDS = ("correctness_policy", "correct_option", "correct_index", "numeric_answer", "answer_key")

GSI1_INCLUDE = ("type", "title", "status", "created_at", "joined_at", "submitted_at", "live_session_id",
                "plan_id", "version", "role")
GSI2_INCLUDE = ("type", "title", "status", "lifecycle", "persistence", "widget_type", "owner_actor_id",
                "join_code", "created_at", "updated_at", "plan_key", "version")

# Engine offload policy: any listed attribute > MB_OFFLOAD_THRESHOLD (16 KiB) → S3, replaced by <attr>_ref.
OFFLOAD = {
    (CTX, "SESSION"): ("topics", "stage_activity"),
    (CTX, "EVT"): ("payload",),                                   # carries responses, questions, aggregates
    (CTX, "CMD"): ("result",),                                    # handoff packets, tutor outputs
    (CTX, "TAKEOVER"): ("handoff_packet",),
    (CTX, "REC"): ("action", "rationale"),                        # model output
    (CTX, "ACT"): ("public", "answer_key"),                       # question body + server-only key
    (CTX, "ACTDEF"): ("prompt", "options", "correctness_policy"),
    (CTX, "RESP"): ("response",),                                 # student-submitted answers
    (CTX, "RESPHIST"): ("response",),
    (CTX, "WSPEC"): ("spec", "validation", "source_lineage"),     # artifact payloads + validator evidence
    (CTX, "WIDGET"): ("spec", "state"),
    (CTX, "PLAN"): ("topics",),                                   # scenes
    (CTX, "MSG"): ("content",),                                   # chat transcript
    (CTX, "PATCH"): ("operations", "impact", "validation"),       # model/parser output
}

TABLES = [Table(CTX, gsis=("GSI1", "GSI2"), stream=True, ttl=True,
                include_gsis=(("GSI1", GSI1_INCLUDE), ("GSI2", GSI2_INCLUDE)),
                description="C3 live classroom, activity runs, runtime widgets, presentation-plan authoring")]


# ---------------------------------------------------------------- helpers

def _pad(n, width: int) -> str:
    return str(int(n)).zfill(width)


def norm_actor(actor: str | None) -> str | None:
    """LIV-S08: collapse a doubled `instructor:` prefix."""
    if actor is None:
        return None
    while actor.startswith("instructor:instructor:"):
        actor = actor[len("instructor:"):]
    return actor


def _month(v) -> str:
    if isinstance(v, dt.datetime) and v.tzinfo is not None:
        v = v.astimezone(dt.timezone.utc)
    return v.strftime("%Y-%m")


def _student_uuid(participant_id: str | None) -> str | None:
    if participant_id and participant_id.startswith("student:"):
        return participant_id[len("student:"):]
    return None


def _public_activity(stage_activity):
    if not isinstance(stage_activity, dict):
        return stage_activity
    return {k: v for k, v in stage_activity.items() if k not in ANSWER_KEY_FIELDS}


# ---------------------------------------------------------------- live.session → META, JOINCODE, STAFF

SESSION_SQL = """
SELECT s.live_session_id, s.plan_id, s.title, s.join_code, s.status, s.control_mode, s.controller,
       s.agent_locked, s.state_version, s.last_sequence, s.current_topic_index, s.current_scene_index,
       s.course_limit_seconds, s.interaction_buffer_seconds, s.hard_limit, s.extension_seconds,
       s.started_at, s.paused_at, s.paused_total_seconds, s.topic_started_at, s.completed_at,
       s.stage -> 'activity' AS stage_activity, s.created_by, s.created_at, s.updated_at, s.topics,
       p.version AS plan_version,
       (SELECT i.activity_instance_id FROM activity.instance i
         WHERE i.live_session_id = s.live_session_id AND i.status = 'OPEN'
         ORDER BY i.opened_at DESC, i.activity_instance_id LIMIT 1) AS open_activity_instance_id
FROM live.session s
LEFT JOIN authoring.presentation_plan p ON p.plan_id = s.plan_id
ORDER BY s.created_at, s.live_session_id
"""


def session_items(r: dict):
    sid = s(r["live_session_id"])
    pk = f"SESSION#{sid}"
    created = iso(r["created_at"])
    owner = norm_actor(r["created_by"])
    meta = {
        "PK": pk, "SK": "META", "type": "SESSION",
        "GSI2PK": f"LIVESESSIONS#{_month(r['created_at'])}", "GSI2SK": f"{created}#{sid}",
        "live_session_id": sid, "title": r["title"], "join_code": r["join_code"], "status": r["status"],
        "control_mode": r["control_mode"], "controller": r["controller"], "agent_locked": r["agent_locked"],
        "state_version": r["state_version"], "current_topic_index": r["current_topic_index"],
        "current_scene_index": r["current_scene_index"], "course_limit_seconds": r["course_limit_seconds"],
        "interaction_buffer_seconds": r["interaction_buffer_seconds"], "hard_limit": r["hard_limit"],
        "extension_seconds": r["extension_seconds"], "started_at": r["started_at"], "paused_at": r["paused_at"],
        "paused_total_seconds": r["paused_total_seconds"], "topic_started_at": r["topic_started_at"],
        "completed_at": r["completed_at"], "topics": r["topics"],
        "stage_activity": _public_activity(r["stage_activity"]),
        "open_activity_instance_id": s(r["open_activity_instance_id"]),
        "owner_actor_id": owner, "created_by": owner, "source_created_by": r["created_by"] if owner != r["created_by"] else None,
        "plan_id": s(r["plan_id"]), "plan_version": r["plan_version"],
        "created_at": r["created_at"], "updated_at": r["updated_at"],
        "version": r["state_version"],
    }
    if r["plan_id"] is not None:
        meta["GSI1PK"], meta["GSI1SK"] = f"PLAN#{s(r['plan_id'])}", f"LIVE#{created}#{sid}"
    out = [meta]
    out.append({"PK": f"JOINCODE#{r['join_code']}", "SK": "JOINCODE", "type": "JOINCODE",
                "live_session_id": sid, "created_at": r["created_at"]})
    out.append({"PK": pk, "SK": f"STAFF#{owner}", "type": "STAFF",
                "GSI1PK": f"STAFF#{owner}", "GSI1SK": f"LIVE#{created}#{sid}",
                "live_session_id": sid, "actor_id": owner, "role": "OWNER", "title": r["title"],
                "status": r["status"], "created_at": r["created_at"], "version": 1})
    return out


# ---------------------------------------------------------------- SEQ counter (from session_event)

SEQ_SQL = """
SELECT s.live_session_id, s.last_sequence AS source_last_sequence,
       COALESCE(e.max_sequence, 0) AS last_sequence, COALESCE(e.n, 0) AS event_count,
       COALESCE(e.min_sequence, 0) AS min_sequence
FROM live.session s
LEFT JOIN (SELECT live_session_id, max(sequence) AS max_sequence, min(sequence) AS min_sequence, count(*) AS n
             FROM live.session_event GROUP BY live_session_id) e USING (live_session_id)
ORDER BY s.live_session_id
"""


def seq_item(r: dict):
    sid = s(r["live_session_id"])
    contiguous = r["event_count"] == r["last_sequence"] and r["min_sequence"] in (0, 1)
    return [{"PK": f"SESSION#{sid}", "SK": "SEQ", "type": "SEQ", "live_session_id": sid,
             "last_sequence": r["last_sequence"], "source_last_sequence": r["source_last_sequence"],
             "event_count": r["event_count"], "contiguous": contiguous}]


# ---------------------------------------------------------------- live.participant → PART

PART_SQL = """
SELECT p.live_session_id, p.participant_id, p.role, p.student_id, p.display_name, p.group_id, p.control_mode,
       p.confused, p.joined_at, p.last_seen_at,
       count(*) OVER (PARTITION BY p.live_session_id,
                      regexp_replace(p.participant_id, '^(instructor:)+', 'instructor:')) AS norm_dupes
FROM live.participant p
ORDER BY p.live_session_id, p.participant_id
"""


def part_item(r: dict):
    sid = s(r["live_session_id"])
    src = r["participant_id"]
    pid = norm_actor(src) if r["norm_dupes"] == 1 else src
    item = {"PK": f"SESSION#{sid}", "SK": f"PART#{pid}", "type": "PART", "live_session_id": sid,
            "participant_id": pid, "source_participant_id": src if pid != src else None,
            "role": r["role"], "student_id": s(r["student_id"]), "display_name": r["display_name"],
            "group_id": r["group_id"], "control_mode": r["control_mode"], "confused": r["confused"],
            "joined_at": r["joined_at"], "last_seen_at": r["last_seen_at"], "version": 1}
    if r["role"] == "STUDENT" and r["student_id"] is not None:
        item["GSI1PK"], item["GSI1SK"] = f"STUDENT#{s(r['student_id'])}", f"LIVE#{iso(r['joined_at'])}#{sid}"
    return [item]


# ---------------------------------------------------------------- live.session_event → EVT

EVT_SQL = """
SELECT live_session_id, sequence, event_id, event_type, session_version, correlation_id, causation_id,
       actor_type, actor_id, audience, audience_id, payload, created_at
FROM live.session_event
ORDER BY live_session_id, sequence
"""


def evt_item(r: dict):
    sid = s(r["live_session_id"])
    return [{"PK": f"SESSION#{sid}", "SK": f"EVT#{_pad(r['sequence'], 12)}", "type": "EVT",
             "live_session_id": sid, "sequence": r["sequence"], "event_id": s(r["event_id"]),
             "event_type": r["event_type"], "session_version": r["session_version"],
             "correlation_id": r["correlation_id"], "causation_id": r["causation_id"],
             "actor_type": r["actor_type"], "actor_id": r["actor_id"], "audience": r["audience"],
             "audience_id": r["audience_id"], "payload": r["payload"], "created_at": r["created_at"]}]


# ---------------------------------------------------------------- live.command_receipt → CMD (actor-bound)

CMD_SQL = """
SELECT live_session_id, client_command_id, command_type, actor_type, actor_id, status, result, created_at
FROM live.command_receipt
ORDER BY live_session_id, client_command_id
"""


def cmd_item(r: dict):
    sid = s(r["live_session_id"])
    actor = norm_actor(r["actor_id"]) or "unknown"
    item = {"PK": f"SESSION#{sid}", "SK": f"CMD#{actor}#{r['client_command_id']}", "type": "CMD",
            "live_session_id": sid, "client_command_id": r["client_command_id"],
            "command_type": r["command_type"], "actor_type": r["actor_type"], "actor_id": actor,
            "source_actor_id": r["actor_id"] if r["actor_id"] != actor else None,
            "status": r["status"], "result": r["result"], "created_at": r["created_at"],
            "legacy_receipt": True}   # request_hash absent: legacy receipts match on actor + ccid only
    return [item]


# ---------------------------------------------------------------- live.topic_run → TOPICRUN

TOPICRUN_SQL = """
SELECT live_session_id, topic_index, title, planned_seconds, started_at, ended_at, actual_seconds, status
FROM live.topic_run
ORDER BY live_session_id, topic_index
"""


def topicrun_item(r: dict):
    sid = s(r["live_session_id"])
    return [{"PK": f"SESSION#{sid}", "SK": f"TOPICRUN#{_pad(r['topic_index'], 4)}", "type": "TOPICRUN",
             "live_session_id": sid, "topic_index": r["topic_index"], "title": r["title"],
             "planned_seconds": r["planned_seconds"], "started_at": r["started_at"], "ended_at": r["ended_at"],
             "actual_seconds": r["actual_seconds"], "active_seconds": r["actual_seconds"],
             "status": r["status"], "version": 1}]


# ---------------------------------------------------------------- live.recommendation → REC

REC_SQL = """
SELECT recommendation_id, live_session_id, source, action, rationale, based_on_version, status,
       decided_by, decided_at, created_at
FROM live.recommendation
ORDER BY live_session_id, created_at, recommendation_id
"""


def rec_item(r: dict):
    sid = s(r["live_session_id"])
    return [{"PK": f"SESSION#{sid}", "SK": f"REC#{s(r['recommendation_id'])}", "type": "REC",
             "live_session_id": sid, "recommendation_id": s(r["recommendation_id"]), "source": r["source"],
             "action": r["action"], "rationale": r["rationale"], "based_on_version": r["based_on_version"],
             "status": r["status"], "decided_by": r["decided_by"], "decided_at": r["decided_at"],
             "attempt_count": 0, "created_at": r["created_at"], "version": 1}]


# ---------------------------------------------------------------- live.takeover → TAKEOVER (+ TAKEOVER_ACTIVE)

TAKEOVER_SQL = """
SELECT takeover_id, live_session_id, scope, scope_id, instructor, handoff_packet, started_at, ended_at,
       row_number() OVER (PARTITION BY live_session_id, scope, scope_id, (ended_at IS NULL)
                          ORDER BY started_at DESC, takeover_id) AS active_rank
FROM live.takeover
ORDER BY live_session_id, started_at, takeover_id
"""


def takeover_items(r: dict):
    sid = s(r["live_session_id"])
    tid = s(r["takeover_id"])
    instructor = norm_actor(r["instructor"])
    item = {"PK": f"SESSION#{sid}", "SK": f"TAKEOVER#{tid}", "type": "TAKEOVER", "live_session_id": sid,
            "takeover_id": tid, "scope": r["scope"], "scope_id": r["scope_id"], "instructor": instructor,
            "handoff_packet": r["handoff_packet"], "started_at": r["started_at"], "ended_at": r["ended_at"],
            "version": 1}
    out = [item]
    if r["ended_at"] is None and r["active_rank"] == 1:
        out.append({"PK": f"SESSION#{sid}", "SK": f"TAKEOVER_ACTIVE#{r['scope']}#{r['scope_id']}",
                    "type": "TAKEOVER_ACTIVE", "live_session_id": sid, "takeover_id": tid,
                    "scope": r["scope"], "scope_id": r["scope_id"], "started_at": r["started_at"]})
    return out


# ---------------------------------------------------------------- activity.instance → ACT (answer-key snapshot)

ACT_SQL = """
SELECT i.activity_instance_id, i.live_session_id, i.activity_id, i.status, i.anonymous, i.opened_by,
       i.opened_at, i.closes_at, i.closed_at,
       d.activity_type, d.prompt, d.options, d.correctness_policy, d.estimated_seconds,
       d.persistence_mode, d.source_type AS definition_source_type, d.status AS definition_status,
       (SELECT min(e.created_at) FROM live.session_event e
         WHERE e.live_session_id = i.live_session_id AND e.event_type = 'activity.revealed'
           AND strpos(e.payload::text, i.activity_instance_id::text) > 0) AS revealed_at
FROM activity.instance i
LEFT JOIN activity.definition d ON d.activity_id = i.activity_id
ORDER BY i.live_session_id, i.opened_at, i.activity_instance_id
"""


def act_item(r: dict):
    sid = s(r["live_session_id"])
    aid = s(r["activity_instance_id"])
    public = {"activity_type": r["activity_type"], "prompt": r["prompt"], "options": r["options"]}
    definition = {"activity_id": s(r["activity_id"]), **public, "correctness_policy": r["correctness_policy"],
                  "estimated_seconds": r["estimated_seconds"]}
    return [{"PK": f"SESSION#{sid}", "SK": f"ACT#{aid}", "type": "ACT", "live_session_id": sid,
             "activity_instance_id": aid, "activity_id": s(r["activity_id"]),
             "definition_source": "SESSION" if r["persistence_mode"] in ("SESSION", "EPHEMERAL") else "CONTENT",
             "definition_sha256": sha256(json_bytes(definition)) if r["activity_type"] is not None else None,
             "definition_status": r["definition_status"], "estimated_seconds": r["estimated_seconds"],
             "public": public, "answer_key": r["correctness_policy"],
             "status": r["status"], "anonymous": r["anonymous"], "opened_by": norm_actor(r["opened_by"]),
             "opened_at": r["opened_at"], "closes_at": r["closes_at"], "closed_at": r["closed_at"],
             "revealed_at": r["revealed_at"] if r["status"] == "REVEALED" else None, "version": 1}]


# ---------------------------------------------------------------- activity.response → RESP

RESP_SQL = """
SELECT r.response_id, r.activity_instance_id, i.live_session_id, r.participant_id, r.response, r.confidence,
       r.is_correct, r.client_command_id, r.submitted_at
FROM activity.response r
JOIN activity.instance i ON i.activity_instance_id = r.activity_instance_id
ORDER BY i.live_session_id, r.activity_instance_id, r.participant_id
"""


def resp_item(r: dict):
    sid = s(r["live_session_id"])
    aid = s(r["activity_instance_id"])
    src = r["participant_id"]
    pid = norm_actor(src)
    item = {"PK": f"SESSION#{sid}", "SK": f"ACT#{aid}#RESP#{pid}", "type": "RESP", "live_session_id": sid,
            "activity_instance_id": aid, "response_id": s(r["response_id"]), "participant_id": pid,
            "source_participant_id": src if pid != src else None, "response": r["response"],
            "confidence": r["confidence"], "is_correct": r["is_correct"],
            "client_command_id": r["client_command_id"], "submitted_at": r["submitted_at"],
            "attempt_no": 1, "version": 1}
    uid = _student_uuid(pid)
    if uid:
        item["GSI1PK"], item["GSI1SK"] = f"STUDENT#{uid}", f"LIVERESP#{iso(r['submitted_at'])}#{aid}"
    return [item]


# ---------------------------------------------------------------- visual.widget_spec → WSPEC (runtime rows only)

WSPEC_SQL = """
SELECT widget_spec_id, widget_type, spec_version, title, spec, lifecycle, persistence, live_session_id,
       source_type, source_lineage, validation, content_hash, created_by, created_at, expires_at,
       reviewed_by, reviewed_at
FROM visual.widget_spec
ORDER BY created_at, widget_spec_id
"""


def is_library_spec(r: dict) -> bool:
    return r["live_session_id"] is None and (r["persistence"] == "STATIC" or r["lifecycle"] == "PROMOTED_TO_TEMPLATE")


def wspec_item(r: dict):
    if is_library_spec(r):
        return []                     # library spec: stays in PostgreSQL, served from mb-content
    wid = s(r["widget_spec_id"])
    sid = s(r["live_session_id"])
    created = iso(r["created_at"])
    lifecycle = r["lifecycle"] if r["lifecycle"] in WSPEC_LIFECYCLES else "VALIDATED"
    if r["expires_at"] is not None:
        ttl = epoch(r["expires_at"])
    elif r["persistence"] == "EPHEMERAL":
        ttl = ttl_after(r["created_at"], 1)
    elif sid is None:
        ttl = ttl_after(r["created_at"], 30)
    else:
        ttl = None                    # session-scoped: set by mb-live-archiver after the session is archived
    item = {"PK": f"WSPEC#{wid}", "SK": "META", "type": "WSPEC",
            "GSI2PK": f"WSPEC_LC#{lifecycle}", "GSI2SK": f"{created}#{wid}",
            "widget_spec_id": wid, "widget_type": r["widget_type"], "spec_version": r["spec_version"],
            "title": r["title"], "spec": r["spec"], "lifecycle": lifecycle,
            "source_lifecycle": r["lifecycle"] if lifecycle != r["lifecycle"] else None,
            "persistence": r["persistence"], "live_session_id": sid, "source_type": r["source_type"],
            "source_lineage": r["source_lineage"], "validation": r["validation"],
            "content_hash": r["content_hash"], "created_by": norm_actor(r["created_by"]),
            "created_at": r["created_at"], "expires_at": r["expires_at"], "reviewed_by": r["reviewed_by"],
            "reviewed_at": r["reviewed_at"], "ttl": ttl, "version": 1}
    if sid is not None:
        item["GSI1PK"], item["GSI1SK"] = f"SESSION#{sid}", f"WSPEC#{created}"
    return [item]


# ---------------------------------------------------------------- visual.widget_state → WIDGET (authoritative)

WIDGET_SQL = """
SELECT w.live_session_id, w.widget_instance_id, w.widget_spec_id, w.state, w.state_version, w.visible,
       w.updated_at,
       s.stage -> 'widgets' -> w.widget_instance_id -> 'spec' AS stage_spec,
       ws.spec AS wspec_spec
FROM visual.widget_state w
LEFT JOIN live.session s ON s.live_session_id = w.live_session_id
LEFT JOIN visual.widget_spec ws ON ws.widget_spec_id = w.widget_spec_id
ORDER BY w.live_session_id, w.widget_instance_id
"""


def widget_item(r: dict):
    sid = s(r["live_session_id"])
    stage_spec = r["stage_spec"]
    return [{"PK": f"SESSION#{sid}", "SK": f"WIDGET#{r['widget_instance_id']}", "type": "WIDGET",
             "live_session_id": sid, "widget_instance_id": r["widget_instance_id"],
             "widget_spec_id": s(r["widget_spec_id"]),
             "spec": stage_spec if stage_spec is not None else r["wspec_spec"],
             "spec_source": "STAGE" if stage_spec is not None else ("WSPEC" if r["wspec_spec"] is not None else None),
             "state": r["state"], "visible": r["visible"], "state_version": r["state_version"],
             "updated_at": r["updated_at"], "version": r["state_version"]}]


# ---------------------------------------------------------------- authoring.presentation_plan (+ plan_topic) → PLAN

PLAN_SQL = """
SELECT p.plan_id, p.plan_key, p.version, p.parent_plan_id, p.title, p.description, p.status,
       p.course_limit_seconds, p.interaction_buffer_seconds, p.hard_limit, p.created_by, p.created_at,
       p.updated_at, p.approved_at, p.published_at,
       COALESCE((SELECT json_agg(json_build_object(
                    'topic_id', t.topic_id, 'ordinal', t.ordinal, 'title', t.title, 'concept', t.concept,
                    'problem_ref', t.problem_ref, 'planned_seconds', t.planned_seconds,
                    'min_seconds', t.min_seconds, 'max_seconds', t.max_seconds, 'required', t.required,
                    'scenes', t.scenes) ORDER BY t.ordinal, t.topic_id)
                 FROM authoring.plan_topic t WHERE t.plan_id = p.plan_id), '[]'::json) AS topics,
       (SELECT count(*) FROM live.session ls WHERE ls.plan_id = p.plan_id) AS session_count
FROM authoring.presentation_plan p
ORDER BY p.plan_key, p.version, p.plan_id
"""


def plan_item(r: dict):
    pid = s(r["plan_id"])
    item = {"PK": f"PLAN#{pid}", "SK": "META", "type": "PLAN",
            "GSI1PK": f"PLANKEY#{r['plan_key']}", "GSI1SK": f"V#{_pad(r['version'], 6)}",
            "GSI2PK": "PLANS", "GSI2SK": f"{iso(r['updated_at'])}#{pid}",
            "plan_id": pid, "plan_key": r["plan_key"], "version": r["version"],
            "parent_plan_id": s(r["parent_plan_id"]), "title": r["title"], "description": r["description"],
            "status": r["status"], "course_limit_seconds": r["course_limit_seconds"],
            "interaction_buffer_seconds": r["interaction_buffer_seconds"], "hard_limit": r["hard_limit"],
            "topics": r["topics"], "revision": 1, "session_count": r["session_count"],
            "created_by": r["created_by"], "created_at": r["created_at"], "updated_at": r["updated_at"],
            "approved_at": r["approved_at"], "published_at": r["published_at"]}
    return [item]


PLANKEY_SQL = """
SELECT p.plan_key, max(p.version) AS max_version,
       (array_agg(p.plan_id ORDER BY p.version DESC, p.plan_id) FILTER (WHERE p.status = 'PUBLISHED'))[1]
           AS published_plan_id,
       max(p.version) FILTER (WHERE p.status = 'PUBLISHED') AS published_version,
       (array_agg(p.plan_id ORDER BY p.version DESC, p.plan_id) FILTER (WHERE p.status IN ('DRAFT', 'APPROVED')))[1]
           AS editable_plan_id,
       max(p.version) FILTER (WHERE p.status IN ('DRAFT', 'APPROVED')) AS editable_version
FROM authoring.presentation_plan p
GROUP BY p.plan_key
ORDER BY p.plan_key
"""


def plankey_items(r: dict):
    pk = f"PLANKEY#{r['plan_key']}"
    out = [{"PK": pk, "SK": "COUNTER", "type": "PLANKEY_COUNTER", "plan_key": r["plan_key"],
            "max_version": r["max_version"]}]
    if r["published_plan_id"] is not None:
        out.append({"PK": pk, "SK": "PUBLISHED", "type": "PLANKEY_PUBLISHED", "plan_key": r["plan_key"],
                    "plan_id": s(r["published_plan_id"]), "version": r["published_version"]})
    if r["editable_plan_id"] is not None:
        out.append({"PK": pk, "SK": "EDITABLE", "type": "PLANKEY_EDITABLE", "plan_key": r["plan_key"],
                    "plan_id": s(r["editable_plan_id"]), "version": r["editable_version"]})
    return out


PLAN_TOPIC_SQL = """
SELECT topic_id, plan_id, ordinal
FROM authoring.plan_topic
ORDER BY plan_id, ordinal, topic_id
"""


def plan_topic_none(_r: dict):
    return []                         # embedded in PLAN.topics (row count verified here)


# ---------------------------------------------------------------- authoring.chat_session / chat_message / proposed_patch

CHAT_SQL = """
SELECT c.chat_session_id, c.plan_id, c.actor, c.created_at,
       (SELECT count(*) FROM authoring.chat_message m WHERE m.chat_session_id = c.chat_session_id) AS last_message_seq
FROM authoring.chat_session c
ORDER BY c.created_at, c.chat_session_id
"""


def chat_item(r: dict):
    cid = s(r["chat_session_id"])
    return [{"PK": f"CHAT#{cid}", "SK": "META", "type": "CHAT",
             "GSI1PK": f"PLAN#{s(r['plan_id'])}", "GSI1SK": f"CHAT#{iso(r['created_at'])}#{cid}",
             "chat_session_id": cid, "plan_id": s(r["plan_id"]), "actor": r["actor"],
             "last_message_seq": r["last_message_seq"], "created_at": r["created_at"], "version": 1}]


MSG_SQL = """
SELECT m.message_id AS source_message_id, m.chat_session_id, m.role, m.content, m.patch_id, m.created_at,
       row_number() OVER (PARTITION BY m.chat_session_id ORDER BY m.message_id) AS message_seq
FROM authoring.chat_message m
ORDER BY m.chat_session_id, m.message_id
"""


def msg_item(r: dict):
    cid = s(r["chat_session_id"])
    return [{"PK": f"CHAT#{cid}", "SK": f"MSG#{_pad(r['message_seq'], 12)}", "type": "MSG",
             "chat_session_id": cid, "message_id": r["message_seq"], "source_message_id": r["source_message_id"],
             "role": r["role"], "content": r["content"], "patch_id": s(r["patch_id"]),
             "created_at": r["created_at"]}]


PATCH_SQL = """
SELECT patch_id, chat_session_id, plan_id, summary, operations, impact, validation, proposer, status,
       result_plan_id, decided_by, decided_at, created_at
FROM authoring.proposed_patch
ORDER BY chat_session_id, created_at, patch_id
"""


def patch_item(r: dict):
    cid = s(r["chat_session_id"])
    return [{"PK": f"CHAT#{cid}", "SK": f"PATCH#{s(r['patch_id'])}", "type": "PATCH",
             "chat_session_id": cid, "patch_id": s(r["patch_id"]), "plan_id": s(r["plan_id"]),
             "plan_revision": 1, "summary": r["summary"], "operations": r["operations"], "impact": r["impact"],
             "validation": r["validation"], "proposer": r["proposer"], "status": r["status"],
             "result_plan_id": s(r["result_plan_id"]), "decided_by": r["decided_by"],
             "decided_at": r["decided_at"], "created_at": r["created_at"], "version": 1}]


# ---------------------------------------------------------------- mappings

def _m(name, sql, fn, expected=True, note=""):
    return Mapping(name, table=CTX, sql=sql, transform=fn, expected_source=name if expected else None, note=note)


MAPPINGS = [
    _m("live.session", SESSION_SQL, session_items, note="META + JOINCODE sentinel + STAFF owner"),
    _m("live.session#seq", SEQ_SQL, seq_item, expected=False, note="SEQ counter from max(session_event.sequence)"),
    _m("live.participant", PART_SQL, part_item),
    _m("live.session_event", EVT_SQL, evt_item),
    _m("live.command_receipt", CMD_SQL, cmd_item, note="CMD re-keyed by actor"),
    _m("live.topic_run", TOPICRUN_SQL, topicrun_item),
    _m("live.recommendation", REC_SQL, rec_item),
    _m("live.takeover", TAKEOVER_SQL, takeover_items, note="TAKEOVER + TAKEOVER_ACTIVE for open takeovers"),
    _m("activity.instance", ACT_SQL, act_item, note="ACT with public + answer_key snapshot"),
    _m("activity.response", RESP_SQL, resp_item),
    _m("visual.widget_spec", WSPEC_SQL, wspec_item, note="library specs skipped (stay in PG)"),
    _m("visual.widget_state", WIDGET_SQL, widget_item),
    _m("authoring.presentation_plan", PLAN_SQL, plan_item, note="topics embedded"),
    _m("authoring.presentation_plan#plankey", PLANKEY_SQL, plankey_items, expected=False,
       note="PLANKEY_COUNTER/PUBLISHED/EDITABLE sentinels"),
    _m("authoring.plan_topic", PLAN_TOPIC_SQL, plan_topic_none, note="embedded in PLAN.topics"),
    _m("authoring.chat_session", CHAT_SQL, chat_item),
    _m("authoring.chat_message", MSG_SQL, msg_item, note="message_id → per-chat monotonic int"),
    _m("authoring.proposed_patch", PATCH_SQL, patch_item),
]
