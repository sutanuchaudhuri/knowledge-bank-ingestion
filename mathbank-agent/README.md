# mathbank-agent

Agentic backend for the MathBank tutor, built on [Google ADK](https://github.com/google/adk-python),
using **OpenAI models via LiteLLM** (not Gemini) to answer questions about the
competition-math corpus stored in Postgres (`mathbank-db`) and served over
REST (`mathbank-rest`).

The agent's corpus tools never query Postgres directly — corpus data access goes through
`mathbank-rest`'s hybrid (semantic + lexical) search and lookup endpoints,
keeping Postgres as the single source of truth and the REST API as the only
read/write boundary (see `mathematics_tutor_db_plan/` for why).
ADK conversation sessions, events and state are stored directly in Postgres
in the isolated `agent_sessions` schema, not in corpus tables.

## Persistent server sessions

`make run`, `make start` and `make web` use `server.py` with ADK's
`DatabaseSessionService` and the psycopg async driver. Connection settings are
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`,
`POSTGRES_PASSWORD`, and `POSTGRES_SSLMODE`. Precedence is shell, agent `.env`,
root `.env`, then REST `.env`. `make sync-env` also copies these settings into
the agent `.env`. SSL defaults to `require`; set `disable` explicitly for a
local server without TLS.

Startup verifies connectivity and creates the isolated schema and ADK tables
if needed. The configured database role needs CREATE permission on the database
for the initial schema creation, and ownership/access to its ADK tables.
Initialization errors stop startup; there is no SQLite/in-memory fallback.
Credentials are not passed in command-line arguments or printed.

Session state and events survive server restarts, keyed by ADK application,
user and session IDs. These are conversation records, not measured learner
mastery. Existing `.adk/session.db` files are preserved but are not automatically
migrated; old sessions are not available through the Postgres-backed server.
The CLI `make chat`, evaluation and smoke-test runners remain ephemeral.
Back up and apply retention controls to `agent_sessions` as conversation data.

Run focused tests with `.venv/bin/python -m pytest tests/test_session_storage.py`.
Set `MATHBANK_TEST_POSTGRES=1` to additionally verify live event/state persistence
across two separate database-service instances; the test deletes its own session.

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

# Set OPENAI_API_KEY in root .env and run make sync-openai-key from the root,
# shell keys are ignored. Configure Postgres as described above.
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

### Artifact specialist agents

The tutor now delegates through **Google ADK `AgentTool`**, not a public remote
A2A endpoint. All ten agents in the artifact handoff's topology are instantiated
in [artifact_agents.py](agents/mathbank_tutor/artifact_agents.py):

| Agent | Delegation / capability |
|---|---|
| Subject Planning | Routes to Geometry, Algebra, Combinatorics or Number Theory |
| Geometry | Geometry plans, exact triangle incircles and validated SVG previews |
| Algebra | Equation/term plans and stable LaTeX alignment |
| Combinatorics | Labelled cases, nodes, tables and trees |
| Number Theory | Modulus, factors, divisibility and Euclidean structures |
| LaTeX | Mathematical text refinement for subject agents |
| SVG | Declarative layout/semantic-ID refinement; never executable SVG |
| Overlay/Frame | Ordered valid-target pedagogical highlights |
| Annotation | Captions, concept tags and supplied explanation/step links |
| Validation | Calls authoritative REST plan validation and reports actual errors |

The root exposes the planner and four subject agents as tools; subjects can
delegate to the five refinement/validation agents. This is a directed acyclic
Agent-as-Tool network: the tutor retains conversational control, and specialists
return results to their caller. Simple drawings do not invoke every refinement
agent unnecessarily. Reusable publication/indexing remains an explicit staff
operation; previews are private, ephemeral and do not write the corpus or store.

Each specialist uses the tutor's existing OpenAI/LiteLLM model configuration.
Student authentication is invocation-scoped: ADK child runners require restoring
`temp:` authorization via an async-context-local handoff because child session
creation strips it. Tokens are never model arguments/prompts/results or saved
conversation events. Anonymous delegation stops before inference/REST access.
At most 16 delegations and 24 specialist model calls are allowed per invocation;
each delegate times out after 120 seconds. These are operational limits, not a
dollar spending cap. Provider failures do not select a different model/provider.

The tested ADK baseline is `google-adk[db]>=2.11`. Verify without paid calls:

```sh
.venv/bin/python -m pytest -q tests/test_artifact_agents.py
```

These tests use real ADK Runner/AgentTool execution with scripted models and
mocked REST, proving nested routing/authentication and all subject paths. They do
not certify live model tool-selection quality or implement remote A2A discovery,
agent cards, cross-service tasks, or a remote trust/authentication protocol.

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
