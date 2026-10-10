"""Shared authoring and publication services for deterministic micro-courses."""

from __future__ import annotations

import hashlib
import json
from collections import deque
from typing import Any
from uuid import uuid4

from sqlalchemy import text

TARGETS = {
    "CONCEPT": ("knowledge.concept", "concept_id"),
    "TECHNIQUE": ("knowledge.technique", "technique_id"),
    "SKILL": ("knowledge.skill", "skill_id"),
}
STATE_TARGETS = {
    **TARGETS,
    "MISCONCEPTION": ("knowledge.misconception", "misconception_id"),
}
STATE_BINDINGS = {
    "CONCEPT": ("pedagogy.micro_course_state_concept", "concept_id"),
    "TECHNIQUE": ("pedagogy.micro_course_state_technique", "technique_id"),
    "SKILL": ("pedagogy.micro_course_state_skill", "skill_id"),
    "MISCONCEPTION": ("pedagogy.micro_course_state_misconception", "misconception_id"),
}
FORBIDDEN_POLICY_FLAGS = (
    "may_create_quiz",
    "may_search_web",
    "may_recommend_media",
    "may_generate_diagram",
    "may_add_course_state",
)
DEFAULT_AGENT_POLICY = {
    "may_rephrase": True,
    "may_explain_current_content": True,
    "may_create_quiz": False,
    "may_search_web": False,
    "may_recommend_media": False,
    "may_generate_diagram": False,
    "may_add_course_state": False,
}


class MicroCourseNotFound(ValueError):
    pass


class MicroCourseConflict(RuntimeError):
    pass


def _policy_errors(policy: dict | None, subject: str, *, require_explicit: bool) -> list[str]:
    effective = policy or {}
    errors = []
    for flag in FORBIDDEN_POLICY_FLAGS:
        if effective.get(flag) is True:
            errors.append(f"{subject} agent policy forbids {flag}=true")
        elif require_explicit and effective.get(flag) is not False:
            errors.append(f"{subject} agent policy must explicitly set {flag}=false")
    return errors


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def record_audit_event(
    conn,
    actor_type: str,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    before_state: dict | None = None,
    after_state: dict | None = None,
    request_id: str | None = None,
) -> str:
    """Append one row to the general-purpose audit trail (requirements/44 MCX-8).
    Always generates a request_id if the caller doesn't supply one, so every audited
    action is independently traceable even when called outside an HTTP request."""
    request_id = request_id or str(uuid4())
    conn.execute(
        text("""
        INSERT INTO audit.action_log
            (actor_type, actor_id, action, entity_type, entity_id, before_state, after_state, request_id)
        VALUES (:actor_type, :actor_id, :action, :entity_type, :entity_id,
                CAST(:before AS jsonb), CAST(:after AS jsonb), :request_id)
    """),
        {
            "actor_type": actor_type.upper(),
            "actor_id": actor_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "before": _json(before_state) if before_state is not None else None,
            "after": _json(after_state) if after_state is not None else None,
            "request_id": request_id,
        },
    )
    return request_id


def _required_text(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field} is required")
    return normalized


def _canonical_target(conn, target_type: str, target_id: str) -> tuple[str, str]:
    target_type = target_type.upper()
    try:
        table, id_column = STATE_TARGETS[target_type]
    except KeyError as exc:
        raise ValueError(f"unsupported canonical target type: {target_type}") from exc
    found = conn.execute(
        text(f"SELECT 1 FROM {table} WHERE {id_column} = :id"),
        {"id": str(target_id)},
    ).scalar_one_or_none()
    if found is None:
        raise ValueError(f"unknown {target_type.lower()} id: {target_id}")
    return target_type, id_column


def _editable_release(conn, release_id: str, *, lock: bool = True) -> dict:
    suffix = " FOR UPDATE" if lock else ""
    row = (
        conn.execute(
            text(
                "SELECT release_id, micro_course_id, status FROM pedagogy.micro_course_release "
                "WHERE release_id=:id" + suffix
            ),
            {"id": str(release_id)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise MicroCourseNotFound("micro-course release not found")
    release = dict(row)
    if release["status"] != "DRAFT":
        raise MicroCourseConflict("only DRAFT releases can be edited; create a new draft release")
    return release


def validate_state_graph(
    states: list[dict], transitions: list[dict]
) -> list[str]:
    """Check entry reachability and terminal completion on a persisted state graph."""
    if not states:
        return ["release has no states"]

    state_ids = {str(state["state_id"]) for state in states}
    entry = min(states, key=lambda state: (state["ordinal"], str(state["state_id"])))
    entry_id = str(entry["state_id"])
    errors: list[str] = []
    edges: dict[str, set[str]] = {state_id: set() for state_id in state_ids}
    reverse: dict[str, set[str]] = {state_id: set() for state_id in state_ids}
    for transition in transitions:
        source = str(transition["from_state_id"])
        target = str(transition["to_state_id"])
        if source not in state_ids or target not in state_ids:
            errors.append(f"transition {transition.get('transition_id', '')} crosses release boundary")
            continue
        edges[source].add(target)
        reverse[target].add(source)

    reached = {entry_id}
    pending = deque([entry_id])
    while pending:
        source = pending.popleft()
        for target in edges[source] - reached:
            reached.add(target)
            pending.append(target)

    for state in states:
        state_id = str(state["state_id"])
        if state.get("required", True) and state_id not in reached:
            errors.append(f"required state {state['state_key']} is unreachable from the entry state")

    terminal_ids = {state_id for state_id, targets in edges.items() if not targets}
    can_finish = set(terminal_ids)
    pending = deque(terminal_ids)
    while pending:
        target = pending.popleft()
        for source in reverse[target] - can_finish:
            can_finish.add(source)
            pending.append(source)
    for state in states:
        state_id = str(state["state_id"])
        if state.get("required", True) and state_id not in can_finish:
            errors.append(f"required state {state['state_key']} has no path to a terminal state")
    return errors


def list_courses(conn, limit: int = 50, offset: int = 0) -> list[dict]:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("limit must be 1..200 and offset must be non-negative")
    rows = conn.execute(
        text("""
        SELECT course.micro_course_id, course.canonical_code, course.title, course.description,
               course.metadata, course.is_active, course.deactivated_at, course.updated_at,
               course.estimated_minutes, course.difficulty_level,
               latest.release_id, latest.version, latest.status,
               COALESCE(counts.state_count, 0) AS state_count,
               COALESCE(targets.primary_targets, '[]'::jsonb) AS primary_targets
        FROM pedagogy.micro_course course
        LEFT JOIN LATERAL (
            SELECT r.release_id, r.version, r.status
            FROM pedagogy.micro_course_release r
            WHERE r.micro_course_id=course.micro_course_id
            ORDER BY r.version DESC LIMIT 1
        ) latest ON true
        LEFT JOIN LATERAL (
            SELECT count(*) AS state_count
            FROM pedagogy.micro_course_state s
            WHERE s.release_id=latest.release_id
        ) counts ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                'target_type', t.target_type, 'target_id',
                COALESCE(t.concept_id, t.technique_id, t.skill_id), 'name',
                COALESCE(concept.name, technique.name, skill.name), 'slug',
                COALESCE(concept.slug, technique.slug, skill.slug), 'ordinal', t.ordinal
            ) ORDER BY t.ordinal) AS primary_targets
            FROM pedagogy.micro_course_target t
            LEFT JOIN knowledge.concept concept ON concept.concept_id=t.concept_id
            LEFT JOIN knowledge.technique technique ON technique.technique_id=t.technique_id
            LEFT JOIN knowledge.skill skill ON skill.skill_id=t.skill_id
            WHERE t.micro_course_id=course.micro_course_id AND t.role='PRIMARY'
        ) targets ON true
        ORDER BY course.canonical_code
        LIMIT :limit OFFSET :offset
    """),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(row) for row in rows]


def search_canonical_targets(conn, target_type: str, query: str, limit: int = 20) -> list[dict]:
    if limit < 1 or limit > 50:
        raise ValueError("limit must be 1..50")
    target_type = _required_text(target_type, "target_type").upper()
    if target_type == "MISCONCEPTION":
        rows = conn.execute(
            text("""
            SELECT misconception_id AS id, canonical_code AS slug, name
            FROM knowledge.misconception
            WHERE review_status='APPROVED'
              AND (canonical_code ILIKE :pattern OR name ILIKE :pattern)
            ORDER BY name, canonical_code LIMIT :limit
        """),
            {"pattern": f"%{query.strip()}%", "limit": limit},
        ).mappings()
        return [dict(row) for row in rows]
    if target_type not in TARGETS:
        raise ValueError("target_type must be CONCEPT, TECHNIQUE, SKILL, or MISCONCEPTION")
    table, id_column = TARGETS[target_type]
    rows = conn.execute(
        text(f"""
        SELECT {id_column} AS id, slug, name
        FROM {table}
        WHERE slug ILIKE :pattern OR name ILIKE :pattern
        ORDER BY name, slug LIMIT :limit
    """),
        {"pattern": f"%{query.strip()}%", "limit": limit},
    ).mappings()
    return [dict(row) for row in rows]


def list_published_courses(conn, limit: int = 50, offset: int = 0) -> list[dict]:
    if limit < 1 or limit > 200 or offset < 0:
        raise ValueError("limit must be 1..200 and offset must be non-negative")
    rows = conn.execute(
        text("""
        SELECT c.canonical_code, c.title, c.description, c.metadata, c.estimated_minutes,
               c.difficulty_level, r.release_id, r.version,
               COALESCE(state_counts.state_count, 0) AS state_count,
               COALESCE(targets.primary_targets, '[]'::jsonb) AS primary_targets
        FROM pedagogy.micro_course c
        JOIN pedagogy.micro_course_release r
          ON r.micro_course_id=c.micro_course_id AND r.status='PUBLISHED'
        LEFT JOIN LATERAL (
            SELECT count(*) AS state_count
            FROM pedagogy.micro_course_state s WHERE s.release_id=r.release_id
        ) state_counts ON true
        LEFT JOIN LATERAL (
            SELECT jsonb_agg(jsonb_build_object(
                'target_type', t.target_type, 'name',
                COALESCE(concept.name, technique.name, skill.name),
                'slug', COALESCE(concept.slug, technique.slug, skill.slug)
            ) ORDER BY t.ordinal) AS primary_targets
            FROM pedagogy.micro_course_target t
            LEFT JOIN knowledge.concept concept ON concept.concept_id=t.concept_id
            LEFT JOIN knowledge.technique technique ON technique.technique_id=t.technique_id
            LEFT JOIN knowledge.skill skill ON skill.skill_id=t.skill_id
            WHERE t.micro_course_id=c.micro_course_id AND t.role='PRIMARY'
        ) targets ON true
        WHERE c.is_active
        ORDER BY c.title, c.canonical_code LIMIT :limit OFFSET :offset
    """),
        {"limit": limit, "offset": offset},
    ).mappings()
    return [dict(row) for row in rows]


def get_published_course(conn, canonical_code: str) -> dict:
    course = (
        conn.execute(
            text("""
            SELECT c.micro_course_id, c.canonical_code, c.title, c.description, c.metadata,
                   c.estimated_minutes, c.difficulty_level, r.release_id, r.version,
                   r.learning_objectives, r.prerequisite_summary
            FROM pedagogy.micro_course c
            JOIN pedagogy.micro_course_release r
              ON r.micro_course_id=c.micro_course_id AND r.status='PUBLISHED'
            WHERE c.canonical_code=:code AND c.is_active
        """),
            {"code": _required_text(canonical_code, "canonical_code")},
        )
        .mappings()
        .one_or_none()
    )
    if course is None:
        raise MicroCourseNotFound("published micro-course not found")
    return _assemble_course_reader_payload(conn, course)


def get_course_preview(conn, canonical_code: str, release_id: str | None = None) -> dict:
    """Admin-only preview of any release (DRAFT included) in the exact shape the
    student reader consumes (requirements/43 AMC-14/§4.3) — never a second renderer.
    Ignores `is_active`/deactivation so admins can still QA a hidden course."""
    code = _required_text(canonical_code, "canonical_code")
    params: dict = {"code": code}
    release_filter = "TRUE"
    if release_id:
        release_filter = "r.release_id=:release_id"
        params["release_id"] = release_id
    course = (
        conn.execute(
            text(f"""
            SELECT c.micro_course_id, c.canonical_code, c.title, c.description, c.metadata,
                   c.estimated_minutes, c.difficulty_level, r.release_id, r.version,
                   r.status AS release_status,
                   r.learning_objectives, r.prerequisite_summary
            FROM pedagogy.micro_course c
            JOIN pedagogy.micro_course_release r ON r.micro_course_id=c.micro_course_id
            WHERE c.canonical_code=:code AND {release_filter}
            ORDER BY r.version DESC
            LIMIT 1
        """),
            params,
        )
        .mappings()
        .one_or_none()
    )
    if course is None:
        raise MicroCourseNotFound("micro-course release not found")
    return _assemble_course_reader_payload(conn, course, approved_only=False)


def _assemble_course_reader_payload(conn, course, approved_only: bool = True) -> dict:
    """Shared assembly for the public reader shape — used by both the public
    `get_published_course` (always approved-only content) and the admin
    `get_course_preview` (shows unapproved/draft content too, so an admin previewing
    a draft sees exactly what they are about to publish, not an empty shell)."""
    result = dict(course)
    release_id = str(result["release_id"])
    interaction_filter = "AND i.review_status='APPROVED'" if approved_only else ""
    qa_filter = "AND review_status='APPROVED'" if approved_only else ""
    learning_item_filter = "AND li.review_status='APPROVED' AND li.student_visible" if approved_only else ""
    transcript_filter = "AND t.status='APPROVED'" if approved_only else ""
    segment_filter = "AND seg.review_status='APPROVED'" if approved_only else ""
    transition_filter = "AND review_status='APPROVED'" if approved_only else ""
    result["primary_targets"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT t.target_type,
                   COALESCE(concept.name, technique.name, skill.name) AS name,
                   COALESCE(concept.slug, technique.slug, skill.slug) AS slug
            FROM pedagogy.micro_course_target t
            LEFT JOIN knowledge.concept concept ON concept.concept_id=t.concept_id
            LEFT JOIN knowledge.technique technique ON technique.technique_id=t.technique_id
            LEFT JOIN knowledge.skill skill ON skill.skill_id=t.skill_id
            WHERE t.micro_course_id=:course_id AND t.role='PRIMARY'
            ORDER BY t.ordinal
        """),
            {"course_id": str(result["micro_course_id"])},
        ).mappings()
    ]
    result["prerequisite_targets"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT t.target_type,
                   COALESCE(concept.name, technique.name, skill.name) AS name,
                   COALESCE(concept.slug, technique.slug, skill.slug) AS slug
            FROM pedagogy.micro_course_target t
            LEFT JOIN knowledge.concept concept ON concept.concept_id=t.concept_id
            LEFT JOIN knowledge.technique technique ON technique.technique_id=t.technique_id
            LEFT JOIN knowledge.skill skill ON skill.skill_id=t.skill_id
            WHERE t.micro_course_id=:course_id AND t.role='PREREQUISITE'
            ORDER BY t.ordinal
        """),
            {"course_id": str(result["micro_course_id"])},
        ).mappings()
    ]
    result["modules"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT module_id, module_key, ordinal, title, objective,
                   estimated_seconds, required
            FROM pedagogy.micro_course_module
            WHERE release_id=:id ORDER BY ordinal
        """),
            {"id": release_id},
        ).mappings()
    ]
    result["states"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT s.state_id, s.module_id, m.module_key, s.state_key, s.ordinal,
                   s.state_type, s.title, s.objective, s.student_instruction,
                   s.estimated_seconds, s.required, s.skippable
            FROM pedagogy.micro_course_state s
            LEFT JOIN pedagogy.micro_course_module m USING (module_id)
            WHERE s.release_id=:id ORDER BY s.ordinal
        """),
            {"id": release_id},
        ).mappings()
    ]
    for state in result["states"]:
        state_id = str(state["state_id"])
        state["assets"] = [
            dict(row)
            for row in conn.execute(
                text("""
                SELECT a.asset_id, a.uri, a.asset_kind, a.title, a.source_url, a.mime_type,
                       a.object_size_bytes,
                       sa.presentation_role, v.canonical_url AS video_url,
                       v.duration_ms
                FROM pedagogy.micro_course_state_asset sa
                JOIN visual.asset a USING (asset_id)
                LEFT JOIN pedagogy.video_asset v
                  ON v.visual_asset_id=a.asset_id AND v.review_status='APPROVED'
                WHERE sa.state_id=:id AND a.validation_status='VALID'
                ORDER BY sa.ordinal
            """),
                {"id": state_id},
            ).mappings()
        ]
        for asset in state["assets"]:
            asset["asset_id"] = str(asset["asset_id"])
            asset["private_object"] = str(asset["uri"]).startswith("object-store:")
            asset.pop("uri", None)
        state["qa_contexts"] = [
            dict(row)
            for row in conn.execute(
                text(f"""
                SELECT context_type, question_pattern, approved_content,
                       concept_id, technique_id, skill_id, misconception_id
                FROM pedagogy.state_qa_context
                WHERE state_id=:id {qa_filter}
                ORDER BY priority DESC
            """),
                {"id": state_id},
            ).mappings()
        ]
        state["learning_items"] = [
            dict(row)
            for row in conn.execute(
                text(f"""
                SELECT li.learning_item_id, li.question_text, li.choices,
                       si.purpose, si.ordinal, si.required
                FROM pedagogy.micro_course_state_learning_item si
                JOIN pedagogy.learning_item li USING (learning_item_id)
                WHERE si.state_id=:id {learning_item_filter}
                ORDER BY si.ordinal
            """),
                {"id": state_id},
            ).mappings()
        ]
        state["transcript_segments"] = [
            dict(row)
            for row in conn.execute(
                text(f"""
                SELECT seg.segment_id, seg.start_ms, seg.end_ms, seg.transcript_text,
                       seg.speaker, seg.segment_index
                FROM pedagogy.micro_course_state_asset sa
                JOIN pedagogy.video_asset v ON v.visual_asset_id=sa.asset_id
                JOIN pedagogy.video_transcript t USING (video_asset_id)
                JOIN pedagogy.video_transcript_segment seg USING (transcript_id)
                WHERE sa.state_id=:id {transcript_filter}
                  {segment_filter}
                ORDER BY seg.start_ms, seg.segment_index
            """),
                {"id": state_id},
            ).mappings()
        ]
        state["interactions"] = [
            dict(row)
            for row in conn.execute(
                text(f"""
                SELECT i.interaction_instance_id, i.canonical_code, i.title,
                       i.instance_config, i.initial_state, i.learning_objective,
                       i.success_criteria, v.version AS template_version,
                       t.template_key, t.interaction_family, v.default_layout,
                       v.allowed_controls, v.allowed_icons, v.accessibility_policy,
                       scene.scene_json
                FROM pedagogy.micro_course_state_interaction si
                JOIN visual.interaction_instance i USING (interaction_instance_id)
                JOIN visual.interaction_template_version v USING (interaction_template_version_id)
                JOIN visual.interaction_template t USING (interaction_template_id)
                LEFT JOIN visual.scene_spec scene
                  ON scene.scene_spec_id=i.scene_spec_id AND scene.status='APPROVED'
                WHERE si.state_id=:id {interaction_filter}
                  AND v.status='PUBLISHED'
                ORDER BY si.ordinal
            """),
                {"id": state_id},
            ).mappings()
        ]
        for interaction in state["interactions"]:
            interaction["interaction_instance_id"] = str(
                interaction["interaction_instance_id"]
            )
        state["activities"] = [
            dict(row)
            for row in conn.execute(
                text("""
                SELECT a.activity_id, a.activity_type, a.prompt, a.options,
                       a.correctness_policy, sa.ordinal, sa.purpose, sa.required
                FROM pedagogy.micro_course_state_activity sa
                JOIN activity.definition a USING (activity_id)
                WHERE sa.state_id=:id
                ORDER BY sa.ordinal
            """),
                {"id": state_id},
            ).mappings()
        ]
        for activity in state["activities"]:
            activity["activity_id"] = str(activity["activity_id"])
    result["transitions"] = [
        dict(row)
        for row in conn.execute(
            text(f"""
            SELECT from_state_id, to_state_id, transition_type, condition_type,
                   condition_payload, priority
            FROM pedagogy.micro_course_transition
            WHERE release_id=:id {transition_filter}
            ORDER BY from_state_id, priority
        """),
            {"id": release_id},
        ).mappings()
    ]
    return result


