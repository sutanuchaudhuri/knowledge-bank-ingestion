# FastMCP + Prefab IntelliTutor — Copilot Implementation Pack

## Mission

Build MathBank / IntelliTutor as an agentic MCP application where the model can open
rich learner/admin apps directly in the conversation, while canonical curriculum,
grading, progress, tutoring routes, hints, misconception evidence, graph mappings,
and publication rules remain deterministic and server-authoritative.

This pack is based on the following FastMCP documentation pages:

- https://gofastmcp.com/getting-started/welcome
- https://gofastmcp.com/apps/overview
- https://gofastmcp.com/apps/quickstart
- https://gofastmcp.com/apps/fastmcp-app
- https://gofastmcp.com/apps/prefab
- https://gofastmcp.com/apps/generative
- https://gofastmcp.com/apps/low-level

FastMCP documents that any documentation page can also be fetched as Markdown by
appending `.md`. Copilot should use that facility when implementation details need
fresh verification.

## Cross-reference

[requirements/49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md](../requirements/49_FASTMCP_INTELLITUTOR_MCP_APPS_INTEGRATION.md)
tracks this pack in the main requirements series and maps its impact onto the existing
`requirements/` documents (notably the already-running `mathbank-agent` Google ADK tutor, the
micro-course platform, and the tutoring-route hint ladder). Read it alongside this pack before
starting implementation.

## Read order

1. `01_FASTMCP_DECISION_ARCHITECTURE.md`
2. `02_APP_AND_TOOL_BOUNDARIES.md`
3. `03_STUDENT_INTELLITUTOR_PREFAB_UI.md`
4. `04_MICROCOURSE_QUIZ_AND_NAVIGATION.md`
5. `05_HINTS_STEPS_ROUTES_AND_MISCONCEPTIONS.md`
6. `06_PROGRESS_AND_ANALYTICS_UI.md`
7. `07_AGENTIC_ORCHESTRATION.md`
8. `08_GENERATIVE_UI_POLICY.md`
9. `09_CUSTOM_HTML_ADVANCED_MATH_UI.md`
10. `10_ADMIN_AUTHORING_FASTMCP_APPS.md`
11. `11_REAL_END_TO_END_EXAMPLES.md`
12. `12_IMPLEMENTATION_TEST_DEPLOYMENT.md`
13. `13_SOURCE_MAP.md`

## Architectural rule

Use four FastMCP App patterns deliberately:

```text
1. @mcp.tool(app=True) + Prefab
   -> fixed UI, server prepares data once, browser-only reactive interactions

2. FastMCPApp
   -> UI must call backend tools: quiz submit, hint, next step, search, save,
      record event, start route, ask scoped tutor, refresh progress

3. GenerativeUI
   -> model creates presentation at runtime
   -> INTERNAL / authoring / analysis only by default
   -> never canonical learner curriculum or grading UI

4. Custom HTML Apps
   -> only when Prefab cannot express the math interaction:
      geometry canvas, specialized SVG/WebGL, custom video timeline,
      advanced equation/graph editor, physics visualizer
```

## MathBank invariants

- PostgreSQL is canonical.
- Neo4j is derived/rebuildable structural graph only.
- Learner misconception evidence stays private in PostgreSQL.
- Published micro-course releases and tutoring-route releases are immutable.
- Student answer keys remain server-side.
- A wrong answer is evidence, not automatically a confirmed misconception.
- Runtime LLMs do not invent canonical steps, quizzes, routes, graph nodes,
  interactions, animations, or remediation.
- Prefab / MCP Apps are presentation and interaction surfaces, not a replacement for
  MathBank's domain services.

## Definition of done

The implementation is not done until all of the following work through MCP Apps:

```text
open learner home
→ open micro-course
→ render current state
→ play curated video / show transcript-aware controls
→ show deterministic interactive artifact
→ submit fixed quiz
→ obtain deterministic feedback
→ request approved hint
→ reveal approved next tutoring step
→ run misconception probe/remediation
→ start/return from tutoring route
→ advance course
→ open progress dashboard
→ show model a textual summary alongside rich UI
→ admin can author/review/publish the same objects
→ no hidden answers or private learner evidence leak into UI/Neo4j
```
