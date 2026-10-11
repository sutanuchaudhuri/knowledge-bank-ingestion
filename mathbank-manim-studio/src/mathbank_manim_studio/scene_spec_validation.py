"""Pure, DB-free SceneSpec validation (requirements/60 §3). Mirrors the JSON Schema and
the semantic checks mathbank-rest's `interaction_validators.validate_scene_spec` applies
to already-persisted `visual.scene_spec` rows — ported to operate directly on a dict,
since these are ephemeral drafts that do not (and, in v1, never will) exist as a
`visual.scene_spec` row.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

_SCHEMA_PATH = (
    Path(__file__).resolve().parents[3]
    / "documentation" / "copilot-instructions" / "interaction-template-library"
    / "schemas" / "scene_spec.schema.json"
)

# The v1 object/action vocabulary this project's compiler actually implements
# (requirements/60 §3) — a real, documented *subset* of ITL-4's full 18-object/23-action
# surface, not the complete catalog vocabulary.
SUPPORTED_OBJECT_TYPES = {
    "TITLE_TEXT", "TEXT", "EQUATION", "STATE_NODE", "FUNCTION_GRAPH", "GRAPH_POINT", "MATRIX",
}
SUPPORTED_ACTIONS = {
    "SHOW", "HIDE", "WRITE", "HIGHLIGHT", "DRAW_TRANSITION", "EQUATION_MORPH", "WAIT",
}

# The exact field each v1 object type/action needs for the compiler to produce something
# non-empty — checked in addition to the generic JSON Schema (which, by design, only
# requires "id"/"type" so the schema stays reusable for ITL-4's full future vocabulary).
REQUIRED_OBJECT_FIELDS: dict[str, tuple[str, ...]] = {
    "TITLE_TEXT": ("label",),
    "TEXT": ("label",),
    "EQUATION": ("latex",),
    "STATE_NODE": ("label",),
    "FUNCTION_GRAPH": ("expr",),
    "GRAPH_POINT": ("on",),
    "MATRIX": ("rows",),
}
REQUIRED_TIMELINE_FIELDS: dict[str, tuple[str, ...]] = {
    "SHOW": ("targets",),
    "HIDE": ("targets",),
    "WRITE": ("targets",),
    "HIGHLIGHT": ("targets",),
    "DRAW_TRANSITION": ("from", "to"),
    "EQUATION_MORPH": ("from", "to"),
}

# Plain-text object types whose "label" must never contain LaTeX — math notation belongs
# in an EQUATION object's "latex" field instead (requirements/60 §3, enforced below).
_PLAIN_TEXT_OBJECT_TYPES = {"TITLE_TEXT", "TEXT", "STATE_NODE"}
_LATEX_LIKE = re.compile(r"\\\(|\\\[|\\[A-Za-z]{2,}")


def _load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text())


def validate_scene_spec_dict(scene_json: dict, *, require_supported_vocabulary: bool = True
                              ) -> list[str]:
    """Returns a list of human-readable violation strings; empty means the SceneSpec is
    usable. Three layers, in order: JSON Schema structure, semantic reference integrity
    (duplicate/unknown object ids), and (optionally) this project's v1 vocabulary support."""
    errors: list[str] = []
    validator = Draft202012Validator(_load_schema())
    for error in validator.iter_errors(scene_json):
        errors.append(f"schema: {error.message} at {'/'.join(str(p) for p in error.path)}")
    if errors:
        return errors  # semantic checks below assume a structurally valid document

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

    if require_supported_vocabulary:
        for obj in scene_json.get("objects", []):
            obj_type = obj.get("type")
            if obj_type not in SUPPORTED_OBJECT_TYPES:
                errors.append(
                    f"object {obj.get('id')!r} has unsupported type {obj_type!r} "
                    f"(v1 supports: {sorted(SUPPORTED_OBJECT_TYPES)})"
                )
                continue
            for field in REQUIRED_OBJECT_FIELDS.get(obj_type, ()):
                if not obj.get(field):
                    errors.append(
                        f"object {obj.get('id')!r} (type {obj_type!r}) is missing "
                        f"required field {field!r}"
                    )
            if obj_type in _PLAIN_TEXT_OBJECT_TYPES and _LATEX_LIKE.search(obj.get("label") or ""):
                errors.append(
                    f"object {obj.get('id')!r} (type {obj_type!r}) has a 'label' that "
                    "looks like LaTeX (contains a backslash command or \\(...\\)/\\[...\\] "
                    "delimiters) — plain TEXT/TITLE_TEXT/STATE_NODE labels must be plain "
                    "display text; use an EQUATION object's 'latex' field for math notation"
                )
        for entry in scene_json.get("timeline", []):
            action = entry.get("action")
            if action not in SUPPORTED_ACTIONS:
                errors.append(
                    f"timeline action {action!r} is unsupported "
                    f"(v1 supports: {sorted(SUPPORTED_ACTIONS)})"
                )
                continue
            for field in REQUIRED_TIMELINE_FIELDS.get(action, ()):
                if not entry.get(field):
                    errors.append(
                        f"timeline entry with action {action!r} is missing required "
                        f"field {field!r}"
                    )
    return errors
