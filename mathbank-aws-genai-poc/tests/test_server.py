import asyncio
import base64

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from strands.bidi.types import events as ev
from strands.bidi.types.media import AudioDelta

from mathbank_genai_poc.budget import AudioBudget
from mathbank_genai_poc.config import Settings
from mathbank_genai_poc.server import create_app, to_client

ORIGIN = {"origin": "http://127.0.0.1:8040"}


class FakeAgent:
    def __init__(self, script=(), fail_start=False):
        self.script, self.fail_start = list(script), fail_start
        self.sent, self.stopped, self.state = [], False, None
        self.done = asyncio.Event()

    async def start(self, invocation_state=None):
        if self.fail_start:
            raise RuntimeError("AccessDeniedException: private detail")
        self.state = invocation_state

    async def send(self, data):
        self.sent.append(data)
        if data == "close":
            self.done.set()

    async def receive(self):
        for item in self.script:
            if callable(item):
                await item(self.state)
            else:
                yield item
        await self.done.wait()

    async def stop(self):
        self.stopped = True
        self.done.set()


def make(tmp_path, agent, **overrides):
    settings = Settings(max_session_seconds=overrides.pop("seconds", 30), budget_ledger=tmp_path / "u.json",
                        audio_budget_seconds=overrides.pop("budget", 300))
    budget = AudioBudget(settings.budget_ledger, settings.audio_budget_seconds)
    return TestClient(create_app(settings, agent_factory=lambda: agent, budget=budget)), budget


def drain(socket):
    """Receive until the server closes the socket."""
    messages = []
    while True:
        try:
            messages.append(socket.receive_json())
        except WebSocketDisconnect:
            return messages


def test_full_session_forwards_audio_text_and_maps_events(tmp_path):
    async def sources(state):
        await state["on_sources"]({"topic": "inversion", "grounded": True, "concepts": [], "practice_problems": []})

    audio = base64.b64encode(b"\x01\x00" * 4).decode()
    agent = FakeAgent([
        ev.BidiConnectionStartEvent(connection_id="c", model="m"),
        ev.BidiTranscriptDeltaEvent(delta="Hel", role="assistant", content_id="t1"),
        ev.BidiAudioDeltaEvent(audio=audio, format="pcm", sample_rate=24000, channels=1, content_id="a1"),
        ev.BidiToolUseBlocksEvent(tool_uses=[{"toolUseId": "1", "name": "search_math_topic", "input": {"topic": "x"}}]),
        sources,
        ev.BidiBargeInEvent(),
    ])
    client, budget = make(tmp_path, agent)
    with client.websocket_connect("/ws", headers=ORIGIN) as socket:
        assert socket.receive_json()["type"] == "ready"
        socket.send_bytes(b"\x00\x01" * 320)
        socket.send_bytes(b"\x00")                      # odd length: dropped
        socket.send_text('{"type":"text","text":"  teach me inversion  "}')
        types = [socket.receive_json()["type"] for _ in range(6)]
        socket.send_text('{"type":"stop"}')
        tail = drain(socket)
    assert types == ["status", "transcript", "audio", "tool", "sources", "barge_in"]
    assert tail[-1]["type"] == "ended" and tail[-1]["reason"] == "stopped"
    assert isinstance(agent.sent[0], AudioDelta) and agent.sent[0].source["bytes"] == b"\x00\x01" * 320
    assert agent.sent[1:] == ["teach me inversion"]
    assert agent.stopped and budget._read()["sessions"][0]["reason"] == "stopped"


def test_cross_origin_socket_is_refused_before_any_model_use(tmp_path):
    agent = FakeAgent()
    client, budget = make(tmp_path, agent)
    with (pytest.raises(WebSocketDisconnect) as closed,
          client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as socket):
        socket.receive_json()
    assert closed.value.code == 1008
    assert agent.state is None and budget.used() == 0


def test_time_limit_ends_session_and_is_recorded(tmp_path):
    agent = FakeAgent()
    client, budget = make(tmp_path, agent, seconds=10)
    from mathbank_genai_poc import server

    real_sleep = asyncio.sleep

    async def fast_sleep(seconds):
        await real_sleep(0.05 if seconds >= 10 else seconds)

    server.asyncio.sleep = fast_sleep
    try:
        with client.websocket_connect("/ws", headers=ORIGIN) as socket:
            assert socket.receive_json()["type"] == "ready"
            messages = drain(socket)
    finally:
        server.asyncio.sleep = real_sleep
    assert messages[-1]["reason"] == "time_limit" and agent.stopped
    assert budget._read()["sessions"][0]["reason"] == "time_limit"


def test_exhausted_budget_refuses_new_session(tmp_path):
    agent = FakeAgent()
    client, _ = make(tmp_path, agent, budget=5)
    with client.websocket_connect("/ws", headers=ORIGIN) as socket:
        message = socket.receive_json()
    assert message["type"] == "error" and "budget" in message["message"]
    assert agent.state is None


def test_start_failure_is_sanitized_and_recorded(tmp_path):
    client, budget = make(tmp_path, FakeAgent(fail_start=True))
    with client.websocket_connect("/ws", headers=ORIGIN) as socket:
        message = socket.receive_json()
    assert message["type"] == "error" and "private" not in message["message"]
    assert budget._read()["sessions"][0]["reason"] == "start_failed"


def test_health_reports_targets_without_aws_calls(tmp_path):
    client, _ = make(tmp_path, FakeAgent())
    body = client.get("/health").json()
    assert body["model"] == "amazon.nova-2-5-sonic" and body["vector_bucket"] == "mathbank-vectors-dev"
    assert body["budget_remaining_s"] == 300 and body["session_active"] is False
    assert "no-store" in client.get("/").headers["cache-control"]


def test_unmapped_events_are_dropped():
    assert to_client(ev.BidiAudioStartEvent(content_id="x")) is None
    assert to_client(ev.BidiUsageEvent(input_tokens=1, output_tokens=2, total_tokens=3))["output_tokens"] == 2
