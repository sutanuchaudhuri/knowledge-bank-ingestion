---
name: mathbank-live
description: 'Working in mathbank-live: the separately deployable Next.js + Socket.IO realtime classroom. Use when editing server.mjs, the Socket.IO gateway, or Classroom.jsx/useLive.js.'
argument-hint: 'Optional: gateway, event, or component name to focus on'
---

# mathbank-live conventions

Full detail: [mathbank-live/README.md](../../../mathbank-live/README.md).

## Non-negotiables

- This app owns **no state** — `mathbank-rest`'s `/v1/live/*` is the single source of truth for
  session/participant/event state. The gateway only relays and replays.
- `server.mjs` is a **custom** Node server — never set `output: "standalone"` in `next.config.js`.
- Reconnect correctness depends on the client passing its true `last_sequence` into `live:join`;
  don't "simplify" this by always replaying from zero.
- `mathbank-widgets` is copied by file (`make sync-widgets`), not symlinked or registry-installed —
  re-run `make install` after any change to that sibling package, edits don't propagate otherwise.

## Before changing anything

1. `make test` (node --test, gateway + event unit tests) must stay green.
2. `make smoke` exercises a real two-socket connection against a running `mathbank-rest` + this
   app — use it before trusting any gateway change, unit tests alone won't catch a live wiring bug.
3. Tutor-facing operations are paid/rate-limited (`createOpLimiter({ limit: 6 })`) — a
   paused-tutor/takeover response under load is expected behavior, not a bug to "fix" by removing
   the limiter.