def start_enrollment(conn, canonical_code: str, student_id: str) -> dict:
    """Create or resume a learner's in-progress enrollment on the published release."""
    code = _required_text(canonical_code, "canonical_code")
    course = (
        conn.execute(
            text("""
            SELECT c.micro_course_id, c.canonical_code, r.release_id
            FROM pedagogy.micro_course c
            JOIN pedagogy.micro_course_release r
              ON r.micro_course_id=c.micro_course_id AND r.status='PUBLISHED'
            WHERE c.canonical_code=:code AND c.is_active
            FOR UPDATE OF c
        """),
            {"code": code},
        )
        .mappings()
        .one_or_none()
    )
    if course is None:
        raise MicroCourseNotFound("published micro-course not found")
    student_status = conn.execute(
        text("SELECT status FROM learner.student_profile WHERE student_id=:student_id"),
        {"student_id": str(student_id)},
    ).scalar_one_or_none()
    if student_status != "ACTIVE":
        raise MicroCourseNotFound("active student account not found")

    existing = conn.execute(
        text("""
        SELECT enrollment_id
        FROM learner.micro_course_enrollment
        WHERE student_id=:student_id AND micro_course_id=:course_id
          AND status='IN_PROGRESS'
        ORDER BY started_at DESC, enrollment_id DESC
        LIMIT 1
        FOR UPDATE
    """),
        {"student_id": str(student_id), "course_id": str(course["micro_course_id"])},
    ).scalar_one_or_none()
    if existing is not None:
        return get_enrollment_runtime(conn, str(existing), str(student_id))

    entry_state_id = conn.execute(
        text("""
        SELECT state_id
        FROM pedagogy.micro_course_state
        WHERE release_id=:release_id
        ORDER BY ordinal, state_id
        LIMIT 1
    """),
        {"release_id": str(course["release_id"])},
    ).scalar_one_or_none()
    if entry_state_id is None:
        raise MicroCourseConflict("published course has no entry state")
    enrollment_id = conn.execute(
        text("""
        INSERT INTO learner.micro_course_enrollment
            (student_id, micro_course_id, release_id)
        VALUES (:student_id, :course_id, :release_id)
        RETURNING enrollment_id
    """),
        {
            "student_id": str(student_id),
            "course_id": str(course["micro_course_id"]),
            "release_id": str(course["release_id"]),
        },
    ).scalar_one()
    conn.execute(
        text("""
        INSERT INTO tutor.micro_course_runtime (enrollment_id, current_state_id)
        VALUES (:enrollment_id, :state_id)
    """),
        {"enrollment_id": str(enrollment_id), "state_id": str(entry_state_id)},
    )
    conn.execute(
        text("""
        INSERT INTO learner.micro_course_state_event (enrollment_id, state_id, event_type, payload)
        VALUES (:enrollment_id, :state_id, 'ENROLLED', CAST(:payload AS jsonb))
    """),
        {
            "enrollment_id": str(enrollment_id),
            "state_id": str(entry_state_id),
            "payload": _json({"canonical_code": course["canonical_code"]}),
        },
    )
    return get_enrollment_runtime(conn, str(enrollment_id), str(student_id))


