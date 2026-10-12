"""Validators for the interaction template library (requirements/41 ITL-17) and
the micro-course platform (requirements/40 MCR-17). Each function returns a
list of human-readable violation strings; an empty list means the object may
be approved/published. These are pure checks against already-persisted rows
plus the row being validated — they never call a model.
"""

from __future__ import annotations

from sqlalchemy import text


def validate_interaction_template_version(conn, version_id: str) -> list[str]:
    row = (
        conn.execute(
            text("""
        SELECT input_schema, state_schema, event_schema, output_schema,
               allowed_controls, allowed_icons, diagnostic_capabilities,
               animation_slots, accessibility_policy
        FROM visual.interaction_template_version WHERE interaction_template_version_id = :id
    """),
            {"id": version_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return ["template version not found"]
    errors = []
    for field in ("input_schema", "state_schema", "event_schema", "output_schema"):
        if not row[field] or row[field].get("$placeholder"):
            errors.append(
                f"{field} is a placeholder; a real JSON Schema must be authored before publish"
            )
    control_keys = {
        key
        for key in conn.execute(text("SELECT control_key FROM visual.control_template")).scalars()
    }
    for control in row["allowed_controls"] or []:
        if control not in control_keys:
            errors.append(f"unknown control {control!r}")
    icon_keys = {
        key for key in conn.execute(text("SELECT token_key FROM visual.icon_token")).scalars()
    }
    for icon in row["allowed_icons"] or []:
        if icon not in icon_keys:
            errors.append(f"icon {icon!r} is outside the approved registry")
    if not row["accessibility_policy"]:
        errors.append(
            "accessibility_policy is empty; keyboard/focus/screen-reader/reduced-motion policy is required"
        )
    return errors


def validate_interaction_instance(conn, instance_id: str) -> list[str]:
    row = (
        conn.execute(
            text("""
        SELECT i.instance_config, i.success_criteria, i.feedback_policy_id, i.scene_spec_id,
               v.status AS version_status, v.interaction_template_version_id
        FROM visual.interaction_instance i
        JOIN visual.interaction_template_version v USING (interaction_template_version_id)
        WHERE i.interaction_instance_id = :id
    """),
            {"id": instance_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return ["interaction instance not found"]
    errors = []
    if row["version_status"] != "PUBLISHED":
        errors.append("bound template version is not PUBLISHED")
    if not row["success_criteria"]:
        errors.append("missing success_criteria")
    if row["feedback_policy_id"] is not None:
        policy_status = conn.execute(
            text(
                "SELECT review_status FROM pedagogy.feedback_policy WHERE feedback_policy_id = :id"
            ),
            {"id": row["feedback_policy_id"]},
        ).scalar_one_or_none()
        if policy_status != "APPROVED":
            errors.append("attached feedback_policy is not APPROVED")
    if row["scene_spec_id"] is not None:
        scene_status = conn.execute(
            text("SELECT status FROM visual.scene_spec WHERE scene_spec_id = :id"),
            {"id": row["scene_spec_id"]},
        ).scalar_one_or_none()
        if scene_status != "APPROVED":
            errors.append("attached scene_spec is not APPROVED")
    # Every error_signature this instance's misconception bindings imply must have an
    # approved evidence rule for the bound template version, so runtime evaluation can
    # always resolve evidence (no "unsupported" signature can silently do nothing).
    unsupported = conn.execute(
        text("""
        SELECT m.misconception_id FROM visual.interaction_instance_misconception m
        WHERE m.interaction_instance_id = :id AND m.role = 'CAN_REVEAL'
          AND NOT EXISTS (
              SELECT 1 FROM pedagogy.misconception_evidence_rule r
              WHERE r.misconception_id = m.misconception_id
                AND r.interaction_template_version_id = :version AND r.review_status = 'APPROVED'
          )
    """),
        {"id": instance_id, "version": row["interaction_template_version_id"]},
    ).all()
    if unsupported:
        errors.append(
            f"{len(unsupported)} CAN_REVEAL misconception binding(s) have no approved evidence rule"
        )
    return errors


def validate_scene_spec(conn, scene_spec_id: str) -> list[str]:
    scene_json = conn.execute(
        text("SELECT scene_json FROM visual.scene_spec WHERE scene_spec_id = :id"),
        {"id": scene_spec_id},
    ).scalar_one_or_none()
    if scene_json is None:
        return ["scene spec not found"]
    errors = []
    object_ids = [obj.get("id") for obj in scene_json.get("objects", [])]
    if len(object_ids) != len(set(object_ids)):
        errors.append("duplicate object ids in scene")
    known_ids = set(object_ids)
    for entry in scene_json.get("timeline", []):
        for target in entry.get("targets", []) or []:
            if target not in known_ids:
                errors.append(f"timeline references unknown object {target!r}")
        for key in ("from", "to"):
            value = entry.get(key)
            if value is not None and value not in known_ids:
                errors.append(f"timeline references unknown object {value!r}")
    return errors


def validate_evidence_rule(conn, evidence_rule_id: str) -> list[str]:
    row = (
        conn.execute(
            text("""
        SELECT evidence_weight, requires_probe, diagnostic_learning_item_id
        FROM pedagogy.misconception_evidence_rule WHERE evidence_rule_id = :id
    """),
            {"id": evidence_rule_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return ["evidence rule not found"]
    errors = []
    if not (-1 <= float(row["evidence_weight"]) <= 1):
        errors.append("evidence_weight out of range")
    if row["requires_probe"] and not row["diagnostic_learning_item_id"]:
        errors.append("requires_probe is true but no diagnostic_learning_item_id is attached")
    return errors
