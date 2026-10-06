# mathbank-web

Next.js chat frontend for the MathBank tutor. The browser only ever talks to
**this app** (same-origin, no CORS needed) — `app/api/agent/*` route handlers
run server-side and proxy to the `mathbank-agent` Google ADK REST server,
which itself calls `mathbank-rest` → Postgres.

```
browser ──same-origin──▶ mathbank-web (Next.js, :5173)
                              │ app/api/agent/session, app/api/agent/run
                              │ (server-side fetch, no CORS)
                              ▼
                         mathbank-agent (ADK REST, :8001) ──▶ mathbank-rest ──▶ Postgres
```

This replaces an earlier Vite/React version that called `mathbank-agent`
directly from the browser — `adk api_server` rejects cross-origin browser
requests by default (`403 Forbidden: origin not allowed`), so routing through
Next.js's own server avoids needing to configure CORS on the agent at all.

## Quick start

```bash
cp .env.example .env   # MATHBANK_AGENT_BASE_URL, defaults to http://127.0.0.1:8001
make install
make dev                # http://localhost:5173
```

Requires `mathbank-agent` running (`make -C ../mathbank-agent run`), which in
turn requires `mathbank-rest` running (`make -C ../mathbank-rest run`).

## Current user model

Students sign in at `/login` (httpOnly JWT cookie); admins at `/admin/login`.
The ADK `user_id` is derived on the server (`/api/agent/session`): the student
UUID when signed in, otherwise `anonymous`; any client-supplied id is ignored.
Signed-in chats are linked to the student in `learner.agent_session_link`, so
the full conversation can be rebuilt at `/learn/conversations` (student) and
`/admin/conversations` (admin, incl. tool calls). Anonymous chats stay
unlinked. See [requirements/22](../requirements/22_AGENT_SESSION_TRANSCRIPTS.md).

Admins can browse the imported Prasolov corpus at `/admin/textbooks`:

- Coverage matrix across source, Postgres, pgvector and Neo4j.
- Problems, transformations and taxonomy.
- `/admin/textbooks/problems/{canonical_code}`, which shows solution steps, transformations, diagrams (including solution-hidden ones) and per-store status.

See [requirements/24](../requirements/24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md).

## Tests

```bash
make test           # node unit tests (tests/*.test.mjs), no services needed
make e2e-install    # one-time: Playwright Chromium
make e2e            # Playwright regression against the running stack (no paid calls)
make e2e-llm        # also runs @llm specs (small paid OpenAI calls)
make e2e-report     # open the last HTML report
```

`E2E_BASE_URL` overrides `http://localhost:5173`. See
[requirements/23](../requirements/23_E2E_REGRESSION_SUITE.md).
