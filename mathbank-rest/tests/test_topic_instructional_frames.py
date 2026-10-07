import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi import HTTPException

from mathbank_rest import artifact_runtime as runtime
from mathbank_rest.routers.artifacts import GeometryPreview, _geometry_preview

spec = importlib.util.spec_from_file_location(
    "topic_lessons", Path(__file__).resolve().parents[2]
    / "mathbank-agent/agents/mathbank_tutor/topic_lessons.py",
)
lessons = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lessons)


def test_authored_diagram_renders_four_safe_reset_to_base_frames():
    plan = GeometryPreview.model_validate(lessons.chord_diagram())
    rendered = [_geometry_preview(plan, i)["preview_svg"] for i in range(4)]
    assert len(set(rendered)) == 4
    for data in rendered:
        assert not runtime.svg_errors(data)
        assert b"<script" not in data
    first = {node.get("id"): node for node in ET.fromstring(rendered[1]).iter()}
    second = {node.get("id"): node for node in ET.fromstring(rendered[2]).iter()}
    assert any(node.get("stroke") == "#0284c7" for node in first["PA"].iter())
    assert not any(node.get("stroke") == "#0284c7" for node in second["PA"].iter())
    assert any(node.get("stroke") == "#0284c7" for node in second["PC"].iter())
    with pytest.raises(HTTPException) as exc:
        _geometry_preview(plan, 4)
    assert exc.value.status_code == 404

