import json
from pathlib import Path

import pytest

from geometry_scene.errors import GeometryError, InvalidFrame
from geometry_scene.schemas import SceneInput, StateDelta
from geometry_scene.service import apply_delta, create_scene, validate_frame

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def scene():
    value = json.loads((FIXTURES / "01_cyclic_quad.json").read_text())["initial"]
    return create_scene(SceneInput.model_validate(value))


def test_cumulative_overlay_targets_and_serialized_replay():
    frame = scene()
    updated = apply_delta(
        frame,
        StateDelta.model_validate(
            {
                "expected_version": 0,
                "visual": {
                    "overlays": [
                        {
                            "id": "focus_A",
                            "targets": ["point_A", "segment_AB"],
                            "caption": "Focus A",
                        }
                    ]
                },
            }
        ),
    )
    assert 'href="#point_A"' in updated.svg
    assert 'id="focus_A"' in updated.svg
    later = apply_delta(updated, StateDelta(expected_version=1))
    assert later.visual_state.overlays == updated.visual_state.overlays
    assert validate_frame(later).valid
    assert frame.visual_state.overlays == ()


def test_overlay_nonexistent_target_is_explicit_failure():
    with pytest.raises(GeometryError, match="nonexistent"):
        apply_delta(
            scene(),
            StateDelta.model_validate(
                {
                    "expected_version": 0,
                    "visual": {"overlays": [{"id": "bad", "targets": ["missing"]}]},
                }
            ),
        )


def test_realization_changes_require_explicit_relayout():
    with pytest.raises(ValueError, match="relayout"):
        StateDelta(expected_version=0, realization_seed=19)
    previous = scene()
    updated = apply_delta(
        previous,
        StateDelta(
            expected_version=0, relayout=True, realization_seed=19, rendering_mode="SCHEMATIC"
        ),
    )
    assert updated.scene_state.seed == 19
    assert updated.scene_state.rendering_mode == "SCHEMATIC"
    assert updated.validation.valid
    assert updated.math_state.relations == previous.math_state.relations


def test_minimum_angle_never_weakens_locked_givens():
    with pytest.raises(GeometryError, match="minimum-angle"):
        create_scene(
            SceneInput.model_validate(
                {
                    "objects": {"A": {}, "B": {}, "C": {}},
                    "positions": {"A": [100, 100], "B": [500, 100], "C": [490, 115]},
                    "relations": [
                        {
                            "id": "triangle",
                            "type": "TRIANGLE",
                            "args": ["A", "B", "C"],
                            "status": "GIVEN",
                        }
                    ],
                    "minimum_angle_degrees": 20,
                }
            )
        )


def test_marker_references_cannot_borrow_an_unrelated_fact():
    value = json.loads((FIXTURES / "09_midpoint_auxiliary.json").read_text())["initial"]
    value["entities"] = [
        {
            "id": "fake_equal",
            "type": "EQUAL_LENGTH_MARK",
            "refs": ["A", "C", "C", "B"],
            "relation_id": "midpoint",
        }
    ]
    with pytest.raises(InvalidFrame, match="marker references"):
        create_scene(SceneInput.model_validate(value))


def test_unresolved_focus_reference_is_rejected():
    with pytest.raises(GeometryError, match="visual reference"):
        apply_delta(
            scene(),
            StateDelta.model_validate({"expected_version": 0, "visual": {"focus": ["missing"]}}),
        )
