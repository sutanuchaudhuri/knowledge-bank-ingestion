---
name: mathbank-local-services
description: 'Working across the MathBank repo''s locally-running dev services: start/stop/restart/status for any service, list every service and its URL/port, check logs on failure, and change a service''s port. Use when asked to start, stop, restart, or check the status of mathbank-rest/agent/web/live or any extra service, to show what''s currently running and its URL, to debug why a service won''t come up, or to run a service on a non-default port.'
argument-hint: 'Optional: service short name (rest, agent, web, live, db, graph, manim, ml-inference, ml-frontend, mcp) to focus on'
---

# mathbank-local-services conventions

Full detail: the root [Makefile](../../../Makefile) (every target's one-line `##` comment is the
source of truth) and [documentation/GOTCHAS.md §12](../../../documentation/GOTCHAS.md) (the
auto-kill-on-port-conflict design this all depends on). This skill is **local dev process
management only** — for the AWS-deployed Fargate/Lambda copies of these same apps, use the
`mathbank-infra-aws` skill instead; the two are deliberately separate (different lifecycle,
different cost model, different URLs).

## What this skill does

This is the **local operational control plane** for every MathBank service that runs as a
background daemon on this machine — one shared pidfile/logfile/port convention
(`mathbank-scripts/start-service.sh`) that every core and extra service's `make start` calls.

| Service | Short name | Default port | Daemon-backed? |
|---|---|---|---|
| `mathbank-rest` | `rest` | 8000 | ✅ |
| `mathbank-agent` | `agent` | 8001 | ✅ |
| `mathbank-web` | `web` | 5173 | ✅ |
| `mathbank-live` | `live` | 5174 | ✅ |
| `mathbank-db` (Postgres) | `db` | 5433 | ✅ (idempotent start, never port-killed) |
| `mathbank-graph` (Neo4j) | `graph` | 7687 (bolt) / 7474 (browser) | ✅ (idempotent start, never port-killed) |
| `mathbank-manim-studio` | `manim` | 8020 | ✅ |
| `mathbank-ml-inference` | `ml-inference` | 8010 | ✅ |
| `mathbank-ml-frontend` | `ml-frontend` | 5175 | ✅ |
| `mathbank-mcp-competitions` | `mcp` | stdio by default (no daemon) | ❌ — `make mcp-demo`/`mcp-test` only |
| `mathbank-exam-agent` | — | 8030 | ❌ — `make exam-agent-run` only (foreground; deployed via Lambda for real use) |

Given a request, it will:
- **Start / stop / restart / check status** of one service or the whole core stack.
- **List every running service and its URL** (`make access` / `make access-extra`), without
  touching anything.
- **Diagnose why a service won't start** — port already held by something else, unhealthy
  process restarted automatically, or the daemon exited immediately — by reading the right
  `.server.log` first, not guessing.
- **Change a service's port** for one run, via each service's own `PORT`/`WEB_PORT`/`LIVE_PORT`
  Make variable override — without editing any file.

## Example prompts

- *"What's currently running and what URLs can I open?"* → `make status` then `make access`
  (add `make status-extra` / `make access-extra` for manim-studio/ml-inference/ml-frontend).
- *"Start everything"* → `make up` (REST/agent/web/live against remote Neon/AuraDB — the normal
  path; `make up-local-db` only if you explicitly want local Postgres/Neo4j instead).
- *"Stop everything"* → `make down` (core 4) — mention `make down-extra`/`make down-local-db`
  if those were also started.
- *"Restart mathbank-web, it's acting weird"* → `make web-restart`, then `make web-status`.
- *"mathbank-rest won't start"* → read `mathbank-rest/.server.log` (the exact path the failed
  `start` target prints) before guessing; check for a port-conflict message first (§ below).
- *"Run mathbank-live on port 6000 instead"* → `make live-start LIVE_PORT=6000` (one-off, not
  persisted — see Port overrides below for why NOT to edit `.env`/Makefile defaults for this).
- *"Show me mathbank-rest's logs"* → `tail -n 100 mathbank-rest/.server.log` (or `tail -f` to
  follow live); same pattern for any service (`<service-dir>/.server.log`).
- *"Is anything hogging port 5173?"* → `lsof -nP -iTCP:5173 -sTCP:LISTEN` — do this before
  assuming a start failure is a code bug.
- *"Open a real terminal window per service so I can watch live logs"* → `make up-windows` (core
  4) or `make up-windows-all` (core 4 + manim-studio/ml-inference/ml-frontend), macOS only.

## Non-negotiables

