"""Presentation tools: learner-token auth, validated widget blocks, deterministic formatting only."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.mathbank_tutor.tools import step_runtime_tools, widget_tools  # noqa: E402

SPEC = {"widget_type": "GEOMETRY_DIAGRAM", "spec_version": "1.0", "title": "Power of a point", "config": {}}


def ctx(token="tok"):
    return SimpleNamespace(state={"temp:student_token": token} if token else {}, function_call_id="c1")


def mock_rest(monkeypatch, handler):
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(step_runtime_tools, "_client",
                        lambda: httpx.Client(base_url="http://rest", transport=httpx.MockTransport(wrapped)))
    return calls


def test_anonymous_gets_sign_in_required_without_rest(monkeypatch):
    calls = mock_rest(monkeypatch, lambda r: httpx.Response(500))
    assert widget_tools.propose_widget("power of a point", ctx(None))["error"] == "SIGN_IN_REQUIRED"
    assert widget_tools.format_math("PA*PB", ctx(None))["error"] == "SIGN_IN_REQUIRED"
    assert calls == []


def test_propose_widget_returns_fenced_block_never_stores(monkeypatch):
    calls = mock_rest(monkeypatch, lambda r: httpx.Response(200, json={
        "spec": SPEC, "strategy": "GEOMETRY", "validation": {"valid": True, "errors": [], "warnings": []}}))
    out = widget_tools.propose_widget("power of a point", ctx(), '{"steps": ["a"]}')
    body = json.loads(calls[0].content)
    assert calls[0].url.path == "/v1/widgets/generate"
    assert calls[0].headers["authorization"] == "Bearer tok"
    assert body == {"intent": "power of a point", "context": {"steps": ["a"]}}  # no store flag
    assert out["markdown_block"].startswith("```widget\n") and out["markdown_block"].endswith("\n```")
    assert json.loads(out["markdown_block"][10:-4]) == SPEC


def test_propose_widget_rejects_bad_context_and_invalid_specs(monkeypatch):
    mock_rest(monkeypatch, lambda r: httpx.Response(200, json={
        "spec": SPEC, "validation": {"valid": False, "errors": ["dangling ref"]}}))
    assert widget_tools.propose_widget("x", ctx(), "[1]")["error"] == "BAD_CONTEXT_JSON"
    assert widget_tools.propose_widget("x", ctx(), "{oops")["error"] == "BAD_CONTEXT_JSON"
    assert widget_tools.propose_widget("  ", ctx())["error"] == "EMPTY_INTENT"
    assert widget_tools.propose_widget("x", ctx())["error"] == "WIDGET_INVALID"


def test_format_math_is_deterministic_only(monkeypatch):
    calls = mock_rest(monkeypatch, lambda r: httpx.Response(200, json={
        "input": "PA*PB", "formatted": "$PA \\\\cdot PB$", "engine": "deterministic", "warnings": []}))
    out = widget_tools.format_math("PA*PB", ctx())
    assert json.loads(calls[0].content)["mode"] == "deterministic"
    assert out["changed"] is True and out["warnings"] == []


def test_rest_errors_are_passed_through(monkeypatch):
    mock_rest(monkeypatch, lambda r: httpx.Response(401, json={"detail": "nope"}))
    assert widget_tools.propose_widget("power of a point", ctx())["error"] == "HTTP_401"
