# 28 — Distributed Live Platform & Socket Deployable (`LIVE`)

Requirement IDs: `LIVE-*`. Source pack: `math_tutor_distributed_platform_copilot_handoff/` (18 files including
`START_HERE_COPILOT.md`, `PACKAGE_MANIFEST.md`, `SHA256SUMS.json`, `UPSTREAM_PLATFORM_REFERENCES.md`).
**Keep the pack** until this document and the tracker are audited. Built on the fluid widget layer
([27](27_FLUID_WIDGET_LAYER.md)); student add-ons in [29](29_STUDENT_INPUT_ADDONS.md).

Status legend: ✅ delivered and tested · 🟡 partial · ⏳ not started · 🕓 deferred by design · ➖ pack file missing.

---

## 1. What was built

`mathbank-live/` is a **separate deployable** (own `package.json`, `Makefile`, port **5174**), not a route inside
`mathbank-web`. It is a Next.js app with a custom Node server (`server.mjs`) that mounts a Socket.IO gateway
on the same HTTP server.

| Part | File | Responsibility |
|---|---|---|
| Custom server | `mathbank-live/server.mjs` | Next request handler + Socket.IO on `/socket.io`; `destroyUpgrade:false` so HMR sockets survive in dev. |
| Gateway | `lib/gateway.mjs` | Auth on connect (student JWT cookie `mb_student_token` or admin session cookie `mb_admin_session`), room joins, `live:op` → REST relay, event pump, rate limit. **No business logic.** |
| Event helpers | `lib/events.mjs` | Pure audience/room routing and replay merge — browser-safe (no `node:crypto`); clients import this, never `gateway.mjs`. |
| REST client | `lib/rest.mjs`, `lib/server.js` | Server-side calls to `mathbank-rest` with admin key or the student bearer; key never reaches the browser. |
| Student classroom | `app/s/[sid]`, `_components/Classroom.jsx` | Topic/time bar, stage widgets, tutor/instructor feed, MathComposer + voice, activity card, "I'm confused". |
| Instructor console | `app/i/[sid]`, `_components/Console.jsx` | Controls, NL command box, recommendations, participants/confusion, takeover/lock, event log. |
| Home / login | `app/page.jsx`, `app/login`, `app/api/auth/*` | Create/join sessions by code; student and admin login (cookies shared with `mathbank-web` because cookies are host-scoped, not port-scoped). |
| Next API | `app/api/{join,sessions,me,format-math,voice/*}` | Thin server-side proxies (see [REST_API](reference/REST_API.md) §mathbank-live). |

### Communication planes (pack START_HERE §Communication planes)

| Plane | Implemented as |
|---|---|
| Browser live plane | Socket.IO `ws://<host>:5174/socket.io` (polling fallback). |
| Authoritative API plane | FastAPI `/v1/live/*`, `/v1/instructor/live/*`, `/v1/tutor/sessions/*`, `/v1/activities/*`, `/v1/widgets/*` (writes PostgreSQL). |
| Backend domain-event plane | `live.session_event` (append-only, ordered by `sequence`) + `pipeline.outbox_event` in the same transaction. NATS not used (🕓). |
| Future agent plane | ADK agent tools (`propose_widget`, `format_math`) and `/v1/tutor/sessions/{sid}/actions|messages` (proposals only). MCP gateway ⏳. |

### Socket protocol

| Direction | Event | Payload / ack |
|---|---|---|
| C→S | `live:join` | `{session_id, last_sequence}` → ack `{ok, role, participant_id, state, events}` (events = replay after `last_sequence`). |
| C→S | `live:op` | `{session_id, op, args}`; `op` ∈ student/staff `state`, `command`, `respond`, `ask_tutor`; staff-only `transition`, `pause`, `resume`, `open_activity`, `close_activity`, `reveal_activity`, `show_widget`, `hide_widget`, `override`, `instructor_nl`, `decide` → ack `{ok, data}` or `{ok:false, status, error, code}`. Staff ops are refused for students by **REST** auth, not only the gateway. |
| S→C | `live:event` | One event envelope (see `04` row in §2). |
| S→C | `connect_error` | `UNAUTHENTICATED` for anonymous sockets. |

Rooms: `${sid}|session`, `${sid}|student:<participant_id>`, `${sid}|group:<id>`, `${sid}|instructor`.
Audience `SESSION` → session room; `STUDENT` → that student's room plus instructors; `INSTRUCTOR` → instructor room only
(handoff packets, aggregates, recommendations never reach students).