- **Never manually `kill` a process on a service's port without going through its own `make
  <svc>-stop` first** — `start-service.sh` only auto-kills a port it recognizes as *its own*
  previously-recorded PID (via the pidfile); a port held by something else is left alone and the
  `start` target fails loudly instead, specifically to avoid killing an unrelated process by
  accident ([GOTCHAS.md §12](../../../documentation/GOTCHAS.md)).
- **`db`/`graph` (Postgres/Neo4j) are never port-killed on start**, unlike every other service —
  forcefully killing a database process on a stuck port is a data-corruption risk, not just an
  inconvenience. Their `start` targets check `pg_ctl status`/`neo4j status` and no-op if already
  running instead of ever touching the port directly.
- **A service's `start` target restarts its own unhealthy process automatically** if the pidfile's
  PID is alive but failing its HTTP readiness check — this is by design (self-healing), not a bug
  to "fix" by making `start` idempotently refuse to touch a running process.
- **Logs always live at `<service-dir>/.server.log`, PID at `<service-dir>/.server.pid`** — the
  same two filenames for every daemon-backed service (`mathbank-scripts/start-service.sh`'s one
  shared convention). Never guess a different log path; it's always this one, relative to that
  service's own directory, not the repo root.
- **`PORT`/`WEB_PORT`/`LIVE_PORT` overrides are a Makefile variable, not an environment variable
  read by the app itself** — pass it on the `make` command line (`make rest-start PORT=8005`),
  not via `export PORT=8005` in a shell, or a background `nohup` process started later in the same
  shell can silently inherit a stale value from an earlier `source .env`
  ([GOTCHAS.md §14](../../../documentation/GOTCHAS.md)).
- **`mathbank-exam-agent` and `mathbank-mcp-competitions` have no `start`/`stop`/`status`
  daemon targets** — the former is `make exam-agent-run` (foreground only; it's designed to run
  for real via its Lambda deployment, not as a local daemon), the latter defaults to stdio (no
  network port at all) unless explicitly run with `MCP_TRANSPORT=http`.

## Start / stop / restart / status — one service

```bash
make rest-start / rest-stop / rest-restart / rest-status              # :8000
make agent-start / agent-stop / agent-restart / agent-status          # :8001
make web-start / web-stop / web-restart / web-status                  # :5173
make live-start / live-stop / live-restart / live-status              # :5174
make db-start / db-stop / db-status                                   # :5433 (no restart target — idempotent start)
make graph-start / graph-stop / graph-status                          # :7687/:7474 (no restart target — idempotent start)
make manim-start / manim-stop / manim-restart / manim-status          # :8020
make ml-inference-start / -stop / -restart / -status                  # :8010
make ml-frontend-start / -stop / -restart / -status                   # :5175
```

Or `cd` into the service's own directory and drop the `<svc>-` prefix (`cd mathbank-rest && make
start`) — identical targets, useful when you want that service's own `make help` listing.

## Start / stop / status — the whole stack

```bash
make up              # sync keys, start rest/agent/web/live against remote Neon/AuraDB (the normal path)
make up-local-db      # same, but also starts local Postgres/Neo4j first (local-DB dev only)
make down             # stop rest/agent/web/live
make down-local-db    # stop local Postgres/Neo4j (only relevant after up-local-db)
make status           # status of rest/agent/web/live
make up-extra         # start manim-studio + ml-inference + ml-frontend
make down-extra       # stop those three
make status-extra     # status of those three
```

## See what's running and its URL (read-only, no restart)

```bash
make access         # web/API/Swagger URLs for rest/agent/web/live + the remote Neon/AuraDB endpoints (no passwords)
make access-extra    # URLs for manim-studio/ml-inference/ml-frontend/mcp-competitions
make access-local     # same as access, but shows LOCAL Postgres/Neo4j details (only after up-local-db)
```

`make access`/`access-extra` only print — they never start, stop, or restart anything.

## Check logs on a failure

```bash
tail -n 100 mathbank-rest/.server.log     # last 100 lines; substitute any service's own directory
tail -f mathbank-web/.server.log          # follow live while reproducing the issue
```

A failed `start` target always prints the exact log path in its own error message — trust that
over guessing. Common failure signatures to look for once inside the log:
- **Port already occupied** (printed by `start-service.sh` itself, before even writing to the
  log): `ERROR: port <N> is already occupied (PID <M>), not by a process this script started. No
  process was killed.` — run `lsof -nP -iTCP:<port> -sTCP:LISTEN` to identify `<M>`, then either
  stop that process yourself or pick a different port for this run (see below).
- **Process exited immediately during startup**: `ERROR: <name> exited during startup. Inspect
  <path>/.server.log` — the log almost always has the real Python/Node stack trace right above
  the bare "process died" message; also try the service's own `make run`/`make dev` (foreground)
  to see the error live instead of re-reading a log file.
- **Recorded process alive but never became ready**: `ERROR: <name> did not become ready at <url>
  within <N>s` — the process is up but never returned HTTP 200 on its readiness URL within the
  timeout; check the log for a slow/hanging startup step (e.g. a slow DB connection), or raise
  the timeout for one run with `START_TIMEOUT=120 make <svc>-start`.

## Port overrides (one-off, not persisted)

```bash
make rest-start PORT=8005
make agent-start AGENT_PORT=8011
make web-start WEB_PORT=5183
make live-start LIVE_PORT=6174
make manim-start PORT=8021
make ml-inference-start PORT=8011
make ml-frontend-start WEB_PORT=5185
```

This only changes the port for **that one invocation** (a plain Make variable override, not a
persisted `.env` edit) — re-running `make <svc>-start` without the override goes back to the
default. If another service calls this one by its default URL (e.g. `mathbank-web` calling
`mathbank-rest` at `:8000`), changing just one side's port without also updating the caller's
`MATHBANK_REST_BASE_URL`-style env var will break that cross-service call — prefer a port
override only for isolated, single-service debugging, not for the whole stack at once.
