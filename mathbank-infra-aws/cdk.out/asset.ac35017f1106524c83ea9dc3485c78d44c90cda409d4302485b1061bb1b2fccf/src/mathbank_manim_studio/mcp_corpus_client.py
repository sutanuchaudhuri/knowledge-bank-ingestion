"""Spawns `mathbank-mcp-competitions` (requirements/49) as a real subprocess over stdio
and exposes its tools to an OpenAI-style tool-calling loop — the exact pattern that
project's own `agent_demo/agent.py` uses, reused here so the research agent (requirements/
60) is the first *second* real consumer of that MCP server, not a one-off demo.
"""
from __future__ import annotations

from pathlib import Path

from fastmcp.client.transports import PythonStdioTransport

from mathbank_manim_studio.config import get_settings


def competitions_transport() -> PythonStdioTransport:
    settings = get_settings()
    script_path = Path(settings.mcp_competitions_script)
    python_cmd = settings.mcp_competitions_python
    return PythonStdioTransport(script_path=script_path, python_cmd=python_cmd)


def mcp_tool_to_openai_tool(tool) -> dict:
    """Same minimal MCP-to-OpenAI adapter as mathbank-mcp-competitions/agent_demo/agent.py."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema or {"type": "object", "properties": {}},
        },
    }
