"""Step-runtime agent tools: auth via temp state, server-owned versions, idempotency, mode mapping."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import httpx

path = Path(__file__).resolve().parents[1] / "agents/mathbank_tutor/tools/step_runtime_tools.py"
spec = spec_from_file_location("step_runtime_tools", path)
tools = module_from_spec(spec)
spec.loader.exec_module(tools)

RUNTIME = {
    "attempt": {"solve_attempt_id": "att-1", "problem_code": "PRASOLOV_PGV1_3_33", "statement_text": "Prove...",
                "status": "IN_PROGRESS", "current_mode": "SOLVING", "state_version": 7},
    "current_step": {"solution_step_id": "s2", "step_type": "APPLY", "goal": "Apply", "skill_name": "Power",
                     "help_level_used": 0, "state": "PRESENTED"},
    "recovery": None, "progress": {"total_steps": 3, "completed_steps": 1},
    "timeline": [{"global_step_index": 1, "state": "COMPLETED_INDEPENDENTLY", "reference_text": "Step one."},
                 {"global_step_index": 2, "state": "PRESENTED"}],
}


def ctx(token="tok", user="stu-1", call="call-9"):
    return SimpleNamespace(state={"temp:student_token": token} if token else {}, user_id=user,
                           function_call_id=call)


def mock_rest(monkeypatch, handler):
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    monkeypatch.setattr(tools, "_client", lambda: httpx.Client(base_url="http://rest",
                                                               transport=httpx.MockTransport(wrapped)))
    return calls


def test_anonymous_chat_gets_sign_in_required_without_calling_rest(monkeypatch):
    calls = mock_rest(monkeypatch, lambda r: httpx.Response(500))
    assert tools.get_attempt_runtime("att-1", ctx(token=None))["error"] == "SIGN_IN_REQUIRED"
    assert tools.start_step_attempt("X", ctx(token="tok", user="anonymous"))["error"] == "SIGN_IN_REQUIRED"
    assert calls == []


def test_runtime_packet_is_compact_and_mode_mapped(monkeypatch):
    calls = mock_rest(monkeypatch, lambda r: httpx.Response(200, json=RUNTIME))
    packet = tools.get_attempt_runtime("att-1", ctx())
    assert calls[0].headers["authorization"] == "Bearer tok"
    assert calls[0].url.path == "/v1/attempts/att-1/runtime"
    assert packet["response_mode"] == "ORIGINAL_PROBLEM" and packet["state_version"] == 7
    assert packet["completed_steps"] == [{"global_step_index": 1, "state": "COMPLETED_INDEPENDENTLY",
                                          "reference_text": "Step one."}]
    assert "reference_text" not in packet["current_step"]


def test_response_modes():
    def rt(mode, status="IN_PROGRESS", help_level=0, recovery=None):
        return {"attempt": {"current_mode": mode, "status": status},
                "current_step": {"help_level_used": help_level}, "recovery": recovery}
    assert tools.response_mode(rt("SOLVING", help_level=2)) == "STEP_HINT"
    assert tools.response_mode(rt("DIAGNOSING")) == "DIAGNOSTIC"
    assert tools.response_mode(rt("RECOVERY", recovery={"status": "ACTIVE"})) == "RECOVERY"
    assert tools.response_mode(rt("RECOVERY", recovery={"status": "COMPLETED"})) == "RETURN_TO_STEP"
    assert tools.response_mode(rt("SOLVING", status="COMPLETED")) == "COMPLETED"


def test_mutations_use_server_state_version_and_call_id_idempotency(monkeypatch):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=RUNTIME)
        return httpx.Response(200, json={"evaluation_status": "EVALUATED"})

    calls = mock_rest(monkeypatch, handler)
    out = tools.submit_step_response("att-1", "PRASOLOV/3.33/s2", "OA·OB = OT²", ctx())
    post = next(c for c in calls if c.method == "POST")
    assert post.url.raw_path.decode().endswith("/steps/PRASOLOV%2F3.33%2Fs2/responses")
    assert post.headers["idempotency-key"] == "agent:respond:call-9"
    import json
    assert json.loads(post.content) == {"response_text": "OA·OB = OT²", "state_version": 7, "evaluate": True}
    assert out["result"]["evaluation_status"] == "EVALUATED" and out["runtime"]["state_version"] == 7


def test_rest_errors_are_returned_as_codes(monkeypatch):
    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=RUNTIME)
        return httpx.Response(409, json={"detail": {"code": "NO_RECOVERY_MATERIAL", "message": "none"}})

    mock_rest(monkeypatch, handler)
    out = tools.start_recovery_plan("att-1", ctx(), gap_diagnosis_id="g-1")
    assert out == {"error": "NO_RECOVERY_MATERIAL", "message": "none", "status": 409}


def test_recovery_answer_body_only_carries_supplied_fields(monkeypatch):
    bodies = []

    def handler(request):
        if request.method == "GET":
            return httpx.Response(200, json=RUNTIME)
        import json
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    mock_rest(monkeypatch, handler)
    tools.answer_recovery_item("att-1", "plan-1", "item-1", ctx(), choice_index=2)
    tools.answer_recovery_item("att-1", "plan-1", "item-1", ctx(), acknowledged=True)
    assert bodies == [{"state_version": 7, "choice_index": 2}, {"state_version": 7, "acknowledged": True}]


def test_agent_registers_all_step_tools():
    names = {f.__name__ for f in tools.STEP_RUNTIME_TOOLS}
    assert {"get_attempt_runtime", "submit_step_response", "request_step_hint", "diagnose_step_gap",
            "start_recovery_plan", "answer_recovery_item", "resume_original_step"} <= names


def test_temp_token_is_never_persisted_in_the_session_store(tmp_path):
    import asyncio
    from google.adk.events import Event, EventActions
    from google.adk.sessions import DatabaseSessionService

    async def run():
        service = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{tmp_path / 's.db'}")
        session = await service.create_session(app_name="mathbank_tutor", user_id="stu-1")
        await service.append_event(session, Event(author="user", invocation_id="i1",
                                                  actions=EventActions(state_delta={tools.TOKEN_STATE_KEY: "secret",
                                                                                    "visible": 1})))
        assert session.state.get(tools.TOKEN_STATE_KEY) == "secret"  # usable during the invocation
        reloaded = await service.get_session(app_name="mathbank_tutor", user_id="stu-1", session_id=session.id)
        assert reloaded.state.get("visible") == 1
        assert tools.TOKEN_STATE_KEY not in reloaded.state
        assert all(tools.TOKEN_STATE_KEY not in (e.actions.state_delta or {}) for e in reloaded.events)

    asyncio.run(run())
