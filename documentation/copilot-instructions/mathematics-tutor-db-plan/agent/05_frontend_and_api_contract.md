# Agent 05 — Frontend and API Contract

## `mathbank-web` ↔ `mathbank-agent` contract

`mathbank-web` never calls `mathbank-rest` directly — only the ADK REST
server exposed by `mathbank-agent` (`adk api_server`, default port `8001`).

### Create a session (once per browser tab)

```
POST /apps/{app_name}/users/{user_id}/sessions/{session_id}
```

- `app_name` is always `"mathbank_tutor"` (the folder name under
  `mathbank-agent/agents/`).
- `user_id` is `"anonymous"` today (see
  [06_security_and_access_model.md](06_security_and_access_model.md)).
- `session_id` is a client-generated random string
  (`mathbank-web/src/agentClient.js::newSessionId()`); ADK persists session
  state server-side (in-memory by default — restarting `mathbank-agent`
  loses all sessions, which is fine for this stage).

### Send a message

```
POST /run
Content-Type: application/json

{
  "app_name": "mathbank_tutor",
  "user_id": "anonymous",
  "session_id": "web-1733...-ab12cd",
  "new_message": {"role": "user", "parts": [{"text": "..."}]}
}
```

Response: `list[Event]`. Each event has (among other fields):

```json
{
  "author": "mathbank_tutor",
  "content": {
    "role": "model",
    "parts": [
      {"function_call": {"name": "search_problems", "args": {...}}},
      {"function_response": {"name": "search_problems", "response": {...}}},
      {"text": "The most recent question on combinatorics is..."}
    ]
  }
}
```

`mathbank-web` concatenates every non-user `text` part across all returned
events as the displayed reply (`agentClient.js::sendMessage`). A richer UI
could instead render `function_call`/`function_response` parts as
collapsible "thinking" steps for transparency — not implemented yet.

There is also `POST /run_sse` (Server-Sent Events, token-by-token streaming)
which `mathbank-web` does not use yet but is a natural next step for a
"typing..." experience.

## `mathbank-agent` ↔ `mathbank-rest` contract

The tools in `agents/mathbank_tutor/tools/rest_tools.py` are plain `httpx`
calls against `mathbank-rest`'s existing v1 API
(`mathbank-rest/src/mathbank_rest/routers/v1.py`):

| Endpoint | Method | Notes |
|---|---|---|
| `/v1/search/problems` | POST | Hybrid RAG; body = `{query, filters:{competition,year_min,year_max}, retrieval:{semantic,lexical}, order_by, limit}` |
| `/v1/problems/by-code/{canonical_code}` | GET | Returns `concepts[]`, `techniques[]`, `solutions[]` nested |
| `/v1/competitions` | GET | — |
| `/v1/corpus/coverage` | GET | Per-competition papers/problems/mapped counts |
| `/v1/concepts` | GET | `?domain=` substring filter |
| `/v1/concepts/{slug}/problems` | GET | — |

`MATHBANK_REST_BASE_URL` (default `http://127.0.0.1:8000`) is the only
configuration the agent needs to find it — no service discovery, no shared
database credentials (the agent process never holds a Postgres password).

## Environment variables summary

| Variable | Used by | Default |
|---|---|---|
| `OPENAI_API_KEY` | `mathbank-agent` (LiteLLM), `mathbank-rest` (query embeddings), `mathbank-db` (corpus embeddings) | *(must be exported in the shell — never committed)* |
| `MATHBANK_AGENT_MODEL` | `mathbank-agent` | `openai/gpt-4o-mini` |
| `MATHBANK_REST_BASE_URL` | `mathbank-agent` | `http://127.0.0.1:8000` |
| `VITE_AGENT_BASE_URL` | `mathbank-web` | `http://127.0.0.1:8001` |
| `MATHBANK_AGENT_DEFAULT_ROLE` | `mathbank-agent` (reserved, not yet enforced) | `ANONYMOUS` |