def get_enrollment_runtime(conn, enrollment_id: str, student_id: str) -> dict:
    """Return the pinned release's current approved state and learner-safe material."""
    row = (
        conn.execute(
            text("""
            SELECT e.enrollment_id, e.status AS enrollment_status, e.started_at, e.completed_at,
                   e.micro_course_id, e.release_id, r.version, rt.state_version,
                   c.canonical_code, c.title AS course_title, c.description AS course_description,
                   c.estimated_minutes, s.state_id, s.state_key, s.ordinal AS state_ordinal,
                   s.state_type, s.title AS state_title, s.objective, s.student_instruction,
                   s.estimated_seconds, s.required, m.module_id, m.title AS module_title,
                   (SELECT count(*) FROM pedagogy.micro_course_state all_states
                    WHERE all_states.release_id=e.release_id) AS step_count,
                   (SELECT count(*) FROM pedagogy.micro_course_state prior
                    WHERE prior.release_id=e.release_id AND prior.ordinal<=s.ordinal) AS step_number
            FROM learner.micro_course_enrollment e
            JOIN tutor.micro_course_runtime rt ON rt.enrollment_id = e.enrollment_id
            JOIN pedagogy.micro_course_release r ON r.release_id = e.release_id
            JOIN pedagogy.micro_course c ON c.micro_course_id = e.micro_course_id
            JOIN pedagogy.micro_course_state s ON s.state_id = rt.current_state_id
            LEFT JOIN pedagogy.micro_course_module m ON m.module_id = s.module_id
            WHERE e.enrollment_id=:enrollment_id AND e.student_id=:student_id
        """),
            {"enrollment_id": str(enrollment_id), "student_id": str(student_id)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise MicroCourseNotFound("micro-course enrollment not found")
    result = dict(row)
    state_id = str(result["state_id"])
    result["current_state"] = {
        key: result.pop(key)
        for key in (
            "state_id", "state_key", "state_ordinal", "state_type", "state_title",
            "objective", "student_instruction", "estimated_seconds", "required",
            "module_id", "module_title",
        )
    }
    result["current_state"]["title"] = result["current_state"].pop("state_title")
    result["current_state"]["ordinal"] = result["current_state"].pop("state_ordinal")
    result["current_state"]["state_id"] = str(result["current_state"]["state_id"])
    result["current_state"]["module_id"] = (
        str(result["current_state"]["module_id"])
        if result["current_state"]["module_id"] is not None else None
    )
    result["current_state"]["assets"] = [
        dict(asset)
        for asset in conn.execute(
            text("""
            SELECT a.asset_id, a.uri, a.asset_kind, a.title, a.source_url, a.mime_type,
                   a.object_size_bytes, sa.presentation_role,
                   v.canonical_url AS video_url, v.duration_ms
            FROM pedagogy.micro_course_state_asset sa
            JOIN visual.asset a USING (asset_id)
            LEFT JOIN pedagogy.video_asset v
              ON v.visual_asset_id=a.asset_id AND v.review_status='APPROVED'
            WHERE sa.state_id=:state_id AND a.validation_status='VALID'
            ORDER BY sa.ordinal
        """),
            {"state_id": state_id},
        ).mappings()
    ]
    for asset in result["current_state"]["assets"]:
        asset["asset_id"] = str(asset["asset_id"])
        asset["private_object"] = str(asset["uri"]).startswith("object-store:")
        asset.pop("uri", None)
    result["current_state"]["interactions"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT i.interaction_instance_id, i.canonical_code, i.title,
                   i.instance_config, i.initial_state, i.learning_objective,
                   i.success_criteria, v.version AS template_version,
                   t.template_key, t.interaction_family, v.default_layout,
                   v.allowed_controls, v.allowed_icons, v.accessibility_policy,
                   scene.scene_json
            FROM pedagogy.micro_course_state_interaction si
            JOIN visual.interaction_instance i USING (interaction_instance_id)
            JOIN visual.interaction_template_version v USING (interaction_template_version_id)
            JOIN visual.interaction_template t USING (interaction_template_id)
            LEFT JOIN visual.scene_spec scene
              ON scene.scene_spec_id=i.scene_spec_id AND scene.status='APPROVED'
            WHERE si.state_id=:state_id AND i.review_status='APPROVED'
              AND v.status='PUBLISHED'
            ORDER BY si.ordinal
        """),
            {"state_id": state_id},
        ).mappings()
    ]
    for interaction in result["current_state"]["interactions"]:
        interaction["interaction_instance_id"] = str(interaction["interaction_instance_id"])
    result["current_state"]["activities"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT a.activity_id, a.activity_type, a.prompt, a.options,
                   a.correctness_policy, sa.ordinal, sa.purpose, sa.required
            FROM pedagogy.micro_course_state_activity sa
            JOIN activity.definition a USING (activity_id)
            WHERE sa.state_id=:state_id
            ORDER BY sa.ordinal
        """),
            {"state_id": state_id},
        ).mappings()
    ]
    for activity in result["current_state"]["activities"]:
        activity["activity_id"] = str(activity["activity_id"])
    answered_activity_responses = {
        row["activity_id"]: row["is_correct"]
        for row in conn.execute(
            text("""
            SELECT DISTINCT ON (payload->>'activity_id')
                   payload->>'activity_id' AS activity_id, (payload->>'is_correct')::boolean AS is_correct
            FROM learner.micro_course_state_event
            WHERE enrollment_id=:enrollment_id AND event_type='ACTIVITY_RESPONSE'
            ORDER BY payload->>'activity_id', created_at DESC
        """),
            {"enrollment_id": str(result["enrollment_id"])},
        ).mappings()
        if row["activity_id"] is not None
    }
    for activity in result["current_state"]["activities"]:
        if activity["activity_id"] in answered_activity_responses:
            activity["answered_correctly"] = answered_activity_responses[activity["activity_id"]]
    result["current_state"]["learning_items"] = [
        dict(item)
        for item in conn.execute(
            text("""
            SELECT li.learning_item_id, li.question_text, li.choices,
                   si.purpose, si.ordinal, si.required
            FROM pedagogy.micro_course_state_learning_item si
            JOIN pedagogy.learning_item li USING (learning_item_id)
            WHERE si.state_id=:state_id AND li.review_status='APPROVED'
              AND li.student_visible
            ORDER BY si.ordinal
        """),
            {"state_id": state_id},
        ).mappings()
    ]
    required_item_ids = {
        str(item["learning_item_id"])
        for item in result["current_state"]["learning_items"]
        if item["required"]
    }
    answered_item_ids = {
        str(item_id)
        for item_id in conn.execute(
            text("""
            SELECT DISTINCT payload->>'learning_item_id'
            FROM learner.micro_course_state_event
            WHERE enrollment_id=:enrollment_id AND event_type='QUIZ_RESPONSE'
        """),
            {"enrollment_id": str(result["enrollment_id"])},
        ).scalars()
        if item_id is not None
    }
    result["current_state"]["answered_learning_item_ids"] = sorted(
        answered_item_ids & {
            str(item["learning_item_id"])
            for item in result["current_state"]["learning_items"]
        }
    )
    assessment_complete = required_item_ids.issubset(answered_item_ids)
    result["current_state"]["transcript_segments"] = [
        dict(segment)
        for segment in conn.execute(
            text("""
            SELECT seg.segment_id, seg.start_ms, seg.end_ms, seg.transcript_text,
                   seg.speaker, seg.segment_index
            FROM pedagogy.micro_course_state_asset sa
            JOIN pedagogy.video_asset v ON v.visual_asset_id=sa.asset_id
            JOIN pedagogy.video_transcript t USING (video_asset_id)
            JOIN pedagogy.video_transcript_segment seg USING (transcript_id)
            WHERE sa.state_id=:state_id AND t.status='APPROVED'
              AND seg.review_status='APPROVED'
            ORDER BY seg.start_ms, seg.segment_index
        """),
            {"state_id": state_id},
        ).mappings()
    ]
    result["current_state"]["qa_contexts"] = [
        dict(context)
        for context in conn.execute(
            text("""
            SELECT context_type, question_pattern, approved_content
            FROM pedagogy.state_qa_context
            WHERE state_id=:state_id AND review_status='APPROVED'
            ORDER BY priority DESC
        """),
            {"state_id": state_id},
        ).mappings()
    ]
    outgoing = [
        dict(transition)
        for transition in conn.execute(
            text("""
            SELECT transition_id, transition_type, condition_type, priority
            FROM pedagogy.micro_course_transition
            WHERE release_id=:release_id AND from_state_id=:state_id
              AND review_status='APPROVED'
            ORDER BY priority, transition_id
        """),
            {"release_id": str(result["release_id"]), "state_id": state_id},
        ).mappings()
    ]
    result["can_continue"] = any(
        transition["condition_type"] == "ALWAYS"
        and transition["transition_type"] in {"NEXT", "USER_CONTINUE"}
        for transition in outgoing
    ) and assessment_complete
    result["can_go_back"] = any(
        transition["condition_type"] == "ALWAYS"
        and transition["transition_type"] == "USER_BACK"
        for transition in outgoing
    )
    result["can_finish"] = not outgoing and assessment_complete
    result["release_id"] = str(result["release_id"])
    result["enrollment_id"] = str(result["enrollment_id"])
    result["current_state"]["state_id"] = str(result["current_state"]["state_id"])
    return result


def submit_learning_item_response(
    conn, enrollment_id: str, student_id: str, learning_item_id: str, choice_index: int
) -> dict:
    """Grade a fixed, approved multiple-choice item attached to the active state."""
    runtime = (
        conn.execute(
            text("""
            SELECT e.status, e.release_id, rt.current_state_id
            FROM learner.micro_course_enrollment e
            JOIN tutor.micro_course_runtime rt USING (enrollment_id)
            WHERE e.enrollment_id=:enrollment_id AND e.student_id=:student_id
            FOR UPDATE OF e, rt
        """),
            {"enrollment_id": str(enrollment_id), "student_id": str(student_id)},
        )
        .mappings()
        .one_or_none()
    )
    if runtime is None:
        raise MicroCourseNotFound("micro-course enrollment not found")
    if runtime["status"] != "IN_PROGRESS":
        raise MicroCourseConflict("micro-course enrollment is not in progress")
    item = (
        conn.execute(
            text("""
            SELECT li.learning_item_id, li.choices, li.correct_answer, li.answer_or_solution_seed
            FROM pedagogy.micro_course_state_learning_item si
            JOIN pedagogy.learning_item li USING (learning_item_id)
            WHERE si.state_id=:state_id AND si.learning_item_id=:item_id
              AND li.review_status='APPROVED' AND li.student_visible
        """),
            {"state_id": str(runtime["current_state_id"]), "item_id": learning_item_id},
        )
        .mappings()
        .one_or_none()
    )
    if item is None:
        raise MicroCourseNotFound("approved learning item not found in the current lesson state")
    choices = item["choices"]
    if not isinstance(choices, list) or not item["correct_answer"]:
        raise MicroCourseConflict("learning item is not configured as a gradable multiple-choice question")
    if choice_index < 0 or choice_index >= len(choices):
        raise ValueError("choice_index is outside the available choices")
    is_correct = choices[choice_index] == item["correct_answer"]
    conn.execute(
        text("""
        INSERT INTO learner.micro_course_state_event (enrollment_id, state_id, event_type, payload)
        VALUES (:enrollment_id, :state_id, 'QUIZ_RESPONSE', CAST(:payload AS jsonb))
    """),
        {
            "enrollment_id": str(enrollment_id),
            "state_id": str(runtime["current_state_id"]),
            "payload": _json({
                "learning_item_id": str(item["learning_item_id"]),
                "choice_index": choice_index,
                "is_correct": is_correct,
            }),
        },
    )
    return {
        "learning_item_id": str(item["learning_item_id"]),
        "choice_index": choice_index,
        "is_correct": is_correct,
        "explanation": item["answer_or_solution_seed"],
    }


def submit_activity_response(
    conn,
    enrollment_id: str,
    student_id: str,
    activity_id: str,
    *,
    choice_index: int | None = None,
    value: float | None = None,
) -> dict:
    """Record (and self-grade) a response to a static preview-quiz activity
    (activity.definition, attached via attach_activity) anywhere in the student's
    enrolled release — not gated to the current state, since these questions are
    explicitly ungraded/optional and a learner may answer one after moving on.
    Unlike submit_learning_item_response, this never affects can_continue/mastery;
    it exists purely so quiz attempts are recorded for the learner and reviewers."""
    runtime = (
        conn.execute(
            text("""
            SELECT e.status, e.release_id
            FROM learner.micro_course_enrollment e
            WHERE e.enrollment_id=:enrollment_id AND e.student_id=:student_id
            FOR UPDATE OF e
        """),
            {"enrollment_id": str(enrollment_id), "student_id": str(student_id)},
        )
        .mappings()
        .one_or_none()
    )
    if runtime is None:
        raise MicroCourseNotFound("micro-course enrollment not found")
    if runtime["status"] != "IN_PROGRESS":
        raise MicroCourseConflict("micro-course enrollment is not in progress")
    activity = (
        conn.execute(
            text("""
            SELECT sa.state_id, a.activity_type, a.options, a.correctness_policy
            FROM pedagogy.micro_course_state_activity sa
            JOIN pedagogy.micro_course_state s USING (state_id)
            JOIN activity.definition a USING (activity_id)
            WHERE sa.activity_id=:activity_id AND s.release_id=:release_id
        """),
            {"activity_id": str(activity_id), "release_id": str(runtime["release_id"])},
        )
        .mappings()
        .one_or_none()
    )
    if activity is None:
        raise MicroCourseNotFound("quiz activity not found in this course release")
    policy = activity["correctness_policy"] or {}
    if activity["activity_type"] == "NUMERIC":
        if value is None:
            raise ValueError("value is required for a numeric quiz activity")
        correct_value = policy.get("correct_value")
        is_correct = correct_value is not None and abs(float(value) - float(correct_value)) < 1e-9
        response_payload = {"value": value}
    else:
        options = activity["options"] or []
        if choice_index is None:
            raise ValueError("choice_index is required for a multiple-choice quiz activity")
        if choice_index < 0 or choice_index >= len(options):
            raise ValueError("choice_index is outside the available options")
        is_correct = choice_index == policy.get("correct_index")
        response_payload = {"choice_index": choice_index}
    conn.execute(
        text("""
        INSERT INTO learner.micro_course_state_event (enrollment_id, state_id, event_type, payload)
        VALUES (:enrollment_id, :state_id, 'ACTIVITY_RESPONSE', CAST(:payload AS jsonb))
    """),
        {
            "enrollment_id": str(enrollment_id),
            "state_id": str(activity["state_id"]),
            "payload": _json({"activity_id": str(activity_id), "is_correct": is_correct, **response_payload}),
        },
    )
    return {
        "activity_id": str(activity_id),
        "is_correct": is_correct,
        "explanation": policy.get("explanation"),
    }


def record_interaction_event(
    conn,
    enrollment_id: str,
    student_id: str,
    interaction_instance_id: str,
    *,
    event_type: str,
    semantic_action: str,
    control_key: str | None = None,
    object_id: str | None = None,
    before_state: dict | None = None,
    action_payload: dict | None = None,
    after_state: dict | None = None,
) -> str:
    """Record one silent/implicit interaction-telemetry event — a slider settling, a
    matrix cell edit, a graph click — distinct from an explicit quiz attempt
    (requirements/44 §4.1, MCX-7). Writes learner.interaction_event (schema from
    migration 033, unwired until now) and enqueues a LEARNER_SIGNAL on the existing
    transactional outbox (pipeline.outbox_event) for later evaluation against
    pedagogy.misconception_evidence_rule. Evaluating that evidence and projecting it
    into Neo4j is a separate, not-yet-implemented outbox consumer (requirements/44 §4.2);
    this function only records and queues the raw signal."""
    enrollment = (
        conn.execute(
            text("""
            SELECT e.enrollment_id, e.status, rt.current_state_id
            FROM learner.micro_course_enrollment e
            JOIN tutor.micro_course_runtime rt USING (enrollment_id)
            WHERE e.enrollment_id=:enrollment_id AND e.student_id=:student_id
        """),
            {"enrollment_id": str(enrollment_id), "student_id": str(student_id)},
        )
        .mappings()
        .one_or_none()
    )
    if enrollment is None:
        raise MicroCourseNotFound("micro-course enrollment not found")
    if enrollment["status"] != "IN_PROGRESS":
        raise MicroCourseConflict("micro-course enrollment is not in progress")
    interaction_exists = conn.execute(
        text("SELECT 1 FROM visual.interaction_instance WHERE interaction_instance_id=:id"),
        {"id": str(interaction_instance_id)},
    ).scalar_one_or_none()
    if interaction_exists is None:
        raise MicroCourseNotFound("interaction instance not found")
    event_id = conn.execute(
        text("""
        INSERT INTO learner.interaction_event
            (student_id, enrollment_id, course_state_id, interaction_instance_id, event_type,
             semantic_action, control_key, object_id, before_state, action_payload, after_state)
        VALUES (:student_id, :enrollment_id, :state_id, :instance_id, :event_type, :semantic_action,
                :control_key, :object_id, CAST(:before AS jsonb), CAST(:payload AS jsonb), CAST(:after AS jsonb))
        RETURNING interaction_event_id
    """),
        {
            "student_id": str(student_id),
            "enrollment_id": str(enrollment_id),
            "state_id": str(enrollment["current_state_id"]),
            "instance_id": str(interaction_instance_id),
            "event_type": _required_text(event_type, "event_type").upper(),
            "semantic_action": _required_text(semantic_action, "semantic_action").upper(),
            "control_key": control_key,
            "object_id": object_id,
            "before": _json(before_state) if before_state is not None else None,
            "payload": _json(action_payload or {}),
            "after": _json(after_state) if after_state is not None else None,
        },
    ).scalar_one()
    conn.execute(
        text("""
        INSERT INTO pipeline.outbox_event (event_type, aggregate_type, aggregate_id, payload)
        VALUES ('LEARNER_SIGNAL', 'ENROLLMENT', :enrollment_id, CAST(:payload AS jsonb))
    """),
        {
            "enrollment_id": str(enrollment_id),
            "payload": _json({
                "interaction_event_id": str(event_id),
                "student_id": str(student_id),
                "interaction_instance_id": str(interaction_instance_id),
                "semantic_action": semantic_action.upper(),
                "action_payload": action_payload or {},
            }),
        },
    )
    return str(event_id)


def advance_enrollment(
    conn,
    enrollment_id: str,
    student_id: str,
    expected_state_version: int,
    action: str,
) -> dict:
    """Apply an approved unconditional transition using optimistic version checks."""
    normalized_action = _required_text(action, "action").upper()
    if normalized_action not in {"CONTINUE", "BACK"}:
        raise ValueError("action must be CONTINUE or BACK")
    runtime = (
        conn.execute(
            text("""
            SELECT e.status, e.release_id, rt.current_state_id, rt.state_version
            FROM learner.micro_course_enrollment e
            JOIN tutor.micro_course_runtime rt USING (enrollment_id)
            WHERE e.enrollment_id=:enrollment_id AND e.student_id=:student_id
            FOR UPDATE OF e, rt
        """),
            {"enrollment_id": str(enrollment_id), "student_id": str(student_id)},
        )
        .mappings()
        .one_or_none()
    )
    if runtime is None:
        raise MicroCourseNotFound("micro-course enrollment not found")
    if runtime["status"] != "IN_PROGRESS":
        raise MicroCourseConflict("micro-course enrollment is not in progress")
    if int(runtime["state_version"]) != expected_state_version:
        raise MicroCourseConflict("micro-course lesson changed; refresh before continuing")

    transition_types = ("NEXT", "USER_CONTINUE") if normalized_action == "CONTINUE" else ("USER_BACK",)
    transition = (
        conn.execute(
            text("""
            SELECT transition_id, to_state_id
            FROM pedagogy.micro_course_transition
            WHERE release_id=:release_id AND from_state_id=:state_id
              AND review_status='APPROVED' AND condition_type='ALWAYS'
              AND transition_type = ANY(:transition_types)
            ORDER BY priority, transition_id
            LIMIT 1
        """),
            {
                "release_id": str(runtime["release_id"]),
                "state_id": str(runtime["current_state_id"]),
                "transition_types": list(transition_types),
            },
        )
        .mappings()
        .one_or_none()
    )
    if transition is None:
        outgoing_count = conn.execute(
            text("""
            SELECT count(*) FROM pedagogy.micro_course_transition
            WHERE release_id=:release_id AND from_state_id=:state_id
              AND review_status='APPROVED'
        """),
            {
                "release_id": str(runtime["release_id"]),
                "state_id": str(runtime["current_state_id"]),
            },
        ).scalar_one()
        if normalized_action != "CONTINUE" or outgoing_count:
            raise MicroCourseConflict(f"no approved {normalized_action.lower()} transition from the current state")
        conn.execute(
            text("""
            UPDATE learner.micro_course_enrollment
            SET status='COMPLETED', completed_at=now()
            WHERE enrollment_id=:enrollment_id
        """),
            {"enrollment_id": str(enrollment_id)},
        )
        conn.execute(
            text("""
            UPDATE tutor.micro_course_runtime
            SET state_version=state_version+1, updated_at=now()
            WHERE enrollment_id=:enrollment_id
        """),
            {"enrollment_id": str(enrollment_id)},
        )
        event_type = "COMPLETED"
        to_state_id = runtime["current_state_id"]
    else:
        to_state_id = transition["to_state_id"]
        conn.execute(
            text("""
            UPDATE tutor.micro_course_runtime
            SET current_state_id=:state_id, state_version=state_version+1, updated_at=now()
            WHERE enrollment_id=:enrollment_id
        """),
            {"enrollment_id": str(enrollment_id), "state_id": str(to_state_id)},
        )
        event_type = "STATE_CHANGED"
    conn.execute(
        text("""
        INSERT INTO learner.micro_course_state_event (enrollment_id, state_id, event_type, payload)
        VALUES (:enrollment_id, :state_id, :event_type, CAST(:payload AS jsonb))
    """),
        {
            "enrollment_id": str(enrollment_id),
            "state_id": str(to_state_id),
            "event_type": event_type,
            "payload": _json({
                "action": normalized_action,
                "from_state_id": str(runtime["current_state_id"]),
                "to_state_id": str(to_state_id),
                "from_state_version": int(runtime["state_version"]),
            }),
        },
    )
    return get_enrollment_runtime(conn, enrollment_id, student_id)


def get_course(conn, canonical_code: str) -> dict:
    course = (
        conn.execute(
            text("""
            SELECT micro_course_id, canonical_code, title, description, metadata, estimated_minutes,
                   difficulty_level, created_by, created_at, updated_at,
                   is_active, deactivated_at, deactivated_by
            FROM pedagogy.micro_course WHERE canonical_code=:code
        """),
            {"code": _required_text(canonical_code, "canonical_code")},
        )
        .mappings()
        .one_or_none()
    )
    if course is None:
        raise MicroCourseNotFound("micro-course not found")
    course = dict(course)
    course["targets"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT target_type, concept_id, technique_id, skill_id, role, ordinal
            FROM pedagogy.micro_course_target WHERE micro_course_id=:id
            ORDER BY role, ordinal
        """),
            {"id": str(course["micro_course_id"])},
        ).mappings()
    ]
    course["releases"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT release_id, version, parent_release_id, status, created_by, created_at,
                   published_at
            FROM pedagogy.micro_course_release
            WHERE micro_course_id=:id ORDER BY version DESC
        """),
            {"id": str(course["micro_course_id"])},
        ).mappings()
    ]
    return course


