# 13 — FastMCP Source Map

This document distinguishes source-supported FastMCP behavior from IntelliTutor design
decisions.

## A. Framework welcome

Source:
https://gofastmcp.com/getting-started/welcome

Used for:
- FastMCP covers servers, clients and apps.
- Apps render interactive interfaces directly from MCP tools.
- FastMCP handles schema/validation/transport/protocol concerns.
- documentation pages can be retrieved by appending `.md`.
- FastMCP docs also expose an MCP documentation server.

Important source caveat:
The documentation reflects FastMCP's `main` branch and may include features not yet in a
stable release. Copilot must verify APIs against the installed/pinned version.

## B. Apps overview

Source:
https://gofastmcp.com/apps/overview

Used for:
- four primary app patterns:
  Interactive Tools, FastMCPApp, Generative UI, Custom HTML.
- `@mcp.tool(app=True)` as starting point.
- FastMCPApp for UI-to-backend callbacks.
- Generative UI for model-written Prefab.
- Custom HTML for full-control interfaces.
- Prefab active-development warning and version pinning recommendation.

## C. Quickstart

Source:
https://gofastmcp.com/apps/quickstart

Used for:
- install `fastmcp[apps]`.
- `PrefabApp()` composition.
- `Column`, `Grid`, `DataTable`, charts.
- client-side state.
- `SetState`, `Rx`, `If`.
- `fastmcp dev apps`.
- browser-local reactivity without server round trips.

## D. Interactive Tools / Prefab

Source:
https://gofastmcp.com/apps/prefab

Used for:
- fixed Prefab tools.
- DataTable/search/sort.
- charts.
- composed dashboards.
- state/Rx/reactive conditional UI.
- sandboxed iframe/CSP.
- `ToolResult(content=..., structured_content=...)` so user sees UI while model sees a
  textual summary.
- use FastMCPApp when backend callbacks are needed.

## E. FastMCPApp

Source:
https://gofastmcp.com/apps/fastmcp-app

Used for:
- `@app.ui()` model-visible entry points.
- `@app.tool()` app-visible backend tools.
- `@app.tool(model=True)` when both audiences need a tool.
- `CallTool`.
- function-reference tool resolution for composition safety.
- `on_success`, `on_error`, `RESULT`, `ERROR`.
- `result_key`.
- actions such as `SetState`, `ToggleState`, `AppendState`, `PopState`, `ShowToast`.
- loading-state pattern.
- manual Forms.
- `Form.from_model()` with Pydantic.
- mounting/providers.
- app names must be unique.
- visibility metadata is not a security boundary; enforce auth server-side.

## F. Generative UI

Source:
https://gofastmcp.com/apps/generative

Used for:
- `GenerativeUI`.
- model-written Prefab Python.
- progressive rendering.
- `generate_prefab_ui`.
- `search_prefab_components`.
- `data` values supplied to sandbox.
- server-side final validation.
- standard-library + Prefab sandbox constraints.
- no arbitrary external Python packages.

IntelliTutor policy derived from these facts:
Generative UI is internal/supplemental by default, not canonical graded curriculum.

## G. Custom HTML

Source:
https://gofastmcp.com/apps/low-level

Used for:
- tool + `ui://` HTML resource architecture.
- `AppConfig`.
- model/app visibility options.
- visibility is not security.
- `@modelcontextprotocol/ext-apps` host communication.
- `ontoolresult`.
- `callServerTool`.
- host context callbacks.
- deny-by-default CSP.
- `ResourceCSP`.
- `ResourcePermissions`.
- runtime check for Apps extension support.

## H. IntelliTutor-specific additions

The following are MathBank/IntelliTutor architectural decisions, not claims made by
FastMCP documentation:

- PostgreSQL canonical storage.
- Neo4j derived instructional graph.
- immutable micro-course/tutoring-route releases.
- fixed hint ladders.
- deterministic misconception evidence.
- interaction templates/SceneSpecs.
- timestamp-approved video Q&A.
- no learner-specific misconception edges in shared Neo4j.
- server-hidden answer keys.
- canonical authoring/review/publication process.

Copilot must preserve those project invariants while using FastMCP as the interactive
application surface.
