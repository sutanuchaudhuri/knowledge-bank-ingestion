# Agent 04 — Example Queries (worked, against the live system)

All traces below are real — either captured from
`mathbank-agent/scripts/smoke_test.py` runs or direct `curl` calls against the
running `mathbank-rest` during development. None of this output is invented.

## 1. "What are the recent questions on combinatorics?" (flagship)

**Tool call chosen by the model:**

```
search_problems(query="combinatorics", recent_first=True)
```

**REST request** (`POST /v1/search/problems`):

```json
{"query": "combinatorics", "order_by": "year_desc", "limit": 10, "filters": {}}
```

**What happens in `mathbank-rest`:** `query` is embedded via
`text-embedding-3-small`; the hybrid RRF SQL finds candidate chunks by
semantic similarity (no literal word "combinatorics" needs to appear in a
problem — this is the point of semantic search) and by lexical match; results
are then re-sorted by `ed.year DESC` because `order_by="year_desc"`.

**Top result:**

```json
{
  "canonical_code": "PAPER_SMT_2021_COMBO_Q09",
  "year": 2021,
  "competition": "Stanford Math Tournament",
  "statement_text": "9. Alice plays the violin and piano, and would like to create a practice schedule. She will only practice one instrument on a given day, she can have break days when she does not ..."
}
```

**Agent's final answer** (actual model output, `gpt-4o-mini`):

> The most recent question on combinatorics is from the Stanford Math
> Tournament (SMT) 2021: [...] **Canonical Code:** PAPER_SMT_2021_COMBO_Q09
> **Year:** 2021 **Competition:** Stanford Math Tournament
> If you would like a full solution to this problem, please let me know!

Note the model correctly offered to fetch the solution via a second tool
call (`get_problem_by_code`) rather than fabricating one.

## 2. "Problems about cyclic quadrilaterals and power of a point"

Semantic-only match (no filters) — demonstrates retrieval working on concept
overlap rather than exact phrase matching (the phrase "power of a point"
does not appear verbatim in the top hits):

```
search_problems(query="cyclic quadrilateral power of a point")
```

Top 3 results, all genuinely on-topic SMT Power-round problems:

| canonical_code | year | lexical_rank | semantic_rank |
|---|---|---|---|
| `PAPER_SMT_2011_POWER_Q03` | 2011 | — | 3 |
| `PAPER_SMT_2011_POWER_Q10` | 2011 | — | 4 |
| `PAPER_SMT_2011_POWER_Q11` | 2011 | — | 7 |

`lexical_rank` is empty for all three — `websearch_to_tsquery` found no exact
term overlap, so relevance here is carried entirely by the embedding
similarity.

## 3. "AIME problems about ordered pairs of positive integers"

Demonstrates a query that engages **both** signals, plus a hard filter:

```
search_problems(query="ordered pairs of positive integers", competition="AIME")
```

```json
{"query": "ordered pairs of positive integers", "limit": 10, "filters": {"competition": "AIME"}}
```

Top result (both ranks populated — exact phrase overlap *and* semantic
similarity):

```json
{
  "canonical_code": "AIME_2012_II_Q01",
  "year": 2012,
  "statement_text": "Find the number of ordered pairs of positive integer solutions $(m, n)$ to the equation $20m + 12n = 2012$.",
  "rrf_score": 0.0273,
  "semantic_rank": 21,
  "lexical_rank": 7
}
```

The `competition="AIME"` filter is a plain `WHERE comp.external_code = 'AIME'`
clause applied to the SQL joins *after* candidate retrieval — it is never
encoded into the embedding itself.

## 4. "What problems use the Law of Sines?"

Two-step, concept-browsing flow rather than free-text search:

```
list_concepts(domain="Sines")
  → [{"slug": "geo-tri-sine", "name": "Law of Sines", ...}, ...]
get_problems_for_concept(concept_slug="geo-tri-sine", limit=5)
  → [{"canonical_code": "AIME_1989_Q10", "year": 1989, "role": "PRIMARY", "confidence": 0.9}, ...]
```

Use this flow instead of `search_problems` when the user names a specific
taxonomy concept rather than describing a topic in free text — it returns
*curated* tags (`knowledge.problem_concept`, confidence-scored) rather than
embedding similarity, so it's exact rather than approximate.

## 5. "How complete is your HMMT coverage?"

```
get_corpus_coverage()
  → [..., {"competition": "HMMT", "papers": 2, "problems": 12,
           "problems_with_concept": 12, "problems_with_technique": 3}, ...]
```

Real, current answer: only **2 papers / 12 problems** are registered for HMMT
(all three HMMT variants — `HMMT_FEB`, `HMMT_NOV`, `HMMT_INV` — share the
display name "HMMT" and are summed together here), with 100% concept
coverage but only 3/12 technique coverage. A well-grounded agent answer
should say this plainly rather than imply broad HMMT coverage — see
`00_implementation_progress.md` Round 3/4 for *why* (most HMMT papers aren't
downloaded/parsed yet; `pipeline.pdf_source` tracks exactly which).

## 6. "Show me the full solution to AIME 1983 Problem 5"

```
search_problems(query="AIME 1983 problem 5")   # or the model may recognize
                                                 # the canonical_code pattern
                                                 # directly and skip to:
get_problem_by_code(canonical_code="AIME_1983_Q05")
```

Returns the real statement, `official_answer="004"`, and **4 distinct
AoPS-community solutions** (verified in Round 2/5 of the ingestion pipeline;
also mirrored as 4 `HAS_SOLUTION` edges in the Neo4j graph projection).

## Design takeaway

Every example above is answerable with the current 6-tool surface without
the agent ever seeing SQL, embedding vectors, or Postgres connection details
— the REST contract successfully hides all of that (per
`vector/11_rest_vector_search_contracts.md`'s design goal). The one gap
visible in example 5 (HMMT under-coverage) is a *data* gap, not a retrieval
or agent-design gap — it is answered honestly rather than hidden.
