# 01 — FastMCP Decision Architecture

## 1. Source-supported FastMCP facts

FastMCP is a framework for MCP servers, clients and apps. Apps let tools render interactive
interfaces directly in the conversation.

The FastMCP Apps overview describes four major approaches:

1. Interactive Tools — `@mcp.tool(app=True)` returning Prefab components.
2. `FastMCPApp` — for UIs that call backend tools.
3. Generative UI — the LLM writes Prefab code at runtime.
4. Custom HTML — direct MCP Apps extension with HTML/CSS/JS.

Prefab is under active development. FastMCP sets a minimum `prefab-ui` version but does
not pin an upper bound. The IntelliTutor deployment MUST pin an exact tested
`prefab-ui` version in its lockfile.

## 2. IntelliTutor decision table

| Requirement | Use | Why |
|---|---|---|
| Show static lesson summary | `@mcp.tool(app=True)` Prefab | simple fixed UI |
| Search/filter already-loaded problems | Prefab client state + `Rx` | no round trip needed |
| Toggle worked-example section | Prefab client state + `If` | local-only |
| Submit quiz answer | `FastMCPApp` backend tool | authoritative grading |
| Request next hint | `FastMCPApp` backend tool | hint-level policy is server-owned |
| Advance course | `FastMCPApp` backend tool | transition/gating is server-owned |
| Start route/problem attempt | `FastMCPApp` backend tool | creates/pins canonical attempt |
| Ask contextual tutor | `FastMCPApp` backend tool | server builds grounding envelope |
| Save learner interaction event | `FastMCPApp` backend tool | evidence/audit persistence |
| Progress dashboard with no mutations | app=True or FastMCPApp | depends on refresh/drilldown needs |
| Admin CRUD | `FastMCPApp` | writes to canonical Postgres |
| Admin AI draft preview | Generative UI or fixed Prefab | never auto-publish |
| Student canonical lesson UI | fixed Prefab/FastMCPApp | deterministic, testable |
| Geometry drag canvas | Custom HTML | specialized graphical control |
| Physics/3D visualizer | Custom HTML | WebGL/canvas/custom JS |
| Timestamped custom video/transcript | Prefab if sufficient; Custom HTML otherwise | exact timeline control |
| One-off internal data visualization | Generative UI | model-tailored display is acceptable |

## 3. Server topology

Recommended logical decomposition:

```text
FastMCP("IntelliTutor")
  |
  +-- student_app: FastMCPApp("intellitutor-student")
  |
  +-- tutoring_app: FastMCPApp("intellitutor-tutoring")
  |
  +-- progress_app: FastMCPApp("intellitutor-progress")
  |
  +-- admin_app: FastMCPApp("intellitutor-admin")
  |
  +-- optional GenerativeUI provider (internal/admin scope only)
  |
  +-- custom HTML resources under ui://intellitutor/...
```

The app names must be unique within a server.

## 4. Domain service boundary

FastMCP handlers call the existing MathBank service layer.

Correct:

```text
FastMCP tool
  -> CourseRuntimeService
  -> PostgreSQL transaction
  -> outbox/audit
```

Incorrect:

```text
Prefab UI
  -> direct SQL

FastMCP tool
  -> duplicated grading logic

Custom HTML
  -> direct Neo4j mutation
```

## 5. Visibility is not security

FastMCP distinguishes model-visible and app-visible tools, but its documentation is
explicit that visibility is not an authorization boundary.

Therefore:

```text
@app.ui()
```

is normally model-visible.

```text
@app.tool()
```

is normally app-visible / omitted from the model list.

But every sensitive backend operation must still perform:
- authentication;
- authorization;
- enrollment/ownership validation;
- release pin validation;
- CSRF/session-equivalent protections appropriate to transport;
- argument validation;
- rate/budget limits where relevant.

## 6. Client-side state vs server state

Use Prefab state for ephemeral presentation:

```text
selected tab
expanded card
local filter
selected table row
temporary slider position
show/hide target
```

Use server state for:

```text
course enrollment
current course state
quiz attempt
route attempt
hint level
interaction evidence
confirmed misconception state
mastery
publication/review
AI usage/audit
```

## 7. Host fallback

Not every MCP host supports the Apps extension. Custom HTML docs show that support can be
checked with:

```text
Context.client_supports_extension(UI_EXTENSION_ID)
```

Every model-visible learner entry point should therefore have a text fallback.

Example:

```text
if Apps supported:
    return structured learner UI
else:
    return concise text state + safe next actions
```

## 8. Content Security Policy

Prefab apps are sandboxed. Custom HTML apps have a deny-by-default CSP.

Never broaden CSP globally. Declare only required domains for:
- YouTube/embed frame;
- trusted CDN scripts if unavoidable;
- MathBank API/WebSocket endpoints;
- approved media hosts.

Prefer self-hosted/bundled assets when practical.
