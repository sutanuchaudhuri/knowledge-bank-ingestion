from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from geometry_scene.cli import render_fixture
from geometry_scene.schemas import Frame
from geometry_scene.service import validate_frame

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted((ROOT / "fixtures").glob("*.json"))


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_multishot_specification(path, tmp_path):
    document = json.loads(path.read_text())
    frames = render_fixture(document, tmp_path)
    replay = render_fixture(document, tmp_path / "replay")
    assert len(frames) == len(document["expected"])
    for index, (frame, expected) in enumerate(zip(frames, document["expected"])):
        assert frame.validation.valid, frame.validation.errors
        assert frame == Frame.model_validate_json(frame.model_dump_json())
        assert frame == replay[index], "seeded replay changed"
        assert validate_frame(frame).valid
        scene, visual, math = frame.scene_state, frame.visual_state, frame.math_state
        assert scene.version == visual.version == math.version == index
        tree = ET.fromstring(frame.svg)
        ids = [e.attrib["id"] for e in tree.iter() if "id" in e.attrib]
        assert len(ids) == len(set(ids))
        assert set(scene.entities).issubset(ids)
        for name in expected.get("entities", []):
            assert name in scene.entities
            assert visual.styles[name].visible
        for name in expected.get("absent", []):
            assert name not in scene.entities or not visual.styles[name].visible
        for field, value in (("highlight", "HIGHLIGHT"), ("background", "BACKGROUND")):
            for name in expected.get(field, []):
                assert visual.styles[name].emphasis == value
        for name in expected.get("dashed", []):
            assert visual.styles[name].line_style == "DASHED"
        for name in expected.get("arcs", []):
            assert visual.styles[name].render_mode == "VISIBLE_ARC"
            assert scene.entities[name].type == "CIRCLE"
        for name, status in expected.get("statuses", {}).items():
            assert next(r.status for r in math.relations if r.id == name) == status
        for name, label in expected.get("labels", {}).items():
            assert visual.styles[name].label == label
        if index:
            previous = frames[index - 1]
            assert set(previous.scene_state.entities).issubset(scene.entities)
            if not frame.applied_delta.relayout:
                for name, entity in previous.scene_state.entities.items():
                    if entity.type == "POINT":
                        assert (entity.x, entity.y) == (
                            scene.entities[name].x,
                            scene.entities[name].y,
                        ), name
        for suffix in ("math_state", "scene_state", "visual_state", "validation", "bundle"):
            assert (tmp_path / f"{suffix}_{index:03}.json").exists()
        assert (tmp_path / f"frame_{index:03}.svg").exists()


def test_all_ten_cases_are_executable():
    assert len(CASES) == 10


def test_circumcenter_focus_must_not_be_generic_quad(tmp_path):
    document = json.loads((ROOT / "fixtures/05_circumcenter_chain.json").read_text())
    frames = render_fixture(document, tmp_path)
    first = frames[1]
    assert "triangle_BCD" in first.scene_state.entities
    assert "point_A1" in first.scene_state.entities
    assert "point_A1" in first.svg
    assert "quadrilateral_ABCD" in first.scene_state.entities
    assert first.visual_state.styles["point_A1"].emphasis == "HIGHLIGHT"
