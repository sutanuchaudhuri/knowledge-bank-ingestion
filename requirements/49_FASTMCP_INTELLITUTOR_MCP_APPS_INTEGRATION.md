# 49. FastMCP + Prefab IntelliTutor: MCP Apps integration and cross-document impact map (planning only)

> **Explicit scope note.** Planning and documentation only — **no code has been changed**. This
> document does not duplicate the detailed FastMCP implementation design; that design already
> exists, in full, in
> [FASTMCP_INTELLITUTOR_COPILOT/](/Volumes/External/Developer/knowledge-bank-ingestion/FASTMCP_INTELLITUTOR_COPILOT)
> (13 files, read order and mission in its own
> [00_INDEX.md](/Volumes/External/Developer/knowledge-bank-ingestion/FASTMCP_INTELLITUTOR_COPILOT/00_INDEX.md)).
> This document's job is narrower and specific to this repository's existing `requirements/`
> series: (1) register that pack as a tracked requirement, and (2) map, concretely, which existing
> requirement documents and already-built systems it touches, what would need to change or be
> reconciled in each, and which open questions must be answered before any of it is implemented.

## 0. Status and scope

| | |
|---|---|
| Status | **Planning only.** Not implemented. Nothing in `FASTMCP_INTELLITUTOR_COPILOT/` has been wired into `mathbank-rest`, `mathbank-agent`, or any app. `grep`-confirmed: no `fastmcp`/`FastMCP`/`MCP Apps` reference exists anywhere else in the repository outside that folder. |
| What this is | MathBank/IntelliTutor exposed as a **FastMCP server** so an MCP-Apps-capable host (e.g. an MCP-compatible chat client) can open rich, interactive learner/admin UI ("Prefab" components, or hand-built HTML for cases Prefab can't express) directly inside a conversation, while all grading, gating, canonical content and publication rules stay server-authoritative in the existing MathBank service layer. |
| Source of truth for mechanics | [FASTMCP_INTELLITUTOR_COPILOT/](/Volumes/External/Developer/knowledge-bank-ingestion/FASTMCP_INTELLITUTOR_COPILOT) — read `13_SOURCE_MAP.md` first if you need to know what is an actual FastMCP/Prefab framework fact (cited to `gofastmcp.com`) versus a MathBank-specific design decision layered on top. |
| Source of truth for impact | This document (§2–§4). |

## 1. One-paragraph architecture summary (full detail lives in the folder, not here)

FastMCP's four app patterns — `@mcp.tool(app=True)` fixed Prefab, `FastMCPApp` (UI that calls
app-only backend tools for authoritative actions), Generative UI (model-written Prefab, internal/
admin-only by default), and Custom HTML (only when Prefab can't express the interaction, e.g.
geometry drag canvases) — are proposed as a **fourth presentation surface** for MathBank, in
addition to the existing `mathbank-web` (Next.js), `mathbank-live` (Socket.IO), and
`mathbank-agent` (Google ADK chat) surfaces. The pack's own stated principle is that FastMCP tools
must call the *existing* MathBank service layer rather than reimplement grading/evidence/
publication logic — which is the right principle, and exactly why a careful impact map against the
already-built services those tools would call is necessary before any of it is implemented.

## 2. The most important reconciliation this document identifies: a second, parallel agent stack

**This is the single highest-priority open question in this entire document.** MathBank already
has a real, running, production tutoring agent — it is not a gap FastMCP is filling, it is a
second system with closely overlapping responsibility:

