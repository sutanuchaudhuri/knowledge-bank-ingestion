import json
from pathlib import Path

import pytest

from geometry_scene.errors import InvalidFrame
from geometry_scene.schemas import SceneInput, StateDelta
from geometry_scene.service import apply_delta, create_scene

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.mark.parametrize(
    "caption",
    [
        "A, B, C are collinear.",
        "These points lie on the same line.",
        "A, B, C form a straight line.",
    ],
)
def test_caption_cannot_supply_missing_proof(caption):
    document = json.loads((FIXTURES / "02_collinear_target.json").read_text())
    frame = create_scene(SceneInput.model_validate(document["initial"]))
    # The actual fixture target contains A, C, E.
    caption = caption.replace("B", "E")
    with pytest.raises(InvalidFrame, match="caption"):
        apply_delta(frame, StateDelta(expected_version=0, visual={"caption": caption}))


def test_caption_can_name_a_goal_without_asserting_it():
    document = json.loads((FIXTURES / "02_collinear_target.json").read_text())
    frame = create_scene(SceneInput.model_validate(document["initial"]))
    accepted = apply_delta(
        frame, StateDelta(expected_version=0, visual={"caption": "Goal: prove collinearity."})
    )
    assert accepted.validation.valid
