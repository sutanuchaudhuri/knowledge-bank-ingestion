from types import SimpleNamespace
from uuid import uuid4

import httpx
from agents.mathbank_tutor.tools import attempt_media_tools, step_runtime_tools


def test_media_context_tools_are_authenticated_read_only(monkeypatch):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(200, json={"status": "APPROVED", "evidence_ids": ["e1"]})

    monkeypatch.setattr(
        step_runtime_tools,
        "_client",
        lambda: httpx.Client(
            base_url="http://rest", transport=httpx.MockTransport(handle)
        ),
    )
    ctx = SimpleNamespace(
        state={"temp:student_token": "synthetic"}, function_call_id="c1"
    )
    sid, aid, step = str(uuid4()), str(uuid4()), str(uuid4())
    assert attempt_media_tools.get_multimodal_attempt(sid, ctx)["status"] == "APPROVED"
    assert attempt_media_tools.get_multimodal_step_assessment(aid, step, ctx)[
        "evidence_ids"
    ] == ["e1"]
    assert [request.method for request in calls] == ["GET", "GET"]
    assert calls[0].url.path == f"/v1/attempt-media/submissions/{sid}"
    assert (
        calls[1].url.path == f"/v1/attempt-media/attempts/{aid}/steps/{step}/assessment"
    )
    assert calls[0].headers["authorization"] == "Bearer synthetic"


def test_media_context_tools_do_not_request_data_for_anonymous_learner(monkeypatch):
    def unexpected():
        raise AssertionError("No request is allowed without a student token")

    monkeypatch.setattr(step_runtime_tools, "_client", unexpected)
    ctx = SimpleNamespace(state={})
    assert (
        attempt_media_tools.get_multimodal_attempt(str(uuid4()), ctx)["error"]
        == "SIGN_IN_REQUIRED"
    )