def deactivate_course(conn, canonical_code: str, actor: str) -> dict:
    """Hide a course from the student catalog without touching release history/immutability
    (requirements/43 AMC-4). Works regardless of release status — deactivation is a course-level
    concern, independent of whether a release is DRAFT/PUBLISHED/SUPERSEDED/RETIRED."""
    actor = _required_text(actor, "actor")
    course = conn.execute(
        text("SELECT micro_course_id, is_active FROM pedagogy.micro_course WHERE canonical_code=:code FOR UPDATE"),
        {"code": _required_text(canonical_code, "canonical_code")},
    ).mappings().one_or_none()
    if course is None:
        raise MicroCourseNotFound("micro-course not found")
    if not course["is_active"]:
        raise MicroCourseConflict("course is already deactivated")
    conn.execute(
        text("""
        UPDATE pedagogy.micro_course
        SET is_active=false, deactivated_at=now(), deactivated_by=:actor
        WHERE micro_course_id=:id
    """),
        {"id": str(course["micro_course_id"]), "actor": actor},
    )
    record_audit_event(
        conn, "ADMIN", actor, "COURSE_DEACTIVATED", "MICRO_COURSE", str(course["micro_course_id"]),
        before_state={"is_active": True}, after_state={"is_active": False},
    )
    return {"canonical_code": canonical_code, "is_active": False}


def reactivate_course(conn, canonical_code: str, actor: str) -> dict:
    actor = _required_text(actor, "actor")
    course = conn.execute(
        text("SELECT micro_course_id, is_active FROM pedagogy.micro_course WHERE canonical_code=:code FOR UPDATE"),
        {"code": _required_text(canonical_code, "canonical_code")},
    ).mappings().one_or_none()
    if course is None:
        raise MicroCourseNotFound("micro-course not found")
    if course["is_active"]:
        raise MicroCourseConflict("course is already active")
    conn.execute(
        text("""
        UPDATE pedagogy.micro_course
        SET is_active=true, deactivated_at=NULL, deactivated_by=NULL
        WHERE micro_course_id=:id
    """),
        {"id": str(course["micro_course_id"])},
    )
    record_audit_event(
        conn, "ADMIN", actor, "COURSE_REACTIVATED", "MICRO_COURSE", str(course["micro_course_id"]),
        before_state={"is_active": False}, after_state={"is_active": True},
    )
    return {"canonical_code": canonical_code, "is_active": True}


