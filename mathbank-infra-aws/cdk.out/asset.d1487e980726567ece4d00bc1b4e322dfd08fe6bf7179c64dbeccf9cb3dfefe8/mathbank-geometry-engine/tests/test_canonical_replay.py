import json
from pathlib import Path

import pytest

from geometry_scene.cli import render_fixture
from geometry_scene.schemas import Frame
from geometry_scene.service import apply_delta, validate_frame

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "fixture", sorted((ROOT / "fixtures").glob("*.json")), ids=lambda p: p.stem
)
def test_sorted_json_object_storage_reconstructs_every_svg(fixture, tmp_path):
    frames = render_fixture(json.loads(fixture.read_text()), tmp_path)
    for index, frame in enumerate(frames):
        restored = Frame.model_validate_json(
            json.dumps(frame.model_dump(mode="json"), sort_keys=True)
        )
        assert validate_frame(restored).valid
        if index < len(frames) - 1:
            assert apply_delta(restored, frames[index + 1].applied_delta) == frames[index + 1]
