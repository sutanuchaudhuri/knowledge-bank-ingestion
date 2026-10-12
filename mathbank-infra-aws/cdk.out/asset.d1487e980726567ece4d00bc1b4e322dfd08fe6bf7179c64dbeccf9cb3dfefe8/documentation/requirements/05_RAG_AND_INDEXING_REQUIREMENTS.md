# RAG And Indexing Requirements

## Purpose

The current local/remote MathBank implementation uses PostgreSQL pgvector/FTS
and Neo4j, not the historical Firestore/Sheets sketch below. Tutor searches now
combine reviewed graph candidates with vector similarity and lexical candidates,
fused at problem level. See [requirements 16](16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md)
for source evidence, filters and explicit degraded-retrieval acceptance.

The RAG layer enables natural language and structured queries against the corpus, such as:
- "Show me all questions on Probability"
- "Give me 10 hard AIME questions on Number Theory"
- "What AMC10 questions involve conditional probability from 2019–2023?"

## Retrieval Architecture

```
User query
    │
    ▼
Query Router
    ├─ Keyword / filter path ──▶ Firestore / Sheets (metadata filter)
    │                                  │
    └─ Semantic path ──────────▶ Vector DB (embedding ANN)
                                       │
                         Merge + re-rank results
                                       │
                         Return top-K documents (question.md or chunks)
```

## Query Types

| Query Type | Example | Strategy |
|---|---|---|
| Topic filter | "All questions on Probability" | Metadata filter on primary_topic |
| Subtopic filter | "All questions on Conditional Probability" | Metadata filter on subtopic |
| Competition filter | "All AMC12 questions from 2022" | Metadata filter on competition + year |
| Difficulty filter | "Hard AIME questions" | Metadata filter on competition + difficulty |
| Semantic search | "Questions about geometric series in combinatorics" | Vector ANN |
| Hybrid | "Medium probability questions with visual diagrams" | Filter + vector |
| Document retrieval | "Give me the full AMC10A 2023 paper" | Exact paper_id lookup |

## Indexing Requirements

### RAG-001: Metadata Index
- Every chunk stored in vector DB must carry filterable metadata fields:
  `question_id`, `paper_id`, `competition_id`, `year`, `primary_topic`, `subtopic`, `difficulty_band`, `chunk_type`, `visual_role`.
- These fields enable pre-filter before ANN search.

### RAG-002: Vector Index
- Embedding model: Google `text-embedding-004` (768 dimensions) or OpenAI `text-embedding-3-small`.
- Distance metric: cosine similarity.
- Index type: HNSW or equivalent approximate nearest-neighbour.
- Supported backends: Vertex AI Vector Search, Pinecone, or pgvector on Cloud SQL.
- Chunks are embedded at ingest time; re-embedding is triggered only on content hash change.

### RAG-003: Keyword / BM25 Index
- Questions and paper titles are indexed in a BM25-compatible store.
- Enables exact keyword recall for topic names (e.g. "Vieta's formulas").
- Implemented via Elasticsearch on Cloud Run or Firestore text indexes.

### RAG-004: Category Index Tables
- A dedicated `topics` collection/table with fields: `topic_id`, `display_name`, `question_count`, `competitions[]`, `subtopics[]`.
- Supports autocomplete and category-browser endpoints.
- Rebuilt by the `generate_indexes` pipeline command.

### RAG-005: Whole-Document Index
- Each paper stored as a single document for "retrieve full paper" queries.
- Separate from chunk index; not split or windowed.
- Metadata: `paper_id`, `competition_id`, `year`, `form`, `question_count`.

## Retrieval Requirements

### RAG-006: Topic Query
- Query: `{ "topic": "Probability" }`
- Strategy: filter metadata index by `primary_topic == "Probability"`.
- Returns: list of `question_id`, `paper_id`, `year`, `subtopic`, `difficulty_band`, `chunk_type == "statement"`.
- Max results: configurable, default 50.

### RAG-007: Free-Text Query
- Query: `{ "q": "probability with replacement from a bag of marbles" }`
- Strategy: embed query, ANN search with optional metadata pre-filter.
- Returns: top-K chunks ranked by cosine similarity, with parent question metadata.

### RAG-007b: Concept Query (taxonomy vectors) — implemented 2026-10-06
- Query: `POST /v1/search/concepts {"query": "power of a point", "node_types": ["TECHNIQUE"], "chapter_number": 3, "limit": 10}`
- Strategy: hard filters on `pedagogy.taxonomy_node`, then exact cosine distance over the filtered `TAXONOMY_NODE` embeddings (profile `pedagogy_step_v2`) fused with lexical `ts_rank_cd` by RRF (k=60). Falls back to lexical with a warning if the query embedding fails.
- Returns: taxonomy node id/type/name/parent/chapter, corpus `slug` + `slug_kind` (concept/skill/technique), step-linked `problem_count` and up to 5 `example_problem_codes`. No solution text.
- Consumer: the tutor agent's `search_concepts` tool grounds any named topic before choosing problems.

### RAG-008: Combined Filter + Semantic Query
- Query: `{ "topic": "Geometry", "difficulty": "hard", "q": "circles inscribed in triangles" }`
- Strategy: pre-filter by topic + difficulty, then vector search within filtered set.
- Returns: ranked list with scores.

### RAG-009: Document Retrieval
- Query: `{ "paper_id": "PAPER_AMC10A_2023" }`
- Strategy: direct lookup in whole-document index.
- Returns: full `paper.md` content.

### RAG-010: Chunk Retrieval
- Query: `{ "question_id": "AMC10A_2023_Q05", "chunk_type": "solution" }`
- Strategy: metadata exact match.
- Returns: chunk content and metadata.

## Re-Ranking

- RAG-011: When combining keyword and vector results, apply reciprocal rank fusion (RRF) for final ordering.
- RAG-012: Results are post-filtered to remove chunks from `chunk_type == "context"` when caller requests statement or solution only.

## Incremental Update

- RAG-013: When a question is added or updated, only its chunks are re-embedded and upserted.
- RAG-014: Category indexes are rebuilt incrementally (append new questions to topic index, do not rebuild from scratch unless `--full-rebuild`).
- RAG-015: Embedding refresh is idempotent: content hash match skips re-embedding.

## Evaluation

- RAG-016: Maintain a golden evaluation set of 50 topic queries with known relevant question IDs.
- RAG-017: Precision@10 >= 0.8 on topic queries before enabling production retrieval.
- RAG-018: Evaluation script: `scripts/eval_rag.py --queries evals/topic_queries.jsonl`.
