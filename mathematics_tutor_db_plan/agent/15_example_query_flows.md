> **Status**: complements `04_example_queries.md`, which has the real,
> live-run traces against the actual system. These are additional flow
> patterns (structured browse, technique semantics, follow-ups, aggregates,
> admin diagnostics) not all yet exercised live.

# 15 — Example Query Flows

## Example 1 — Recent combinatorics

### User

```text
What are the recent questions on combinatorics?
```

### Agent interpretation

```json
{
  "resource": "question",
  "topic_text": ["combinatorics"],
  "time_intent": "recent"
}
```

### Tool

```text
search_questions(
    query="combinatorics",
    topic_slugs=["combinatorics"],
    time_policy="recent",
    limit=10
)
```

### REST plan

```text
1. validate anonymous visibility
2. resolve `combinatorics` taxonomy node
3. find latest configured N distinct competition years
4. build eligible problem set
5. taxonomy candidate ranking
6. FTS candidate ranking
7. pgvector candidate ranking
8. fuse ranks
9. canonical problem deduplication
10. return top 10 + total hit count + effective filters
```

### Answer

The agent uses only returned records and reports the effective year window.

---

## Example 2 — Structured exact query

### User

```text
Show AMC 10A combinatorics questions from 2025.
```

REST can mostly use relational/taxonomy filters.

Vector search may be skipped because the request is already precise.

This is important: hybrid RAG is available, not mandatory.

---

## Example 3 — Technique semantics

### User

```text
Find recent problems where double counting is useful even if they are not tagged double counting.
```

Plan:

```text
hard filter: recent
taxonomy branch: combinatorics if appropriate
semantic query: "double counting ..."
vector retrieval: STRUCTURAL_NORMALIZED + TECHNIQUE_SIGNATURE
FTS: "double counting" and aliases
fuse
```

The response can distinguish explicitly tagged and semantically similar results.

---

## Example 4 — Similarity from pasted problem

### User

```text
Find questions similar to:
How many colorings of ...
```

Tool:

```text
search_similar_questions(text=..., limit=10)
```

REST embeds the query text and applies vector-heavy retrieval, optionally enriching with inferred taxonomy candidates.

The LLM should not itself solve the pasted problem merely to fabricate search tags.

---

## Example 5 — Follow-up

### Turn 1

```text
Show recent combinatorics questions.
```

### Turn 2

```text
Only AIME.
```

The ADK session can infer that "only AIME" modifies the previous search.

Tool call becomes:

```text
search_questions(
    query="combinatorics",
    topic_slugs=["combinatorics"],
    competition_slugs=["aime"],
    time_policy="recent"
)
```

---

## Example 6 — Aggregate query

### User

```text
What combinatorics techniques have appeared most often in AIME since 2020?
```

This should call an analytics endpoint, not retrieve 20 chunks and ask the LLM to count them.

REST performs the aggregation in PostgreSQL and returns exact counts.

---

## Example 7 — Admin diagnostic

### Admin

```text
Why did 2024 HMMT February #6 rank above #9 for this query?
```

The agent calls an admin retrieval-debug tool.

REST returns rank components.

The model explains the diagnostics but does not invent ranking internals.