| | Existing: `mathbank-agent` (doc 10, `AGT-01` ✅ done) | Proposed: FastMCP/MCP Apps (this folder) |
|---|---|---|
| Framework | Google ADK `LlmAgent` + OpenAI via `LiteLlm` | FastMCP Apps (Prefab / Generative UI / Custom HTML) |
| Entry point | `mathbank-agent/server.py` (port 8001), ADK's own session/tool-calling protocol | An MCP server any MCP-Apps-capable host connects to |
| Hint ladder tool | `request_step_hint`/`request_next_hint` ([step_runtime_tools.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-agent/agents/mathbank_tutor/tools/step_runtime_tools.py)/[rest_tools.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-agent/agents/mathbank_tutor/tools/rest_tools.py)) | `request_hint`/`request_next_step` (doc 05 of the pack) |
| Attempt/route lifecycle | `start_step_attempt`, `submit_step_response`, `diagnose_step_gap`, `start_recovery_plan`, `get_next_recovery_item`, `resume_original_step` | `start_tutoring_route`, `submit_route_response`, `return_from_route` (docs 04/05/07) |
| Geometry/artifact rendering | `draw_geometry_diagram`, `generate_geometry_scene`, `request_artifact`/`preview_artifact` ([artifact_tools.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-agent/agents/mathbank_tutor/tools/artifact_tools.py), [geometry_scene_tools.py](/Volumes/External/Developer/knowledge-bank-ingestion/mathbank-agent/agents/mathbank_tutor/tools/geometry_scene_tools.py)) | Custom HTML geometry/physics apps (doc 09) |
| Model-proposed UI | `propose_widget` — a **deterministic, whitelisted, validated widget spec** rendered by `mathbank-web`'s `WidgetHost`, never executed as code (doc 27) | Generative UI — the **model writes Prefab Python**, executed in a Pyodide sandbox, validated server-side after the fact (doc 08 of the pack) |
| Scoped contextual Q&A | the existing `/v1/tutor/coach`/`guidance-plan`/`micro-check` endpoints (doc 13), plus this session's doc 42 §42.I/doc 47 §3.2 scoped-AI-panel design | `ask_current_context` with its own, independently-specified grounding envelope (doc 07 of the pack) |

None of the 13 FastMCP pack documents mentions `mathbank-agent`, ADK, or ever reconciles with it —
confirmed by reading every file. **Before any implementation**, a decision is required on exactly
one of these three shapes, not an assumption:

1. **Replace** — FastMCP/MCP Apps becomes the one agentic/tutoring surface, and `mathbank-agent`
   is deprecated or narrowed to whatever ADK-specific capability FastMCP can't cover.
2. **Coexist as distinct products** — `mathbank-agent` keeps serving `mathbank-web`'s in-app chat
   tutor; FastMCP is a *separate* MCP server exposed to third-party MCP-Apps hosts (e.g. a
   student using IntelliTutor from within Claude Desktop/ChatGPT rather than mathbank-web). This
   requires explicit product scoping (who actually uses the MCP surface, and why, if the web app
   chat already exists) — not asserted anywhere in the pack today.
