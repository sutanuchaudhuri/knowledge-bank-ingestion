# PostgreSQL 07 — Search, Embeddings, and Indexing

## Retrieval modes

The mathematics tutor needs several retrieval modes simultaneously:

1. exact metadata lookup
2. lexical/full-text search
3. fuzzy name/statement search
4. semantic vector search
5. structured filtering
6. graph traversal

PostgreSQL should support the first five well enough that graph is reserved for relationship-heavy reasoning.

## Full-text search

Create generated or maintained `tsvector` fields for statements, solutions, concept descriptions, and tags. Weight title/canonical metadata above body text.

## Trigram search

Use `pg_trgm` for misspellings, symbol-free text approximations, and taxonomy label lookup.

## Embeddings

Recommended table:

`search.embedding(entity_type, entity_id, chunk_id, embedding_model, embedding_version, dimensions, content_hash, vector, metadata)`.

The uniqueness key should include entity/chunk/model/version/content hash so embeddings are reproducible and stale vectors can be detected.

Do not overwrite embeddings in place when the model changes. Mark older embeddings inactive or retain version rows during migration.

## Chunking

Chunk by semantic structure, not arbitrary character count. Examples:

- problem statement as one chunk
- each solution or solution step
- concept definition + examples
- theorem statement + conditions

Preserve `chunk_ordinal` and the parent entity.

## Hybrid retrieval

A query service can combine:

- lexical score
- vector similarity
- exact taxonomy filters
- contest/year/difficulty filters
- graph proximity score

Store the scoring recipe/version when retrieval results are evaluated experimentally.

## Index strategy

Important indexes:

- `(competition_id, year, paper_code)` dimensions
- `canonical_code UNIQUE`
- GIN FTS on statements/solutions
- trigram GIN on names and statements
- HNSW or IVFFlat vector index depending on scale/update pattern
- partial indexes for pending review and pending work items

Always measure with production-like data before proliferating indexes.
