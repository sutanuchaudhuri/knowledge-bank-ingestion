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

There is no login yet — every browser session is `user_id="anonymous"` with a
random per-tab `session_id`. An `ADMIN` role and real student profiles/attempt
history are planned (see
[`mathematics_tutor_db_plan/agent/06_security_and_access_model.md`](../mathematics_tutor_db_plan/agent/06_security_and_access_model.md))
but not implemented in this UI yet.