Delivery: the gateway pumps `GET /v1/live/sessions/{sid}/events?after=<seq>` every **700 ms** per active session and
fans out new rows. Clients dedupe by `sequence` and on reconnect re-join with their last sequence, so missed events are
replayed from PostgreSQL. `ask_tutor` is rate-limited to **6/min** per socket.

## 2. Per-file map of the handoff pack

| Pack file | Status | Implemented as | Remainder |
|---|---|---|---|
| `START_HERE_COPILOT.md` | ✅ | Architecture audit performed first (REUSE: FastAPI, Postgres/pgvector, Neo4j, ADK, auth, KaTeX; EXTEND: outbox, widget renderer; NEW: live/activity/visual/authoring schemas, socket gateway, live app; DEFER: NATS, Redis, Temporal, MCP). Platform invariants 1–7, 9, 10 hold; invariant 8 (binary assets outside PG) holds trivially because no assets are stored yet. | Asset storage (NYI-LIVE-5). |
| `00_INDEX.md` | ✅ | Reading order followed. | — |
| `01`, `05`–`10`, `14`, `18`, `19`, `21`–`24`, `26`–`29`, `32`, `33` | ➖ missing | Not in the delivered pack. | Obtain and re-audit (NYI-LIVE-9). |
| `02_MICROFRONTEND_ARCHITECTURE.md` | 🟡 | Separate deployable `mathbank-live` for student + instructor live surfaces; shared UI in `mathbank-widgets` (local package, copied by `make sync-widgets`). | No module federation / independent student vs instructor MFE builds — one app with two routes (GOT-LIVE-2). |
| `03_SOCKET_GATEWAY.md` | ✅ | `lib/gateway.mjs`: authenticate, join rooms, relay commands to REST, fan out events, replay on reconnect, rate limits; stateless apart from in-memory pump cursors. | Horizontal scale needs Redis adapter (NYI-LIVE-2). |
| `04_SOCKET_EVENT_CONTRACT.md` | ✅ | Envelope `{event_id, event_type, session_id, sequence, session_version, correlation_id, causation_id, actor_type, actor_id, audience, audience_id, timestamp, payload}`; 30 dotted event types: `session.created|started|paused|resumed|completed`, `participant.joined`, `scene.changed`, `topic.skipped`, `time.adjusted`, `activity.opened|closed|revealed|response.accepted|aggregate.updated`, `widget.shown|updated|hidden`, `tutor.message`, `instructor.message`, `instructor.takeover.started|ended`, `instructor.handoff_packet`, `agent.locked|unlocked`, `branch.selected`, `recommendation.proposed`, `student.confused|question|hint_requested|widget_interaction`. | Formal JSON-schema package not published. |
| `11_VISUAL_AGENT_PLATFORM.md` | 🟡 | Single deterministic visual path: `/v1/widgets/generate` + `compose` + templates; the tutor proposes via `propose_widget`. | Separate visual agent service ⏳ (NYI-LIVE-4). |
| `12_STATIC_VISUAL_AGENT.md` | ⏳ | Static templates exist; no offline batch generation agent. | NYI-LIVE-4. |
| `13_DYNAMIC_VISUAL_AGENT.md` | 🟡 | Dynamic geometry overlays generated deterministically from intent + diagram metadata (fast path). | Slow path (image/SVG generation, job queue) ⏳. |
| `15_ASSET_STORAGE.md` | 🟡 | `visual.asset` table (metadata only, FKs to problem/diagram). | No Asset API, no object store, no signed URLs (NYI-LIVE-5). |
| `16_SHARED_POSTGRES_GRAPH.md` | ✅ | All live state in the shared Neon database (schemas `live`, `activity`, `visual`, `authoring`); graph reads mediated by REST. | — |
| `17_MCP_AGENT_GATEWAY.md` | ⏳ | — | NYI-LIVE-6. |
| `20_HUMAN_HANDOFF.md` | ✅ | `TAKEOVER`/`RELEASE` with scope SESSION/STUDENT/GROUP (`live.takeover`, one active per scope); `control_mode` INSTRUCTOR_ACTIVE blocks AI messages (409 `AI_NOT_IN_CONTROL`); `LOCK_AGENT`; handoff packet `GET /v1/instructor/live/{sid}/handoff` and `instructor.handoff_packet` event; pending AI recommendations → STALE. | Group-scoped takeover has no UI (no groups UI) (NYI-LIVE-3). |
| `25_DURABLE_WORKFLOWS.md` | 🕓 | Temporal deferred, per the pack's own decision criteria: sessions are short, state is in PG with receipts/sequence replay. | Revisit when multi-day workflows appear (NYI-LIVE-7). |
| `30_COPILOT_MASTER_INSTRUCTIONS.md` | ✅ | Rules honoured: PG authoritative, socket is transport, idempotent commands, version checks, AI proposes, instructor wins. | — |
| `31_COPILOT_PROMPT_SEQUENCE.md` | 🟡 | See §3. | — |
| `PACKAGE_MANIFEST.md`, `SHA256SUMS.json`, `UPSTREAM_PLATFORM_REFERENCES.md` | ➖ informational | Upstream zips (expanded v2, interactive course runtime v1, fluid widget layer) are **not** in the repo; minimal compatible models were implemented instead. | GOT-LIVE-1. |

