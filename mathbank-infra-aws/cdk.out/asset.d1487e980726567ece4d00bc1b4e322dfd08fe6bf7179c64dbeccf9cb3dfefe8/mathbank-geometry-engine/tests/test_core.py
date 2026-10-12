from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from geometry_scene import StateDelta, apply_delta, create_scene, validate_frame
from geometry_scene.errors import GeometryError, InvalidFrame, VersionConflict
from geometry_scene.parser import parse_dsl, parse_input
from geometry_scene.schemas import SceneInput

ROOT = Path(__file__).resolve().parents[1]


def initial(number="09"):
    path = next((ROOT / "fixtures").glob(number + "*.json"))
    return SceneInput.model_validate(json.loads(path.read_text())["initial"])


def test_context_parser_does_not_prove_target():
    frame = create_scene(SceneInput(context=({"type": "target", "fact": "A,E,C are collinear"},)))
    assert frame.math_state.relations[0].status == "TARGET_TO_PROVE"
    assert "line_AEC" not in frame.scene_state.entities


def test_yaml_dsl_normalizes_pack_spelling(tmp_path):
    from geometry_scene.parser import load_document

    path = tmp_path / "fixture.yaml"
    path.write_text("""
scene: {id: example_scene, rendering_mode: exact_or_constrained}
objects: {A: {type: point}, B: {type: point}, C: {type: point}}
relations:
  - {type: triangle, args: [A, B, C], status: given}
""")
    parsed = parse_dsl(load_document(path))
    assert parsed.scene_id == "example_scene"
    assert parsed.relations[0].type == "TRIANGLE"


@pytest.mark.parametrize(
    "context",
    [
        ({"type": "given", "fact": "Maybe these triangles appear equal"},),
        ({"type": "guess", "fact": "A,E,C are collinear"},),
    ],
)
def test_ambiguous_language_fails_explicitly(context):
    with pytest.raises(GeometryError):
        parse_input(SceneInput(context=context))


def test_no_text_only_invention():
    with pytest.raises(GeometryError, match="typed context"):
        create_scene(SceneInput(problem_text="Draw something nice"))


def test_atomic_delta_and_version_conflict():
    frame = create_scene(initial())
    snapshot = frame.model_dump_json()
    with pytest.raises(VersionConflict):
        apply_delta(frame, StateDelta(expected_version=1))
    with pytest.raises(GeometryError, match="visual reference"):
        apply_delta(
            frame,
            StateDelta.model_validate(
                {
                    "expected_version": 0,
                    "visual": {"highlight": ["point_missing"]},
                }
            ),
        )
    assert frame.model_dump_json() == snapshot


def test_target_collinearity_cannot_be_rendered_straight():
    value = initial("10").model_dump()
    value["positions"]["Y"] = (470, 180)
    with pytest.raises(InvalidFrame, match="leakage"):
        create_scene(SceneInput.model_validate(value))


@pytest.mark.parametrize(
    "kind,args,marker",
    [
        ("PERPENDICULAR", ["A", "B", "B", "C"], "RIGHT_ANGLE_MARK"),
        ("EQUAL_LENGTH", ["A", "B", "B", "C"], "EQUAL_LENGTH_MARK"),
        ("SIMILAR", ["A", "B", "C", "D", "E", "F"], "CORRESPONDENCE_MARK"),
    ],
)
def test_unproven_markers_are_rejected(kind, args, marker):
    value = {
        "objects": {p: {} for p in set(args)},
        "relations": [{"id": "target", "type": kind, "args": args, "status": "TARGET_TO_PROVE"}],
        "entities": [{"id": "bad_mark", "type": marker, "refs": args, "relation_id": "target"}],
        "visual": {"show": ["bad_mark"]},
    }
    with pytest.raises(InvalidFrame, match="unestablished|leakage"):
        create_scene(SceneInput.model_validate(value))


def test_unproven_cyclicity_circle_is_rejected():
    data = initial("01").model_dump()
    data["relations"][1]["status"] = "TARGET_TO_PROVE"
    data["positions"] = {"A": [100, 100], "B": [400, 100], "C": [400, 400], "D": [100, 400]}
    data["entities"] = [
        {
            "id": "circle_guess",
            "type": "CIRCLE",
            "refs": ["A", "B", "C", "D"],
            "x": 250,
            "y": 250,
            "radius": (45000) ** 0.5,
        }
    ]
    with pytest.raises(InvalidFrame, match="leakage"):
        create_scene(SceneInput.model_validate(data))


def test_tampered_svg_is_invalid():
    frame = create_scene(initial())
    edited = frame.model_copy(
        update={"svg": frame.svg.replace('data-version="0"', 'data-version="99"')}
    )
    assert not validate_frame(edited).valid


def test_impossible_frozen_constraint_is_not_silently_relayouted():
    frame = create_scene(initial("10"))
    delta = StateDelta.model_validate(
        {
            "expected_version": 0,
            "change_status": [
                {"relation_id": "straight", "status": "PROVEN", "provenance": "proof"}
            ],
        }
    )
    with pytest.raises(InvalidFrame, match="constraint violation"):
        apply_delta(frame, delta)


def test_degenerate_circumcenter_fails():
    with pytest.raises(GeometryError, match="nondegenerate"):
        create_scene(
            SceneInput.model_validate(
                {
                    "objects": {"A": {}, "B": {}, "C": {}, "O": {}},
                    "positions": {"A": [100, 100], "B": [200, 100], "C": [300, 100]},
                    "relations": [
                        {
                            "id": "center",
                            "type": "CIRCUMCENTER",
                            "args": ["O", "A", "B", "C"],
                            "status": "GIVEN",
                        }
                    ],
                }
            )
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_nonfinite_geometry_is_rejected(bad):
    with pytest.raises(ValidationError):
        SceneInput(objects={"A": {}}, positions={"A": (bad, 0)})


def test_no_application_or_tutor_dependency():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import geometry_scene,sys; assert not any(n.startswith(('mathbank_rest','google.adk','openai')) for n in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_svg_escapes_untrusted_label_text():
    value = initial().model_dump()
    value["visual"] = {"styles": {"point_C": {"label": "<x>"}}}
    frame = create_scene(SceneInput.model_validate(value))
    assert "<x>" not in frame.svg and "&lt;x&gt;" in frame.svg
