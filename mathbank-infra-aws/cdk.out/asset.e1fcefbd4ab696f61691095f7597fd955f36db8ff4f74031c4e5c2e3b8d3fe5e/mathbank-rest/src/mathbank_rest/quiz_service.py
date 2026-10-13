"""Admin authoring for the activity/quiz bank (requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md
Tier A). `activity.definition` is a table shared with the live/fluid-session system (migration
020); this module only authors `INSTRUCTOR_CREATED`/`STATIC` rows suitable for binding into a
micro-course state via `micro_course_service.attach_activity` — it never edits a `PRECOMPILED`/
`CORPUS_DERIVED` row authored elsewhere, and never creates a `LIVE_AGENT_CREATED`/`SESSION`/
`EPHEMERAL` row (those remain the live-session system's own concern, untouched by this module).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from sqlalchemy import text

from mathbank_rest.micro_course_service import record_audit_event

ACTIVITY_TYPES = {
    "MCQ", "MULTISELECT", "NUMERIC", "SHORT_RESPONSE", "SUBPROBLEM", "STEP_ORDERING",
    "ERROR_DIAGNOSIS", "CONFIDENCE_CHECK", "LIVE_POLL",
}


class ActivityNotFound(ValueError):
    pass


class ActivityConflict(RuntimeError):
    pass


def _required_text(value: str, field: str) -> str:
    value = (value or "").strip()
    if not value:
        raise ValueError(f"{field} is required")
    return value


def _json(value: Any) -> str:
    import json

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def create_activity(
    conn, *, activity_type: str, prompt: str, options: list[dict], correctness_policy: dict,
    estimated_seconds: int = 60, skill_id: str | None = None, source_problem_id: str | None = None,
    created_by: str,
) -> dict:
    """Always creates source_type='INSTRUCTOR_CREATED', persistence_mode='STATIC' — the
    endpoint's entire purpose is authoring exactly the kind of row attach_activity() accepts,
    so nothing created here could ever fail to attach (requirements/46 QZA-1)."""
    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(f"activity_type must be one of {sorted(ACTIVITY_TYPES)}")
    prompt = _required_text(prompt, "prompt")
    created_by = _required_text(created_by, "created_by")
    if skill_id is not None:
        exists = conn.execute(
            text("SELECT 1 FROM knowledge.skill WHERE skill_id=:id"), {"id": skill_id}
        ).scalar_one_or_none()
        if exists is None:
            raise ActivityNotFound("skill_id does not reference a known skill")
    if source_problem_id is not None:
        exists = conn.execute(
            text("SELECT 1 FROM core.problem WHERE problem_id=:id"), {"id": source_problem_id}
        ).scalar_one_or_none()
        if exists is None:
            raise ActivityNotFound("source_problem_id does not reference a known problem")
    activity_id = str(uuid4())
    conn.execute(
        text("""
        INSERT INTO activity.definition
            (activity_id, activity_type, prompt, options, correctness_policy, estimated_seconds,
             target_skill_id, source_problem_id, source_type, persistence_mode, created_by)
        VALUES
            (:id, :activity_type, :prompt, CAST(:options AS jsonb), CAST(:policy AS jsonb), :seconds,
             :skill_id, :source_problem_id, 'INSTRUCTOR_CREATED', 'STATIC', :created_by)
    """),
        {
            "id": activity_id, "activity_type": activity_type, "prompt": prompt,
            "options": _json(options or []), "policy": _json(correctness_policy or {}),
            "seconds": estimated_seconds, "skill_id": skill_id, "source_problem_id": source_problem_id,
            "created_by": created_by,
        },
    )
    record_audit_event(
        conn, "ADMIN", created_by, "ACTIVITY_CREATED", "ACTIVITY", activity_id,
        after_state={"activity_type": activity_type, "prompt": prompt},
    )
    return get_activity(conn, activity_id)


def list_activities(
    conn, *, q: str = "", activity_type: str | None = None, source_type: str | None = None,
    status: str = "ALL", limit: int = 50, offset: int = 0,
) -> dict:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("limit must be 1..200 and offset must be non-negative")
    where = ["1=1"]
    params: dict[str, Any] = {"q": f"%{q}%", "limit": limit, "offset": offset}
    if q:
        where.append("a.prompt ILIKE :q")
    if activity_type:
        if activity_type not in ACTIVITY_TYPES:
            raise ValueError(f"activity_type must be one of {sorted(ACTIVITY_TYPES)}")
        where.append("a.activity_type = :activity_type")
        params["activity_type"] = activity_type
    if source_type:
        where.append("a.source_type = :source_type")
        params["source_type"] = source_type
    if status != "ALL":
        if status not in ("ACTIVE", "INACTIVE"):
            raise ValueError("status must be ACTIVE, INACTIVE, or ALL")
        where.append("a.status = :status")
        params["status"] = status
    rows = conn.execute(
        text(f"""
        SELECT a.activity_id, a.activity_type, a.prompt, a.estimated_seconds, a.source_type,
               a.persistence_mode, a.status, a.deactivated_at, a.deactivated_by,
               a.target_skill_id, a.source_problem_id, a.created_by, a.created_at,
               s.slug AS skill_slug, p.canonical_code AS source_problem_code
        FROM activity.definition a
        LEFT JOIN knowledge.skill s ON s.skill_id = a.target_skill_id
        LEFT JOIN core.problem p ON p.problem_id = a.source_problem_id
        WHERE {" AND ".join(where)}
        ORDER BY a.created_at DESC
        LIMIT :limit OFFSET :offset
    """),
        params,
    ).mappings()
    items = [dict(r) for r in rows]
    for item in items:
        item["activity_id"] = str(item["activity_id"])
        if item["target_skill_id"]:
            item["target_skill_id"] = str(item["target_skill_id"])
        if item["source_problem_id"]:
            item["source_problem_id"] = str(item["source_problem_id"])
    return {"items": items}


def get_activity(conn, activity_id: str) -> dict:
    row = conn.execute(
        text("""
        SELECT a.*, s.slug AS skill_slug, p.canonical_code AS source_problem_code
        FROM activity.definition a
        LEFT JOIN knowledge.skill s ON s.skill_id = a.target_skill_id
        LEFT JOIN core.problem p ON p.problem_id = a.source_problem_id
        WHERE a.activity_id=:id
    """),
        {"id": activity_id},
    ).mappings().one_or_none()
    if row is None:
        raise ActivityNotFound("activity not found")
    result = dict(row)
    result["activity_id"] = str(result["activity_id"])
    if result.get("target_skill_id"):
        result["target_skill_id"] = str(result["target_skill_id"])
    if result.get("source_problem_id"):
        result["source_problem_id"] = str(result["source_problem_id"])
    return result


def update_activity(
    conn, activity_id: str, *, prompt: str | None = None, options: list[dict] | None = None,
    correctness_policy: dict | None = None, estimated_seconds: int | None = None, actor: str,
) -> dict:
    """Rejects (409) editing anything but an INSTRUCTOR_CREATED row (requirements/46 QZA-3) —
    a PRECOMPILED/CORPUS_DERIVED activity was authored by a different, non-admin-REST pipeline
    and must not be silently mutated through this surface."""
    row = conn.execute(
        text("SELECT source_type FROM activity.definition WHERE activity_id=:id FOR UPDATE"),
        {"id": activity_id},
    ).mappings().one_or_none()
    if row is None:
        raise ActivityNotFound("activity not found")
    if row["source_type"] != "INSTRUCTOR_CREATED":
        raise ActivityConflict(f"only INSTRUCTOR_CREATED activities can be edited (this one is {row['source_type']})")
    sets = []
    params: dict[str, Any] = {"id": activity_id}
    if prompt is not None:
        sets.append("prompt=:prompt")
        params["prompt"] = _required_text(prompt, "prompt")
    if options is not None:
        sets.append("options=CAST(:options AS jsonb)")
        params["options"] = _json(options)
    if correctness_policy is not None:
        sets.append("correctness_policy=CAST(:policy AS jsonb)")
        params["policy"] = _json(correctness_policy)
    if estimated_seconds is not None:
        sets.append("estimated_seconds=:seconds")
        params["seconds"] = estimated_seconds
    if not sets:
        raise ValueError("at least one of prompt, options, correctness_policy, estimated_seconds must be supplied")
    conn.execute(text(f"UPDATE activity.definition SET {', '.join(sets)} WHERE activity_id=:id"), params)
    record_audit_event(conn, "ADMIN", actor, "ACTIVITY_UPDATED", "ACTIVITY", activity_id)
    return get_activity(conn, activity_id)


def set_skill_mapping(conn, activity_id: str, skill_id: str | None, actor: str) -> dict:
    row = conn.execute(
        text("SELECT 1 FROM activity.definition WHERE activity_id=:id"), {"id": activity_id}
    ).scalar_one_or_none()
    if row is None:
        raise ActivityNotFound("activity not found")
    if skill_id is not None:
        exists = conn.execute(
            text("SELECT 1 FROM knowledge.skill WHERE skill_id=:id"), {"id": skill_id}
        ).scalar_one_or_none()
        if exists is None:
            raise ActivityNotFound("skill_id does not reference a known skill")
    conn.execute(
        text("UPDATE activity.definition SET target_skill_id=:skill_id WHERE activity_id=:id"),
        {"skill_id": skill_id, "id": activity_id},
    )
    record_audit_event(conn, "ADMIN", actor, "ACTIVITY_SKILL_MAPPED", "ACTIVITY", activity_id,
                        after_state={"target_skill_id": skill_id})
    return get_activity(conn, activity_id)


def set_source_mapping(conn, activity_id: str, source_problem_id: str | None, actor: str) -> dict:
    row = conn.execute(
        text("SELECT 1 FROM activity.definition WHERE activity_id=:id"), {"id": activity_id}
    ).scalar_one_or_none()
    if row is None:
        raise ActivityNotFound("activity not found")
    if source_problem_id is not None:
        exists = conn.execute(
            text("SELECT 1 FROM core.problem WHERE problem_id=:id"), {"id": source_problem_id}
        ).scalar_one_or_none()
        if exists is None:
            raise ActivityNotFound("source_problem_id does not reference a known problem")
    conn.execute(
        text("UPDATE activity.definition SET source_problem_id=:source_problem_id WHERE activity_id=:id"),
        {"source_problem_id": source_problem_id, "id": activity_id},
    )
    record_audit_event(conn, "ADMIN", actor, "ACTIVITY_SOURCE_MAPPED", "ACTIVITY", activity_id,
                        after_state={"source_problem_id": source_problem_id})
    return get_activity(conn, activity_id)


def _guard_published_binding(conn, activity_id: str) -> None:
    """Block deactivating a quiz still bound to a state belonging to a PUBLISHED release
    (requirements/46 §2.5), mirroring the taxonomy_service/micro-course immutability guards."""
    blocking = conn.execute(
        text("""
            SELECT c.canonical_code, r.version
            FROM pedagogy.micro_course_state_activity sa
            JOIN pedagogy.micro_course_state s ON s.state_id = sa.state_id
            JOIN pedagogy.micro_course_release r ON r.release_id = s.release_id AND r.status='PUBLISHED'
            JOIN pedagogy.micro_course c ON c.micro_course_id = r.micro_course_id
            WHERE sa.activity_id = :id
            LIMIT 1
        """),
        {"id": activity_id},
    ).mappings().one_or_none()
    if blocking is not None:
        raise ActivityConflict(
            f"Cannot deactivate: still bound to a state in published micro-course "
            f"{blocking['canonical_code']} v{blocking['version']}"
        )


def deactivate_activity(conn, activity_id: str, actor: str) -> dict:
    row = conn.execute(
        text("SELECT status FROM activity.definition WHERE activity_id=:id FOR UPDATE"),
        {"id": activity_id},
    ).mappings().one_or_none()
    if row is None:
        raise ActivityNotFound("activity not found")
    if row["status"] != "ACTIVE":
        raise ActivityConflict("activity is already deactivated")
    _guard_published_binding(conn, activity_id)
    actor = _required_text(actor, "actor")
    conn.execute(
        text("UPDATE activity.definition SET status='INACTIVE', deactivated_at=now(), deactivated_by=:actor "
             "WHERE activity_id=:id"),
        {"id": activity_id, "actor": actor},
    )
    record_audit_event(conn, "ADMIN", actor, "ACTIVITY_DEACTIVATED", "ACTIVITY", activity_id)
    return {"activity_id": activity_id, "status": "INACTIVE"}


def reactivate_activity(conn, activity_id: str, actor: str) -> dict:
    row = conn.execute(
        text("SELECT status FROM activity.definition WHERE activity_id=:id FOR UPDATE"),
        {"id": activity_id},
    ).mappings().one_or_none()
    if row is None:
        raise ActivityNotFound("activity not found")
    if row["status"] == "ACTIVE":
        raise ActivityConflict("activity is already active")
    actor = _required_text(actor, "actor")
    conn.execute(
        text("UPDATE activity.definition SET status='ACTIVE', deactivated_at=NULL, deactivated_by=NULL "
             "WHERE activity_id=:id"),
        {"id": activity_id},
    )
    record_audit_event(conn, "ADMIN", actor, "ACTIVITY_REACTIVATED", "ACTIVITY", activity_id)
    return {"activity_id": activity_id, "status": "ACTIVE"}