def get_release(conn, release_id: str) -> dict:
    release = (
        conn.execute(
            text("""
            SELECT r.release_id, r.micro_course_id, c.canonical_code, c.title AS course_title,
                   r.version, r.parent_release_id, r.status, r.learning_objectives,
                   r.prerequisite_summary, r.agent_policy, r.content_hash,
                   r.created_by, r.created_at, r.reviewed_by, r.reviewed_at,
                   r.approved_by, r.approved_at, r.published_at
            FROM pedagogy.micro_course_release r
            JOIN pedagogy.micro_course c USING (micro_course_id)
            WHERE r.release_id=:id
        """),
            {"id": str(release_id)},
        )
        .mappings()
        .one_or_none()
    )
    if release is None:
        raise MicroCourseNotFound("micro-course release not found")
    result = dict(release)
    result["modules"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT module_id, module_key, ordinal, title, objective, estimated_seconds, required
            FROM pedagogy.micro_course_module WHERE release_id=:id ORDER BY ordinal
        """),
            {"id": str(release_id)},
        ).mappings()
    ]
    result["states"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT state_id, module_id, state_key, ordinal, state_type, title, objective,
                   student_instruction, estimated_seconds, required, skippable, agent_policy
            FROM pedagogy.micro_course_state WHERE release_id=:id ORDER BY ordinal
        """),
            {"id": str(release_id)},
        ).mappings()
    ]
    result["transitions"] = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT transition_id, from_state_id, to_state_id, transition_type, condition_type,
                   condition_payload, priority, review_status
            FROM pedagogy.micro_course_transition WHERE release_id=:id
            ORDER BY from_state_id, priority
        """),
            {"id": str(release_id)},
        ).mappings()
    ]
    for state in result["states"]:
        state_id = str(state["state_id"])
        bindings = {}
        for target_type, (table, id_column) in STATE_BINDINGS.items():
            bindings[target_type.lower()] = [
                dict(row)
                for row in conn.execute(
                    text(f"""
                    SELECT {id_column} AS target_id, role
                    FROM {table} WHERE state_id=:id ORDER BY {id_column}, role
                """),
                    {"id": state_id},
                ).mappings()
            ]
        state["bindings"] = bindings
        state["interactions"] = [
            dict(row)
            for row in conn.execute(
                text("""
                SELECT i.interaction_instance_id, i.canonical_code, i.title,
                       i.review_status, t.template_key, v.version AS template_version,
                       v.status AS template_status, si.ordinal, si.required
                FROM pedagogy.micro_course_state_interaction si
                JOIN visual.interaction_instance i USING (interaction_instance_id)
                JOIN visual.interaction_template_version v USING (interaction_template_version_id)
                JOIN visual.interaction_template t USING (interaction_template_id)
                WHERE si.state_id=:state_id ORDER BY si.ordinal
            """),
                {"state_id": state_id},
            ).mappings()
        ]
        state["assets"] = [
            dict(row)
            for row in conn.execute(
                text("""
                SELECT a.asset_id, a.title, a.mime_type, a.asset_kind, a.object_size_bytes,
                       a.validation_status, sa.ordinal, sa.presentation_role
                FROM pedagogy.micro_course_state_asset sa
                JOIN visual.asset a USING (asset_id)
                WHERE sa.state_id=:state_id ORDER BY sa.ordinal
            """),
                {"state_id": state_id},
            ).mappings()
        ]
        state["activities"] = [
            dict(row)
            for row in conn.execute(
                text("""
                SELECT a.activity_id, a.activity_type, a.prompt, a.options,
                       a.correctness_policy, sa.ordinal, sa.purpose, sa.required
                FROM pedagogy.micro_course_state_activity sa
                JOIN activity.definition a USING (activity_id)
                WHERE sa.state_id=:state_id ORDER BY sa.ordinal
            """),
                {"state_id": state_id},
            ).mappings()
        ]
        for activity in state["activities"]:
            activity["activity_id"] = str(activity["activity_id"])
    return result


def _release_states_snapshot(conn, release_id: str) -> dict[str, dict]:
    rows = conn.execute(
        text("""
        SELECT state_key, ordinal, state_type, title, required, skippable
        FROM pedagogy.micro_course_state WHERE release_id=:id
    """),
        {"id": str(release_id)},
    ).mappings()
    return {row["state_key"]: dict(row) for row in rows}


def _release_state_interactions_snapshot(conn, release_id: str) -> dict[str, set[str]]:
    rows = conn.execute(
        text("""
        SELECT s.state_key, i.canonical_code AS interaction_code
        FROM pedagogy.micro_course_state_interaction si
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN visual.interaction_instance i USING (interaction_instance_id)
        WHERE s.release_id=:id
    """),
        {"id": str(release_id)},
    ).mappings()
    result: dict[str, set[str]] = {}
    for row in rows:
        result.setdefault(row["state_key"], set()).add(row["interaction_code"])
    return result


def diff_releases(conn, release_id_a: str, release_id_b: str) -> dict:
    """Field-level summary of what differs between two releases of the same
    micro-course (requirements/43 AMC-6) — enough to answer "what would change if I
    publish this draft," not a full line-level content diff. Course-level targets are
    intentionally not compared: pedagogy.micro_course_target is keyed by micro_course_id,
    not release_id, so they are identical across every release of the same course by
    construction."""
    rows = conn.execute(
        text("""
        SELECT release_id, micro_course_id, version FROM pedagogy.micro_course_release
        WHERE release_id = ANY(:ids)
    """),
        {"ids": [str(release_id_a), str(release_id_b)]},
    ).mappings().all()
    by_id = {str(row["release_id"]): row for row in rows}
    if str(release_id_a) not in by_id or str(release_id_b) not in by_id:
        raise MicroCourseNotFound("one or both releases not found")
    if by_id[str(release_id_a)]["micro_course_id"] != by_id[str(release_id_b)]["micro_course_id"]:
        raise ValueError("both releases must belong to the same micro-course")

    states_a = _release_states_snapshot(conn, release_id_a)
    states_b = _release_states_snapshot(conn, release_id_b)
    states_added = sorted(set(states_b) - set(states_a))
    states_removed = sorted(set(states_a) - set(states_b))
    states_changed = [
        {"state_key": key, "before": states_a[key], "after": states_b[key]}
        for key in sorted(set(states_a) & set(states_b))
        if states_a[key] != states_b[key]
    ]

    interactions_a = _release_state_interactions_snapshot(conn, release_id_a)
    interactions_b = _release_state_interactions_snapshot(conn, release_id_b)
    interaction_changes = []
    for key in sorted(set(interactions_a) | set(interactions_b)):
        before = interactions_a.get(key, set())
        after = interactions_b.get(key, set())
        if before != after:
            interaction_changes.append({
                "state_key": key,
                "added": sorted(after - before),
                "removed": sorted(before - after),
            })

    metadata_a = conn.execute(
        text("""
        SELECT c.title, c.description, c.estimated_minutes, c.difficulty_level
        FROM pedagogy.micro_course c JOIN pedagogy.micro_course_release r USING (micro_course_id)
        WHERE r.release_id=:id
    """),
        {"id": str(release_id_a)},
    ).mappings().one()
    metadata_b = conn.execute(
        text("""
        SELECT c.title, c.description, c.estimated_minutes, c.difficulty_level
        FROM pedagogy.micro_course c JOIN pedagogy.micro_course_release r USING (micro_course_id)
        WHERE r.release_id=:id
    """),
        {"id": str(release_id_b)},
    ).mappings().one()

    return {
        "release_a": {"release_id": str(release_id_a), "version": by_id[str(release_id_a)]["version"]},
        "release_b": {"release_id": str(release_id_b), "version": by_id[str(release_id_b)]["version"]},
        "metadata_changed": dict(metadata_a) != dict(metadata_b),
        "states_added": states_added,
        "states_removed": states_removed,
        "states_changed": states_changed,
        "interaction_changes": interaction_changes,
    }


def create_course(
    conn,
    canonical_code: str,
    title: str,
    created_by: str,
    targets: list[dict],
    *,
    description: str | None = None,
    estimated_minutes: int | None = None,
    difficulty_level: int | None = None,
    metadata: dict | None = None,
) -> str:
    code = _required_text(canonical_code, "canonical_code")
    title = _required_text(title, "title")
    creator = _required_text(created_by, "created_by")
    if not targets:
        raise ValueError("at least one existing canonical target is required")
    if not any(target.get("role", "PRIMARY").upper() == "PRIMARY" for target in targets):
        raise ValueError("at least one PRIMARY canonical target is required")

    normalized_targets = []
    for ordinal, target in enumerate(targets):
        target_type = str(target["target_type"]).upper()
        if target_type not in TARGETS:
            raise ValueError(f"unsupported course target type: {target_type}")
        target_type, id_column = _canonical_target(conn, target["target_type"], target["target_id"])
        role = target.get("role", "PRIMARY").upper()
        if role not in {"PRIMARY", "SECONDARY", "PREREQUISITE"}:
            raise ValueError(f"unsupported target role: {role}")
        normalized_targets.append((target_type, id_column, str(target["target_id"]), role, ordinal))

    course_id = conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course
            (canonical_code, title, description, estimated_minutes, difficulty_level, created_by, metadata)
        VALUES (:code, :title, :description, :minutes, :difficulty, :creator, CAST(:metadata AS jsonb))
        RETURNING micro_course_id
    """),
        {
            "code": code,
            "title": title,
            "description": description,
            "minutes": estimated_minutes,
            "difficulty": difficulty_level,
            "creator": creator,
            "metadata": _json(metadata or {}),
        },
    ).scalar_one()
    for target_type, id_column, target_id, role, ordinal in normalized_targets:
        conn.execute(
            text(f"""
            INSERT INTO pedagogy.micro_course_target
                (micro_course_id, target_type, {id_column}, role, ordinal)
            VALUES (:course_id, :target_type, :target_id, :role, :ordinal)
        """),
            {
                "course_id": str(course_id),
                "target_type": target_type,
                "target_id": target_id,
                "role": role,
                "ordinal": ordinal,
            },
        )
    record_audit_event(
        conn, "ADMIN", creator, "COURSE_CREATED", "MICRO_COURSE", str(course_id),
        after_state={"canonical_code": code, "title": title},
    )
    return str(course_id)


def create_release(
    conn, canonical_code: str, created_by: str, parent_release_id: str | None = None
) -> str:
    course = conn.execute(
        text("""
        SELECT micro_course_id FROM pedagogy.micro_course
        WHERE canonical_code=:code FOR UPDATE
    """),
        {"code": _required_text(canonical_code, "canonical_code")},
    ).scalar_one_or_none()
    if course is None:
        raise MicroCourseNotFound("micro-course not found")
    if parent_release_id is not None:
        parent = conn.execute(
            text("""
            SELECT 1 FROM pedagogy.micro_course_release
            WHERE release_id=:release_id AND micro_course_id=:course_id
        """),
            {"release_id": str(parent_release_id), "course_id": str(course)},
        ).scalar_one_or_none()
        if parent is None:
            raise ValueError("parent release does not belong to this micro-course")
    version = conn.execute(
        text("""
        SELECT COALESCE(max(version), 0) + 1
        FROM pedagogy.micro_course_release WHERE micro_course_id=:course_id
    """),
        {"course_id": str(course)},
    ).scalar_one()
    release_id = conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_release
            (micro_course_id, version, parent_release_id, created_by, agent_policy)
        VALUES (:course_id, :version, :parent, :creator, CAST(:policy AS jsonb))
        RETURNING release_id
    """),
        {
            "course_id": str(course),
            "version": version,
            "parent": str(parent_release_id) if parent_release_id else None,
            "creator": _required_text(created_by, "created_by"),
            "policy": _json(DEFAULT_AGENT_POLICY),
        },
    ).scalar_one()
    return str(release_id)


def add_module(
    conn,
    release_id: str,
    module_key: str,
    ordinal: int,
    title: str,
    *,
    objective: str | None = None,
    estimated_seconds: int | None = None,
    required: bool = True,
) -> str:
    _editable_release(conn, release_id)
    module_id = conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_module
            (release_id, module_key, ordinal, title, objective, estimated_seconds, required)
        VALUES (:release_id, :key, :ordinal, :title, :objective, :seconds, :required)
        RETURNING module_id
    """),
        {
            "release_id": str(release_id),
            "key": _required_text(module_key, "module_key"),
            "ordinal": ordinal,
            "title": _required_text(title, "title"),
            "objective": objective,
            "seconds": estimated_seconds,
            "required": required,
        },
    ).scalar_one()
    return str(module_id)


def add_state(
    conn,
    release_id: str,
    state_key: str,
    ordinal: int,
    state_type: str,
    title: str,
    *,
    module_id: str | None = None,
    objective: str | None = None,
    student_instruction: str | None = None,
    estimated_seconds: int | None = None,
    required: bool = True,
    skippable: bool = False,
    agent_policy: dict | None = None,
) -> str:
    _editable_release(conn, release_id)
    if module_id is not None:
        belongs = conn.execute(
            text("""
            SELECT 1 FROM pedagogy.micro_course_module
            WHERE module_id=:module_id AND release_id=:release_id
        """),
            {"module_id": str(module_id), "release_id": str(release_id)},
        ).scalar_one_or_none()
        if belongs is None:
            raise ValueError("module does not belong to this release")
    state_id = conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_state
            (release_id, module_id, state_key, ordinal, state_type, title, objective,
             student_instruction, estimated_seconds, required, skippable, agent_policy)
        VALUES (:release_id, :module_id, :key, :ordinal, :type, :title, :objective,
                :instruction, :seconds, :required, :skippable, CAST(:policy AS jsonb))
        RETURNING state_id
    """),
        {
            "release_id": str(release_id),
            "module_id": str(module_id) if module_id else None,
            "key": _required_text(state_key, "state_key"),
            "ordinal": ordinal,
            "type": _required_text(state_type, "state_type").upper(),
            "title": _required_text(title, "title"),
            "objective": objective,
            "instruction": student_instruction,
            "seconds": estimated_seconds,
            "required": required,
            "skippable": skippable,
            "policy": _json(agent_policy or {}),
        },
    ).scalar_one()
    return str(state_id)


def bind_state_target(
    conn,
    state_id: str,
    target_type: str,
    target_id: str,
    role: str,
    *,
    importance: float | None = None,
    required_level: int | None = None,
) -> None:
    state = conn.execute(
        text("""
        SELECT state_id, release_id FROM pedagogy.micro_course_state WHERE state_id=:id
    """),
        {"id": str(state_id)},
    ).mappings().one_or_none()
    if state is None:
        raise MicroCourseNotFound("micro-course state not found")
    _editable_release(conn, str(state["release_id"]))
    target_type, _ = _canonical_target(conn, target_type, target_id)
    table, binding_column = STATE_BINDINGS[target_type]
    params = {"state_id": str(state_id), "target_id": str(target_id), "role": role.upper()}
    if target_type in {"CONCEPT", "TECHNIQUE"}:
        conn.execute(
            text(f"""
            INSERT INTO {table} (state_id, {binding_column}, role, importance)
            VALUES (:state_id, :target_id, :role, :importance)
        """),
            {**params, "importance": importance},
        )
    elif target_type == "SKILL":
        conn.execute(
            text(f"""
            INSERT INTO {table} (state_id, {binding_column}, role, required_level)
            VALUES (:state_id, :target_id, :role, :required_level)
        """),
            {**params, "required_level": required_level},
        )
    else:
        conn.execute(
            text(f"""
            INSERT INTO {table} (state_id, {binding_column}, role)
            VALUES (:state_id, :target_id, :role)
        """),
            params,
        )


def add_transition(
    conn,
    release_id: str,
    from_state_id: str,
    to_state_id: str,
    transition_type: str,
    *,
    condition_type: str = "ALWAYS",
    condition_payload: dict | None = None,
    priority: int = 0,
) -> str:
    _editable_release(conn, release_id)
    endpoint_count = conn.execute(
        text("""
        SELECT count(*) FROM pedagogy.micro_course_state
        WHERE release_id=:release_id AND state_id IN (:from_id, :to_id)
    """),
        {
            "release_id": str(release_id),
            "from_id": str(from_state_id),
            "to_id": str(to_state_id),
        },
    ).scalar_one()
    transition_type = _required_text(transition_type, "transition_type").upper()
    if endpoint_count != (1 if str(from_state_id) == str(to_state_id) else 2):
        raise ValueError("both transition states must belong to this release")
    if str(from_state_id) == str(to_state_id) and transition_type != "RETRY":
        raise ValueError("self-transitions are permitted only for RETRY")
    transition_id = conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_transition
            (release_id, from_state_id, to_state_id, transition_type, condition_type,
             condition_payload, priority)
        VALUES (:release_id, :from_id, :to_id, :type, :condition, CAST(:payload AS jsonb), :priority)
        RETURNING transition_id
    """),
        {
            "release_id": str(release_id),
            "from_id": str(from_state_id),
            "to_id": str(to_state_id),
            "type": transition_type,
            "condition": _required_text(condition_type, "condition_type").upper(),
            "payload": _json(condition_payload or {}),
            "priority": priority,
        },
    ).scalar_one()
    return str(transition_id)


