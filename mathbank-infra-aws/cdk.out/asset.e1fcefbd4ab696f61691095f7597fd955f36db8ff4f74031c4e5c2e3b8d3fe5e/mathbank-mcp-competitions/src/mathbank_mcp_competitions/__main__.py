"""Entrypoint: `python -m mathbank_mcp_competitions`.

Runs the server over stdio (the default — what most MCP hosts, and this project's own
agent_demo, use to launch it as a subprocess) or over streamable HTTP (`MCP_TRANSPORT=http`
in .env) for other agents/services to connect to as a standing network server.
"""
from __future__ import annotations

from mathbank_mcp_competitions.config import get_settings
from mathbank_mcp_competitions.server import mcp


def main() -> None:
    settings = get_settings()
    if settings.mcp_transport == "http":
        mcp.run(transport="http", port=settings.mcp_http_port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
