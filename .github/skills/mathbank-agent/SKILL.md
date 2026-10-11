---
name: mathbank-agent
description: 'Working in mathbank-agent: the Google ADK + OpenAI tutoring agent that calls mathbank-rest as tools. Use when editing a tool module under agents/mathbank_tutor/tools/, agent.py, or server.py.'
argument-hint: 'Optional: tool module name to focus on'
---

# mathbank-agent conventions

Full detail: [mathbank-agent/README.md](../../../mathbank-agent/README.md).

## Non-negotiables

- This agent **never** touches Postgres/Neo4j directly — every tool call goes through
  `mathbank-rest` over HTTP. Do not add a direct database driver here.
- `propose_widget` returns a deterministic, validated, whitelisted spec — never generate or return
  executable code/arbitrary HTML from a tool; that's a deliberately safer boundary than letting a
  model write its own UI (see `mathbank-widgets`/doc 27).
- `format_math`'s deterministic mode is the default; the paid agentic formatter is reserved for the
  learner's own explicit button, not invoked automatically by this agent.
- Before adding a new MCP-style/FastMCP tool surface: read
  [documentation/requirements/49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md](../../../documentation/requirements/49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md)
  — there's an open, undecided architectural question about whether a proposed FastMCP layer
  replaces, coexists with, or converges with this already-running, already-evaluated agent's tool
  layer. Don't silently build a second, parallel hint-ladder/route-attempt implementation.

## Before changing anything

1. `make test` (pytest) and `make eval-agent` (golden-case tool-selection accuracy — last known
   result 7/7) must both stay green; a tool-selection regression is a real failure, not noise.
2. `mathbank-rest` must already be running (`make -C ../mathbank-rest start`) before manually
   exercising this agent — tool calls fail loudly, not silently, without it.
