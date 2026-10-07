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

### Topic pedagogy and relevance corrections

`pedagogy_agent` is an additional real ADK AgentTool, separate from the ten
artifact specialists and presentation formatter. Exact short topic prompts
(up to 80 characters, e.g. “Power of point”) are deterministically routed before
root-model inference. A public read-only exact-taxonomy plan supplies three
teaching stages, one checkpoint and published-step-supported example codes.
Bare topics now create an ADK-persisted **lesson**, not a contest recommendation.
Power of a Point has seven authored units: theory, recognition, isolated skill,
guided application, mixed application, transfer and original-problem readiness.
Current A-D checkpoints are revision-checked; wrong answers stay, misconceptions
are recorded, and a quiz does not certify mastery. `get_topic_lesson` restores
the current learner-safe view. Other exact topics explicitly disclose missing
authored content instead of inventing validated lessons.

The introductory chord diagram has four validated reset-to-base frames, with
circle/intersection recognition and same-chord pair highlighting. It is private,
ephemeral, requires authorization, and is not a source figure or proof.
Explicit practice uses `/v1/tutor/topic-practice` and its `topic-fit-v1` profile;
up to ten ranked candidates are checked for completeness and one is shown.
Conversation exposure survives topic changes and review resets. Unknown ranking
signals stay unknown; source-order difficulty is not measured contest difficulty.
An unmatched explicit practice request asks for canonical-topic clarification;
it cannot fall through to a loosely related vector recommendation.
The root final reply is pinned to the grounded lesson/candidate rather than an unrelated
model rewrite. Unverified root drafts are not streamed over a pinned plan;
formatter styling must bind to that exact plan and cannot swap its contents.
Long/ambiguous requests still depend on model tool selection.

Clear short relevance complaints after a single known topic recommendation
trigger `report_pedagogy_feedback`, an actual bounded retrieval-audit AgentTool,
then a lesson replan. Reports require runtime-derived
student authorization, stay PENDING with server audit evidence in migrations 023/024, and do not approve tags,
update vectors/graph, change mastery or fine-tune models. The complained-about
candidate is excluded in that conversation even if report storage/sign-in fails;
failure to persist is explicitly disclosed. Older conversations without the
new topic state require the root to resolve the code/topic from context.
Admin `/admin/pedagogy` has a paginated report queue with evidence notes and
RESOLVED/DISMISSED decisions plus explicit relevance/error labels. Resolved
reviewed negatives gate topic practice; reviewed labels are retriever evaluation
data, not automatic training. Actual corrections use revision-checked annotation
review and explicit graph publication, separately.

Applicability requires evidence from the solution reasoning: do not equate
“power of a prime” with “power of a point,” or copy a problem-level technique
onto every step. Approved/published step tags may still be machine-derived and
are not mathematical proof. The existing deterministic step derivation already
has a regression against this false keyword match. Package problem-level tags
remain allegations until checked; rejected/human corrections survive reimports.
Future textbook imports flag structurally unsupported Power proposals as import
conflicts and withhold new canonical bridge tags; no bulk reimport/retagging was
run. Missing signatures require human source review, not automatic rejection.
The configured-model specialist adds normal inference cost; endpoint grounding,
feedback and regression checks require no paid models.
See [topic-first delivery and remaining limits](../requirements/33_TOPIC_FIRST_TUTOR_AND_PRACTICE.md).

### Complete practice recommendations

Selected-problem coaching resolves numbered recommendations and calls
`prepare_problem_guidance`: canonical graph context and source figures are
loaded, then REST privately consults up to six stored solutions before selecting
a short route rationale, 3–5 stages and one first checkpoint. AIME Q1 has an
authored source-gated route; other plans can use the existing REST model.
Raw reference bodies and official-answer fields never enter this tool result.
Safe selected plans remain in ADK session JSON for follow-up context.
Unverified records remain unverified; a taxonomy match is not proof of a strategy.
No private chain-of-thought is shown.
The web activity mapper exposes only allowlisted retrieval statuses and counts,
not raw tool contexts, solutions or warning strings. The exact problem-bound
browser discussion prompt routes deterministically before the root model and
pins the safe plan reply. Broader intent/numbered-selection resolution still
uses the orchestrator; formal Prasolov step-runtime requests remain separate.
`get_next_hint` also uses private REST references before generating one cue.
Missing references/provider errors are explicit; no solution-backed evidence
is invented. Generated plans/hints are not certified correctness. See
[guided workspace contract](../requirements/34_GUIDED_PROBLEM_WORKSPACE.md).

For practice suggestions the tutor uses `search_practice_problems`, which checks
up to five retrieved candidates and returns at most two eligible problems.
`get_practice_problem` also verifies direct taxonomy/skill candidates. These
read-only tools return statement/diagrams/source and ready-to-display Markdown,
never answers or solutions. Required-diagram markers, unparsed Asymptote/image
placeholders, missing statements and unreadable registered diagrams exclude a
candidate. Image availability is verified through the student-safe image route,
not inferred from a database row or model narration.

Rejected statements are not returned by practice search. The tutor is instructed
to select another candidate, not offer a broken question with a “diagram
unavailable” warning. Explicit learner-selected problems remain accessible
through ordinary lookup/source routes. Known original source/PDF links accompany
eligible recommendations. This does not certify paid-model tool choice; offline
tests verify filtering and actual tutor tool registration.

### Presentation formatter and automatic math guard

The root tutor applies an offline `after_model_callback` to every final visible
response: single/double-escaped `\(...\)` and `\[...\]` become canonical Markdown
math; whitespace at the delimiters is trimmed. Code, Asymptote, link destinations,
thought parts, tool arguments and partial streaming chunks are untouched. The UI
independently normalizes accumulated text, including older saved messages.

An additional real ADK `formatter_agent` uses the existing authenticated/bounded
AgentTool delegation (not remote A2A). Ask, for example:
“Keep the wording; color givens blue and the goal indigo, bold key terms and
italicize qualifications.” Its `format_tutor_text` tool accepts the original
text plus at most 24 nonoverlapping `{start,end,style}` annotations, using Python
character offsets. Allowed styles are `bold`, `italic`, `given`, `goal`,
`insight`, `warning`; colors come exclusively from UI theme tokens. Text is
64,000 characters maximum; annotation JSON is 16,000 maximum. Whole inline
formulas may be selected; partial math, existing markup, code, links, arbitrary
CSS/HTML and multiline selections are rejected with `FORMAT_INVALID`.

The formatter's final response is pinned to its last deterministic tool result,
not its model's rewritten prose; the root's final reply is pinned too after
successful delegation. Delegate requests must be JSON `{"text":"exact original",
"instructions":"desired styles"}`. Invocation-scoped source binding rejects a
formatter model that changes the original text before calling its tool.
This is presentation, not mathematical
verification. Formatting cannot repair invalid TeX or infer missing math
delimiters. Ordinary delimiter correction adds no model call; optional semantic
delegation uses the configured model and therefore can incur provider charges.
Scripted ADK tests verify contracts/authorization without paid inference; live
model style/tool-selection quality is not certified.

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
