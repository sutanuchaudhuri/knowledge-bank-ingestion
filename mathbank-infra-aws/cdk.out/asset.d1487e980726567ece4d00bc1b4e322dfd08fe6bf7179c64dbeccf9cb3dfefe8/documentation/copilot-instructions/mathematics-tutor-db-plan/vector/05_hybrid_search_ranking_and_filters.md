# Vector 05 — Hybrid Search, Ranking, and Metadata Filters

## 1. Retrieval should not be vector-only

Mathematics includes exact names and notation that semantic embeddings may blur:

- Stewart's theorem;
- LTE;
- Vieta jumping;
- power of a point;
- `x^2 + y^2`;
- AIME 2022 #13.

The default retrieval stack should therefore be hybrid.

## 2. Candidate channels

Generate candidates from:

1. semantic vector search;
2. PostgreSQL full-text search;
3. exact canonical-code/entity lookup;
4. taxonomy filters/expansions;
5. optional graph expansion.

Then merge and rerank.

## 3. Full-text index

```sql
ALTER TABLE search.chunk
ADD COLUMN textsearch tsvector
GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(chunk_text, ''))
) STORED;

CREATE INDEX idx_chunk_textsearch
ON search.chunk USING gin(textsearch);
```

Do not rely on FTS alone for formulas. Preserve original notation and optionally use trigram/exact-search helpers.

## 4. Semantic candidates

```sql
SELECT
    e.chunk_id,
    1 - (
      e.embedding::vector(1536)
      <=> :query_embedding::vector(1536)
    ) AS semantic_score
FROM search.embedding e
WHERE e.embedding_model_id = :model_id
  AND e.status = 'ACTIVE'
ORDER BY e.embedding::vector(1536)
         <=> :query_embedding::vector(1536)
LIMIT 100;
```

## 5. Lexical candidates

```sql
SELECT
    c.chunk_id,
    ts_rank_cd(
      c.textsearch,
      websearch_to_tsquery('english', :query)
    ) AS lexical_score
FROM search.chunk c
WHERE c.textsearch @@ websearch_to_tsquery('english', :query)
ORDER BY lexical_score DESC
LIMIT 100;
```

## 6. Reciprocal Rank Fusion

Use RRF for the first hybrid merger because lexical and semantic scores have different scales.

```text
RRF(d) = sum_i 1 / (k + rank_i(d))
```

Use a conventional initial constant such as 60, then evaluate against the math retrieval benchmark.

## 7. Second-stage reranking

Later pipeline:

```text
vector top 100
lexical top 100
taxonomy candidates
       ↓
deduplicate
       ↓
RRF
       ↓
top 30–50
       ↓
cross-encoder / LLM reranker
       ↓
top 10–20
```

The reranker never replaces source provenance.

## 8. Hard filters

Hard user intent must remain hard.

Examples:

```text
competition in {AMC10, AIME}
year >= 2015
review_status = VERIFIED
difficulty <= 4
exclude attempted problem IDs
language = en
```

Do not convert a hard requirement into a soft ranking preference.

## 9. Learner-aware filters

The tutor can use relational filters for:

- mastered concepts;
- current target concept;
- excluded future concepts;
- desired difficulty delta;
- previous attempts;
- current hint level;
- solution visibility;
- source quality.

Example request:

```text
Find a similar problem
but one difficulty level easier,
using only mastered concepts,
excluding trigonometry,
and not previously attempted.
```

PostgreSQL is particularly strong here because these are native joins.

## 10. Diversity

Nearest-neighbor results can be repetitive.

After retrieval:

1. group/suppress exact duplicates;
2. penalize near duplicates;
3. diversify across sources and approaches where useful;
4. optionally evaluate Maximum Marginal Relevance.

## 11. Pedagogical ranking

Semantic relevance and instructional suitability are not identical.

Possible final ranking components:

```text
semantic relevance
lexical relevance
taxonomy match
difficulty suitability
prerequisite suitability
source quality
novelty/not already attempted
diversity
```

Store ranking configuration in versioned retrieval profiles instead of hard-coding weights across application code.

## 12. Explainability

Debug mode should expose component evidence:

```json
{
  "semantic_rank": 3,
  "lexical_rank": 8,
  "rrf_score": 0.0308,
  "matched_concepts": ["power-of-a-point"],
  "filters": {
    "competition": ["AMC10"],
    "year_gte": 2015
  }
}
```

This is essential for understanding why a tutor selected a particular example.
