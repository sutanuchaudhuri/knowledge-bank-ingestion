# Agent 01 — Architecture and Design

## Why Google ADK with OpenAI models (not Gemini)

[Google ADK](https://github.com/google/adk-python) is a model-agnostic agent
framework — the `Agent`/`LlmAgent` class accepts any `BaseLlm` implementation.
We use `google.adk.models.lite_llm.LiteLlm`, ADK's built-in
[LiteLLM](https://docs.litellm.ai/) wrapper, with model string
`"openai/gpt-4o-mini"`. LiteLLM reads `OPENAI_API_KEY` from the environment
the same way the official OpenAI SDK does — no Google Cloud credentials,
Vertex AI project, or Gemini API key are required anywhere in this stack.

Why ADK at all, instead of calling the OpenAI SDK directly: it gives us, for
free, the pieces a "real" agent needs beyond a single chat completion —
automatic function-calling schema generation from typed Python functions,
session/state management, a ready-made REST server (`adk api_server`) for the
frontend to talk to, and a clear place to add multi-agent workflows later
(e.g. a separate diagnosis/hint sub-agent) without re-architecting.

## Component diagram

```
┌─────────────────┐      HTTP (JSON)       ┌──────────────────────────┐
│   mathbank-web   │ ─────────────────────▶ │     mathbank-agent        │
│   (React, Vite)   │ ◀───────────────────── │  Google ADK + LiteLlm     │
│   :5173           │   POST /run            │  model=openai/gpt-4o-mini │
└──────────────────┘   POST /apps/.../       │  :8001 (adk api_server)   │
                        sessions/...          └──────────┬───────────────┘
                                                          │ function-calling
                                                          │ tools (plain Python
                                                          │ functions, httpx)
                                                          ▼
                                               ┌──────────────────────────┐
                                               │      mathbank-rest        │
                                               │   FastAPI, :8000           │
                                               │ /v1/search/problems (RAG)  │
                                               │ /v1/problems/by-code/...   │
                                               │ /v1/concepts, /v1/...      │
                                               └──────────┬─────────────────┘
                                                          │ SQL (SQLAlchemy)
                                                          ▼
                                               ┌──────────────────────────┐
                                               │   PostgreSQL (mathbank)    │
                                               │ core.* / knowledge.*       │
                                               │ search.* (pgvector + FTS)  │
                                               └──────────────────────────┘
```

Neo4j (graph projection) is not yet wired into any agent tool — it exists as
a derived read model for future graph-traversal tools (prerequisite chains,
"find a path from concept A to concept B"), per
`mathematics_tutor_db_plan/graph/`.

## Why tools call REST, never Postgres directly

Per `mathematics_tutor_db_plan/postgres/01_architecture_principles.md`'s
governing rule, Postgres is the system of record and the REST API is the
*only* controlled read/write boundary. The agent is just another REST client:

- it cannot accidentally run an unbounded/expensive query — `mathbank-rest`
  already caps `limit` and validates filters;
- authentication/authorization (today: none; tomorrow: anonymous vs. admin
  vs. authenticated student) is enforced in exactly one place;
- the SQL embedding model/HNSW details stay private to `mathbank-rest`'s
  `vector_search.py` — the agent/tool layer never sees embedding dimensions,
  model UUIDs, or raw SQL, matching
  `mathematics_tutor_db_plan_v2/vector/11_rest_vector_search_contracts.md`'s
  design goal ("clients should not need to know embedding dimensions, HNSW
  parameters, physical table names, active model UUIDs").

## Project layout

```
mathbank-agent/
├── pyproject.toml            google-adk, litellm, httpx, python-dotenv
├── .env.example               MATHBANK_AGENT_MODEL, MATHBANK_REST_BASE_URL
├── Makefile                    install / run / web / chat / test
├── scripts/
│   └── smoke_test.py           manual end-to-end check (no interactive loop)
└── agents/
    └── mathbank_tutor/          one folder per agent (ADK convention)
        ├── __init__.py          `from . import agent`
        ├── agent.py             root_agent = Agent(model=LiteLlm(...), tools=[...])
        └── tools/
            └── rest_tools.py     plain typed functions calling mathbank-rest
```

## Tool catalog

Each tool is a plain Python function with type hints and a docstring — ADK
generates the function-calling JSON schema from exactly that, so the
docstring *is* what the model sees when deciding whether/how to call it.

| Tool | REST call | Purpose |
|---|---|---|
| `search_problems(query, competition="", year_min=0, year_max=0, recent_first=False, limit=10)` | `POST /v1/search/problems` | Hybrid semantic+lexical RAG — the primary tool for any open-ended topic question |
| `get_problem_by_code(canonical_code)` | `GET /v1/problems/by-code/{code}` | Full statement, answer, tagged concepts/techniques, and all known solutions for one problem |
| `list_competitions()` | `GET /v1/competitions` | Enumerate tracked competitions |
| `get_corpus_coverage()` | `GET /v1/corpus/coverage` | Per-competition ingestion completeness |
| `list_concepts(domain="", limit=50)` | `GET /v1/concepts` | Browse the taxonomy |
| `get_problems_for_concept(concept_slug, limit=25)` | `GET /v1/concepts/{slug}/problems` | Problems tagged with a specific concept |

See [04_example_queries.md](04_example_queries.md) for real traces of the
agent choosing and calling these tools.

## System instruction (summary)

The agent's instruction (full text in `agent.py`) establishes three hard
rules, enforced by prompting (not yet by a validator — see
[06_security_and_access_model.md](06_security_and_access_model.md) for
hardening ideas):

1. Never invent a problem/competition/solution the tools didn't return.
2. Always call `search_problems` with `recent_first=True` when the user says
   "recent"/"latest"/"newest".
3. Always cite `canonical_code` + competition/year for every problem
   mentioned, so a human (or a future student-attempt feature) can look it up
   again.
