> **Status**: implemented tools (`search_problems`, `get_problem_by_code`,
> `list_competitions`, `get_corpus_coverage`, `list_concepts`,
> `get_problems_for_concept`) are narrower than this full design — see
> `mathbank-agent/agents/mathbank_tutor/tools/rest_tools.py`. Admin tools
> (`admin_get_provenance`, `admin_get_retrieval_debug`,
> `admin_get_pipeline_status`) are **not yet built**.

# 09 — Agent and Tool Design

## 1. Principle

Expose a **small semantic toolset**, not a mirror of every REST endpoint.

The agent should think in corpus operations, for example:

```text
search_questions
get_question
search_concepts
get_taxonomy_node
get_problem_context
```

Admin-only operations can be separate tools.

---

## 2. V1 public tools

### `search_questions`

Primary tool for queries such as:

- recent combinatorics questions
- hard geometry questions
- AIME number theory questions from 2020–2025
- questions using invariants
- similar questions about coloring a board

Input:

```json
{
  "query": "recent combinatorics questions",
  "topics": ["combinatorics"],
  "competitions": [],
  "years": {},
  "difficulty": {},
  "techniques": [],
  "limit": 12
}
```

The tool should not invent a SQL representation. It sends this semantic request to REST.

### `get_question`

Retrieve one canonical problem by public identifier.

### `search_concepts`

Resolve concepts/techniques or browse taxonomy.

### `get_problem_context`

Return surrounding evidence for a selected problem:

- statement
- metadata
- taxonomy
- source
- related concepts
- optionally solution metadata depending on policy

---

## 3. Admin tools

Admin tools should be added only when there is a concrete UI/use case.

Candidates:

### `admin_get_provenance`

Detailed extraction/source/classification evidence.

### `admin_get_retrieval_debug`

Returns:

- SQL-filter candidate count
- FTS rank
- vector rank/distance
- fusion score
- reranker score
- applied filters
- embedding model/version
- retrieval profile

### `admin_get_pipeline_status`

Read ingestion/backfill/embedding run status.

### `admin_search_all_states`

May include draft, quarantined or review-pending records that anonymous users cannot see.

Mutation tools such as reclassify/reindex should be a later admin phase and require explicit confirmation.

---

## 4. Tool schemas should be narrow

Bad:

```text
run_database_query(sql: str)
```

Bad:

```text
call_rest(method, url, body)
```

Good:

```text
search_questions(
    query: str,
    topic_slugs: list[str] | None,
    competition_slugs: list[str] | None,
    year_from: int | None,
    year_to: int | None,
    time_policy: str | None,
    limit: int = 10
)
```

This reduces prompt injection and accidental privilege expansion.

---

## 5. Tool result contract

Every retrieval tool returns a machine-readable envelope:

```json
{
  "request_id": "req_...",
  "effective_query": {
    "query": "combinatorics",
    "topic_slugs": ["combinatorics"],
    "year_from": 2024,
    "year_to": 2026
  },
  "interpretation": {
    "time_policy": "recent",
    "time_basis": "competition_year"
  },
  "total_hits": 47,
  "results": [
    {
      "problem_id": "problem:...",
      "competition": "AIME I",
      "year": 2026,
      "problem_number": 7,
      "statement": "...",
      "topic_paths": ["Combinatorics > ..."],
      "source": {
        "source_id": "...",
        "canonical_label": "..."
      },
      "retrieval": {
        "matched_by": ["taxonomy", "vector"],
        "score": 0.87
      }
    }
  ]
}
```

Anonymous results should omit private/internal diagnostic fields.

---

## 6. Tool-call budget

Most information queries should require one retrieval call.

Use a second call only if:

- the user asks for detail about one returned item
- taxonomy resolution is truly ambiguous
- provenance is requested
- a prior result must be expanded

Avoid autonomous loops that repeatedly search with minor paraphrases.

---

## 7. REST client wrapper

All tool functions share one typed HTTP client: `MathCorpusClient` (see
[`19_reference_python_skeleton.md`](19_reference_python_skeleton.md)).
