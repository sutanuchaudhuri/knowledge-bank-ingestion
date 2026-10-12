> **Status**: design guidance, largely matches what's built (see
> [`01_architecture_and_design.md`](01_architecture_and_design.md) for the
> as-implemented version). This file is the richer source design — read it
> for the *why* behind the ADK/REST/Postgres layering boundaries.

# 07 — System Architecture and Boundaries

## 1. Objective

Build a query agent capable of conversational questions over the mathematics corpus, such as:

- What are the recent questions on combinatorics?
- Show geometry problems involving inversion.
- Find problems similar to this inequality.
- Which AMC 10 problems in the last five years involved expected value?
- Give me AIME problems that combine number theory and combinatorics.
- What techniques occur most often in recent HMMT geometry problems?
- Show the source and taxonomy evidence for this classification.

The first version serves anonymous and admin users only.

---

## 2. Layered architecture

```text
┌────────────────────────────────────────────────────────────┐
│                    Client / Chat UI                        │
└───────────────────────┬────────────────────────────────────┘
                        │
                 identity context
                        │
┌───────────────────────▼────────────────────────────────────┐
│             Google ADK Query Agent                         │
│                                                            │
│  OpenAI LLM                                                │
│  - intent interpretation                                   │
│  - conversational clarification                            │
│  - tool selection                                           │
│  - evidence synthesis                                      │
└───────────────────────┬────────────────────────────────────┘
                        │ Function tools
┌───────────────────────▼────────────────────────────────────┐
│                 Agent Tool Adapter                         │
│                                                            │
│  typed inputs                                              │
│  timeouts/retries                                          │
│  auth propagation                                          │
│  response validation                                       │
└───────────────────────┬────────────────────────────────────┘
                        │ HTTPS/JSON
┌───────────────────────▼────────────────────────────────────┐
│                Mathematics REST API                        │
│                                                            │
│  authentication / authorization                            │
│  query normalization                                       │
│  taxonomy resolution                                       │
│  retrieval planning                                        │
│  hybrid RAG                                                │
│  ranking/deduplication                                     │
│  provenance packaging                                      │
└───────────────┬──────────────────┬─────────────────────────┘
                │                  │
       ┌────────▼────────┐  ┌──────▼────────┐
       │ PostgreSQL core │  │ PostgreSQL     │
       │ corpus/taxonomy │  │ FTS + pgvector │
       └────────┬────────┘  └──────┬────────┘
                │                  │
                └──────────┬───────┘
                           │
                    optional projection
                           │
                    ┌──────▼───────┐
                    │ Graph store  │
                    │ later/when   │
                    │ useful       │
                    └──────────────┘
```

---

## 3. Strong boundaries

### ADK agent owns

- language understanding
- conversational context
- selection among approved tools
- asking clarification only when unavoidable
- turning structured evidence into a useful answer
- explaining how it interpreted ambiguous terms

### REST service owns

- corpus semantics
- canonical identifiers
- authorization
- taxonomy aliases
- temporal interpretation defaults
- SQL query construction
- vector search
- FTS
- ranking
- deduplication
- provenance
- paging
- response size limits

### PostgreSQL owns

- canonical data
- taxonomy
- source provenance
- searchable text
- embeddings
- retrieval metadata
- query/retrieval diagnostics as appropriate

This boundary is deliberate. An LLM-generated SQL tool would make authorization, query cost, correctness, schema evolution and observability much harder.

---

## 4. Why one query agent initially

Do not begin with a large multi-agent team.

For v1 use one `LlmAgent` with a narrow toolset. Retrieval is deterministic enough that separate "planner", "retriever" and "writer" LLM agents would add latency and failure modes without adding much value.

A future supervisor/sub-agent design may be justified for:

- theorem/proof reasoning
- problem-solving tutoring
- corpus administration
- ingestion repair
- personalized tutoring

but not for basic RAG retrieval.

---

## 5. Stateless vs conversational state

The corpus query itself should be stateless.

ADK session state may retain short conversational references:

```text
User: Show recent combinatorics questions.
Agent: [returns list]

User: Only AIME.
```

The second turn can reuse the previous intent as conversational context, but no persistent student model exists.

Persist only operational metadata needed for observability, subject to privacy policy.

---

## 6. Non-goals

The agent is not:

- a database administrator
- a general SQL console
- a source of truth independent of the corpus
- a student-progress tracker
- a grading agent
- an automatic taxonomy editor for anonymous users
- a vector-index administration endpoint

Admin operations should be explicit tools with separate scopes.
