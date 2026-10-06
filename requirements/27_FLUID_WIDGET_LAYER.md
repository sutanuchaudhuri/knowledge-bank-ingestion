# 27 — Fluid Experience & Widget Orchestration Layer (`FW`)

Requirement IDs: `FW-*`. Source pack: `math_tutor_fluid_widget_selected_docs/` (19 files, kept in the repo
until this document and the tracker are audited — **do not delete the pack yet**). Implemented 2026-10-06
following the pack's own `26_COPILOT_MASTER_INSTRUCTIONS.md` and `27_COPILOT_PROMPT_SEQUENCE.md`.

Related: [28 distributed live platform](28_DISTRIBUTED_LIVE_PLATFORM.md) (sockets, `mathbank-live`),
[29 student input add-ons](29_STUDENT_INPUT_ADDONS.md) (LaTeX composer, ElevenLabs voice, agentic formatting),
[18 tracker](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md) §Fluid/Live, [19 gotchas](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md) §15 `FW`/`LIVE`,
[20 NYI](20_NOT_YET_IMPLEMENTED.md) §NYI-FW/LIVE, reference [POSTGRES_SCHEMA](reference/POSTGRES_SCHEMA.md) §migration 020,
[REST_API](reference/REST_API.md) §Fluid/Live.

Status legend: ✅ delivered and tested · 🟡 partial (remainder listed) · ⏳ not started · ➖ out of scope / pack file missing.

---

## 1. Architecture as built

```
Admin/instructor intent ─► Intent compiler (deterministic regex, authoring.parse_admin_message /
                           live_runtime.compile_instructor_command) ─► proposed patch / recommendation
                           ─► validation + impact preview ─► explicit APPLY ─► presentation plan / live state
Tutor agent (ADK) ─► propose_widget / format_math tools ─► REST /v1/widgets/generate (validated WidgetSpec)
                                                                  │
PostgreSQL (authoritative, migration 020) ◄── one transaction: state + live.session_event + pipeline.outbox_event
     │
     └► mathbank-live socket gateway (polls the event log, fans out by audience) ─► student / instructor UIs
        (WidgetHost renders only registered declarative types; nothing generated is executed)
```

