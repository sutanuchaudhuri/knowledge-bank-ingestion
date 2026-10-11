---
name: mathbank-web
description: 'Working in mathbank-web: the Next.js student/admin UI and same-origin REST/agent proxy. Use when editing pages under app/, the shared ui.jsx component set, or anything requiring the modern-ui-design visual contract.'
argument-hint: 'Optional: route or page name to focus on'
---

# mathbank-web conventions

Full detail: [mathbank-web/README.md](../../../mathbank-web/README.md). For any visual/UI change,
load the **modern-ui-design** skill first — it is the authoritative contract for this project's
components, tokens, and layout patterns; this skill only covers this project's own specifics.

## Non-negotiables

- All database credentials live server-side in `app/api/*` route handlers — the browser never
  talks to `mathbank-rest`/`mathbank-agent` directly.
- `useSearchParams()` requires a `Suspense` boundary — this only breaks at `next build`, not
  `next dev`, so always build before considering a change done.
- No `Date.now()`/`Math.random()`/locale-dependent formatting during the initial render — format
  client-side after mount, or you'll get a silent hydration mismatch.
- Admin env var is `MATHBANK_ADMIN_API_KEY`; `mathbank-rest` itself calls the same value
  `ADMIN_API_KEY` — don't assume the names match when debugging `.env` issues.

## Before changing anything

1. `make test` (node unit tests) and `make e2e` (Playwright, no paid calls) must both stay green —
   check [documentation/requirements/23_E2E_REGRESSION_SUITE.md](../../../documentation/requirements/23_E2E_REGRESSION_SUITE.md)
   for coverage/baseline before adding new specs.
2. Grep the e2e specs for any `data-testid`/accessible name you're about to change — preserving
   test contracts is a hard rule, not a suggestion.
3. Known, tracked gaps before you assume something is a bug: see
   [documentation/requirements/48_SITE_WIDE_UX_VISUAL_AUDIT.md](../../../documentation/requirements/48_SITE_WIDE_UX_VISUAL_AUDIT.md)
   (the `db/*`/`graph/*` routes predate the design-token system) and
   [47](../../../documentation/requirements/47_MICRO_COURSE_STUDENT_NAVIGATION_V2_AND_AI_ASSIST.md)
   (per-item course decomposition is designed but not implemented).
