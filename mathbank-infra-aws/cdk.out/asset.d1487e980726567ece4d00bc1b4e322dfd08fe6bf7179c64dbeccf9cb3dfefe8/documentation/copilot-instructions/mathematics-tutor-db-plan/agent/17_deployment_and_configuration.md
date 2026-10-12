> **Status**: `mathbank-agent`/`mathbank-rest`/`mathbank-web` today all run
> as local background daemons (see root `GOTCHAS.md` #12), not yet behind a
> gateway or with the secret-manager/scaling setup described below — this is
> the target design for a real deployment.

# 17 — Deployment and Configuration

## 1. Components

Recommended deployable units:

```text
math-agent-service
math-rest-api
postgresql + pgvector
```

Graph service is optional until graph-dependent features are enabled.

---

## 2. Agent environment

```bash
OPENAI_API_KEY=...
OPENAI_MODEL=openai/<api-model-id>

MATH_API_BASE_URL=https://...
MATH_API_SERVICE_TOKEN=...

AGENT_REQUEST_TIMEOUT_SECONDS=...
AGENT_MAX_SEARCH_RESULTS=...
```

Do not expose REST service tokens to browser clients.

---

## 3. REST environment

Representative settings:

```text
DATABASE_URL
ACTIVE_RETRIEVAL_PROFILE
ACTIVE_EMBEDDING_MODEL_ID
RECENT_DISTINCT_YEAR_COUNT
MAX_PUBLIC_SEARCH_LIMIT
MAX_ADMIN_SEARCH_LIMIT
```

---

## 4. Network

Preferred:

```text
Internet/client
   |
gateway
   |
agent service
   |
private/internal REST
   |
PostgreSQL
```

PostgreSQL should not be reachable directly from the agent's public interface.

---

## 5. Secrets

Use the deployment platform's secret store.

Secrets include:

- OpenAI API key
- internal service token
- database credentials
- admin-auth signing secrets

Never place them in agent prompts or corpus tables.

---

## 6. Horizontal scaling

The query agent is largely stateless.

Scale agent instances horizontally.

Conversational sessions may use ADK-compatible shared session persistence if multi-turn behavior must survive instance changes, but student memory is still out of scope.

REST scales independently.

PostgreSQL tuning is handled at the database layer.

---

## 7. Caching

Safe candidates:

- taxonomy lookup
- competition metadata
- canonical question lookup
- repeated anonymous search result IDs for a short TTL

Be careful caching results whose visibility differs by principal.

Cache key includes:

```text
principal class
retrieval profile
effective filters
query normalization/version
```

---

## 8. Timeouts

Suggested design:

```text
ADK tool timeout > REST search timeout > DB statement timeout
```

This allows the innermost layer to fail cleanly first.

All limits should be configuration, not hard-coded policy.

---

## 9. Deployment independence

ADK does not require the corpus REST API to run in the same process.

Keeping them separate makes it easier to:

- test retrieval without an LLM
- change model providers
- expose REST to other clients
- secure admin endpoints
- independently scale vector search