Key decisions (each traceable to the pack's master instructions):

| Decision | Where |
|---|---|
| Responsibility-specific REST namespaces; no generic `/api/agent/action`. | `routers/fluid.py`, `routers/live.py` |
| Admin chat produces **proposed patches**; only an explicit admin `APPLY` mutates a plan. | `authoring.py`, `authoring.proposed_patch` |
| Published plans immutable (DB trigger), edits create a new DRAFT version with the same `plan_key`. | `authoring.guard_published_plan` / `guard_published_topic` |
| WidgetSpec is versioned declarative JSON; scripts/HTML/handlers rejected at every depth. | `widgets.py` (`FORBIDDEN_KEYS`, `_FORBIDDEN_VALUE`, 64 KB / 300 elements) |
| Activity semantics (`activity.*`) separate from rendering (`visual.*`). | migration 020 |
| Server time authoritative (`time_state`), tutor only **proposes** adaptation. | `live_runtime.time_state`, `live.recommendation` |
| Lessons stay teachable when AI/widgets fail: deterministic templates and formatting, no model in the hot path. | `widgets.compose`, `math_format.deterministic_format` |

## 2. Per-file map of the pack

| Pack file | Status | Implemented as | Remainder |
|---|---|---|---|
| `00_INDEX.md` — four layers, intent→patch→apply flow | ✅ | §1 above; layers kept separate (content/pedagogy untouched). | — |
| `01_EXPERIENCE_PRINCIPLES.md` | ➖ missing from pack | Principles inferred from 16/26. | Obtain file; re-audit (NYI-FW-9). |
| `02_SERVICE_BOUNDARIES.md` | ➖ missing | Boundaries per 26 + distributed pack 02/16. | Same. |
| `03_REST_URL_NAMESPACES.md` | 🟡 | `/v1/authoring/*`, `/v1/live/*`, `/v1/activities/definitions`, `/v1/widgets/*`, `/v1/tutor/sessions/*`, `/v1/tutor/format-math`, `/v1/instructor/live/*`, `/v1/realtime/sessions/{sid}` (47 new paths). | `/v1/content/*` aliases and `/v1/authoring/course-briefs` not created — existing `/v1/problems`, `/v1/solution-steps`, `/v1/learning-items` routes are reused (NYI-FW-1). |
| `04_ADMIN_CHAT_AUTHORING.md` | ✅ (REST) | `POST /v1/authoring/chat/sessions`, `…/messages` (deterministic intent parser → operations `UPDATE_TOPIC_TIME`, `UPDATE_COURSE_LIMIT`, `UPDATE_BUFFER`, `SET_HARD_LIMIT`, `ADD_TOPIC`, `REMOVE_TOPIC`, `MOVE_TOPIC`, `RENAME_TOPIC`, `SET_TOPIC_REQUIRED`, `ADD_SCENE`), `…/proposed-patches`, `…/{patch_id}/apply` with `APPLY`/`REJECT`/`MODIFY`/`ASK_FOR_ALTERNATIVE`; multi-op patch validated atomically; impact diff stored. | No admin **web** page yet (NYI-FW-2); parser is rule-based, no LLM fallback. |
| `05_ADMIN_STRUCTURED_UI.md` | 🟡 | REST: `PUT …/topics`, `PATCH …/timing`, `POST …/validate|approve|publish|new-version`; chat and form edits share one plan row (no hidden config). | Outline/timing/preview/inspector web UI not built (NYI-FW-2); audience, quiz density, widget style, autonomy, purge policy controls not modelled. |
| `06_COURSE_TIME_ORCHESTRATOR.md` | ✅ | `course_limit_seconds`, `interaction_buffer_seconds`, `hard_limit`, `extension_seconds`, pause accounting, `live.topic_run` planned vs actual; `GET /v1/live/sessions/{sid}/time` returns remaining/variance/optional scenes; `EXTEND`/`SHORTEN` commands; hard limit only instructor-overridable. | Scene-level actual seconds approximate (topic-level is exact). |
| `07_ACTIVITY_ORCHESTRATOR.md` | ✅ | `activity.definition` with all 9 types and 4 source types; live instances; one response per participant (re-submit replaces while OPEN); invalid type → 422 `ACTIVITY_INVALID`. | The live classroom renders option-based activities (MCQ, LIVE_POLL, CONFIDENCE_CHECK with options) as buttons; NUMERIC/SHORT_RESPONSE/STEP_ORDERING etc. are accepted by REST but have no live renderer yet (NYI-FW-10). |
| `08_WIDGET_ENGINE_ARCHITECTURE.md` | ✅ | `widgets.py` registry of the 13 types; `mathbank-widgets/WidgetHost` renders all 13; Presentation Runtime decides *when* (`SHOW_WIDGET` command), engine decides *how*. | — |
| `09_WIDGET_SPEC_DSL.md` | ✅ | Base fields `widget_type, version, title, data_refs, config, interaction, persistence, source_lineage`; geometry highlight/dim fields; `POLL_RESULT` with `activity_id`; forbidden keys rejected. | `KNOWLEDGE_GRAPH` spec renders given nodes/edges; live `root_skill_id` graph expansion not wired (NYI-FW-3). |
| `10_STATIC_WIDGETS.md` | 🟡 | Precompiled templates (`power_of_point`, `intersecting_chords`, `triangle`), stored specs with `content_hash`, admin gallery `/admin/widgets`. | No publish-time compilation of a plan's widgets / pre-render cache (NYI-FW-4). |
| `11_DYNAMIC_WIDGETS.md` | ✅ | `POST /v1/widgets/generate` (deterministic intent → template/compose, validated before READY); lifecycle enum in DB; default `EPHEMERAL`/`SESSION`. | No LLM/SVG generation path (by design first; see 28 §visual). |
| `12_GEOMETRY_VISUAL_WIDGETS.md` | ✅ | Primitives POINT…AUXILIARY_CONSTRUCTION and operations HIGHLIGHT…SHOW_RATIO validated (`validate_operations`); references checked against metadata (`_ref_checker` for diagrams). | Student vertex/segment click interactions not emitted as activity events yet (NYI-FW-5); `SolutionStep → WidgetState` sync not wired into the solve workspace. |
| `13_GRAPH_DATA_WIDGETS.md` | ➖ missing | KNOWLEDGE_GRAPH/REASONING_DAG renderers exist. | Obtain file (NYI-FW-9). |
| `14_LIVE_POLL_ENGINE.md` | ✅ | OPEN → responses → aggregate (`response_count`, `option_counts`, `option_percentages`, confidence) → CLOSED → REVEAL produces a `POLL_RESULT` widget; anonymous aggregates; branch thresholds ≥0.8 CONTINUE, ≥0.5 REINFORCE, else PREREQUISITE as a `POLL_BRANCH` recommendation; instructor `SELECT_BRANCH` overrides. | Poll sources are recorded via `source_type` (PRECOMPILED/LIVE_AGENT_CREATED/INSTRUCTOR_CREATED), not the pack's PREPLANNED/AGENT_CREATED spelling (GOT-FW-6). |
| `15_REALTIME_TRANSPORT.md` | ✅ | Delivered as Socket.IO in `mathbank-live` (28); REST `GET …/state` authoritative; reconnect sends `last_sequence`, server replays only missed events. | Event names are dotted lowercase (`scene.changed`) per distributed pack 04, not the upper-case names in this file (GOT-LIVE-9). |
| `16_FLUID_STUDENT_UI.md` | ✅ | `mathbank-live` classroom: stable regions (topic/time, stage widgets, tutor feed, composer, activity panel); state patched in place; "I'm confused" toggle; answer, ask tutor, ask instructor. Web chat/solve render widget blocks inline. | No prefetch of next scene/assets (NYI-FW-6); `HINT_REQUEST` exists in REST but the classroom has no hint button yet. |
| `17_INSTRUCTOR_CONTROL_SURFACE.md` | ✅ | `mathbank-live` console: NEXT/BACK/PAUSE/RESUME/EXTEND/SHORTEN/SKIP/CREATE_POLL/CLOSE/REVEAL/SHOW+HIDE widget/TAKEOVER/RELEASE/LOCK_AGENT, NL box → `POST /v1/instructor/live/{sid}/commands` (low-risk `AUTO_APPLY` set executes, others become recommendations), recommendations accept/reject, participants and confusion signals, event log. | `FORCE_SCENE` maps to topic jump; `ASK_TUTOR` from console not added. |
| `18_AGENT_ORCHESTRATION.md` | ➖ missing | Agent tools `propose_widget`, `format_math`; AI actions via `/v1/tutor/sessions/{sid}/actions` are proposals only. | Obtain file. |
| `19_WIDGET_VALIDATION_SECURITY.md` | ✅ | Whitelist registry, forbidden keys at any depth incl. `on*` handlers, `javascript:` URLs, size limits, diagram reference checks, student input re-validated server-side; KaTeX `trust:false`. Tests in `tests/test_fluid_widgets.py`. | — |
| `20_EPHEMERAL_VS_PERSISTENT.md` | ✅ | `persistence` STATIC/SESSION/EPHEMERAL; promotion `POST /v1/widgets/specs/{id}/review` NOMINATE → `PROMOTION_CANDIDATE`, PROMOTE → `PROMOTED_TO_TEMPLATE` + `STATIC`, REJECT. | Purge job for expired ephemeral specs not scheduled (NYI-FW-7). |
| `21`–`25`, `28` | ➖ missing (failure/fallback, observability, E2E examples, phases, acceptance tests, what-not-to-do) | Fallback behaviour implemented where named in 16/26 (static widget templates, deterministic formatter when the model fails, voice buttons degrade to a "!" state while typing keeps working). | Obtain files (NYI-FW-9). |
| `26_COPILOT_MASTER_INSTRUCTIONS.md` | ✅ | Boundary audit done first; all rules above honoured; test classes: API contract, widget schema, realtime reconnect, browser interaction, security rejection — all present (§4). | — |
| `27_COPILOT_PROMPT_SEQUENCE.md` | 🟡 | Prompts 1–13 and 15 delivered; prompt 14 (failure/fallback) partly: widget failure + reconnect tested, graph/vector outage tests not added. | NYI-FW-8. |

## 3. Requirements (normative, as implemented)

| ID | Requirement | Status |
|---|---|---|
| FW-1 | Every live mutation is a REST command written to PostgreSQL in one transaction with its `live.session_event` and `pipeline.outbox_event`. | ✅ |
| FW-2 | Commands are idempotent by `client_command_id` (`live.command_receipt`) and version-checked by `expected_session_version` for staff/AI (students are not version-bound). | ✅ |
| FW-3 | AI actions never mutate directly: `AI_TUTOR` may only propose (`live.recommendation`, `based_on_version`); proposals become `STALE` on takeover/lock/version change. | ✅ |
| FW-4 | Widget specs are validated before persistence or display; invalid → 422 with error list. | ✅ |
| FW-5 | Student endpoints never return staff-only fields (correctness policy, recommendations, handoff packets, other students' identities). | ✅ (smoke-tested) |
| FW-6 | Published plans immutable; edits create versions. | ✅ (trigger) |
| FW-7 | Course time is server-authoritative and pause-aware. | ✅ |
| FW-8 | Live-created widgets/activities default to SESSION/EPHEMERAL; promotion requires admin review. | ✅ |
| FW-9 | Lessons remain usable without any model: deterministic widget compose, formatter and NL compiler. | ✅ |

## 4. Verification

| Check | Command | Result (2026-10-06) |
|---|---|---|
| REST unit + contract | `cd mathbank-rest && .venv/bin/pytest tests/test_fluid_widgets.py -q` | 55 passed (incl. ACTIVITY_INVALID and widget-generate auth tests) |
| Live DB integration | `.venv/bin/pytest tests/test_live_sessions_live.py tests/test_live_http_live.py -q` (Neon) | passed |
| Widgets package | `node --test mathbank-widgets/tests/*.test.mjs` | 10 passed |
| Web widget blocks | `node --test mathbank-web/tests/widgetBlocks.test.mjs` | 3 passed |
| Browser | `npx playwright test e2e/input-addons.spec.mjs e2e/live-classroom.spec.mjs` | pass |

## 5. Change log

- 2026-10-06: Created after implementing the pack (migration 020, `widgets.py`, `math_format.py`, `authoring.py`,
  `live_runtime.py`, routers `fluid.py`/`live.py`, `mathbank-widgets/`, admin `/admin/widgets`, agent widget tools).
