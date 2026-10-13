"""One-off manual smoke test for the mathbank_tutor agent (not part of CI).

Run with mathbank-rest already serving on MATHBANK_REST_BASE_URL and
OPENAI_API_KEY set:

    .venv/bin/python scripts/smoke_test.py "What are the recent questions on combinatorics?"
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from mathbank_tutor.agent import root_agent


async def main(query: str) -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(app_name="mathbank_tutor", user_id="smoke-test", session_id="s1")
    runner = Runner(agent=root_agent, app_name="mathbank_tutor", session_service=session_service)

    message = types.Content(role="user", parts=[types.Part(text=query)])
    async for event in runner.run_async(user_id="smoke-test", session_id="s1", new_message=message):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(f"[tool call] {part.function_call.name}({part.function_call.args})")
                if part.function_response:
                    print(f"[tool result] {part.function_response.name} -> {str(part.function_response.response)[:300]}")
                if part.text:
                    print(f"[{event.author}] {part.text}")


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "What are the recent questions on combinatorics?"
    asyncio.run(main(query))
