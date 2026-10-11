# 10 — Query Understanding and Planning

## 1. Query interpretation

The conversational layer converts natural language into a semantic retrieval request.

Example:

```text
"What are the recent questions on combinatorics?"
```

Interpretation:

```json
{
  "resource": "question",
  "topic_text": ["combinatorics"],
  "time_intent": "recent",
  "sort_intent": "newest_relevant",
  "answer_intent": "list_and_summarize"
}
```

The agent does **not** choose the actual year range itself.

---

## 2. Why "recent" belongs in REST

The corpus may lag the current calendar.

Suppose the latest competition year currently loaded is 2025 even though the calendar is 2026. If the agent guesses "2024–2026", it may incorrectly imply missing 2026 records.

REST should resolve:

```text
time_policy = recent
```

against the corpus itself.

Recommended default:

```text
recent = latest N distinct competition years represented
```

where `N` is server configuration, e.g. 3.

The response always reports:

```json
{
  "effective_filters": {
    "year_from": 2023,
    "year_to": 2025
  },
  "time_basis": "competition_year",
  "time_policy": "recent"
}
```

The answer can then say:

> I interpreted "recent" as the latest three competition years currently represented in the corpus: 2023–2025.

> **Status**: `mathbank-rest`'s `search_problems` currently supports
> `order_by="year_desc"` and explicit `year_min`/`year_max` filters, but does
> not yet auto-resolve a "recent" time window server-side — the agent/caller
> must pass explicit years. Adding server-resolved `time_policy=recent` is a
> good next increment (see
> [`20_implementation_sequence.md`](20_implementation_sequence.md)).

---

## 3. Topic resolution

Natural language:

```text
combinatorics
counting
pigeonhole
coloring
arrangements
inclusion exclusion
```

must be resolved against canonical taxonomy.

Use:

1. exact taxonomy slug/name match
2. alias/synonym table
3. FTS over taxonomy labels/descriptions
4. taxonomy embeddings when needed

The retrieval response distinguishes:

```text
explicit taxonomy match
semantic topic expansion
```

Do not silently reclassify a problem because its text "sounds combinatorial."

---

## 4. Filter extraction

Agent-extractable filters:

- competition family
- contest
- year/year range
- problem number
- broad topic text
- technique text
- explicit difficulty request
- source type
- answer availability
- solution availability

REST validates all values.

---

## 5. Query classes

### A. Structured browse

> AMC 10 geometry questions from 2024.

Mostly SQL/taxonomy.

### B. Hybrid topical

> Recent combinatorics questions.

SQL/time + taxonomy + FTS + vector.

### C. Semantic similarity

> Problems like this where symmetry avoids casework.

Vector-heavy with optional technique expansion.

### D. Corpus analytics

> Which techniques appear most often in HMMT combinatorics?

Aggregate SQL endpoint, not a RAG answer over top-k documents.

### E. Entity lookup

> Show 2025 AIME I #8.

Canonical lookup, no vector search.

Correct query classification avoids using vector search where a precise database lookup is better.

---

## 6. Planning policy

The ADK tool description should encourage:

```text
entity lookup -> get_question
analytics -> aggregate/search analytics endpoint
structured/hybrid corpus search -> search_questions
concept lookup -> search_concepts
```

Avoid a separate LLM planner unless evaluation shows the root model routinely chooses the wrong tool.

---

## 7. Ambiguity

When a term maps to several taxonomy nodes, REST can return:

```json
{
  "status": "ambiguous",
  "candidates": [...]
}
```

The agent can then ask a concise clarification.

For low-risk ambiguity, REST may return a broader search with an `interpretation_notes` field.
