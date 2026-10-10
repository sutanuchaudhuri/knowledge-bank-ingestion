"""Seed-catalog loader and read-service for the interaction template library
(requirements/41_INTERACTION_TEMPLATE_LIBRARY.md). Idempotent: re-running the
loader only upserts rows by their natural key, never duplicates.

The bundled seed JSON (data/interaction_catalog/*.json) establishes the
*vocabulary* (which control/icon/animation/template keys exist) copied from
the source INTERACTION_TEMPLATE_LIBRARY_COPILOT/seeds/ pack. It intentionally
does not yet carry full JSON-Schema bodies for config/accessibility/input
schemas — those need per-template authoring and are placeholders here
(explicitly non-empty markers, not silently blank) until designed.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

PLACEHOLDER_SCHEMA = {"$placeholder": True, "note": "schema not yet authored"}
DATA_DIR = Path(__file__).resolve().parent / "data" / "interaction_catalog"


def _load_json(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


def load_icon_tokens(conn) -> int:
    rows = _load_json("icon_tokens.json")
    for row in rows:
        conn.execute(
            text("""
            INSERT INTO visual.icon_token (token_key, icon_class, accessible_label)
            VALUES (:token_key, :icon_class, :accessible_label)
            ON CONFLICT (token_key) DO UPDATE SET
                icon_class=excluded.icon_class, accessible_label=excluded.accessible_label
        """),
            row,
        )
    return len(rows)


def load_control_templates(conn) -> int:
    rows = _load_json("control_templates.json")
    for row in rows:
        conn.execute(
            text("""
            INSERT INTO visual.control_template
                (control_key, control_type, config_schema, accessibility_schema)
            VALUES (:control_key, :control_type, CAST(:config AS jsonb), CAST(:a11y AS jsonb))
            ON CONFLICT (control_key) DO UPDATE SET control_type=excluded.control_type
        """),
            {
                "control_key": row["control_key"],
                "control_type": row["control_type"],
                "config": json.dumps(PLACEHOLDER_SCHEMA | {"semantic": row.get("semantic")}),
                "a11y": json.dumps(PLACEHOLDER_SCHEMA),
            },
        )
    return len(rows)


def load_animation_templates(conn) -> int:
    rows = _load_json("animation_templates.json")
    for row in rows:
        conn.execute(
            text("""
            INSERT INTO visual.animation_template
                (animation_key, name, input_schema, reduced_motion_behavior)
            VALUES (:key, :key, CAST(:input AS jsonb), CAST(:motion AS jsonb))
            ON CONFLICT (animation_key) DO UPDATE SET reduced_motion_behavior=excluded.reduced_motion_behavior
        """),
            {
                "key": row["animation_key"],
                "input": json.dumps(PLACEHOLDER_SCHEMA),
                "motion": json.dumps(
                    {
                        "required": bool(row.get("reduced_motion_required")),
                        "fallback": "NOT_YET_AUTHORED",
                    }
                ),
            },
        )
    return len(rows)


def load_interaction_templates(conn) -> int:
    rows = _load_json("interaction_templates.json")
    status_map = {"DRAFT_SEED": "DRAFT"}
    for row in rows:
        template_id = conn.execute(
            text("""
            INSERT INTO visual.interaction_template (template_key, name, interaction_family)
            VALUES (:key, :key, 'UNCATEGORIZED')
            ON CONFLICT (template_key) DO UPDATE SET template_key=excluded.template_key
            RETURNING interaction_template_id
        """),
            {"key": row["template_key"]},
        ).scalar_one()
        status = status_map.get(row.get("status"), "DRAFT")
        conn.execute(
            text("""
            INSERT INTO visual.interaction_template_version
                (interaction_template_id, version, input_schema, state_schema, event_schema,
                 output_schema, content_hash, created_by, status)
            VALUES (:t, :v, CAST(:s AS jsonb), CAST(:s AS jsonb), CAST(:s AS jsonb), CAST(:s AS jsonb),
                    :hash, 'seed-loader', :status)
            ON CONFLICT (interaction_template_id, version) DO NOTHING
        """),
            {
                "t": template_id,
                "v": row["version"],
                "s": json.dumps(PLACEHOLDER_SCHEMA),
                "hash": f"seed:{row['template_key']}:{row['version']}",
                "status": status,
            },
        )
    return len(rows)


def load_all(conn) -> dict:
    return {
        "icon_tokens": load_icon_tokens(conn),
        "control_templates": load_control_templates(conn),
        "animation_templates": load_animation_templates(conn),
        "interaction_templates": load_interaction_templates(conn),
    }


def list_templates(conn) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            text("""
        SELECT t.template_key, t.interaction_family, t.status, v.version, v.status AS version_status
        FROM visual.interaction_template t
        JOIN visual.interaction_template_version v USING (interaction_template_id)
        ORDER BY t.template_key, v.version
    """)
        ).mappings()
    ]
