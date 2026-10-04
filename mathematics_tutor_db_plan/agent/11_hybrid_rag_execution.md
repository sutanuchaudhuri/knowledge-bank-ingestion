> **Status**: matches the implemented hybrid RRF search in
> `mathbank-rest/src/mathbank_rest/db/vector_search.py` — see
> [`../../mathematics_tutor_db_plan_v2`](../../mathematics_tutor_db_plan_v2)
> merge notes in `vector/`. The pre-filter-then-rank fix (GOTCHAS.md #12-ish,
> see root `GOTCHAS.md`) is exactly the "hard eligibility before fusion"
> principle in section 2 below.

# 11 — Hybrid RAG Execution in PostgreSQL

## 1. Retrieval architecture

Hybrid retrieval occurs behind REST.

```text
semantic request
      │
      ▼
query normalization
      │
      ├───────────────┬────────────────┬─────────────────┐
      ▼               ▼                ▼                 ▼
relational        taxonomy          FTS               vector
filters           expansion         rank              rank
      │               │                │                 │
      └───────────────┴────────────┬───┴─────────────────┘
                                   ▼
                             candidate fusion
                                   │
                             dedup / thresholds
                                   │
                          optional reranking
                                   │
                              evidence rows
```

---

## 2. Candidate stages

### Stage 1 — hard eligibility

Examples:

- published/visible state
- caller authorization
- requested competitions
- year range
- resource type

Apply hard filters as early as practical — **before** ranking/ANN search, not
after (filtering a global top-K after the fact can silently return zero
results for an eligible-but-underrepresented subset; see root `GOTCHAS.md`
for a real incident of this class of bug).

### Stage 2 — taxonomy candidates

Match canonical relationships such as:

```text
problem -> concept
problem -> technique
problem -> taxonomy node
```

Taxonomy matches are high-value structured evidence.

### Stage 3 — PostgreSQL full-text search

Search representations such as:

- problem statement
- normalized statement
- solution text when authorized
- concept definitions
- technique descriptions

### Stage 4 — pgvector

Embed the normalized search query and retrieve nearest representations from the active embedding model/index.

Candidate vectors can include:

- `PROBLEM_STATEMENT`
- `STRUCTURAL_NORMALIZED`
- `TECHNIQUE_SIGNATURE`

For a question-list request, solution chunks should normally not dominate retrieval.

---

## 3. Fusion

Start with Reciprocal Rank Fusion because lexical/vector scores have different scales.

Example:

```text
RRF(d) =
    w_taxonomy / (k + rank_taxonomy)
  + w_fts      / (k + rank_fts)
  + w_vector   / (k + rank_vector)
```

A structured taxonomy match can receive a separate boost.

Weights belong in a versioned retrieval profile, not in the agent prompt.

---

## 4. Recency

Recency should not replace semantic relevance.

For "recent combinatorics questions":

1. determine effective recent year window
2. filter to the window
3. rank by hybrid relevance
4. optionally secondarily order near-equal items by year descending

Do not simply sort all combinatorics records by ingestion timestamp.

---

## 5. Deduplication

The same problem may have:

- multiple chunks
- statement vector
- normalized vector
- solution-step vectors
- multiple source captures

Retrieval deduplicates to canonical `problem_id` before returning results.

Retain best supporting representations in an evidence list.

---

## 6. RAG context package

The REST result should already be compact enough for the LLM.

Each result contains:

```text
canonical id
contest/year/problem number
statement
taxonomy
source label
retrieval evidence
```

Do not send hundreds of raw chunks and ask the model to infer which represent the same problem.

---

## 7. Reranking

Add a reranker only after measuring baseline hybrid quality.

Possible triggers:

- semantically subtle technique queries
- large candidate sets
- poor ordering despite good recall

Keep reranking behind REST so its model/version is observable and replaceable.

---

## 8. Query logging

Store retrieval diagnostics separately from user-facing conversation content.

Useful fields:

```text
request_id
principal_class
query_hash or policy-approved text
retrieval_profile
embedding_model_id
effective_filters
candidate_counts
latency
returned_problem_ids
```

Never store the OpenAI API key or bearer credentials.

---

## 9. No-answer behavior

If nothing sufficiently matches:

```json
{
  "total_hits": 0,
  "results": [],
  "interpretation": {...},
  "suggestions": [...]
}
```

The agent should say the corpus search did not find matching records under the effective filters rather than manufacturing examples.
