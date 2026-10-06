# 23 — Automatic Browser Regression Suite (Playwright)

Status: **implemented** — `mathbank-web/e2e/`, config [`playwright.config.mjs`](../mathbank-web/playwright.config.mjs).

## 1. Purpose

A repeatable, browser-level regression run against the live local stack (web :5173 → REST :8000 →
agent :8001 → Neon/Aura) that catches hydration errors, broken pages, auth/ownership regressions,
image rendering, and the solve-workspace recovery loop — without paid model calls by default.

## 2. How to run

```bash
make -C mathbank-web e2e-install   # one-time: Chromium headless shell
make up                            # stack must be running
make -C mathbank-web e2e           # default: no paid model calls (@llm specs skipped)
make -C mathbank-web e2e-llm       # includes @llm specs (small paid OpenAI calls via the agent/REST)
make -C mathbank-web e2e-report    # open last HTML report
```

Environment overrides: `E2E_BASE_URL` (default `http://localhost:5173`), `E2E_LLM=1`,
`E2E_ADMIN_USERNAME` / `E2E_ADMIN_PASSWORD` (otherwise read from `ADMIN_LOGIN_*` in `mathbank-web/.env`).
Artifacts: `mathbank-web/playwright-report/`, `mathbank-web/test-results/` (git-ignored).

## 3. Coverage

| Spec | Checks |
|---|---|
| `public.spec.mjs` | 10 public pages render with no hydration/page errors; anonymous nav shows "Student login"; `/db` lists `PRASOLOV_PGV1` with 1,697 problems. |
| `student.spec.mjs` | Dedicated test learner (`e2e.regression.student@example.com`, auto-registered); signed-in nav; `/learn/conversations`; foreign transcript → 403/404; diagram image loads on `PRASOLOV_PGV1_CH21_P024`; Power-of-a-Point (`CH03_P050`) similar steps + "Strengthen this skill" detour without provenance text, then return. |
| `admin.spec.mjs` | Admin pages redirect to `/admin/login` when signed out; `/admin`, `/admin/conversations`, `/admin/knowledge-gaps`, `/admin/pedagogy` render; conversations API returns `{linked[], unlinked_count}`. |
| `tutor-llm.spec.mjs` (`@llm`) | Home tutor answers a Power-of-a-Point question using `search_problems` and cites Prasolov; the chat appears in conversations; hint + graded step submission. |

`watchPageErrors(page).assertClean()` fails any test that logs a hydration mismatch, uncaught page error, or TypeError.

## 4. Baseline (2026-05, local stack)

- Default run: **23 passed** (~41 s).
- `E2E_LLM=1 tutor-llm.spec.mjs`: **2 passed** (~22 s).

## 5. Rules

- Read-mostly: the suite creates only the dedicated e2e learner, its attempts/agent sessions, and graded
  steps on that learner. It never mutates corpus, taxonomy or admin approvals.
- Specs depend on Prasolov data (`CH03_P050`, `CH21_P024`); if the corpus changes, update `e2e/helpers.mjs`.
- Not run in CI yet (no hosted stack); see [20 register](./20_NOT_YET_IMPLEMENTED.md).
