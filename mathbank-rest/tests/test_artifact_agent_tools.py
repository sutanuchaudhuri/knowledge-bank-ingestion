"""Artifact agent wrappers use student-scoped REST only, with no paid/model commands."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from uuid import uuid4

import pytest


@pytest.fixture
def tools(monkeypatch):
    context = ModuleType("google.adk.tools.tool_context")
    context.ToolContext = object
    runtime = ModuleType("mathbank_tutor.tools.step_runtime_tools")
    runtime._call = lambda *args, **kwargs: {}
    monkeypatch.setitem(sys.modules, "google.adk.tools.tool_context", context)
    monkeypatch.setitem(sys.modules, "mathbank_tutor.tools.step_runtime_tools", runtime)
    path = (
        Path(__file__).resolve().parents[2]
        / "mathbank-agent/agents/mathbank_tutor/tools/artifact_tools.py"
    )
    spec = importlib.util.spec_from_file_location("mathbank_tutor.tools.artifact_tools_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agent_exports_student_only_artifact_tools(tools):
    assert [tool.__name__ for tool in tools.ARTIFACT_TOOLS] == [
        "search_artifacts",
        "get_artifact_bundle",
        "request_artifact",
        "draw_geometry_diagram",
    ]


def test_actual_agent_registry_contains_artifacts_and_preserves_attempt_media():
    source = (
        Path(__file__).resolve().parents[2] / "mathbank-agent/agents/mathbank_tutor/agent.py"
    ).read_text()
    assert "from .tools.artifact_tools import ARTIFACT_TOOLS" in source
    assert "*ARTIFACT_AGENT_TOOLS," in source and "*ATTEMPT_MEDIA_TOOLS," in source
    assert "request_artifact only submits" in source


def test_tool_request_shapes_and_bundle_composition(tools, monkeypatch):
    calls = []
    bundle_id = str(uuid4())

    def call(context, method, path, **kwargs):
        calls.append((method, path, kwargs))
        if path.endswith("/assets"):
            return {"assets": [{"artifact_asset_id": "asset", "content_path": "private-mediated"}]}
        if path.endswith("/frames"):
            return {"frames": [{"ordinal": 0}]}
        return {"artifact_bundle_id": bundle_id}

    monkeypatch.setattr(tools, "_call", call)
    tools.search_artifacts("triangle", None, "GEOMETRY", 12)
    assert calls[-1] == (
        "POST",
        "/v1/artifacts/search",
        {"json": {"query": "triangle", "subject": "GEOMETRY", "limit": 12}},
    )
    assert "generate_embedding" not in calls[-1][2]["json"]
    result = tools.get_artifact_bundle(bundle_id, None)
    assert result["frame_sequence"]["frames"][0]["ordinal"] == 0
    assert result["assets"][0]["content_path"] == "private-mediated"
    plan = {"subject": "ALGEBRA", "topic": "linear equation", "title": "Solve"}
    tools.request_artifact(json.dumps(plan), None)
    assert calls[-1] == ("POST", "/v1/artifacts/requests", {"json": plan})
    assert not any(path.endswith(("/generate", "/index", "/publish")) for _, path, _ in calls)


def test_tool_errors_do_not_fake_artifact_success(tools, monkeypatch):
    monkeypatch.setattr(tools, "_call", lambda *args, **kwargs: {"error": "SIGN_IN_REQUIRED"})
    assert tools.search_artifacts("circle", None)["error"] == "SIGN_IN_REQUIRED"
    assert tools.get_artifact_bundle(str(uuid4()), None)["error"] == "SIGN_IN_REQUIRED"
    assert tools.request_artifact("{}", None)["error"] == "SIGN_IN_REQUIRED"


def test_geometry_tool_invokes_immediate_drawing_not_staff_publication(tools, monkeypatch):
    calls = []
    monkeypatch.setattr(
        tools,
        "_call",
        lambda *args, **kwargs: (
            calls.append((args, kwargs)) or {"markdown_block": "```geometry-artifact\n{}\n```"}
        ),
    )
    plan = {"subject": "GEOMETRY", "title": "Sketch", "elements": []}
    assert "markdown_block" in tools.draw_geometry_diagram(json.dumps(plan), None)
    assert calls[0][0][1:] == ("POST", "/v1/artifacts/geometry-preview")
    assert calls[0][1]["json"] == plan
    assert tools.get_artifact_bundle("not-uuid", None)["error"] == "INVALID_BUNDLE_ID"
    assert tools.request_artifact("[]", None)["error"] == "INVALID_PLAN_JSON"
    assert tools.search_artifacts("x", None, "UNSUPPORTED")["error"] == "INVALID_SUBJECT"