def attach_asset(
    conn, state_id: str, asset_id: str, ordinal: int, presentation_role: str
) -> None:
    state = conn.execute(
        text("SELECT release_id FROM pedagogy.micro_course_state WHERE state_id=:id"),
        {"id": str(state_id)},
    ).scalar_one_or_none()
    if state is None:
        raise MicroCourseNotFound("micro-course state not found")
    _editable_release(conn, str(state))
    conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_state_asset
            (state_id, asset_id, ordinal, presentation_role)
        VALUES (:state_id, :asset_id, :ordinal, :role)
    """),
        {
            "state_id": str(state_id),
            "asset_id": str(asset_id),
            "ordinal": ordinal,
            "role": _required_text(presentation_role, "presentation_role").upper(),
        },
    )


def register_uploaded_asset(
    conn,
    state_id: str,
    object_key: str,
    mime_type: str,
    content_hash: str,
    object_size_bytes: int,
    title: str,
    asset_kind: str,
    presentation_role: str,
    reviewer: str,
    rights_note: str | None = None,
) -> str:
    state = conn.execute(
        text("SELECT release_id FROM pedagogy.micro_course_state WHERE state_id=:id"),
        {"id": str(state_id)},
    ).scalar_one_or_none()
    if state is None:
        raise MicroCourseNotFound("micro-course state not found")
    _editable_release(conn, str(state))
    asset_id = conn.execute(
        text("""
        INSERT INTO visual.asset
            (uri, mime_type, content_hash, object_size_bytes, created_by_agent,
             persistence_mode, validation_status, asset_kind, title, rights_note,
             reviewed_by, reviewed_at)
        VALUES (:uri, :mime_type, :hash, :size, 'micro-course-admin-api',
                'STATIC', 'VALID', :kind, :title, :rights, :reviewer, now())
        RETURNING asset_id
    """),
        {
            "uri": f"object-store:{object_key}",
            "mime_type": mime_type,
            "hash": content_hash,
            "size": object_size_bytes,
            "kind": asset_kind,
            "title": _required_text(title, "title"),
            "reviewer": _required_text(reviewer, "reviewer"),
            "rights": rights_note,
        },
    ).scalar_one()
    conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_state_asset
            (state_id, asset_id, ordinal, presentation_role)
        VALUES (:state, :asset, COALESCE(
            (SELECT max(ordinal) + 1 FROM pedagogy.micro_course_state_asset WHERE state_id=:state), 0
        ), :role)
    """),
        {
            "state": str(state_id),
            "asset": str(asset_id),
            "role": _required_text(presentation_role, "presentation_role").upper(),
        },
    )
    return str(asset_id)


def get_course_activity(conn, canonical_code: str) -> dict:
    """Live aggregate enrollment/quiz-attempt stats for a course's currently published
    release (requirements/43 AMC-7). A live query, not a rollup table: the admin Activity
    tab's volume today does not need a scheduled rollup (see requirements/44 §4.3's
    "live query is a valid default for low-latency-non-critical cases"); if/when volume
    grows, this function's query becomes the seed for a future rollup consumer without
    changing its return shape."""
    course = conn.execute(
        text("""
        SELECT c.micro_course_id, r.release_id, r.version
        FROM pedagogy.micro_course c
        JOIN pedagogy.micro_course_release r
          ON r.micro_course_id=c.micro_course_id AND r.status='PUBLISHED'
        WHERE c.canonical_code=:code
    """),
        {"code": _required_text(canonical_code, "canonical_code")},
    ).mappings().one_or_none()
    if course is None:
        raise MicroCourseNotFound("published micro-course not found")
    release_id = str(course["release_id"])

    counts = conn.execute(
        text("""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE status='IN_PROGRESS') AS in_progress,
               count(*) FILTER (WHERE status='COMPLETED') AS completed
        FROM learner.micro_course_enrollment WHERE release_id=:id
    """),
        {"id": release_id},
    ).mappings().one()
    total = counts["total"] or 0
    completed = counts["completed"] or 0

    funnel = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT s.state_id, s.state_key, s.ordinal, s.title,
                   count(DISTINCT ev.enrollment_id) AS reached_count
            FROM pedagogy.micro_course_state s
            LEFT JOIN learner.micro_course_state_event ev
              ON ev.state_id=s.state_id AND ev.event_type IN ('ENROLLED','STATE_CHANGED')
            WHERE s.release_id=:id
            GROUP BY s.state_id, s.state_key, s.ordinal, s.title
            ORDER BY s.ordinal
        """),
            {"id": release_id},
        ).mappings()
    ]
    for step in funnel:
        step["state_id"] = str(step["state_id"])

    quiz_accuracy = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT a.activity_id, a.prompt, s.state_key,
                   count(ev.event_id) AS attempts,
                   count(ev.event_id) FILTER (WHERE (ev.payload->>'is_correct')::boolean) AS correct
            FROM pedagogy.micro_course_state_activity sa
            JOIN pedagogy.micro_course_state s USING (state_id)
            JOIN activity.definition a USING (activity_id)
            LEFT JOIN learner.micro_course_state_event ev
              ON ev.event_type='ACTIVITY_RESPONSE'
             AND ev.payload->>'activity_id' = a.activity_id::text
             AND ev.enrollment_id IN (SELECT enrollment_id FROM learner.micro_course_enrollment WHERE release_id=:id)
            WHERE s.release_id=:id
            GROUP BY a.activity_id, a.prompt, s.state_key, s.ordinal, sa.ordinal
            ORDER BY s.ordinal, sa.ordinal
        """),
            {"id": release_id},
        ).mappings()
    ]
    for item in quiz_accuracy:
        item["activity_id"] = str(item["activity_id"])

    recent_events = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT ev.event_id, ev.event_type, ev.created_at, s.title AS state_title,
                   COALESCE(NULLIF(trim(concat(left(p.first_name,1), left(p.last_name,1))), ''), '??') AS student_initials
            FROM learner.micro_course_state_event ev
            JOIN learner.micro_course_enrollment e USING (enrollment_id)
            JOIN learner.student_profile p USING (student_id)
            LEFT JOIN pedagogy.micro_course_state s ON s.state_id=ev.state_id
            WHERE e.release_id=:id
            ORDER BY ev.created_at DESC LIMIT 25
        """),
            {"id": release_id},
        ).mappings()
    ]
    for event in recent_events:
        event["event_id"] = str(event["event_id"])

    return {
        "canonical_code": canonical_code,
        "release_id": release_id,
        "version": course["version"],
        "total_enrollments": total,
        "in_progress": counts["in_progress"] or 0,
        "completed": completed,
        "completion_rate": round(completed / total, 4) if total else None,
        "step_funnel": funnel,
        "quiz_accuracy": quiz_accuracy,
        "recent_activity": recent_events,
    }


def get_published_asset(conn, canonical_code: str, asset_id: str) -> dict:
    asset = conn.execute(
        text("""
        SELECT a.uri, a.mime_type, a.content_hash, a.object_size_bytes
        FROM pedagogy.micro_course c
        JOIN pedagogy.micro_course_release r
          ON r.micro_course_id=c.micro_course_id AND r.status='PUBLISHED'
        JOIN pedagogy.micro_course_state s USING (release_id)
        JOIN pedagogy.micro_course_state_asset sa USING (state_id)
        JOIN visual.asset a USING (asset_id)
        WHERE c.canonical_code=:code AND a.asset_id=:asset_id
          AND a.validation_status='VALID'
    """),
        {"code": _required_text(canonical_code, "canonical_code"), "asset_id": str(asset_id)},
    ).mappings().one_or_none()
    if asset is None:
        raise MicroCourseNotFound("published course asset not found")
    if not asset["uri"].startswith("object-store:"):
        raise MicroCourseConflict("course asset is not stored in the private object store")
    return {
        "object_key": asset["uri"].removeprefix("object-store:"),
        "mime_type": asset["mime_type"],
        "content_hash": asset["content_hash"],
        "object_size_bytes": asset["object_size_bytes"],
    }


def list_approved_interactions(conn, limit: int = 100) -> list[dict]:
    if limit < 1 or limit > 250:
        raise ValueError("limit must be 1..250")
    return [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT i.interaction_instance_id, i.canonical_code, i.title,
                   i.learning_objective, v.version AS template_version,
                   t.template_key, t.interaction_family
            FROM visual.interaction_instance i
            JOIN visual.interaction_template_version v USING (interaction_template_version_id)
            JOIN visual.interaction_template t USING (interaction_template_id)
            WHERE i.review_status='APPROVED' AND v.status='PUBLISHED'
            ORDER BY t.template_key, i.title, i.canonical_code
            LIMIT :limit
        """),
            {"limit": limit},
        ).mappings()
    ]


def get_widget_library(conn) -> dict:
    """Browsable interaction-template/control/icon/animation catalog for the admin
    Widgets tab (requirements/43 AMC-8). Templates include every version's status so a
    DRAFT version can be shown as "not yet attachable" rather than hidden entirely."""
    templates = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT t.interaction_template_id, t.template_key, t.interaction_family, t.status,
                   v.interaction_template_version_id, v.version, v.status AS version_status
            FROM visual.interaction_template t
            JOIN visual.interaction_template_version v USING (interaction_template_id)
            ORDER BY t.template_key, v.version
        """)
        ).mappings()
    ]
    for template in templates:
        template["interaction_template_id"] = str(template["interaction_template_id"])
        template["interaction_template_version_id"] = str(template["interaction_template_version_id"])
    controls = [
        dict(row)
        for row in conn.execute(
            text("SELECT control_key, control_type, status FROM visual.control_template ORDER BY control_key")
        ).mappings()
    ]
    icons = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT token_key, icon_class, accessible_label, status
            FROM visual.icon_token ORDER BY token_key
        """)
        ).mappings()
    ]
    animations = [
        dict(row)
        for row in conn.execute(
            text("SELECT animation_key, name, status FROM visual.animation_template ORDER BY animation_key")
        ).mappings()
    ]
    return {"templates": templates, "controls": controls, "icons": icons, "animations": animations}


def attach_interaction(
    conn, state_id: str, interaction_instance_id: str, ordinal: int, required: bool = True
) -> None:
    state = conn.execute(
        text("SELECT release_id FROM pedagogy.micro_course_state WHERE state_id=:id"),
        {"id": str(state_id)},
    ).scalar_one_or_none()
    if state is None:
        raise MicroCourseNotFound("micro-course state not found")
    _editable_release(conn, str(state))
    approved_instance = conn.execute(
        text("""
        SELECT 1
        FROM visual.interaction_instance i
        JOIN visual.interaction_template_version v USING (interaction_template_version_id)
        WHERE i.interaction_instance_id=:instance_id
          AND i.review_status='APPROVED' AND v.status='PUBLISHED'
    """),
        {"instance_id": str(interaction_instance_id)},
    ).scalar_one_or_none()
    if approved_instance is None:
        raise ValueError("course states may use only approved instances with published templates")
    conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_state_interaction
            (state_id, interaction_instance_id, ordinal, required)
        VALUES (:state_id, :instance_id, :ordinal, :required)
    """),
        {
            "state_id": str(state_id),
            "instance_id": str(interaction_instance_id),
            "ordinal": ordinal,
            "required": required,
        },
    )


def attach_learning_item(
    conn,
    state_id: str,
    learning_item_id: str,
    ordinal: int,
    purpose: str,
    *,
    required: bool = True,
) -> None:
    state = conn.execute(
        text("SELECT release_id FROM pedagogy.micro_course_state WHERE state_id=:id"),
        {"id": str(state_id)},
    ).scalar_one_or_none()
    if state is None:
        raise MicroCourseNotFound("micro-course state not found")
    _editable_release(conn, str(state))
    item_status = conn.execute(
        text("""
        SELECT review_status, student_visible FROM pedagogy.learning_item
        WHERE learning_item_id=:id
    """),
        {"id": learning_item_id},
    ).mappings().one_or_none()
    if item_status is None:
        raise MicroCourseNotFound("learning item not found")
    if item_status["review_status"] != "APPROVED" or not item_status["student_visible"]:
        raise ValueError("micro-course learning items must be approved and student-visible")
    conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_state_learning_item
            (state_id, learning_item_id, ordinal, purpose, required)
        VALUES (:state_id, :item_id, :ordinal, :purpose, :required)
    """),
        {
            "state_id": str(state_id),
            "item_id": _required_text(learning_item_id, "learning_item_id"),
            "ordinal": ordinal,
            "purpose": _required_text(purpose, "purpose").upper(),
            "required": required,
        },
    )


