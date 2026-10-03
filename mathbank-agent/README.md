# mathbank-agent

Agentic backend for the MathBank tutor, built on [Google ADK](https://github.com/google/adk-python),
using **OpenAI models via LiteLLM** (not Gemini) to answer questions about the
competition-math corpus stored in Postgres (`mathbank-db`) and served over
REST (`mathbank-rest`).

The agent never queries Postgres directly — all data access goes through
`mathbank-rest`'s hybrid (semantic + lexical) search and lookup endpoints,
keeping Postgres as the single source of truth and the REST API as the only
read/write boundary (see `mathematics_tutor_db_plan/` for why).

## Architecture

```
User (anonymous or admin) ──chat──▶ mathbank-web (React)
                                          │ HTTP
                                          ▼
                              mathbank-agent (Google ADK)
                                  LlmAgent + LiteLlm(openai/gpt-4o-mini)
                                          │ function-calling tools
                                          ▼
                                   mathbank-rest (FastAPI)
                                  /v1/search/problems (hybrid RAG)
                                  /v1/problems/by-code/{code}
                                  /v1/concepts, /v1/corpus/coverage, ...
                                          │ SQL
                                          ▼
                                  Postgres (mathbank)
                            core.* / knowledge.* / search.* (pgvector)
```

Full design docs: [`mathematics_tutor_db_plan/agent/00_index.md`](../mathematics_tutor_db_plan/agent/00_index.md).

## Quick start

```bash
# 1. mathbank-rest must already be running (see ../mathbank-rest/README or DATABASES.md)
cd ../mathbank-rest && make run &

# 2. install + configure this agent
cd ../mathbank-agent
cp .env.example .env            # edit if you want a different model/REST URL
make install

# OPENAI_API_KEY must be set in your shell (already exported in ~/.zshrc on this machine)
make chat                        # talk to the agent directly in the terminal
# or
make run                         # serve it as a REST API on :8001 (for mathbank-web)
# or
make web                         # ADK's built-in browser dev UI, for manual testing
```

Manual smoke test (no terminal chat loop, good for CI/quick checks):

```bash
.venv/bin/python scripts/smoke_test.py "What are the recent questions on combinatorics?"
```

## Tools (`agents/mathbank_tutor/tools/rest_tools.py`)

| Tool | Calls | Use for |
|---|---|---|
| `search_problems` | `POST /v1/search/problems` | Hybrid RAG — "recent questions on X", "problems about Y" |
| `get_problem_by_code` | `GET /v1/problems/by-code/{code}` | Full statement + solutions for one problem |
| `list_competitions` | `GET /v1/competitions` | What competitions exist |
| `get_corpus_coverage` | `GET /v1/corpus/coverage` | How complete the corpus is per competition |
| `list_concepts` | `GET /v1/concepts` | Browse the taxonomy |
| `get_problems_for_concept` | `GET /v1/concepts/{slug}/problems` | Problems tagged with a specific concept |

## Access model today

Every request is either `ANONYMOUS` or `ADMIN` (see
`MATHBANK_AGENT_DEFAULT_ROLE` in `.env`) — both currently get identical,
read-only access; there is no learner/student profile, attempt history, or
mastery tracking yet (see
[`mathematics_tutor_db_plan/agent/06_security_and_access_model.md`](../mathematics_tutor_db_plan/agent/06_security_and_access_model.md)
for the planned extension).
