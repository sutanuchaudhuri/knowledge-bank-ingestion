# 14 — Evidence, Context and Answering

## 1. Grounded answer rule

For corpus-content claims:

```text
No REST evidence -> no corpus claim
```

The LLM may explain general mathematics from its own model knowledge when the product permits it, but it must clearly distinguish that from corpus retrieval.

---

## 2. Evidence record

Recommended evidence object:

```json
{
  "problem_id": "problem:aime:2026:i:7",
  "display_label": "2026 AIME I #7",
  "statement": "...",
  "competition": {
    "name": "AIME I",
    "year": 2026
  },
  "taxonomy": [
    {
      "slug": "combinatorics",
      "path": "Combinatorics",
      "confidence": 1.0,
      "status": "reviewed"
    }
  ],
  "source": {
    "source_id": "src_...",
    "label": "...",
    "canonical": true
  }
}
```

---

## 3. Answer rendering

For:

> What are the recent questions on combinatorics?

Prefer:

```text
I interpreted "recent" as 2024–2026, the latest three
competition years currently represented in the corpus.

1. 2026 AIME I #7 — [short description]
2. 2026 AMC 12A #18 — [short description]
3. 2025 HMMT ... — [short description]

I found 31 matching questions; these are the first 10.
```

The displayed range comes from `effective_filters`, not model inference.

---

## 4. Source references

Every result should carry a stable canonical identifier.

The UI can render:

```text
2026 AIME I #7
problem_id: ...
source: ...
```

For an answer-generation API, include result IDs separately from prose so downstream applications can create links without parsing model text.

---

## 5. Context limits

Retrieval REST returns a controlled number of concise records.

The agent should not automatically fetch full solutions when the user only asked to find questions.

Context expansion is demand-driven:

```text
search -> list
user selects problem -> get context
user asks for solution -> authorized solution endpoint
```

This improves latency, cost and pedagogical control.

---

## 6. Confidence

Do not convert a vector similarity score into a statement like:

> This is definitely combinatorics.

Instead expose evidence type:

```text
canonical taxonomy match
semantic match
lexical match
```

If taxonomy classification is unreviewed, the API can mark it accordingly.

---

## 7. Hallucination defense

The answer instruction should prohibit:

- making up competition/year/problem numbers
- reconstructing missing problem statements
- claiming counts not present in API results
- saying "no such question exists" when only top-k search failed

Use precise wording:

> The current search returned no matches under these filters.

rather than:

> There are no such problems.
