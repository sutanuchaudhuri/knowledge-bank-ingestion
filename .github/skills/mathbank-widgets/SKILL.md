---
name: mathbank-widgets
description: 'Working in mathbank-widgets: the shared React widget renderer, MathComposer, and voice helpers used by mathbank-web and mathbank-live. Use when editing WidgetHost, MathComposer, or any file under src/ in this package.'
argument-hint: 'Optional: component name to focus on'
---

# mathbank-widgets conventions

Full detail: [mathbank-widgets/README.md](../../../mathbank-widgets/README.md).

## Non-negotiables

- This package never calls an AI provider directly — `formatEndpoint`/`sttEndpoint` are always
  host-app-provided routes; keep provider credentials out of this package.
- `WidgetHost` renders **declarative specs only** (dispatch on `widget_type`), never executes
  arbitrary code — this is the safer alternative to `mathbank-agent`'s `propose_widget` tool
  generating free-form UI; don't weaken that boundary.
- `MathComposer` is a fully controlled component — it owns no internal text state; consumers must
  update `value` via `onChange`.
- Changes here require a re-sync in both consumers (`make sync-widgets` in `mathbank-web` and
  `mathbank-live`) before they take effect anywhere — this package is distributed by file-copy, not
  a live symlink or registry install.
- Import only through the documented `exports` (`mathbank-widgets`, `./format`, `./speech`,
  `./server`) — never a deep `src/...` path, since `"sideEffects": false` is declared.

## Before changing anything

1. `make test` (node --test: format/speech/server) and `make lint` (syntax-check `.js`/`.mjs`;
   `.jsx` files need a consumer's JSX transform, this package has none standalone) must stay green.
2. After any change, re-run `make sync-widgets` in both `mathbank-web` and `mathbank-live` and spot
   check their own test suites — a change here with no consumer verification is not actually done.
