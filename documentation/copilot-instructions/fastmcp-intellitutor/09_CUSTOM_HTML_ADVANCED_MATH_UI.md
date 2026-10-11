# 09 — Custom HTML for Advanced Math Interactions

## 1. When to use

FastMCP's Custom HTML Apps are the fallback when Prefab is not enough.

Use for:
- draggable Euclidean geometry;
- graph/network editors with custom edge manipulation;
- precise SVG construction;
- WebGL / 3D physics visualization;
- custom equation canvas;
- synchronized video/transcript timeline;
- highly specialized interaction template renderers.

Do not use Custom HTML merely because the team is more comfortable with JavaScript.

## 2. FastMCP model

A custom MCP App has:
1. a tool that returns data;
2. a `ui://` resource containing HTML.

Tool:

```python
@mcp.tool(app=AppConfig(resource_uri="ui://intellitutor/geometry.html"))
def open_geometry_interaction(instance_id: str) -> dict:
    return interaction_service.student_public_payload(instance_id)
```

Resource:

```python
@mcp.resource(
    "ui://intellitutor/geometry.html",
    app=AppConfig(
        csp=ResourceCSP(
            connect_domains=["https://api.mathbank.example"],
        )
    ),
)
def geometry_view() -> str:
    return load_bundled_html()
```

Use the actual deployment origin/domain rather than the example above.

## 3. Host communication

The MCP Apps JS SDK provides:
- tool result callback;
- `callServerTool`;
- host context changes;
- current host context.

Use this to keep the custom interaction inside the conversation.

## 4. Architecture

```text
Custom HTML renderer
   |
   | semantic action
   v
app.callServerTool(record_interaction_event)
   |
   v
FastMCP backend
   |
   v
same deterministic InteractionRuntimeService
```

Custom JS must not implement a second evidence engine.

## 5. Example: Markov graph/matrix editor

Custom HTML may draw:
- state nodes;
- directed edges;
- edge-probability labels;
- editable matrix cells;
- linked highlight between row and outgoing edges.

When learner commits row A:

```json
{
  "semantic_action": "SET_TRANSITION_ROW",
  "object_id": "matrix:row:A",
  "row": [0.3, 0.4, 0.5]
}
```

Server returns:

```json
{
  "outcome": "ERROR",
  "error_signature": "ROW_SUM_INVALID",
  "focus_object_ids": ["matrix:row:A"],
  "related_object_ids": [
    "transition:A:A",
    "transition:A:B",
    "transition:A:C"
  ],
  "feedback": "This row totals 1.2; all next-state probabilities must total 1."
}
```

Renderer highlights only what the server tells it to highlight.

## 6. Example: geometry interaction

Scene:
- triangle ABC;
- draggable point D on BC;
- cevian AD;
- current ratios displayed.

Semantic event:

```text
MOVE_POINT_D
```

Server may evaluate:
- whether D satisfies a target ratio;
- whether learner has constructed the intended configuration;
- which approved hint is next.

Do not infer a misconception from raw pointer motion.

## 7. Video/transcript custom UI

Custom HTML is appropriate if Prefab cannot meet:
- exact millisecond playhead;
- segment overlays;
- clickable transcript;
- synchronized markers;
- diagram overlay;
- "Ask at this moment."

Every Q&A request sends exact video time. Server resolves an approved transcript segment.

## 8. CSP

Custom HTML apps have a deny-by-default CSP.

Explicitly allow only required:
- resource domains;
- connect domains;
- frame domains;
- base URI domains.

For YouTube/video embedding, allow only the exact required frame domain.

## 9. Permissions

If camera/clipboard/etc. is needed, declare `ResourcePermissions`.

Host may deny it. Always implement graceful feature detection/fallback.

## 10. No hidden secrets

Never put:
- auth tokens;
- DB credentials;
- answer keys;
- server evidence rules

inside HTML/JS resources.

## 11. UI extension fallback

For clients without MCP Apps support, return:
- textual problem/state;
- static asset links where safe;
- equivalent text inputs/actions.

Custom HTML is an enhancement, not the only access path.