## 3. Prompt sequence status (`31_COPILOT_PROMPT_SEQUENCE.md`)

| # | Prompt | Status |
|---|---|---|
| 1 | Architecture audit | ✅ |
| 2 | Shared contracts | ✅ envelope + command contract in REST and `lib/events.mjs` |
| 3 | Live Session Service | ✅ `live_runtime.py`, `routers/live.py` |
| 4 | Socket Gateway | ✅ `mathbank-live/lib/gateway.mjs` |
| 5 | Student MFE | ✅ `/s/[sid]` |
| 6 | Instructor MFE | ✅ `/i/[sid]` |
| 7 | Activity Service | ✅ activities in REST (`activity` schema) — module inside REST, not a separate service |
| 8 | NATS + outbox | 🟡 outbox rows written; NATS ⏳ |
| 9 | Redis | ⏳ |
| 10 | Visual Platform split | ⏳ |
| 11 | Dynamic geometry overlay | ✅ deterministic |
| 12 | Slow visual generation | ⏳ |
| 13 | Dynamic content | ✅ ephemeral live activities/widgets with promotion |
| 14 | Group mode | 🟡 schema + audience/rooms; no UI |
| 15 | MCP Gateway | ⏳ |
| 16 | Temporal decision | 🕓 documented decision: defer |

## 4. Requirements (normative, as implemented)

| ID | Requirement | Status |
|---|---|---|
| LIVE-1 | The socket deployable runs independently (`make -C mathbank-live start`, port 5174) and talks to REST only over HTTP. | ✅ |
| LIVE-2 | Anonymous sockets are rejected; identity comes from the existing student JWT / admin session cookie. | ✅ |
| LIVE-3 | Every socket mutation is relayed to REST; the gateway holds no authoritative state. | ✅ |
| LIVE-4 | Reconnect with `last_sequence` replays exactly the missed events for the caller's audience. | ✅ (unit + smoke) |
| LIVE-5 | Instructor events (handoff, aggregates, recommendations) never reach student rooms. | ✅ (smoke asserts) |
| LIVE-6 | Instructor takeover takes effect immediately and stops AI messages until release. | ✅ |
| LIVE-7 | The admin key never reaches the browser; voice/format proxies run server-side. | ✅ |
| LIVE-8 | `make up` / `make access` include the live app. | ✅ |

## 5. Operations

```bash
make -C mathbank-live install   # npm install + copy ../mathbank-widgets
make -C mathbank-live start     # :5174, logs in mathbank-live/.server.log
make -C mathbank-live access    # URLs
make -C mathbank-live test      # gateway/events unit tests, no services
make -C mathbank-live smoke     # two sockets (instructor + student) against running REST + live, no paid calls
make sync-live-env              # copies REST URL/admin key/JWT secret + ELEVEN_API_KEY into mathbank-live/.env (hidden)
```

Production: `make -C mathbank-live build && npm start` (custom server; Next `output: "standalone"` is **not** used
because it drops the custom server — GOT-LIVE-4).

## 6. Verification

| Check | Result (2026-10-06) |
|---|---|
| `make -C mathbank-live test` | 10/10 pass |
| `make -C mathbank-live smoke` | PASS — join, replay, poll open/answer/reveal, takeover blocks AI (409), instructor-only events not delivered to student |
| `npx playwright test e2e/live-classroom.spec.mjs` (mathbank-web runner) | pass — student and instructor browsers, poll round-trip, takeover banner |
| REST `tests/test_live_sessions_live.py`, `test_live_http_live.py` | pass (Neon) |

## 7. Change log

- 2026-10-06: Created; `mathbank-live` deployable, migration 020 live/activity/visual/authoring schemas, live REST.
