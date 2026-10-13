"""Strands MCP tool integration (requirements/64 §1, §3) — the generator agent's
corpus-grounding tools come from the already-deployed `mathbank-mcp-competitions`
Function URL, not a new or forked MCP server. A context manager, not a long-lived
singleton: each generation request gets its own short-lived MCP session (`start()`/
`stop()`), matching `MCPClient`'s own documented lifecycle and avoiding a stale
connection surviving across a Lambda cold start boundary.
"""
from __future__ import annotations

from contextlib import contextmanager

from strands.tools.mcp.mcp_client import MCPClient

from mathbank_exam_agent.config import get_settings


@contextmanager
def competitions_session():
    """Yields the raw `MCPClient` itself (not just its Strands tool list) — callers
    need both `client.list_tools_sync()` (for `Agent(tools=...)`) and direct
    `client.call_tool_sync(...)` access (for exam_service.py's own topic-resolution
    lookup, requirements/64 §5, which isn't an LLM-reasoning step and shouldn't burn a
    model call just to call one fixed tool)."""
    client = MCPClient(url=get_settings().mcp_competitions_url)
    client.start()
    try:
        yield client
    finally:
        client.stop(None, None, None)