def attach_activity(
    conn,
    state_id: str,
    activity_id: str,
    ordinal: int,
    purpose: str,
    *,
    required: bool = True,
) -> None:
    state = conn.execute(
        text("SELECT release_id FROM pedagogy.micro_course_state WHERE state_id=:id"),
        {"id": str(state_id)},
    ).scalar_one_or_none()
    if state is None:
        raise MicroCourseNotFound("micro-course state not found")
    _editable_release(conn, str(state))
    activity = (
        conn.execute(
            text("""
            SELECT source_type, persistence_mode FROM activity.definition WHERE activity_id=:id
        """),
            {"id": str(activity_id)},
        )
        .mappings()
        .one_or_none()
    )
    if activity is None:
        raise MicroCourseNotFound("activity definition not found")
    if activity["source_type"] not in {"PRECOMPILED", "INSTRUCTOR_CREATED"}:
        raise ValueError("micro-course activities must be precompiled or instructor-created")
    if activity["persistence_mode"] != "STATIC":
        raise ValueError("micro-course activities must use STATIC persistence")
    conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_state_activity
            (state_id, activity_id, ordinal, purpose, required)
        VALUES (:state_id, :activity_id, :ordinal, :purpose, :required)
    """),
        {
            "state_id": str(state_id),
            "activity_id": str(activity_id),
            "ordinal": ordinal,
            "purpose": _required_text(purpose, "purpose").upper(),
            "required": required,
        },
    )


def create_intervention(
    conn,
    release_id: str,
    canonical_code: str,
    name: str,
    entry_state_id: str,
    *,
    target_type: str,
    target_id: str,
) -> str:
    _editable_release(conn, release_id)
    target_type, _ = _canonical_target(conn, target_type, target_id)
    target_columns = {
        "MISCONCEPTION": "target_misconception_id",
        "SKILL": "target_skill_id",
        "TECHNIQUE": "target_technique_id",
    }
    if target_type not in target_columns:
        raise ValueError("interventions target a misconception, skill, or technique")
    entry_belongs = conn.execute(
        text("""
        SELECT 1 FROM pedagogy.micro_course_state
        WHERE state_id=:state_id AND release_id=:release_id
    """),
        {"state_id": str(entry_state_id), "release_id": str(release_id)},
    ).scalar_one_or_none()
    if entry_belongs is None:
        raise ValueError("intervention entry state does not belong to this release")
    intervention_id = conn.execute(
        text(f"""
        INSERT INTO pedagogy.intervention_script
            (release_id, canonical_code, name, {target_columns[target_type]}, entry_state_id)
        VALUES (:release_id, :code, :name, :target_id, :entry_state_id)
        RETURNING intervention_id
    """),
        {
            "release_id": str(release_id),
            "code": _required_text(canonical_code, "canonical_code"),
            "name": _required_text(name, "name"),
            "target_id": str(target_id),
            "entry_state_id": str(entry_state_id),
        },
    ).scalar_one()
    return str(intervention_id)


def add_intervention_step(
    conn,
    release_id: str,
    intervention_id: str,
    ordinal: int,
    step_type: str,
    *,
    prompt_text: str | None = None,
    asset_id: str | None = None,
    learning_item_id: str | None = None,
    activity_id: str | None = None,
    expected_response_type: str | None = None,
) -> str:
    _editable_release(conn, release_id)
    belongs = conn.execute(
        text("""
        SELECT 1 FROM pedagogy.intervention_script
        WHERE intervention_id=:id AND release_id=:release_id
    """),
        {"id": str(intervention_id), "release_id": str(release_id)},
    ).scalar_one_or_none()
    if belongs is None:
        raise ValueError("intervention does not belong to this release")
    step_id = conn.execute(
        text("""
        INSERT INTO pedagogy.intervention_step
            (intervention_id, ordinal, step_type, prompt_text, asset_id, learning_item_id,
             activity_id, expected_response_type)
        VALUES (:intervention_id, :ordinal, :type, :prompt, :asset_id, :item_id,
                :activity_id, :response_type)
        RETURNING intervention_step_id
    """),
        {
            "intervention_id": str(intervention_id),
            "ordinal": ordinal,
            "type": _required_text(step_type, "step_type").upper(),
            "prompt": prompt_text,
            "asset_id": str(asset_id) if asset_id else None,
            "item_id": learning_item_id,
            "activity_id": str(activity_id) if activity_id else None,
            "response_type": expected_response_type,
        },
    ).scalar_one()
    return str(step_id)


def validate_release(
    conn, release_id: str, *, require_approved_children: bool = False
) -> list[str]:
    release = (
        conn.execute(
            text("""
            SELECT r.release_id, r.status, r.agent_policy, c.micro_course_id,
                   c.canonical_code
            FROM pedagogy.micro_course_release r
            JOIN pedagogy.micro_course c USING (micro_course_id)
            WHERE r.release_id=:id
        """),
            {"id": str(release_id)},
        )
        .mappings()
        .one_or_none()
    )
    if release is None:
        return ["micro-course release not found"]

    errors: list[str] = []
    primary_target = conn.execute(
        text("""
        SELECT 1 FROM pedagogy.micro_course_target
        WHERE micro_course_id=:id AND role='PRIMARY' LIMIT 1
    """),
        {"id": str(release["micro_course_id"])},
    ).scalar_one_or_none()
    if primary_target is None:
        errors.append("course has no PRIMARY canonical target")

    states = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT state_id, state_key, ordinal, required, state_type, module_id, agent_policy
            FROM pedagogy.micro_course_state
            WHERE release_id=:id ORDER BY ordinal, state_id
        """),
            {"id": str(release_id)},
        ).mappings()
    ]
    transitions = [
        dict(row)
        for row in conn.execute(
            text("""
            SELECT transition_id, from_state_id, to_state_id
            FROM pedagogy.micro_course_transition WHERE release_id=:id
        """),
            {"id": str(release_id)},
        ).mappings()
    ]
    errors.extend(validate_state_graph(states, transitions))

    required_assets = conn.execute(
        text("""
        SELECT DISTINCT s.state_key
        FROM pedagogy.micro_course_state_asset sa
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN visual.asset a USING (asset_id)
        WHERE s.release_id=:id AND s.required
          AND sa.presentation_role<>'OPTIONAL'
          AND a.validation_status<>'VALID'
    """),
        {"id": str(release_id)},
    ).scalars().all()
    errors.extend(f"required state {key} uses an asset that is not VALID" for key in required_assets)

    bad_modules = conn.execute(
        text("""
        SELECT s.state_key FROM pedagogy.micro_course_state s
        JOIN pedagogy.micro_course_module m ON m.module_id=s.module_id
        WHERE s.release_id=:id AND m.release_id<>s.release_id
    """),
        {"id": str(release_id)},
    ).scalars().all()
    errors.extend(f"state {key} references a module from another release" for key in bad_modules)

    required_video_ids = [
        str(state["state_id"])
        for state in states
        if state["required"] and state["state_type"] == "VIDEO"
    ]
    for state_id in required_video_ids:
        approved_video = conn.execute(
            text("""
            SELECT 1
            FROM pedagogy.micro_course_state_asset sa
            JOIN pedagogy.video_asset v ON v.visual_asset_id=sa.asset_id
            JOIN visual.asset a ON a.asset_id=sa.asset_id
            WHERE sa.state_id=:state_id AND v.review_status='APPROVED'
              AND a.validation_status='VALID'
            LIMIT 1
        """),
            {"state_id": state_id},
        ).scalar_one_or_none()
        if approved_video is None:
            errors.append(f"required video state {state_id} has no approved valid video asset")
            continue
        approved_transcript = conn.execute(
            text("""
            SELECT 1 FROM pedagogy.micro_course_state_asset sa
            JOIN pedagogy.video_asset v ON v.visual_asset_id=sa.asset_id
            JOIN pedagogy.video_transcript t USING (video_asset_id)
            JOIN pedagogy.video_transcript_segment s USING (transcript_id)
            WHERE sa.state_id=:state_id AND t.status='APPROVED'
              AND s.review_status='APPROVED'
            LIMIT 1
        """),
            {"state_id": state_id},
        ).scalar_one_or_none()
        if approved_transcript is None:
            errors.append(f"required video state {state_id} has no approved transcript segment")

    for state in states:
        if not state["required"]:
            continue
        state_policy = state.get("agent_policy") or {}
        for flag in FORBIDDEN_POLICY_FLAGS:
            if state_policy.get(flag) is True:
                errors.append(
                    f"state {state['state_key']} agent policy forbids {flag}=true"
                )
        if state["state_type"] in {"QUIZ", "CHECKPOINT", "DIAGNOSTIC"}:
            has_learning_item = conn.execute(
                text("""
                SELECT 1 FROM pedagogy.micro_course_state_learning_item
                WHERE state_id=:id AND required LIMIT 1
            """),
                {"id": str(state["state_id"])},
            ).scalar_one_or_none()
            if has_learning_item is None:
                errors.append(f"required {state['state_type'].lower()} state {state['state_key']} has no required learning item")

    bad_misconceptions = conn.execute(
        text("""
        SELECT DISTINCT m.canonical_code
        FROM pedagogy.micro_course_state_misconception b
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN knowledge.misconception m USING (misconception_id)
        WHERE s.release_id=:id AND m.review_status<>'APPROVED'
    """),
        {"id": str(release_id)},
    ).scalars().all()
    errors.extend(f"misconception {code} is not approved" for code in bad_misconceptions)

    invalid_activities = conn.execute(
        text("""
        SELECT DISTINCT a.activity_id
        FROM pedagogy.micro_course_state_activity sa
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN activity.definition a USING (activity_id)
        WHERE s.release_id=:id
          AND (a.source_type NOT IN ('PRECOMPILED','INSTRUCTOR_CREATED')
               OR a.persistence_mode<>'STATIC')
    """),
        {"id": str(release_id)},
    ).scalars().all()
    if invalid_activities:
        errors.append(f"{len(invalid_activities)} attached activity definition(s) are not static and approved-source")

    intervention_rows = conn.execute(
        text("""
        SELECT i.canonical_code, i.review_status, i.target_misconception_id,
               i.entry_state_id
        FROM pedagogy.intervention_script i
        WHERE i.release_id=:id
    """),
        {"id": str(release_id)},
    ).mappings()
    for intervention in intervention_rows:
        code = intervention["canonical_code"]
        if require_approved_children and intervention["review_status"] != "APPROVED":
            errors.append(f"intervention {code} is not approved")
        if intervention["target_misconception_id"] is not None:
            misconception_status = conn.execute(
                text("""
                SELECT review_status FROM knowledge.misconception
                WHERE misconception_id=:id
            """),
                {"id": str(intervention["target_misconception_id"])},
            ).scalar_one_or_none()
            if misconception_status != "APPROVED":
                errors.append(f"intervention {code} targets an unapproved misconception")
        entry_belongs = conn.execute(
            text("""
            SELECT 1 FROM pedagogy.micro_course_state
            WHERE state_id=:state_id AND release_id=:release_id
        """),
            {"state_id": str(intervention["entry_state_id"]), "release_id": str(release_id)},
        ).scalar_one_or_none()
        if entry_belongs is None:
            errors.append(f"intervention {code} entry state is outside this release")
        final_step = conn.execute(
            text("""
            SELECT step_type FROM pedagogy.intervention_step
            WHERE intervention_id=(
                SELECT intervention_id FROM pedagogy.intervention_script
                WHERE release_id=:release_id AND canonical_code=:code
            )
            ORDER BY ordinal DESC LIMIT 1
        """),
            {"release_id": str(release_id), "code": code},
        ).scalar_one_or_none()
        if final_step != "RETURN":
            errors.append(f"intervention {code} must end with a RETURN step")

    pending_contexts = conn.execute(
        text("""
        SELECT count(*) FROM pedagogy.state_qa_context q
        JOIN pedagogy.micro_course_state s USING (state_id)
        WHERE s.release_id=:id AND q.review_status<>'APPROVED'
    """),
        {"id": str(release_id)},
    ).scalar_one()
    if require_approved_children and pending_contexts:
        errors.append(f"{pending_contexts} state Q&A context(s) are not approved")

    pending_transitions = conn.execute(
        text("""
        SELECT count(*) FROM pedagogy.micro_course_transition
        WHERE release_id=:id AND review_status<>'APPROVED'
    """),
        {"id": str(release_id)},
    ).scalar_one()
    if require_approved_children and pending_transitions:
        errors.append(f"{pending_transitions} transition(s) are not approved")
    pending_markers = conn.execute(
        text("""
        SELECT count(*) FROM pedagogy.video_timeline_marker m
        JOIN pedagogy.micro_course_state s USING (state_id)
        WHERE s.release_id=:id AND m.review_status<>'APPROVED'
    """),
        {"id": str(release_id)},
    ).scalar_one()
    if require_approved_children and pending_markers:
        errors.append(f"{pending_markers} video timeline marker(s) are not approved")
    invalid_learning_items = conn.execute(
        text("""
        SELECT count(*) FROM pedagogy.micro_course_state_learning_item si
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN pedagogy.learning_item li USING (learning_item_id)
        WHERE s.release_id=:id AND si.required
          AND (li.review_status<>'APPROVED' OR NOT li.student_visible)
    """),
        {"id": str(release_id)},
    ).scalar_one()
    if invalid_learning_items:
        errors.append(
            f"{invalid_learning_items} required learning item(s) are not approved and student-visible"
        )

    unapproved_interactions = conn.execute(
        text("""
        SELECT s.state_key, i.canonical_code
        FROM pedagogy.micro_course_state_interaction si
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN visual.interaction_instance i USING (interaction_instance_id)
        JOIN visual.interaction_template_version v USING (interaction_template_version_id)
        WHERE s.release_id=:id
          AND (i.review_status<>'APPROVED' OR v.status<>'PUBLISHED')
        ORDER BY s.ordinal, si.ordinal
    """),
        {"id": str(release_id)},
    ).mappings()
    errors.extend(
        f"state {row['state_key']} interaction {row['canonical_code']} is not approved with a published template"
        for row in unapproved_interactions
    )

    errors.extend(
        _policy_errors(release["agent_policy"], "release", require_explicit=True)
    )

    return errors


