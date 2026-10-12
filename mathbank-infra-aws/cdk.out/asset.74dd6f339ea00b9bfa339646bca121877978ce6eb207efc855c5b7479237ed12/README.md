# mathbank-mcp-competitions

A standalone **FastMCP server** exposing MathBank's competition/problem/concept/technique
corpus to **any MCP-capable agent** — not just `mathbank-agent` — plus a **Prefab UI
competition explorer** rendered as HTML inside any MCP-Apps-capable host.

Implements the scoped slice of
[documentation/requirements/49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md](../documentation/requirements/49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md)
the user asked for directly: *"a parallel mcp server for other agents to fetch
competition specific data"* + *"a full MCP server and an agent with prefab client
rendered in html."* This is a genuinely separate project from `mathbank-agent` — see doc
49 §2's "coexist as distinct products" recommendation — and does not touch or depend on
it.

**Status: fully implemented and live-tested** (not a scaffold — every tool below is real,
backed by the live `mathbank-rest` REST API, and verified with real data in this pass).

## What's in here

| Piece | What it is |
|---|---|
| `src/mathbank_mcp_competitions/server.py` | The FastMCP server: 6 plain data-fetch tools + one `FastMCPApp` with a Prefab `.ui()` entry point |
| `src/mathbank_mcp_competitions/rest_client.py` | Thin `httpx` wrapper around `mathbank-rest`'s existing `/v1/*` endpoints — no SQL, no duplicated retrieval logic (the fastmcp-intellitutor pack's "domain service boundary" rule) |
| `src/mathbank_mcp_competitions/__main__.py` | `python -m mathbank_mcp_competitions` — runs over stdio (default) or streamable HTTP |
| `agent_demo/agent.py` | A **real, independent** OpenAI-function-calling agent (not ADK, not mathbank-agent) that spawns this server as a subprocess over stdio and answers questions using its tools — proof the server works for "other agents" |
| `tests/test_server.py` | 9 live tests against the real MCP protocol path (FastMCP's in-memory `Client`), asserting on real corpus data |
| `tests/test_agent_demo.py` | 2 always-on tests (subprocess spawn + tool-schema adapter) + 1 opt-in live-LLM test (`AGENT_DEMO_LIVE_LLM=1`) |
| `tests/test_scene_promotion_tools.py` | 1 opt-in live test (`MANIM_STUDIO_LIVE_TEST=1`) — the full promote→validate→approve round trip through the real MCP tool layer |

## Tools

| Tool | Visibility | Purpose |
|---|---|---|
| `list_competitions` | model | Every competition (AMC10/AMC12/AIME/HMMT/.../etc.) with its code/name/level |
| `list_problems` | model | Problems filtered by competition/year/concept/technique |
| `get_problem` | model | One problem's full statement/answer/source/mapped concepts by canonical code |
| `search_problems` | model | Hybrid semantic+lexical+graph search over problem statements |
| `list_concepts` | model | Canonical concept taxonomy |
| `list_techniques` | model | Canonical solution techniques |
| `load_competition_problems` | app-only | Backend tool the Prefab UI's competition picker calls |
| `open_competition_explorer` | model + UI | Renders the Prefab competition explorer (picker + searchable/paginated problem table) |
| `list_promotable_scenes` | model, admin-scoped | Lists DONE, unpromoted Manim Video Studio render jobs (requirements/60 §7) — requires `admin_api_key` |
| `promote_scene_to_catalog` | model, admin-scoped | Promotes a render job into a new DRAFT `visual.scene_spec` catalog row — requires `admin_api_key` |
| `validate_scene_in_catalog` | model, admin-scoped | Runs mathbank-rest's structural validator against a DRAFT scene — requires `admin_api_key` |
| `approve_scene_in_catalog` | model, admin-scoped | Validates and approves a DRAFT scene (then immutable) — requires `admin_api_key` |

The four `*_scene*` tools are the first admin-scoped (write-capable) extension of this
server (requirements/60 §7) — each requires the caller to pass a real `admin_api_key`
argument, validated by `mathbank-rest` itself (the same shared secret its own
`X-Admin-Api-Key` header uses), never by this server. The tools remain visible to any
MCP client regardless of whether it has the key — consistent with FastMCP's own
"visibility is not security" principle — they are simply inert without it (a `401`
propagates up from `mathbank-rest`).

## Getting started

```bash
make install
cp .env.example .env   # point MATHBANK_REST_BASE_URL at your running mathbank-rest, add OPENAI_API_KEY for the agent demo
make test              # 11 pass, 1 opt-in-skipped by default
make run                # stdio server, e.g. for Claude Desktop / any MCP host's config
```

### Try the bundled agent demo

```bash
.venv/bin/python -m agent_demo.agent "Find a real AMC10 geometry problem about triangle area and tell me its canonical code and official answer."
```

This spawns the server as a real subprocess, lets OpenAI's function-calling loop pick
and call tools, and prints a grounded final answer — e.g. it correctly found
`AMC10_2009A_Q10` / answer `(B) 7√3` in testing, verified against the same data
`mathbank-rest`'s own search endpoint returns.

### Connecting from an MCP host (Claude Desktop, etc.)

```json
{
  "mcpServers": {
    "mathbank-competitions": {
      "command": "/absolute/path/to/mathbank-mcp-competitions/.venv/bin/python",
      "args": ["-m", "mathbank_mcp_competitions"],
      "cwd": "/absolute/path/to/mathbank-mcp-competitions"
    }
  }
}
```

## Design notes / gotchas found while building this

- **`Select`'s `value` field does not accept a reactive `Rx` binding** (unlike
  `DataTableColumn.rows`, which does) — the fastmcp-intellitutor pack's own example code
  pattern doesn't cover this. Fixed by using `name="competition"` plus
  `SelectOption(selected=...)` computed server-side at render time instead, which is also
  the pattern the `prefab_ui` package's own bundled `field.py`/`form.py` components use
  internally.
- **`PrefabApp.title` is required**, not optional — the pack's illustrative
  `03_STUDENT_INTELLITUTOR_PREFAB_UI.md` §5 example omits it; the real `prefab_ui`
  package's `PrefabApp` model requires it.
- **A `FastMCPApp` is mounted into a `FastMCP` server via the `providers=[...]`
  constructor argument**, not a `.mount()` call (`.mount()` is for composing two full
  `FastMCP` servers together, not attaching a `FastMCPApp`/`Provider`) — this means the
  `FastMCPApp` and everything decorated onto it must be fully defined *before*
  constructing the `FastMCP(...)` instance, which drove this file's top-to-bottom
  ordering (Prefab app first, then `mcp = FastMCP(..., providers=[competitions_app])`,
  then the plain tools).
- **`.model_dump()` on a raw Prefab component tree undercounts nested children** — the
  real wire-format serialization used by FastMCP's actual tool-call response (verified via
  `Client.call_tool(...).structured_content`) is correct and complete; a bare
  `PrefabApp.model_dump()` called directly in a Python REPL is not representative of the
  real MCP-protocol output and should not be used to debug rendering issues — call through
  a real `fastmcp.Client` instead, exactly as `tests/test_server.py` does.
