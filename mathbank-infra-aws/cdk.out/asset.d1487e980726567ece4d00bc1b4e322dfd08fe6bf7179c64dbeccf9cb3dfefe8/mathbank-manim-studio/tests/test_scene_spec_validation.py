import json
from pathlib import Path

from mathbank_manim_studio.scene_spec_validation import validate_scene_spec_dict

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "markov_two_state.json").read_text()
)


def test_real_fixture_is_valid():
    assert validate_scene_spec_dict(FIXTURE) == []


def test_missing_required_field_object_type():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [{"id": "a", "type": "EQUATION"}],  # missing "latex"
        "timeline": [{"at_ms": 0, "action": "WRITE", "targets": ["a"]}],
    }
    errors = validate_scene_spec_dict(spec)
    assert any("latex" in e for e in errors)


def test_unknown_object_type_rejected():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [{"id": "a", "type": "VECTOR_FIELD"}],
        "timeline": [],
    }
    errors = validate_scene_spec_dict(spec)
    assert any("unsupported type" in e for e in errors)


def test_duplicate_object_ids_rejected():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [
            {"id": "a", "type": "TEXT", "label": "one"},
            {"id": "a", "type": "TEXT", "label": "two"},
        ],
        "timeline": [],
    }
    errors = validate_scene_spec_dict(spec)
    assert any("duplicate" in e for e in errors)


def test_timeline_unknown_target_rejected():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [{"id": "a", "type": "TEXT", "label": "hi"}],
        "timeline": [{"at_ms": 0, "action": "SHOW", "targets": ["ghost"]}],
    }
    errors = validate_scene_spec_dict(spec)
    assert any("unknown object" in e for e in errors)


def test_latex_in_plain_text_label_rejected():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [{"id": "a", "type": "TEXT", "label": r"If \(x_1\) and \(x_2\)"}],
        "timeline": [{"at_ms": 0, "action": "SHOW", "targets": ["a"]}],
    }
    errors = validate_scene_spec_dict(spec)
    assert any("looks like LaTeX" in e for e in errors)


def test_plain_equation_latex_is_fine():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [{"id": "a", "type": "EQUATION", "latex": r"x^2 + bx + c = 0"}],
        "timeline": [{"at_ms": 0, "action": "WRITE", "targets": ["a"]}],
    }
    assert validate_scene_spec_dict(spec) == []


def test_unsupported_action_rejected():
    spec = {
        "scene_key": "x", "scene_version": 1,
        "objects": [{"id": "a", "type": "TEXT", "label": "hi"}],
        "timeline": [{"at_ms": 0, "action": "ZOOM_IN", "targets": ["a"]}],
    }
    errors = validate_scene_spec_dict(spec)
    assert any("unsupported" in e for e in errors)


def test_missing_schema_required_top_level_key_rejected():
    spec = {"scene_key": "x", "objects": [], "timeline": []}  # missing scene_version
    errors = validate_scene_spec_dict(spec)
    assert any("schema" in e for e in errors)
