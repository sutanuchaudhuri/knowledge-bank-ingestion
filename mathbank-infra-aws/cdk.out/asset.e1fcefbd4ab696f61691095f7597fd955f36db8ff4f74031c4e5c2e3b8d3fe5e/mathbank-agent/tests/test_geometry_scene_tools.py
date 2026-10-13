import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

PATH=Path(__file__).resolve().parents[1]/"agents/mathbank_tutor/tools/geometry_scene_tools.py"
spec=importlib.util.spec_from_file_location("geometry_scene_tools",PATH)
tools=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tools)


def context(token="test-token"):
    return SimpleNamespace(state={"temp:student_token":token} if token else {},function_call_id="call-one")


def test_anonymous_never_invokes_paid_geometry(monkeypatch):
    monkeypatch.setattr(tools,"_client",lambda: (_ for _ in ()).throw(AssertionError("no request")))
    assert tools.generate_geometry_scene("ABCD","Focus",context(None))["error"]=="SIGN_IN_REQUIRED"


def test_authenticated_scene_block_and_temp_credential(monkeypatch):
    requests=[]
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={
            "scene_id":"scene_one","version":1,"caption":"Focus A1","current_math_step":"A1",
            "validation":{"valid":True},
        })
    monkeypatch.setattr(tools,"_client",lambda:httpx.Client(base_url="http://rest",
                        transport=httpx.MockTransport(handler)))
    ctx=context()
    result=tools.generate_geometry_scene("ABCD","Understand A1",ctx,current_math_step="A1")
    assert result["markdown_block"].startswith("```geometry-scene\n")
    assert requests[0].headers["authorization"]=="Bearer test-token"
    assert requests[0].headers["idempotency-key"]=="geometry:call-one"
    assert json.loads(requests[0].content)["goal"]=="Understand A1"
    assert ctx.state["geometry:last_scene"]=={"scene_id":"scene_one","version":1}
    assert "test-token" not in result["markdown_block"]


def test_invalid_context_explicit_error():
    result=tools.generate_geometry_scene("ABCD","Focus",context(),context_json='{"not":"list"}')
    assert result["error"]=="INVALID_GEOMETRY_REQUEST"


def test_network_error_is_explicit(monkeypatch):
    def handler(request):
        raise httpx.ConnectError("offline",request=request)
    monkeypatch.setattr(tools,"_client",lambda:httpx.Client(base_url="http://rest",
                        transport=httpx.MockTransport(handler)))
    assert tools.generate_geometry_scene("ABCD","Focus",context())["error"]=="GEOMETRY_TRANSPORT_ERROR"


@pytest.mark.parametrize("payload", [
    [],
    {"validation": {"valid": "true"}},
    {"validation": {"valid": True}, "scene_id": "../invalid", "version": 0,
     "caption": "Focus", "current_math_step": ""},
    {"validation": {"valid": True}, "scene_id": "scene_one", "version": True,
     "caption": "Focus", "current_math_step": ""},
    {"validation": {"valid": True}, "scene_id": "scene_one", "version": 0,
     "caption": None, "current_math_step": ""},
])
def test_invalid_accepted_response_never_mutates_state(monkeypatch, payload):
    monkeypatch.setattr(tools, "_client", lambda: httpx.Client(
        base_url="http://rest", transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload))))
    ctx = context()
    before = dict(ctx.state)
    result = tools.generate_geometry_scene("ABCD", "Focus", ctx)
    assert result["error"] in {"GEOMETRY_RESPONSE_INVALID", "GEOMETRY_NOT_ACCEPTED"}
    assert ctx.state == before
    assert "markdown_block" not in result


def test_failed_interpretation_preserves_safe_run_reference(monkeypatch):
    run_id = "failed_" + "a" * 32
    monkeypatch.setattr(tools, "_client", lambda: httpx.Client(
        base_url="http://rest", transport=httpx.MockTransport(
            lambda request: httpx.Response(422, json={"detail": {
                "code": "GEOMETRY_PLAN_EXHAUSTED", "message": "No accepted candidate.",
                "run_id": run_id}}))))
    ctx = context()
    result = tools.generate_geometry_scene("ABCD", "Focus", ctx)
    assert result["error"] == "GEOMETRY_PLAN_EXHAUSTED"
    assert result["run_id"] == run_id
    assert "geometry:last_scene" not in ctx.state
