# Vector 07 — Relational + Vector + Graph Integration

## 1. Distinguish three relationship classes

### Canonical relational fact

Example:

```text
2025-AMC10A-18 belongs to the AMC 10A 2025 paper.
```

Stored in PostgreSQL domain tables.

### Asserted knowledge relationship

Example:

```text
Power of a Point PREREQUISITE_FOR Radical Axis.
```

Stored authoritatively in PostgreSQL knowledge tables and projected to the graph.

### Similarity observation

Example:

```text
Problem A is close to Problem B under embedding model M.
```

This is a retrieval/computed signal, not automatically a mathematical fact.

## 2. Vector → graph candidate generation

Vector search is useful for proposing:

- `SIMILAR_TO` candidate problem edges;
- duplicate/near-duplicate candidates;
- potential concept links;
- potential technique links;
- misconception clusters.

Recommended flow:

```text
vector similarity
      ↓
candidate pair
      ↓
structural/taxonomy checks
      ↓
confidence/evidence
      ↓
assertion candidate in PostgreSQL
      ↓
review/validation
      ↓
accepted canonical knowledge relation
      ↓
graph projection
```

Do not write ANN neighbors directly into the graph as permanent knowledge.

## 3. Graph → vector retrieval

The graph can constrain semantic search.

Example request:

> Find a harder problem on concept C using only techniques adjacent to concepts already mastered.

Flow:

1. graph/taxonomy expands the allowed concept/technique set;
2. SQL obtains eligible problem IDs;
3. pgvector ranks semantically within that eligible set;
4. difficulty and learner-state filters apply;
5. final reranker chooses the result set.

Embeddings should not be asked to infer the prerequisite graph from scratch on every query.

## 4. Full retrieval composition

```text
query text/entity
     │
     ├── query embedding ─────── vector candidates
     │
     ├── exact text ──────────── lexical candidates
     │
     ├── structured intent ───── SQL filters
     │
     └── knowledge intent ────── graph/taxonomy expansion
                                  │
                                  ▼
                              candidate fusion
                                  │
                                  ▼
                                rerank
                                  │
                                  ▼
                           tutor context set
```

## 5. Materialized similarity

Do not precompute every pairwise similarity; that becomes quadratic.

If durable high-value similarity is needed, materialize only selected relationships.

```sql
CREATE TABLE knowledge.problem_similarity (
    source_problem_id uuid NOT NULL REFERENCES core.problem,
    target_problem_id uuid NOT NULL REFERENCES core.problem,
    similarity_kind text NOT NULL,
    embedding_model_id uuid REFERENCES search.embedding_model,
    score numeric NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    review_status text NOT NULL DEFAULT 'AUTO',
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (
      source_problem_id,
      target_problem_id,
      similarity_kind,
      embedding_model_id
    )
);
```

Use this only for reviewed similarity, deduplication, curriculum sequences, or caches with clear value.

## 6. Taxonomy assignment assistance

For a new problem:

1. embed the problem;
2. retrieve nearest concept definitions and technique signatures;
3. retrieve nearest already-tagged problems;
4. combine those signals;
5. create candidate concept/technique assertions with confidence and provenance;
6. review/validate;
7. write accepted assertions into canonical knowledge tables.

The embedding model assists taxonomy; it does not become the taxonomy.

## 7. Learner state

Do not encode mastery only in a learner vector.

Mastery/history remain structured relational state.

Vectors can represent learner-generated free text such as:

- an explanation;
- a written solution attempt;
- a misconception;
- a question.

Semantic retrieval can then find related explanations/misconceptions/problems, while mastery calculations remain auditable.

## 8. Provenance chain

Every returned tutor item must trace:

```text
retrieval result
  → embedding
  → chunk
  → representation
  → source entity
  → source/provenance record
```

If graph expansion was used, the retrieval trace should also record the graph path or knowledge relations that expanded the candidate set.
