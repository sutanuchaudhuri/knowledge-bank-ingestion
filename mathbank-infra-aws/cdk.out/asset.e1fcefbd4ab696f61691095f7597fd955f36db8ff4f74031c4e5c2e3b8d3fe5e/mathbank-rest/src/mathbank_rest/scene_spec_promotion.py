"""Promotes an ephemeral Manim Video Studio render job (requirements/60) into the
canonical, versioned `visual.scene_spec` catalog (requirements/41 ITL-1/ITL-4).

Mathbank-manim-studio is treated as a genuine peer service here, not a sibling Python
package: this module calls its REST API (list candidates, fetch the rendered video,
mark-promoted) rather than reading `studio.*` tables directly, even though both services
share one physical Postgres instance — the same "call the REST API, don't import the
sibling's code" boundary already established for mathbank-mcp-competitions
(requirements/49).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.engine import Connection

from mathbank_rest import object_store
from mathbank_rest.config import settings
from mathbank_rest.db.postgres import engine


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _content_hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


class PromotionError(ValueError):
    pass


def list_promotable_candidates(conn: Connection) -> list[dict]:
    """DONE, unpromoted render jobs from the Manim Video Studio, enriched with whether
    mathbank-rest's own catalog already has a scene_spec for that job (a stronger,
    local idempotency check than trusting the peer service's own flag alone)."""
    response = httpx.get(
        f"{settings.manim_studio_base_url}/v1/render-jobs",
        params={"status": "DONE", "unpromoted_only": True},
        timeout=10,
    )
    response.raise_for_status()
    candidates = response.json()
    job_ids = [c["id"] for c in candidates]
    already_promoted: set[str] = set()
    if job_ids:
        rows = conn.execute(
            text("SELECT source_studio_job_id FROM visual.scene_spec "
                 "WHERE source_studio_job_id = ANY(:ids)"),
            {"ids": job_ids},
        ).scalars().all()
        already_promoted = set(rows)
    return [c for c in candidates if c["id"] not in already_promoted]


def promote_render_job(*, render_job_id: str, canonical_code: str, created_by: str) -> str:
    """Fetches the render job + its video from mathbank-manim-studio, inserts a new DRAFT
    `visual.scene_spec` row (+ a `visual.asset` row for the video), and tells the peer
    service the job is now promoted. Returns the new scene_spec_id.

    Idempotent: if this exact (render_job_id) was already promoted, raises PromotionError
    instead of creating a duplicate catalog row.

    Deliberately owns its own `engine.begin()` transaction rather than accepting an
    external `conn` (unlike every other function in this module) — see GOTCHAS.md: the
    local INSERT must actually be COMMITTED before the mark-promoted HTTP call fires,
    since mathbank-manim-studio's own database connection cannot see an uncommitted row
    from a different service's open transaction, and its `promoted_scene_spec_id` column
    has a real foreign key into `visual.scene_spec` that would otherwise fail."""
    with engine.begin() as conn:
        already = conn.execute(
            text("SELECT scene_spec_id FROM visual.scene_spec WHERE source_studio_job_id = :id"),
            {"id": render_job_id},
        ).scalar_one_or_none()
        if already is not None:
            raise PromotionError(f"render job {render_job_id} was already promoted as {already}")

        job_response = httpx.get(
            f"{settings.manim_studio_base_url}/v1/render-jobs/{render_job_id}", timeout=10
        )
        if job_response.status_code == 404:
            raise PromotionError("render job not found in the Manim Video Studio")
        job_response.raise_for_status()
        job = job_response.json()
        if job["status"] != "DONE":
            raise PromotionError(f"render job is {job['status']}, not DONE")
        scene_spec_json = job["scene_spec_json"]
        if not scene_spec_json:
            raise PromotionError("render job has no scene_spec_json")

        video_response = httpx.get(
            f"{settings.manim_studio_base_url}/v1/render-jobs/{render_job_id}/video", timeout=30
        )
        video_response.raise_for_status()
        stored = object_store.put_bytes(video_response.content, "mp4")

        next_version = conn.execute(
            text("SELECT COALESCE(MAX(version), 0) + 1 FROM visual.scene_spec "
                 "WHERE canonical_code = :code"),
            {"code": canonical_code},
        ).scalar_one()

        asset_id = conn.execute(
            text("""
                INSERT INTO visual.asset
                    (uri, mime_type, content_hash, asset_kind, created_by_agent,
                     persistence_mode, validation_status, object_size_bytes)
                VALUES (:uri, 'video/mp4', :content_hash, 'MANIM_VIDEO', :created_by,
                        'STATIC', 'PENDING', :size_bytes)
                RETURNING asset_id
            """),
            {
                "uri": f"object-store:{stored['object_key']}",
                "content_hash": stored["sha256"],
                "created_by": created_by,
                "size_bytes": stored["size_bytes"],
            },
        ).scalar_one()

        scene_spec_id = conn.execute(
            text("""
                INSERT INTO visual.scene_spec
                    (canonical_code, version, scene_schema_version, scene_json, content_hash,
                     created_by, rendered_video_asset_id, source_studio_job_id)
                VALUES (:code, :version, 'v1', :scene_json, :content_hash, :created_by,
                        :asset_id, :job_id)
                RETURNING scene_spec_id
            """),
            {
                "code": canonical_code,
                "version": next_version,
                "scene_json": _json(scene_spec_json),
                "content_hash": _content_hash(scene_spec_json),
                "created_by": created_by,
                "asset_id": asset_id,
                "job_id": render_job_id,
            },
        ).scalar_one()
    # `with engine.begin()` has now committed — only past this point is the new
    # scene_spec_id visible to mathbank-manim-studio's own, separate connection.

    try:
        httpx.post(
            f"{settings.manim_studio_base_url}/v1/render-jobs/{render_job_id}/mark-promoted",
            json={"scene_spec_id": str(scene_spec_id)},
            headers={"X-Admin-Api-Key": settings.admin_api_key},
            timeout=10,
        ).raise_for_status()
    except httpx.HTTPError:
        # Best-effort: mathbank-rest's own source_studio_job_id check above is the
        # authoritative idempotency guard; the peer service's own flag is only used for
        # its own candidate-list UX, so a failure here does not need to fail promotion.
        pass

    return str(scene_spec_id)


