-- requirements/51 ENR-2: semantic similarity search for misconceptions and taxonomy
-- nodes (concept/skill/technique/subconcept) — the real fix for "no similarity search
-- happening in the graph at all". Embedding tables follow the exact convention already
-- established by search.embedding / artifact_runtime.artifact_embedding: pgvector,
-- text-embedding-3-small, 1536 dimensions, a dedicated table (not an inline column),
-- schema-qualified type/operator references per GOTCHAS.md §15 (Neon's neondb_owner has
-- an empty search_path — unqualified `vector`/`<=>` fail even though the extension is
-- installed).
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge.misconception_embedding (
    misconception_id uuid PRIMARY KEY REFERENCES knowledge.misconception(misconception_id) ON DELETE CASCADE,
    model text NOT NULL,
    dimensions integer NOT NULL DEFAULT 1536 CHECK (dimensions BETWEEN 1 AND 8192),
    source_text_sha256 text NOT NULL,
    embedding public.vector NOT NULL CHECK (vector_dims(embedding) = dimensions),
    generated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pedagogy.taxonomy_node_embedding (
    taxonomy_node_id text PRIMARY KEY REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE CASCADE,
    model text NOT NULL,
    dimensions integer NOT NULL DEFAULT 1536 CHECK (dimensions BETWEEN 1 AND 8192),
    source_text_sha256 text NOT NULL,
    embedding public.vector NOT NULL CHECK (vector_dims(embedding) = dimensions),
    generated_at timestamptz NOT NULL DEFAULT now()
);

-- Precomputed top-k nearest-neighbor pairs, not a live ANN query path — this project has
-- no live vector-search use case for these two entity types yet (unlike search.embedding,
-- which backs /v1/search/problems). Recomputed in full by the generation script whenever
-- embeddings change; cheap at this row count (~77K) without needing an HNSW/ivfflat index.
CREATE TABLE IF NOT EXISTS knowledge.misconception_similarity (
    misconception_id_a uuid NOT NULL REFERENCES knowledge.misconception(misconception_id) ON DELETE CASCADE,
    misconception_id_b uuid NOT NULL REFERENCES knowledge.misconception(misconception_id) ON DELETE CASCADE,
    similarity double precision NOT NULL CHECK (similarity BETWEEN -1 AND 1),
    rank smallint NOT NULL CHECK (rank > 0),
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (misconception_id_a, misconception_id_b),
    CHECK (misconception_id_a <> misconception_id_b)
);

CREATE TABLE IF NOT EXISTS pedagogy.taxonomy_node_similarity (
    taxonomy_node_id_a text NOT NULL REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE CASCADE,
    taxonomy_node_id_b text NOT NULL REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE CASCADE,
    similarity double precision NOT NULL CHECK (similarity BETWEEN -1 AND 1),
    rank smallint NOT NULL CHECK (rank > 0),
    computed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (taxonomy_node_id_a, taxonomy_node_id_b),
    CHECK (taxonomy_node_id_a <> taxonomy_node_id_b)
);

CREATE INDEX IF NOT EXISTS idx_misconception_similarity_a ON knowledge.misconception_similarity(misconception_id_a);
CREATE INDEX IF NOT EXISTS idx_taxonomy_node_similarity_a ON pedagogy.taxonomy_node_similarity(taxonomy_node_id_a);