def review_release(
    conn, release_id: str, status: str, reviewer: str, note: str | None = None
) -> dict:
    normalized_status = _required_text(status, "status").upper()
    if normalized_status not in {"APPROVED", "NEEDS_REVISION", "REJECTED"}:
        raise ValueError("review status must be APPROVED, NEEDS_REVISION, or REJECTED")
    reviewer = _required_text(reviewer, "reviewer")
    release = (
        conn.execute(
            text("""
            SELECT release_id, status AS release_status FROM pedagogy.micro_course_release
            WHERE release_id=:id FOR UPDATE
        """),
            {"id": str(release_id)},
        )
        .mappings()
        .one_or_none()
    )
    if release is None:
        raise MicroCourseNotFound("micro-course release not found")
    if release["release_status"] not in {"DRAFT", "REVIEWED"}:
        raise MicroCourseConflict("only DRAFT or REVIEWED releases can be reviewed")
    if normalized_status == "APPROVED":
        errors = validate_release(conn, release_id)
        if errors:
            return {"status": "REJECTED", "errors": errors}
        conn.execute(
            text("""
            UPDATE pedagogy.micro_course_transition
            SET review_status='APPROVED'
            WHERE release_id=:id AND review_status='PENDING_REVIEW'
        """),
            {"id": str(release_id)},
        )
        conn.execute(
            text("""
            UPDATE pedagogy.intervention_script
            SET review_status='APPROVED'
            WHERE release_id=:id AND review_status='PENDING_REVIEW'
        """),
            {"id": str(release_id)},
        )
        conn.execute(
            text("""
            UPDATE pedagogy.state_qa_context q
            SET review_status='APPROVED'
            FROM pedagogy.micro_course_state s
            WHERE q.state_id=s.state_id AND s.release_id=:id
              AND q.review_status='PENDING_REVIEW'
        """),
            {"id": str(release_id)},
        )
        conn.execute(
            text("""
            UPDATE pedagogy.video_timeline_marker m
            SET review_status='APPROVED'
            FROM pedagogy.micro_course_state s
            WHERE m.state_id=s.state_id AND s.release_id=:id
              AND m.review_status='PENDING_REVIEW'
        """),
            {"id": str(release_id)},
        )
    conn.execute(
        text("""
        INSERT INTO pedagogy.micro_course_review (release_id, status, note, reviewed_by)
        VALUES (:id, :status, :note, :reviewer)
    """),
        {
            "id": str(release_id),
            "status": normalized_status,
            "note": note,
            "reviewer": reviewer,
        },
    )
    release_status = "APPROVED" if normalized_status == "APPROVED" else "DRAFT"
    conn.execute(
        text("""
        UPDATE pedagogy.micro_course_release
        SET status=:status, reviewed_by=:reviewer, reviewed_at=now(),
            approved_by=CASE WHEN :status='APPROVED' THEN :reviewer ELSE NULL END,
            approved_at=CASE WHEN :status='APPROVED' THEN now() ELSE NULL END
        WHERE release_id=:id
    """),
        {"id": str(release_id), "status": release_status, "reviewer": reviewer},
    )
    record_audit_event(
        conn, "ADMIN", reviewer, f"RELEASE_REVIEW_{normalized_status}", "MICRO_COURSE_RELEASE",
        str(release_id), after_state={"status": normalized_status, "note": note},
    )
    return {"status": normalized_status, "errors": []}


def _content_hash(conn, release_id: str) -> str:
    snapshot: dict[str, list[dict]] = {}
    table_queries = {
        "course": "SELECT c.canonical_code, c.title, c.description, c.metadata, c.estimated_minutes, c.difficulty_level FROM pedagogy.micro_course c JOIN pedagogy.micro_course_release r USING (micro_course_id) WHERE r.release_id=:id",
        "release": "SELECT learning_objectives, prerequisite_summary, agent_policy FROM pedagogy.micro_course_release WHERE release_id=:id",
        "targets": "SELECT target_type, concept_id, technique_id, skill_id, role, ordinal FROM pedagogy.micro_course_target WHERE micro_course_id=(SELECT micro_course_id FROM pedagogy.micro_course_release WHERE release_id=:id) ORDER BY role, ordinal, target_type",
        "modules": "SELECT module_key, ordinal, title, objective, estimated_seconds, required FROM pedagogy.micro_course_module WHERE release_id=:id ORDER BY ordinal, module_key",
        "states": "SELECT state_key, ordinal, state_type, title, objective, student_instruction, required, skippable, agent_policy FROM pedagogy.micro_course_state WHERE release_id=:id ORDER BY ordinal, state_key",
        "interactions": "SELECT s.state_key, si.ordinal, si.required, i.canonical_code, i.interaction_template_version_id, i.instance_config, i.initial_state, i.success_criteria, i.content_hash, i.review_status FROM pedagogy.micro_course_state_interaction si JOIN pedagogy.micro_course_state s USING (state_id) JOIN visual.interaction_instance i USING (interaction_instance_id) WHERE s.release_id=:id ORDER BY s.ordinal, si.ordinal",
        "concept_bindings": "SELECT s.state_key, b.concept_id, b.role, b.importance FROM pedagogy.micro_course_state_concept b JOIN pedagogy.micro_course_state s USING (state_id) WHERE s.release_id=:id ORDER BY s.ordinal, b.concept_id, b.role",
        "technique_bindings": "SELECT s.state_key, b.technique_id, b.role, b.importance FROM pedagogy.micro_course_state_technique b JOIN pedagogy.micro_course_state s USING (state_id) WHERE s.release_id=:id ORDER BY s.ordinal, b.technique_id, b.role",
        "skill_bindings": "SELECT s.state_key, b.skill_id, b.role, b.required_level FROM pedagogy.micro_course_state_skill b JOIN pedagogy.micro_course_state s USING (state_id) WHERE s.release_id=:id ORDER BY s.ordinal, b.skill_id, b.role",
        "misconception_bindings": "SELECT s.state_key, b.misconception_id, b.role FROM pedagogy.micro_course_state_misconception b JOIN pedagogy.micro_course_state s USING (state_id) WHERE s.release_id=:id ORDER BY s.ordinal, b.misconception_id, b.role",
        "assets": "SELECT s.state_key, a.uri, a.mime_type, a.content_hash, a.object_size_bytes, a.asset_kind, a.title, a.source_url, a.rights_note, sa.ordinal, sa.presentation_role, v.provider, v.external_video_id, v.canonical_url, v.title AS video_title FROM pedagogy.micro_course_state_asset sa JOIN pedagogy.micro_course_state s USING (state_id) JOIN visual.asset a USING (asset_id) LEFT JOIN pedagogy.video_asset v ON v.visual_asset_id=a.asset_id WHERE s.release_id=:id ORDER BY s.ordinal, sa.ordinal",
        "transcripts": "SELECT s.state_key, v.external_video_id, t.version, t.language_code, t.source_type, t.content_hash, t.status, seg.segment_index, seg.start_ms, seg.end_ms, seg.transcript_text, seg.speaker, seg.segment_hash, seg.review_status FROM pedagogy.micro_course_state_asset sa JOIN pedagogy.micro_course_state s USING (state_id) JOIN pedagogy.video_asset v ON v.visual_asset_id=sa.asset_id JOIN pedagogy.video_transcript t USING (video_asset_id) JOIN pedagogy.video_transcript_segment seg USING (transcript_id) WHERE s.release_id=:id ORDER BY s.ordinal, t.version, seg.segment_index",
        "learning_items": "SELECT s.state_key, li.learning_item_id, li.question_text, li.choices, li.correct_answer, li.answer_or_solution_seed, li.review_status, li.student_visible, si.ordinal, si.purpose, si.required FROM pedagogy.micro_course_state_learning_item si JOIN pedagogy.micro_course_state s USING (state_id) JOIN pedagogy.learning_item li USING (learning_item_id) WHERE s.release_id=:id ORDER BY s.ordinal, si.ordinal",
        "activities": "SELECT s.state_key, a.activity_id, a.activity_type, a.prompt, a.options, a.correctness_policy, a.source_type, a.persistence_mode, sa.ordinal, sa.purpose, sa.required FROM pedagogy.micro_course_state_activity sa JOIN pedagogy.micro_course_state s USING (state_id) JOIN activity.definition a USING (activity_id) WHERE s.release_id=:id ORDER BY s.ordinal, sa.ordinal",
        "qa_contexts": "SELECT s.state_key, q.context_type, q.question_pattern, q.approved_content, q.concept_id, q.technique_id, q.skill_id, q.misconception_id, q.priority, q.review_status FROM pedagogy.state_qa_context q JOIN pedagogy.micro_course_state s USING (state_id) WHERE s.release_id=:id ORDER BY s.ordinal, q.priority, q.qa_context_id",
        "transitions": "SELECT from_state_id, to_state_id, transition_type, condition_type, condition_payload, priority FROM pedagogy.micro_course_transition WHERE release_id=:id ORDER BY from_state_id, priority, transition_id",
        "timeline_markers": "SELECT s.state_key, v.external_video_id, m.timestamp_ms, m.marker_type, m.learning_item_id, m.activity_id, m.intervention_id, m.note, m.review_status FROM pedagogy.video_timeline_marker m JOIN pedagogy.micro_course_state s USING (state_id) JOIN pedagogy.video_asset v USING (video_asset_id) WHERE s.release_id=:id ORDER BY s.ordinal, m.timestamp_ms, m.marker_id",
        "interventions": "SELECT canonical_code, name, target_misconception_id, target_skill_id, target_technique_id, entry_state_id, review_status FROM pedagogy.intervention_script WHERE release_id=:id ORDER BY canonical_code",
        "intervention_steps": "SELECT i.canonical_code, st.ordinal, st.step_type, st.prompt_text, st.asset_id, st.learning_item_id, st.activity_id, st.expected_response_type FROM pedagogy.intervention_step st JOIN pedagogy.intervention_script i USING (intervention_id) WHERE i.release_id=:id ORDER BY i.canonical_code, st.ordinal",
    }
    for name, query in table_queries.items():
        rows = conn.execute(text(query), {"id": str(release_id)}).mappings()
        snapshot[name] = [dict(row) for row in rows]
    return hashlib.sha256(_json(snapshot).encode("utf-8")).hexdigest()


def publish_release(conn, release_id: str, publisher: str) -> dict:
    publisher = _required_text(publisher, "publisher")
    release = (
        conn.execute(
            text("""
            SELECT r.release_id, r.micro_course_id, r.status, r.version
            FROM pedagogy.micro_course_release r
            WHERE r.release_id=:id FOR UPDATE
        """),
            {"id": str(release_id)},
        )
        .mappings()
        .one_or_none()
    )
    if release is None:
        raise MicroCourseNotFound("micro-course release not found")
    if release["status"] != "APPROVED":
        raise MicroCourseConflict("release must be APPROVED before publishing")
    latest_review = conn.execute(
        text("""
        SELECT status FROM pedagogy.micro_course_review
        WHERE release_id=:id ORDER BY reviewed_at DESC, review_id DESC LIMIT 1
    """),
        {"id": str(release_id)},
    ).scalar_one_or_none()
    if latest_review != "APPROVED":
        raise MicroCourseConflict("release has no current APPROVED review")
    errors = validate_release(conn, release_id, require_approved_children=True)
    if errors:
        return {"status": "REJECTED", "errors": errors}

    previous = conn.execute(
        text("""
        SELECT release_id FROM pedagogy.micro_course_release
        WHERE micro_course_id=:course_id AND status='PUBLISHED' FOR UPDATE
    """),
        {"course_id": str(release["micro_course_id"])},
    ).scalar_one_or_none()
    if previous is not None:
        conn.execute(
            text("""
            UPDATE pedagogy.micro_course_release SET status='SUPERSEDED'
            WHERE release_id=:id
        """),
            {"id": str(previous)},
        )

    content_hash = _content_hash(conn, release_id)
    conn.execute(
        text("""
        UPDATE pedagogy.micro_course_release
        SET status='PUBLISHED', published_at=now(), content_hash=:hash,
            approved_by=COALESCE(approved_by, :publisher),
            approved_at=COALESCE(approved_at, now())
        WHERE release_id=:id
    """),
        {"id": str(release_id), "hash": content_hash, "publisher": publisher},
    )
    conn.execute(
        text("""
        INSERT INTO pipeline.outbox_event (event_type, aggregate_type, aggregate_id, payload)
        VALUES ('MICRO_COURSE_PUBLISHED', 'COURSE_RELEASE', :id,
                CAST(:payload AS jsonb))
    """),
        {
            "id": str(release_id),
            "payload": _json(
                {
                    "release_id": str(release_id),
                    "micro_course_id": str(release["micro_course_id"]),
                    "version": release["version"],
                    "content_hash": content_hash,
                }
            ),
        },
    )
    record_audit_event(
        conn, "ADMIN", publisher, "RELEASE_PUBLISHED", "MICRO_COURSE_RELEASE", str(release_id),
        after_state={"version": release["version"], "content_hash": content_hash},
    )
    return {
        "status": "PUBLISHED",
        "release_id": str(release_id),
        "content_hash": content_hash,
        "projection": "PENDING",
    }
