# 20 — Implementation Sequence

## Phase 0 — Freeze contracts

Before coding the agent, finalize:

- canonical question ID
- public visibility rule
- taxonomy slugs
- `/v1/search/questions` schema
- effective filter schema
- evidence schema
- anonymous/admin claims

---

## Phase 1 — REST retrieval without an agent

Implement and test:

```text
POST /v1/search/questions
GET  /v1/questions/{id}
POST /v1/search/concepts
```

Verify:

- SQL filters
- taxonomy matching
- PostgreSQL FTS
- pgvector
- fusion
- recency policy
- deduplication

Use curl/pytest before introducing an LLM.

---

## Phase 2 — Retrieval evaluation

Create golden query set.

Reach acceptable Recall@K and filter correctness for:

- topic
- competition
- year
- recent
- semantic technique
- similarity

---

## Phase 3 — ADK public query agent

Add:

- Google ADK
- OpenAI model via `LiteLlm`
- typed REST tools
- anonymous role only
- answer grounding rules

Run tool-selection and hallucination tests.

---

## Phase 4 — Admin read tools

Add:

- provenance
- retrieval debug
- pipeline status

Implement scope-aware tool exposure plus REST enforcement.

---

## Phase 5 — Conversation UX

Support follow-ups such as:

```text
Only AIME.
Harder ones.
Show #3 in full.
Which of these use double counting?
```

Keep corpus retrieval itself stateless.

---

## Phase 6 — Production observability

Add:

- distributed trace IDs
- agent/tool latency
- retrieval diagnostics
- OpenAI cost/token metrics
- zero-result dashboards
- eval regression suite

---

## Phase 7 — Optional graph-assisted retrieval

Only after PostgreSQL hybrid retrieval is established.

Potential uses:

- prerequisite expansion
- technique neighbors
- concept paths
- multi-hop relationship questions

Graph results return through REST, not directly to the agent.

> **Status**: this phase is substantially **done** — `mathbank-graph`
> projects the full corpus graph (Competition/Paper/Problem/Solution/
> Concept/Technique nodes, `TESTS`/`USES_TECHNIQUE`/`CONCEPT_RELATION`
> edges) and `mathbank-web`'s `/graph` views already query it directly for
> visualization. The agent itself does not yet call a graph-backed REST
> tool for multi-hop reasoning — that remains the open increment.

---

## Phase 8 — Student bounded context

Later, separately implement:

- authenticated student principal
- attempts
- learner state
- personalization
- recommendations

Do not block v1 on this phase. See
[`18_future_student_profile_and_mastery.md`](18_future_student_profile_and_mastery.md)
for the detailed data model and graph attributes this phase will need.

---

# Recommended first vertical slice

Build one end-to-end query:

```text
"What are the recent questions on combinatorics?"
```

Acceptance criteria:

1. ADK uses configured OpenAI model.
2. Agent calls `search_questions`.
3. No direct database access exists in agent code.
4. REST resolves `recent`.
5. REST resolves `combinatorics`.
6. PostgreSQL structured filters run.
7. PostgreSQL FTS runs.
8. pgvector search runs.
9. ranks are fused and deduplicated.
10. only visible questions are returned.
11. agent names only returned problems.
12. answer states effective year range.
13. trace links agent -> REST -> DB retrieval.
14. anonymous cannot access admin diagnostics.

> **Status**: this vertical slice is **implemented and verified live** —
> see `mathematics_tutor_db_plan/agent/04_example_queries.md` for the real
> captured trace of exactly this query. Criteria 4 (REST resolving "recent")
> is the one partial gap — see the status note in
> [`10_query_understanding_and_planning.md`](10_query_understanding_and_planning.md).

Once this slice works, most remaining query types are extensions rather than architectural changes.
