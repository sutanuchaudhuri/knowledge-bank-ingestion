-- Follow-up to 040: migration 040's embedding columns used a flexible, unconstrained
-- `public.vector` type (matching artifact_runtime.artifact_embedding's precedent), but
-- that precedent never needed an ANN index because it never computes all-pairs
-- similarity. This migration's generation script does — a full self-join over
-- knowledge.misconception's 70,018 rows is ~4.9 billion row-pairs without an index,
-- impractical to compute directly. pgvector's HNSW/ivfflat indexes require a FIXED
-- dimension on the column itself (`vector(1536)`, not a bare `vector` + CHECK), so this
-- migration switches both embedding tables to that fixed type and adds the index. Safe to
-- run as a plain ALTER: 040 was applied moments before this file with zero rows written to
-- either table yet (confirmed live), so there is no embedding data to migrate/lose.
ALTER TABLE knowledge.misconception_embedding
    DROP CONSTRAINT IF EXISTS misconception_embedding_embedding_check,
    ALTER COLUMN embedding TYPE public.vector(1536);

ALTER TABLE pedagogy.taxonomy_node_embedding
    DROP CONSTRAINT IF EXISTS taxonomy_node_embedding_embedding_check,
    ALTER COLUMN embedding TYPE public.vector(1536);

CREATE INDEX IF NOT EXISTS idx_misconception_embedding_hnsw
    ON knowledge.misconception_embedding USING hnsw (embedding public.vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_taxonomy_node_embedding_hnsw
    ON pedagogy.taxonomy_node_embedding USING hnsw (embedding public.vector_cosine_ops);
