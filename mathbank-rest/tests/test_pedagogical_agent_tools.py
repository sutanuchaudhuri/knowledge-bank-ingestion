"""Agent wrappers must use the same anonymous, versioned REST contracts."""

import ast
import importlib.util
import json
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS_PATH = ROOT / "mathbank-agent/agents/mathbank_tutor/tools/rest_tools.py"
spec = importlib.util.spec_from_file_location("pedagogical_agent_tools", TOOLS_PATH)
tools = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


def test_pedagogical_tools_use_rest_only(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"fixture": True})

    monkeypatch.setattr(
        tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(handler),
        ),
    )
    assert tools.get_problem_learning_context("AIME Code") == {"fixture": True}
    tools.get_prerequisite_path("select", 3)
    tools.find_easier_same_skill_problems("FIXTURE", 2)
    tools.get_next_hint("FIXTURE", "strategy", "I tried counting subsets.", 2)
    assert requests[0].url.raw_path == b"/v1/tutor/learning-context/AIME%20Code"
    assert requests[1].url.path == "/v1/tutor/prerequisites/select"
    assert requests[1].url.params["max_depth"] == "3"
    assert requests[2].url.path == "/v1/tutor/practice/FIXTURE"
    assert requests[2].url.params["limit"] == "2"
    assert requests[3].url.path == "/v1/tutor/coach"
    assert json.loads(requests[3].content) == {
        "problem_code": "FIXTURE",
        "diagnosis": "strategy",
        "student_attempt": "I tried counting subsets.",
        "hint_level": 2,
    }
    assert requests[3].extensions["timeout"]["read"] == 60.0
    assert not any("/learner/" in request.url.path for request in requests)


def test_tool_failures_are_explicit(monkeypatch):
    monkeypatch.setattr(
        tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://test",
            transport=httpx.MockTransport(
                lambda request: httpx.Response(503, json={"detail": "Database unavailable"}),
            ),
        ),
    )
    with pytest.raises(httpx.HTTPStatusError) as error:
        tools.find_easier_same_skill_problems("FIXTURE")
    assert error.value.response.status_code == 503


def test_agent_registers_all_teaching_tools_and_diagnostic_first_instruction():
    source = (ROOT / "mathbank-agent/agents/mathbank_tutor/agent.py").read_text()
    tree = ast.parse(source)
    instruction = next(
        ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "INSTRUCTION" for target in node.targets
        )
    )
    agent = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "Agent"
    )
    registered = {
        item.id
        for keyword in agent.keywords
        if keyword.arg == "tools"
        for item in keyword.value.elts
    }
    assert {
        "get_problem_learning_context",
        "get_prerequisite_path",
        "get_next_hint",
        "find_easier_same_skill_problems",
    } <= registered
    assert "FIRST call get_problem_learning_context" in instruction
    assert "Do not fetch get_problem_by_code or full solutions" in instruction
    assert "new attempt" in instruction and "generated/provisional" in instruction
