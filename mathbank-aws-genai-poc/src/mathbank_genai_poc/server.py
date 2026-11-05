"""Local browser front end: FastAPI serves the page and bridges one WebSocket to one live BidiAgent session.

Browser -> server: binary frames of mono PCM16 at ``input_sample_rate``; JSON ``{"type":"text","text":...}`` or
``{"type":"stop"}``. Server -> browser: JSON events (``ready``, ``audio``, ``transcript``, ``barge_in``, ``tool``,
``sources``, ``usage``, ``status``, ``ended``, ``error``).

Guardrails: loopback bind, exact same-origin WebSocket check (a cross-site page cannot spend the budget), one live
session at a time, bounded frame/text sizes, a per-session time limit and the cumulative audio budget ledger.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from strands.bidi.types import events as ev
from strands.bidi.types.media import AudioDelta

from mathbank_genai_poc.budget import AudioBudget, BudgetExhausted
from mathbank_genai_poc.config import PROJECT_ROOT, Settings, get_settings
from mathbank_genai_poc.knowledge import KnowledgeBase

LOG = logging.getLogger("mathbank_genai_poc")
STATIC = PROJECT_ROOT / "src" / "mathbank_genai_poc" / "static"
MAX_AUDIO_FRAME = 64 * 1024
MAX_TEXT = 500


def to_client(event: Any) -> dict | None:
    """Translate one Strands bidi output event into a small browser message (``None`` = not shown)."""
    if isinstance(event, ev.BidiAudioDeltaEvent):
        return {"type": "audio", "audio": event.audio, "rate": event.sample_rate}
    if isinstance(event, ev.BidiTranscriptDeltaEvent):
        return {"type": "transcript", "id": event.content_id, "role": event.role, "delta": event.delta}
    if isinstance(event, ev.BidiTranscriptBlockEvent):
        return {"type": "transcript", "id": event.content_id, "role": event.role, "text": event.transcript, "final": True}
    if isinstance(event, ev.BidiTranscriptStopEvent):
        return {"type": "transcript", "id": event.content_id, "role": event.role, "final": True}
    if isinstance(event, ev.BidiBargeInEvent):
        return {"type": "barge_in"}
    if isinstance(event, ev.BidiToolUseBlocksEvent):
        return {"type": "tool", "calls": [{"name": t.get("name"), "input": t.get("input")} for t in event.tool_uses]}
    if isinstance(event, ev.BidiUsageEvent):
        return {"type": "usage", "input_tokens": event.input_tokens, "output_tokens": event.output_tokens}
    if isinstance(event, ev.BidiResponseStartEvent):
        return {"type": "status", "state": "speaking"}
    if isinstance(event, ev.BidiResponseStopEvent):
        return {"type": "status", "state": "listening"}
    if isinstance(event, ev.BidiConnectionStartEvent):
        return {"type": "status", "state": "connected"}
    if isinstance(event, ev.BidiConnectionRestartEvent):
        return {"type": "status", "state": "reconnecting"}
    return None


def create_app(settings: Settings | None = None, *, agent_factory: Callable[[], Any] | None = None,
               budget: AudioBudget | None = None) -> FastAPI:
    settings = settings or get_settings()
    budget = budget or AudioBudget(settings.budget_ledger, settings.audio_budget_seconds)
    kb = KnowledgeBase(settings)
    if agent_factory is None:
        from mathbank_genai_poc.agent import build_agent

        def agent_factory() -> Any:
            return build_agent(settings, kb)

    allowed_origins = {f"http://{settings.host}:{settings.port}", f"http://localhost:{settings.port}",
                       f"http://127.0.0.1:{settings.port}"}
    session_lock = asyncio.Lock()
    app = FastAPI(title="MathBank voice tutor POC", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "model": settings.sonic_model_id, "sonic_region": settings.sonic_region,
                "vector_bucket": settings.vector_bucket, "content_table": settings.content_table,
                "data_region": settings.data_region, "budget_remaining_s": round(budget.remaining(), 1),
                "session_active": session_lock.locked()}

    @app.websocket("/ws")
    async def live(ws: WebSocket) -> None:
        if ws.headers.get("origin") not in allowed_origins:
            await ws.close(code=1008, reason="origin not allowed")
            return
        await ws.accept()
        if session_lock.locked():
            await ws.send_json({"type": "error", "message": "Another live session is already running."})
            await ws.close(code=1013)
            return
        async with session_lock:
            try:
                seconds = budget.grant(settings.max_session_seconds)
            except BudgetExhausted as error:
                await ws.send_json({"type": "error", "message": str(error)})
                await ws.close(code=1008)
                return
            await run_session(ws, agent_factory(), seconds)

    async def run_session(ws: WebSocket, agent: Any, seconds: float) -> None:
        send_lock = asyncio.Lock()

        async def send(message: dict) -> None:
            async with send_lock:
                await ws.send_json(message)

        async def on_sources(payload: dict) -> None:
            await send({"type": "sources", **payload})

        started = time.monotonic()
        reason = "ended"
        try:
            await agent.start(invocation_state={"on_sources": on_sources})
        except Exception as error:  # noqa: BLE001
            LOG.warning("agent start failed: %s", type(error).__name__)
            budget.record(time.monotonic() - started, "start_failed")
            await send({"type": "error", "message": "Could not connect to the voice model. Check AWS access."})
            await ws.close()
            return
        await send({"type": "ready", "seconds": round(seconds), "model": settings.sonic_model_id,
                    "rate_in": settings.input_sample_rate, "rate_out": settings.output_sample_rate})

        async def pump_in() -> str:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    return "client_closed"
                if (data := message.get("bytes")) is not None:
                    if not data or len(data) > MAX_AUDIO_FRAME or len(data) % 2:
                        continue
                    await agent.send(AudioDelta(format="pcm", source={"bytes": data}))
                elif (raw := message.get("text")) is not None:
                    try:
                        body = json.loads(raw)
                    except ValueError:
                        continue
                    if body.get("type") == "stop":
                        return "stopped"
                    text = str(body.get("text", "")).strip()[:MAX_TEXT]
                    if body.get("type") == "text" and text:
                        await agent.send(text)

        async def pump_out() -> str:
            async for event in agent.receive():
                if (message := to_client(event)) is not None:
                    await send(message)
            return "model_closed"

        async def limit() -> str:
            await asyncio.sleep(seconds)
            return "time_limit"

        tasks = [asyncio.create_task(coro) for coro in (pump_in(), pump_out(), limit())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finished = done.pop()
            if (failure := finished.exception()) is not None:
                LOG.warning("live session failed: %s", type(failure).__name__)
                reason = "client_closed" if isinstance(failure, WebSocketDisconnect) else "error"
                if reason == "error":
                    await send({"type": "error", "message": "The live session failed. Start a new session to retry."})
            else:
                reason = finished.result()
        except Exception:  # noqa: BLE001 - the socket may already be gone
            reason = "error"
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            try:
                await agent.stop()
            except Exception as error:  # noqa: BLE001
                LOG.warning("agent stop failed: %s", type(error).__name__)
            used = time.monotonic() - started
            total = budget.record(used, reason)
            try:
                await send({"type": "ended", "reason": reason, "seconds": round(used, 1),
                            "budget_remaining_s": round(max(0.0, budget.limit - total), 1)})
                await ws.close()
            except Exception:  # noqa: BLE001
                LOG.debug("client socket already closed")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(app, host=settings.host, port=settings.port, proxy_headers=False, ws_max_size=MAX_AUDIO_FRAME * 2)


if __name__ == "__main__":
    main()
