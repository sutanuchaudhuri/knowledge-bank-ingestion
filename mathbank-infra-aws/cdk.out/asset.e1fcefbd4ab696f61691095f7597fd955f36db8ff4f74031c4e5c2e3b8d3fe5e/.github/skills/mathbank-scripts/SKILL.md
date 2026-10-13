---
name: mathbank-scripts
description: 'Working in mathbank-scripts: shared root-level developer/ops tooling (credential sync, service start/stop, connectivity checks) used by every service in the repo. Use when editing a sync-*.mjs script, start-service.sh, or project_env.py.'
argument-hint: 'Optional: script name to focus on'
---

# mathbank-scripts conventions

Full detail: [mathbank-scripts/README.md](../../../mathbank-scripts/README.md).
(Renamed from `scripts/` for naming consistency with the rest of this repo.)

## Non-negotiables

- `project_env.py` reads credentials **only** from the root `.env` — shell-exported env vars are
  deliberately ignored (see `documentation/GOTCHAS.md` GOT-ENV-1). Don't "fix" this to also honor
  shell vars; that's the point of the design.
- Every Python service (`mathbank-rest`, `mathbank-agent`, `mathbank-data-ingestion`) imports
  `project_env` via `sys.path.insert(0, str(SERVICE_ROOT.parent / "mathbank-scripts"))` — a bare
  quoted string with no trailing slash. If this folder is ever renamed again, a plain
  `grep "mathbank-scripts/"` search will **miss** these; search for the bare quoted string
  `"mathbank-scripts"` too. This exact blind spot broke 9 files during this folder's own rename
  and was only caught by actually running `import mathbank_rest...`, not by text search alone.
- `start-service.sh` is the one generic background-process launcher every `make start` target in
  this repo calls — changing its readiness-probe or PID-file logic affects every service at once;
  test against more than one service's `make start`/`make stop` before considering a change done.

## Before changing anything

1. `node --test *.test.mjs` (15 tests covering sync-openai-key, sync-live-env, sync-neon-env,
   start-service) must stay green.
2. After any change here, spot-check `make up`/`make status`/`make down` from the repo root, not
   just this folder's own tests — the real integration point is the root Makefile and every
   service's own Makefile calling into this one.
