# MathBank Agent — Design & Flow Documentation

This directory documents the **agentic layer** built on top of the data
platform in `mathematics_tutor_db_plan/` (Postgres system of record + Neo4j
graph projection + `search.*` pgvector/hybrid-RAG subsystem) and
`mathematics_tutor_db_plan_v2/vector/` (the vector/RAG subsystem itself).

Implementation lives in three sibling projects at the repo root:

| Project | Role |
|---|---|
| [`mathbank-rest/`](../../mathbank-rest) | FastAPI service; the *only* read/write boundary to Postgres — hybrid RAG search + corpus lookups |
| [`mathbank-agent/`](../../mathbank-agent) | Google ADK agent (OpenAI models via LiteLLM); tools call `mathbank-rest` only, never Postgres directly |
| [`mathbank-web/`](../../mathbank-web) | Minimal React chat frontend; talks to `mathbank-agent`'s ADK REST server only |

For how the underlying Postgres/Neo4j/search data actually got populated, see
[`../00_implementation_progress.md`](../00_implementation_progress.md) — this
directory assumes that data already exists and documents what's built *on top*
of it.

## Documents

1. [**01_architecture_and_design.md**](01_architecture_and_design.md) —
   component diagram, why Google ADK + LiteLLM/OpenAI (not Gemini), why tools
   call REST instead of Postgres directly, tool catalog.
2. [**02_ingestion_pipeline_flow.md**](02_ingestion_pipeline_flow.md) —
   end-to-end data flow from raw corpus (CSV + crawled PDFs/AoPS pages) through
   Postgres, embeddings, and the Neo4j graph projection. Summarizes/links the
   five ingestion rounds already completed.
3. [**03_inference_and_retrieval_flow.md**](03_inference_and_retrieval_flow.md) —
   what happens, step by step, between a user typing a question and the agent
   replying: session creation, function-calling, hybrid RRF SQL, response
   synthesis. Sequence diagram included.
4. [**04_example_queries.md**](04_example_queries.md) — several fully worked
   example queries (including the flagship *"What are the recent questions on
   combinatorics?"*, run live against the real system) with the exact tool
   call, REST request/response, and underlying SQL for each.
5. [**05_frontend_and_api_contract.md**](05_frontend_and_api_contract.md) —
   the React ↔ ADK REST contract (`/apps/.../sessions/...`, `/run`), request/
   response shapes, and the REST endpoints `mathbank-rest` exposes to tools.
6. [**06_security_and_access_model.md**](06_security_and_access_model.md) —
   today's anonymous/admin model, what's intentionally *not* implemented yet
   (student profiles, attempt history, mastery-aware retrieval), and the
   planned extension points.

## One-line summary of the full flow

```
React chat ──▶ ADK agent (OpenAI via LiteLLM) ──tool call──▶ mathbank-rest
  ──hybrid RRF SQL (pgvector + FTS)──▶ Postgres (core.* / knowledge.* / search.*)
  ──rows──▶ mathbank-rest ──JSON──▶ agent ──grounded answer──▶ React chat
```

Nothing in the agent or frontend ever talks to Postgres or Neo4j directly —
`mathbank-rest` is the sole boundary, matching the governing rule from
`mathematics_tutor_db_plan/README.md`: *"nothing exists only in the graph"*
extends here to *"nothing is answered that the REST API didn't return."*
