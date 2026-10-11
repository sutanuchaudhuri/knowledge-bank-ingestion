"""A minimal, real "other agent" demonstrating the whole point of requirements/49's
"parallel MCP server for other agents to fetch competition specific data": an
independent LLM-driven agent — NOT `mathbank-agent`, not even in the same framework —
that spawns `mathbank-mcp-competitions` as a subprocess over stdio (the standard way an
MCP host launches a local MCP server) and lets OpenAI's function-calling loop decide
which tools to call to answer a student's question.

This purposely does NOT reuse any mathbank-agent code — the whole point is proving the
MCP server is usable by *any* agent stack, not just the existing Google ADK tutor.

Run with: `python -m agent_demo.agent "<question>"` (requires `mathbank-rest`'s dev
server running, and OPENAI_API_KEY set — see .env.example).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport
from openai import AsyncOpenAI

from mathbank_mcp_competitions.config import get_settings

SERVER_ENTRYPOINT = Path(__file__).resolve().parents[1] / "src/mathbank_mcp_competitions/__main__.py"


def _mcp_tool_to_openai_tool(tool) -> dict:
    """Translates one MCP tool definition into an OpenAI Chat Completions function-tool
    schema — the standard, minimal adapter any non-MCP-native agent framework needs,
    since OpenAI's plain function-calling API doesn't speak MCP's tool schema directly."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }


async def run_agent(question: str, *, model: str = "gpt-4.1-mini", max_turns: int = 6) -> str:
    settings = get_settings()
    transport = PythonStdioTransport(script_path=SERVER_ENTRYPOINT)

    async with Client(transport) as mcp_client:
        mcp_tools = await mcp_client.list_tools()
        # Exclude the app-only/UI tools from this plain-text agent's tool list — a
        # text-only agent has no way to render a Prefab UI, so it should only ever see
        # the data-fetch tools (requirements/49, 01_FASTMCP_DECISION_ARCHITECTURE.md §5
        # — "visibility is not security," but it's still correct UX to not offer a tool
        # whose result this particular client can't do anything useful with).
        text_tools = [t for t in mcp_tools if t.name not in {"load_competition_problems", "open_competition_explorer"}]
        openai_tools = [_mcp_tool_to_openai_tool(t) for t in text_tools]

        openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research assistant with tools to query MathBank's "
                    "competition math corpus (AMC/AIME/HMMT/etc.) over MCP. Use the "
                    "tools to find real, specific data before answering — never invent "
                    "a problem or competition that the tools don't confirm exists."
                ),
            },
            {"role": "user", "content": question},
        ]

        for _ in range(max_turns):
            response = await openai_client.chat.completions.create(
                model=model, messages=messages, tools=openai_tools,
            )
            choice = response.choices[0]
            messages.append(choice.message.model_dump(exclude_none=True))

            if not choice.message.tool_calls:
                return choice.message.content or ""

            for tool_call in choice.message.tool_calls:
                args = json.loads(tool_call.function.arguments or "{}")
                result = await mcp_client.call_tool(tool_call.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result.data)[:4000],
                })

    return "(reached max_turns without a final answer)"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else (
        "Find a real AMC10 geometry problem about triangle area and tell me its canonical "
        "code and official answer."
    )
    answer = asyncio.run(run_agent(question))
    print(answer)


if __name__ == "__main__":
    main()