3. **Converge on one underlying tool layer, two front doors** — the *service calls* behind both
   stacks' tools are unified (both wrap the identical `step_runtime`/`route`/`interaction`/
   `micro_course` service functions, which is good practice either way) but the *agent
   orchestration framework* itself genuinely remains two separate things (ADK's `LlmAgent` loop vs.
   an MCP host's own model loop) because they serve different client populations.

This document recommends decision (3) as the lowest-risk starting point (it requires no
deprecation of a working, evaluated system — doc 10's AGT-12 already reports a 7/7 passing golden-
case eval for the ADK agent — while still allowing the MCP surface to be built), but this is
explicitly a product decision for the project owner, not something this document settles
unilaterally.

## 3. Generative UI vs. the existing whitelisted-widget precedent (a second, narrower reconciliation)

Doc 27 (Fluid Widget Layer) already solved "let the model propose a visual, safely" with
`propose_widget`: the model returns a short JSON intent, the **deterministic, validated** server
side produces a whitelisted widget spec, and `mathbank-web`'s `WidgetHost` renders it — the model
never emits executable code. The FastMCP pack's Generative UI (doc 08 there) is a materially
different, riskier mechanism: **the model writes Prefab Python at runtime**, executed client-side
in Pyodide while streaming, then validated server-side only after the fact. The pack's own policy
already restricts this to internal/admin/non-canonical use (correctly, and consistent with doc
27's caution) — but doc 27 itself should be read before enabling Generative UI for anything,
since it already represents MathBank's considered position on "how much should a model be allowed
to decide about its own UI," and that position is more conservative than Generative UI's default
capability.

## 4. Impact map — every existing requirement document this would touch

| Doc | Why it's impacted | What would need to happen |
|---|---|---|
| [10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md](10_AGENTIC_TUTOR_AND_STUDENT_MASTERY_REQUIREMENTS.md) | Describes the **existing, evaluated** ADK/OpenAI agent this pack never mentions. | Add an explicit cross-reference and resolve §2's three-way decision before any FastMCP tool duplicates an ADK tool's responsibility. |
| [13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md](13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md) | `coach`/misconception-evidence design here is the backend the FastMCP "scoped tutor" (doc 07 of the pack) would call. | Confirm the existing `/v1/tutor/coach` grounding hierarchy and this pack's `ask_current_context` envelope are the *same* design, not two independently-specified ones (today they are independently written, not yet reconciled). |
| [39_PRECOMPILED_TUTORING_ROUTES.md](39_PRECOMPILED_TUTORING_ROUTES.md) | Its H1–H5 hint ladder (`pedagogy.route_step`, `route_step_hint`) is **exactly** the mechanism FastMCP doc 05 describes, under different names. | No schema change implied; FastMCP's hint/route tools should be thin wrappers over this already-built, already-immutable-release system, not a new hint-ladder implementation. |
| [40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md) | FastMCP's `open_course`/`advance_course`/course-state DTO (pack docs 03–04) map directly onto this doc's `pedagogy.micro_course*` runtime. | The Prefab student DTO must be generated from the *same* `_assemble_course_reader_payload` service helper this session already built (see doc 42/43/47), not a second, parallel DTO assembly. |
| [41_INTERACTION_TEMPLATE_LIBRARY.md](41_INTERACTION_TEMPLATE_LIBRARY.md) | Custom HTML geometry/Markov-matrix editors (pack doc 09) must reuse the same deterministic evidence engine this doc specifies for `InteractionTemplateRenderer.jsx`. | Any FastMCP Custom HTML renderer is a **second front-end implementation** of the same template family and must stay in lock-step with this doc's evidence rules — flagged here as an ongoing dual-maintenance cost, not a one-time task. |
| [42_MICRO_COURSE_STUDENT_NAVIGATION.md](42_MICRO_COURSE_STUDENT_NAVIGATION.md) | Its JSON contract (published-course/enrollment-runtime shapes) is the natural DTO source for the Prefab course UI. | FastMCP tools should consume this exact contract (MCN-1's "stable, content-agnostic JSON contract") rather than defining a parallel shape, per pack doc 04 §1–2's own "server-authoritative state" principle. |
| [43_ADMIN_MICRO_COURSE_AUTHORING_UI.md](43_ADMIN_MICRO_COURSE_AUTHORING_UI.md) | Pack doc 10 proposes a parallel FastMCP admin authoring app covering the same course/release/quiz authoring workflow this doc already built in Next.js. | Decide whether FastMCP admin authoring is a genuinely separate product surface (e.g. "authoring from within an MCP chat host") or redundant with the already-shipped `/admin/micro-courses` workspace — not assumed by either document today. |
| [44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md](44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md) | Two different "beyond the browser" strategies now exist on paper: this doc's React Native mobile app, and MCP Apps hosted in a third-party chat client. Also: doc 44's AI-token-usage metering (MCX-16) would need to additionally cover every FastMCP tool call, not only web/mobile REST calls. | Decide whether MCP Apps is a third client surface alongside mobile (most likely, since MCP hosts are conversational clients, not a MathBank-controlled mobile app) and extend MCX-16's per-student AI-cost accounting to include FastMCP tool invocations explicitly. |
| [45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md](45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md) | Pack doc 01 §5 states plainly: "visibility is not security" — every FastMCP tool must independently re-check auth server-side. Doc 45 already found the admin API key is **not even registered as a real OpenAPI security scheme** and is misreported as optional. | Fixing doc 45's APID-3 (register the admin key as a real security scheme) becomes a harder prerequisite once a second calling surface (FastMCP tools) also depends on that same auth check being airtight — the risk of an under-checked admin tool is higher with a second entry point, not lower. |
| [46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md](46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md) | Pack doc 10 §5 ("Quiz authoring") describes the exact same admin quiz-creation workflow (prompt/options/correct answer/explanation/purpose/canonical targets) this doc already proposed as QZA-1–8. | FastMCP's admin quiz-authoring tool should call doc 46's proposed `POST /v1/admin/activities`/`PATCH .../skill-mapping` endpoints once built, not define a second quiz-creation code path. |
| [47_MICRO_COURSE_STUDENT_NAVIGATION_V2_AND_AI_ASSIST.md](47_MICRO_COURSE_STUDENT_NAVIGATION_V2_AND_AI_ASSIST.md) | Its per-item decomposition/single-active-item/"Help me?"/"Give up" design and the pack's per-item quiz rendering (doc 04) plus scoped-tutor design (doc 07) are **the same feature, specified twice, independently**, in two different documents written without awareness of each other. | Reconcile explicitly: doc 47's `sequence_position`-based item stream and single-active-item gating should be the one source of truth for *what* is shown; the pack's Prefab rendering is one possible *how* (a second front-end), not a reason to redesign the sequencing model a second time. |
| [27_FLUID_WIDGET_LAYER.md](27_FLUID_WIDGET_LAYER.md) | `propose_widget`'s whitelisted-spec pattern (already shipped) is the closest existing precedent to, and meaningfully safer than, the pack's Generative UI default (§3 above). | Read before enabling Generative UI for any learner-facing (even supplemental) use; doc 27's existing caution should inform, at minimum, the `ENABLE_GENERATIVE_UI_LEARNER` flag default the pack itself already recommends `false`. |
| [30_MODERN_UI_DESIGN_SYSTEM.md](30_MODERN_UI_DESIGN_SYSTEM.md) | Prefab is a **fourth UI technology stack** (`mathbank-web`/`mathbank-live`/`mathbank-widgets` plus now Prefab components: `Card`/`Badge`/`Metric`/`DataTable` instead of `PageHeader`/`Pill`/`Callout`). Doc 30's token/component contract has no defined mapping to Prefab's component set at all. | Either explicitly scope doc 30 as "does not govern Prefab/MCP Apps surfaces" (a real fragmentation the project should accept consciously) or write a parallel "Prefab visual conventions" mapping so a student doesn't get a visually inconsistent experience depending on which surface they're using. |
| [48_SITE_WIDE_UX_VISUAL_AUDIT.md](48_SITE_WIDE_UX_VISUAL_AUDIT.md) | Same root cause as doc 30's row above — this audit's findings and remediation apply only to the Next.js surface; a FastMCP/Prefab surface would need its own, separate sweep using Prefab-appropriate equivalents of the same checklist. | Note as an explicit non-goal of doc 48 (it does not, and could not yet, cover a UI stack that doesn't exist in the repo). |
| [32_MULTIMODAL_ATTEMPTS_AND_ARTIFACTS.md](32_MULTIMODAL_ATTEMPTS_AND_ARTIFACTS.md) | `mathbank-agent`'s existing `request_artifact`/`preview_artifact`/`get_multimodal_attempt` tools already cover much of what a Custom HTML "artifact" MCP App (pack doc 09) would need. | Any FastMCP artifact-rendering app should call this doc's existing artifact-bundle service, not reintroduce a parallel artifact pipeline. |
| [37_GEOMETRY_SCENE_ENGINE.md](37_GEOMETRY_SCENE_ENGINE.md) / [38_NEURAL_GEOMETRY_ENGINE.md](38_NEURAL_GEOMETRY_ENGINE.md) | Directly named as the Custom HTML "draggable geometry" example (pack doc 09 §1/§6); `mathbank-agent`'s `generate_geometry_scene`/`draw_geometry_diagram` already call this engine from the ADK side. | A FastMCP Custom HTML geometry renderer must call the identical deterministic geometry-core service these docs define, not a parallel implementation — same dual-maintenance caution as the interaction-template row above. |
| [11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md](11_SYSTEM_DIAGRAMS_TESTING_AND_METRICS.md) | Pack doc 12 §4–5 specifies a whole new test tier (Prefab snapshot tests, MCP Apps-fallback tests, "visibility is not security" penetration-style tests) this doc's testing framework doesn't yet enumerate. | Add a new test-tier section once any FastMCP work begins; until then, no action — tracked here as a forward pointer. |
| [19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md) | "Visibility is not a security boundary" and "the Generative UI sandbox excludes third-party packages (NumPy/pandas/requests)" are exactly the shape of hard-won pitfall this doc exists to record. | Add both as entries **once implementation actually hits them**, not speculatively now. |
| [20_NOT_YET_IMPLEMENTED.md](20_NOT_YET_IMPLEMENTED.md) | Registry of open work. | Add this document (49) and the `FASTMCP_INTELLITUTOR_COPILOT/` pack as a tracked, not-yet-started item once this document is accepted. |

## 5. Explicit non-goals of this document

- **Not** implementing any FastMCP server, tool, or Prefab app.
- **Not** re-deciding FastMCP/Prefab framework mechanics already settled in
  [FASTMCP_INTELLITUTOR_COPILOT/13_SOURCE_MAP.md](/Volumes/External/Developer/knowledge-bank-ingestion/FASTMCP_INTELLITUTOR_COPILOT/13_SOURCE_MAP.md) —
  this document only adds the MathBank-repository-specific impact lens that pack intentionally
  left out of its own scope.
- **Not** resolving §2's replace/coexist/converge decision — that is flagged as a required
  decision, not decided here.
- **Not** proposing deprecation of `mathbank-agent`, `mathbank-web`, or any existing surface.
- **Not** a security review of the FastMCP pack's own stated security principles (§1 §5 "visibility
  is not security," §2 §8 authorization matrix) — those read as sound and consistent with this
  repository's existing posture (e.g. this session's doc 45 finding, independently, that the
  current admin-key scheme needs exactly this kind of hardening); this document does not
  re-derive or re-verify them.

## 6. Requirement inventory (FMI-*)

| ID | Requirement | Acceptance evidence |
|---|---|---|
| FMI-1 | Agent-architecture relationship is explicitly decided | One of §2's three options (replace / coexist / converge) is chosen and recorded, in writing, before any FastMCP tool is implemented |
| FMI-2 | No duplicated hint-ladder/route implementation | Any FastMCP hint/route tool calls the existing doc 39 `pedagogy.route_step`/`route_step_hint` service functions directly; no second hint-level-gating implementation exists |
| FMI-3 | No duplicated micro-course DTO assembly | Any FastMCP course-state tool reuses `_assemble_course_reader_payload` (or its REST endpoint) rather than re-querying `pedagogy.micro_course_state_*` tables independently |
| FMI-4 | No duplicated quiz-authoring surface | Any FastMCP admin quiz-authoring tool calls doc 46's proposed (or, once built, implemented) `/v1/admin/activities` endpoints, not a new write path |
| FMI-5 | No duplicated interaction/geometry evidence engine | Any FastMCP Custom HTML interaction/geometry renderer calls the existing `InteractionRuntimeService`/geometry-core service; a diff tool or regression suite can show zero divergence in evidence outcomes between the Next.js renderer and the MCP renderer for the same interaction instance |
| FMI-6 | Generative UI stays non-canonical by default | `ENABLE_GENERATIVE_UI_LEARNER=false` in every environment until a separate, explicit review (informed by doc 27's existing precedent) approves learner-facing use |
| FMI-7 | Admin-key auth hardening (doc 45 APID-3) treated as a co-requisite, not an independent nice-to-have | Before any FastMCP admin tool ships, the admin API key is registered as a real, enforced security scheme — not left as the currently-misreported-as-optional header |
| FMI-8 | Visual-consistency scope is explicit | Doc 30 states plainly whether Prefab/Custom-HTML surfaces are in or out of its scope, rather than leaving an implicit gap |

## Cross-document relationship

This document is the single point from which every other requirement doc listed in §4 should be
read when FastMCP/MCP Apps work is picked up; it does not replace, duplicate, or restate those
documents' own content, and it does not replace
[FASTMCP_INTELLITUTOR_COPILOT/](/Volumes/External/Developer/knowledge-bank-ingestion/FASTMCP_INTELLITUTOR_COPILOT)'s
own, already-complete, 13-document implementation design.