def approve_scene_and_validate_asset(conn: Connection, scene_spec_id: str, approved_by: str
                                      ) -> None:
    """Approving a scene is the one explicit human judgment that the rendered video is
    actually fine to show real students — so it also flips the linked `visual.asset`'s
    `validation_status` from 'PENDING' to 'VALID' in the same step (that flag is what
    `micro_course_service.get_published_asset` requires before a student can stream it;
    leaving it PENDING forever would silently 404 every approved scene's video)."""
    conn.execute(
        text("""
            UPDATE visual.asset SET validation_status = 'VALID', reviewed_by = :reviewed_by,
                   reviewed_at = now()
            WHERE asset_id = (
                SELECT rendered_video_asset_id FROM visual.scene_spec WHERE scene_spec_id = :id
            )
        """),
        {"id": scene_spec_id, "reviewed_by": approved_by},
    )


# --- requirements/60 §7 continued: a minimal, generic "watch this explainer video"
# interaction template, so a promoted-and-approved scene can become a real
# `visual.interaction_instance` attachable to a published micro-course state through the
# *existing* `attach_interaction`/ContentTab machinery (requirements/40/43) — no new
# course-binding code needed, since that machinery is already template-agnostic. ---------

_VIDEO_EXPLAINER_TEMPLATE_KEY = "VIDEO_EXPLAINER_V1"


def _ensure_video_explainer_template(conn: Connection, created_by: str) -> str:
    """Idempotently creates (or returns the existing) PUBLISHED template version for
    passive explainer-video interactions. Uses the real, already-seeded `VIDEO_TIMELINE`
    control and `VIDEO`/`PLAY`/`PAUSE`/`COMPLETE` icons (visual.control_template/
    icon_token) — this vocabulary existed in the catalog before this feature but had no
    template using it yet."""
    existing = conn.execute(
        text("""
            SELECT v.interaction_template_version_id
            FROM visual.interaction_template_version v
            JOIN visual.interaction_template t USING (interaction_template_id)
            WHERE t.template_key = :key AND v.status = 'PUBLISHED'
            ORDER BY v.version DESC LIMIT 1
        """),
        {"key": _VIDEO_EXPLAINER_TEMPLATE_KEY},
    ).scalar_one_or_none()
    if existing is not None:
        return str(existing)

    template_id = conn.execute(
        text("""
            INSERT INTO visual.interaction_template (template_key, name, interaction_family, description)
            VALUES (:key, 'Explainer video', 'VIDEO_EXPLAINER', :description)
            ON CONFLICT (template_key) DO UPDATE SET template_key = EXCLUDED.template_key
            RETURNING interaction_template_id
        """),
        {
            "key": _VIDEO_EXPLAINER_TEMPLATE_KEY,
            "description": (
                "A single rendered Manim explainer video (requirements/60) played to the "
                "student with no manipulable controls; completion is a watch-to-end event, "
                "not a graded answer."
            ),
        },
    ).scalar_one()

    input_schema = {"type": "object", "properties": {}}
    state_schema = {
        "type": "object", "required": ["watched"],
        "properties": {"watched": {"type": "boolean"}},
    }
    event_schema = {
        "type": "object", "required": ["event_type"],
        "properties": {"event_type": {"const": "VIDEO_WATCHED"}},
    }
    output_schema = {"type": "object", "properties": {"watched": {"type": "boolean"}}}
    accessibility_policy = {
        "keyboard": "native HTML5 <video> controls are fully keyboard-operable (space "
                    "to play/pause, arrow keys to seek)",
        "screen_reader": "the scene's research-agent-written explanation text is exposed "
                          "as the learning_objective/description alongside the player, as "
                          "a text alternative to the video's narration",
        "reduced_motion": "not yet provided as a separate rendering — tracked as a future "
                           "enhancement, not silently omitted (requirements/60 §2)",
        "touch": "native <video> controls are touch-operable on mobile",
        "color_only_feedback": "none — completion is shown via a checkmark icon and text, "
                                "never color alone",
    }
    version_id = conn.execute(
        text("""
            INSERT INTO visual.interaction_template_version
                (interaction_template_id, version, input_schema, state_schema, event_schema,
                 output_schema, allowed_controls, allowed_icons, accessibility_policy,
                 content_hash, status, created_by, published_at)
            VALUES (:template_id, 1, :input_schema, :state_schema, :event_schema,
                    :output_schema, :allowed_controls, :allowed_icons, :accessibility_policy,
                    :content_hash, 'PUBLISHED', :created_by, now())
            RETURNING interaction_template_version_id
        """),
        {
            "template_id": template_id,
            "input_schema": _json(input_schema),
            "state_schema": _json(state_schema),
            "event_schema": _json(event_schema),
            "output_schema": _json(output_schema),
            "allowed_controls": _json(["VIDEO_TIMELINE"]),
            "allowed_icons": _json(["VIDEO", "PLAY", "PAUSE", "COMPLETE"]),
            "accessibility_policy": _json(accessibility_policy),
            "content_hash": _content_hash(
                {"input": input_schema, "state": state_schema, "event": event_schema,
                 "output": output_schema}
            ),
            "created_by": created_by,
        },
    ).scalar_one()
    return str(version_id)


