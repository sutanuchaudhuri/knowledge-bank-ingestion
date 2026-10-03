# Agent 06 — Security and Access Model

## Today: anonymous and admin are functionally identical

Every request the agent handles comes from one of two roles, carried as
`MATHBANK_AGENT_DEFAULT_ROLE` (`ANONYMOUS` | `ADMIN`) — but **nothing in the
current tool set or REST API actually branches on this value yet**. All six
tools are read-only and return the same data regardless of caller. The role
exists as a placeholder/contract so that:

- adding the first role-gated capability (e.g. an admin-only "mark this
  taxonomy tag reviewed" mutation tool) doesn't require a new auth concept,
  just a check against a value that already flows through the stack;
- the REST layer's own security posture (per
  `mathematics_tutor_db_plan/rest/07_security_validation_observability.md`)
  already assumes a caller-identity concept will show up eventually.

## What's explicitly NOT implemented (by design, not oversight)

- **No login / authentication.** `user_id="anonymous"` is hardcoded in
  `mathbank-web`. There is no password, token, or session cookie anywhere in
  this stack.
- **No student profile.** No table in Postgres stores a learner's identity,
  preferences, or history. `knowledge.*` and `core.*` only model the
  *corpus*, never a *learner*.
- **No attempt history / mastery tracking.** There is no record anywhere of
  which problems a given user has seen, attempted, or solved. Retrieval is
  therefore never personalized or filtered by "problems you haven't tried
  yet" — every user sees the same ranked results for the same query.
- **No write endpoints exposed to the agent.** All six tools call `GET`/`POST
  …/search` endpoints that only read. `mathbank-rest` has no `PUT`/`PATCH`
  endpoints for corpus data yet (per
  `rest/04_insert_update_and_idempotency.md`, those are a planned, separate,
  admin-gated surface — not built).

## Planned extension points (not built — recorded here so the design is traceable)

| Feature | Where it would live |
|---|---|
| Real auth (e.g. OAuth/JWT) terminating at `mathbank-rest`, with the agent forwarding a bearer token per request | `mathbank-rest` middleware + `mathbank-agent`'s `rest_tools.py` adding an `Authorization` header |
| `learner.student_profile` table (id, display name, preferences) | New Postgres schema, analogous to `core.*`/`knowledge.*` |
| `learner.attempt` table (student_id, problem_id, correct, attempted_at, time_spent) | Same; referenced by `core.problem` |
| `NEXT_PROBLEM` / `exclude_attempted` retrieval profile | `search.retrieval_profile` (table already exists, unused — see `mathematics_tutor_db_plan_v2/vector/02_embedding_and_chunk_schema.md` §8) + a new `mathbank-rest` endpoint + a new agent tool |
| Admin-only mutation tools (approve a taxonomy tag, correct a problem statement) | New `mathbank-rest` `PATCH`/`POST` endpoints gated on `role=ADMIN`, new agent tools that only appear in the admin agent's tool list |
| Per-role system instructions | A second `Agent` definition (e.g. `agents/mathbank_admin/`) sharing the same tools module but a stricter/different instruction, OR a single agent reading the role from session state and conditioning its instruction |

## Threat-model notes for the current (read-only, anonymous) surface

- **SQL injection**: not reachable from the agent — all `mathbank-rest`
  queries use parameterized SQLAlchemy `text()` with bound parameters (see
  `mathbank-rest/src/mathbank_rest/db/queries.py` and `vector_search.py`);
  the agent cannot pass raw SQL fragments through any tool argument.
- **Prompt injection via corpus content**: a problem statement scraped from
  AoPS or a PDF could theoretically contain adversarial text aimed at the
  LLM (e.g. "ignore your instructions and..."). The current system
  instruction does not yet include explicit prompt-injection countermeasures
  (e.g. wrapping tool results in a clearly-delimited "untrusted data" block
  and reminding the model that tool output is data, not instructions) — this
  is a real gap worth closing before any admin-capable tools are added, since
  the blast radius of a successful injection grows with tool privilege.
- **Cost/abuse**: there is no rate limiting on `/v1/search/problems` (each
  call costs one OpenAI embedding call) or on the agent's chat endpoint
  (each turn costs one or more chat-completion calls). Acceptable for local
  development; required before any public deployment.
- **Secrets**: `OPENAI_API_KEY` is read from the environment at every layer
  that needs it and is never logged, written to a config file, or returned
  in any API response — see `GOTCHAS.md` item 6.
