"""Tests for the agent_demo subprocess/stdio integration and the MCP-to-OpenAI tool
schema adapter. The subprocess-spawn test is cheap and always runs; the full
LLM-driven test is opt-in (costs a real OpenAI call) via AGENT_DEMO_LIVE_LLM=1, matching
this repo's established opt-in-live-test convention (e.g. mathbank-rest's
MATHBANK_LIVE_QUIZ_TEST=1).
"""
from __future__ import annotations

import os

import pytest
from fastmcp import Client
from fastmcp.client.transports import PythonStdioTransport

from agent_demo.agent import SERVER_ENTRYPOINT, _mcp_tool_to_openai_tool, run_agent


async def test_server_entrypoint_spawns_and_lists_tools_over_stdio():
    """Proves the server is launchable as a genuine subprocess over stdio — the actual
    mechanism any MCP host (or this agent demo) uses — not just importable in-process."""
    transport = PythonStdioTransport(script_path=SERVER_ENTRYPOINT)
    async with Client(transport) as client:
        tools = await client.list_tools()
        assert {"list_competitions", "search_problems"}.issubset({t.name for t in tools})


async def test_mcp_tool_to_openai_tool_shape():
    transport = PythonStdioTransport(script_path=SERVER_ENTRYPOINT)
    async with Client(transport) as client:
        tools = await client.list_tools()
        search_tool = next(t for t in tools if t.name == "search_problems")
        openai_tool = _mcp_tool_to_openai_tool(search_tool)
        assert openai_tool["type"] == "function"
        assert openai_tool["function"]["name"] == "search_problems"
        assert "query" in openai_tool["function"]["parameters"]["properties"]


@pytest.mark.skipif(
    os.environ.get("AGENT_DEMO_LIVE_LLM") != "1",
    reason="Opt-in: costs a real OpenAI call. Set AGENT_DEMO_LIVE_LLM=1 to run.",
)
async def test_live_agent_answers_a_real_question_using_real_tool_data():
    answer = await run_agent(
        "Give me the canonical_code of any one real AMC10 problem from the year 2000."
    )
    assert "AMC10_2000" in answer
