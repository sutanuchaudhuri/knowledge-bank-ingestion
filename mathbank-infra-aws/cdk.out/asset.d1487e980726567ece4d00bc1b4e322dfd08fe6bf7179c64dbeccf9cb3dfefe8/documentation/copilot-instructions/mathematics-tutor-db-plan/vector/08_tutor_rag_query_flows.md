# Vector 08 — Tutor RAG and Retrieval Query Flows

## 1. One generic vector search endpoint is insufficient

The tutor needs distinct retrieval behaviors with different filters and representation types.

## 2. Similar-problem flow

Inputs:

- reference problem or free-form problem text;
- optional competition/source scope;
- target difficulty;
- exclusions.

```text
problem/query representation
        ↓
query embedding
        ↓
semantic candidates
        ↓
hard SQL filters
        ↓
duplicate suppression
        ↓
taxonomy consistency
        ↓
difficulty adjustment
        ↓
final K
```

Return only the problem statement unless solution access is explicitly part of the request.

## 3. Explain-concept flow

For a query such as:

> Why does power of a point work?

retrieve a balanced context set:

1. concept definition;
2. intuitive explanation;
3. theorem/derivation;
4. one or two worked examples;
5. common misconception.

Do not return five semantically similar problem statements.

## 4. Hint-generation flow

For a known problem:

1. load canonical problem;
2. load reviewed concept/technique assertions;
3. retrieve hint patterns and relevant solution steps;
4. apply current hint-level policy;
5. structurally exclude final-answer content if the hint level forbids it;
6. assemble context;
7. generate hint.

Answer leakage must be controlled by retrieval, not only by a generation prompt.

## 5. Diagnose learner solution

For a written attempt:

1. embed learner reasoning;
2. retrieve related misconception representations;
3. retrieve analogous correct solution steps;
4. retrieve prerequisite concept explanations;
5. compare with canonical solution structure;
6. generate diagnostic feedback.

Do not determine mathematical correctness from vector similarity alone.

## 6. Next-problem recommendation

Use:

```text
graph/taxonomy candidate generation
        +
mastery state
        +
difficulty constraints
        +
semantic similarity to current work
        +
novelty/attempt-history exclusion
```

The best next problem is pedagogically adjacent, not simply the nearest vector.

## 7. Research mode

Example:

> Find structurally similar uses of inversion across olympiad geometry.

Research mode may:

- retrieve a larger candidate set;
- expose similarity components;
- include competition/year/source;
- include matched concepts and techniques;
- show relevant solution snippets;
- preserve provenance;
- tolerate higher latency than interactive tutoring.

## 8. Internal query contract

```json
{
  "query_text": "telescoping reciprocal sum",
  "query_entity": null,
  "retrieval_profile": "SIMILAR_PROBLEM",
  "filters": {
    "competitions": ["AIME"],
    "year": {"gte": 2000},
    "review_status": ["VERIFIED"]
  },
  "learner_context": {
    "exclude_attempted": true,
    "max_difficulty_delta": 1
  },
  "representation_kinds": [
    "PROBLEM_STATEMENT",
    "STRUCTURAL_NORMALIZED"
  ],
  "candidate_limit": 100,
  "final_limit": 10,
  "debug": false
}
```

## 9. Context assembly

Do not paste raw retrieval results directly into the tutor model context.

The context assembler should:

1. deduplicate source entities;
2. fit the context budget;
3. preserve equations intact;
4. retain citations/provenance;
5. prioritize reviewed content;
6. respect hint/solution visibility rules;
7. separate source content from generated metadata;
8. avoid overloading the model with redundant examples.

## 10. Retrieval trace

Store enough data to answer: *why did the tutor choose this?*

```json
{
  "retrieval_profile": "SIMILAR_PROBLEM:v3",
  "embedding_model": "math-embed-v2",
  "query_hash": "...",
  "vector_candidates": 100,
  "lexical_candidates": 62,
  "graph_expansions": 14,
  "post_filter_candidates": 47,
  "reranked": 30,
  "returned": 8
}
```

## 11. Low-confidence behavior

The retriever should support an explicit state such as:

```text
INSUFFICIENT_RETRIEVAL_CONFIDENCE
```

Then the tutor can broaden retrieval, rely on canonical concept data, or explain that the corpus did not produce a strong match instead of injecting irrelevant context.
