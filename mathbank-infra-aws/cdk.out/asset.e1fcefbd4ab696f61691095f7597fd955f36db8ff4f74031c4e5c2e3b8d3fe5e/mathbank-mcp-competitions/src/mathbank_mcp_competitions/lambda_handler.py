"""AWS Lambda entrypoint for `mathbank-mcp-competitions` (requirements/62 §4.5,
requirements/63). This is the **new, separately-deployed HTTP Lambda instance** of this
server — distinct from its *existing* stdio-subprocess use bundled into
`mathbank-manim-studio`/`agent_demo` (unaffected by this file).

`FastMCP.run(transport="http", ...)` (the local dev entrypoint, `__main__.py`) blocks
forever running its own Uvicorn server — not usable in Lambda. `FastMCP.http_app(...)`
instead returns a plain ASGI `Starlette` app, which Mangum can wrap exactly like any
other ASGI app (`mathbank-rest`'s own pattern).

`stateless_http=True` is mandatory here (doc 62 §4.5): the MCP streamable-HTTP
transport's default *stateful* mode expects a client to re-send a session ID against
the *same* server process across a tool-call sequence, but Lambda offers no such
process affinity across requests (a 2nd request may hit a cold *or* a different warm
execution environment) — stateless mode creates a fresh in-memory session per request,
which is the only mode compatible with Lambda's request model.

`Mangum(app, lifespan="on")` (not Mangum's default `"auto"`) is also required: FastMCP's
Starlette app relies on its ASGI lifespan (startup/shutdown) to initialise its session
manager task group; Mangum's `"auto"` heuristic does not reliably detect this need for
non-API-Gateway event sources, so lifespan handling is forced on explicitly.
"""
from __future__ import annotations

from mangum import Mangum

from mathbank_mcp_competitions.server import mcp

app = mcp.http_app(stateless_http=True)

handler = Mangum(app, lifespan="on")