def create_video_explainer_instance(
    conn: Connection, *, scene_spec_id: str, canonical_code: str, title: str,
    learning_objective: str, created_by: str, concept_slugs: list[str] | None = None,
    technique_slugs: list[str] | None = None,
) -> str:
    """Creates a new PENDING_REVIEW `visual.interaction_instance` bound to an APPROVED
    scene_spec and the VIDEO_EXPLAINER_V1 template. Still needs the *existing*
    `/instances/{id}/approve` endpoint before it can be attached to a course state
    (attach_interaction already requires APPROVED + PUBLISHED, unchanged by this
    feature)."""
    scene = conn.execute(
        text("SELECT status, scene_json FROM visual.scene_spec WHERE scene_spec_id = :id"),
        {"id": scene_spec_id},
    ).mappings().one_or_none()
    if scene is None:
        raise PromotionError("scene not found")
    if scene["status"] != "APPROVED":
        raise PromotionError(
            f"scene is {scene['status']}, not APPROVED — approve it before creating an "
            "interaction instance"
        )

    version_id = _ensure_video_explainer_template(conn, created_by)

    instance_config = {"scene_key": scene["scene_json"].get("scene_key")}
    initial_state = {"watched": False}
    success_criteria = {
        "type": "WATCHED",
        "description": "Watch the explainer video to completion.",
    }
    instance_id = conn.execute(
        text("""
            INSERT INTO visual.interaction_instance
                (interaction_template_version_id, canonical_code, title, instance_config,
                 initial_state, learning_objective, success_criteria, scene_spec_id,
                 content_hash, created_by)
            VALUES (:version_id, :code, :title, :config, :initial_state, :objective,
                    :success_criteria, :scene_spec_id, :content_hash, :created_by)
            RETURNING interaction_instance_id
        """),
        {
            "version_id": version_id, "code": canonical_code, "title": title,
            "config": _json(instance_config), "initial_state": _json(initial_state),
            "objective": learning_objective, "success_criteria": _json(success_criteria),
            "scene_spec_id": scene_spec_id,
            "content_hash": _content_hash(
                {"version_id": version_id, "scene_spec_id": scene_spec_id,
                 "config": instance_config}
            ),
            "created_by": created_by,
        },
    ).scalar_one()

    for slug in concept_slugs or []:
        concept_id = conn.execute(
            text("SELECT concept_id FROM knowledge.concept WHERE slug = :slug"),
            {"slug": slug},
        ).scalar_one_or_none()
        if concept_id is None:
            raise PromotionError(f"unknown concept slug {slug!r}")
        conn.execute(
            text("""
                INSERT INTO visual.interaction_instance_concept
                    (interaction_instance_id, concept_id, role)
                VALUES (:instance_id, :concept_id, 'TEACHES')
            """),
            {"instance_id": instance_id, "concept_id": concept_id},
        )
    for slug in technique_slugs or []:
        technique_id = conn.execute(
            text("SELECT technique_id FROM knowledge.technique WHERE slug = :slug"),
            {"slug": slug},
        ).scalar_one_or_none()
        if technique_id is None:
            raise PromotionError(f"unknown technique slug {slug!r}")
        conn.execute(
            text("""
                INSERT INTO visual.interaction_instance_technique
                    (interaction_instance_id, technique_id, role)
                VALUES (:instance_id, :technique_id, 'TEACHES')
            """),
            {"instance_id": instance_id, "technique_id": technique_id},
        )

    return str(instance_id)
