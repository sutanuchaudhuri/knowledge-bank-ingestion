-- Migration 011: pgvector metadata for solution steps and published learning items
-- (v2 pack runtime_extension/07_VECTOR_METADATA_AND_RAG.md, 29_GRAPH_VECTOR_METADATA_V2.md).
--
-- Additive extension of the existing search.representation -> search.chunk -> search.embedding
-- pipeline (002). Step and learning-item IDs are text, while search.representation.source_entity_id
-- is uuid, so representations use a deterministic uuid5 surrogate; the real IDs (with foreign keys)
-- live on search.chunk together with the canonical hard-filter columns. Idempotent.

ALTER TABLE search.chunk
    ADD COLUMN IF NOT EXISTS solution_step_id text
        REFERENCES pedagogy.solution_step ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS learning_item_id text
        REFERENCES pedagogy.learning_item ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS skill_node_id text
        REFERENCES pedagogy.taxonomy_node ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS subconcept_node_id text
        REFERENCES pedagogy.taxonomy_node ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS concept_node_id text
        REFERENCES pedagogy.taxonomy_node ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_search_chunk_solution_step
    ON search.chunk (solution_step_id) WHERE solution_step_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_search_chunk_learning_item
    ON search.chunk (learning_item_id) WHERE learning_item_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_search_chunk_skill_node
    ON search.chunk (skill_node_id) WHERE skill_node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_search_chunk_subconcept_node
    ON search.chunk (subconcept_node_id) WHERE subconcept_node_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_search_chunk_metadata
    ON search.chunk USING gin (metadata jsonb_path_ops);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chunk_single_pedagogy_owner') THEN
        ALTER TABLE search.chunk ADD CONSTRAINT chunk_single_pedagogy_owner
            CHECK (solution_step_id IS NULL OR learning_item_id IS NULL);
    END IF;
END $$;

INSERT INTO search.preprocessing_profile (name, version, configuration)
VALUES ('pedagogy_step_v2', 1,
        '{"units": ["SOLUTION_STEP", "LEARNING_ITEM_QUESTION", "LEARNING_ITEM_SKILL_SIGNATURE"],
          "prefix": "[Solution step]|[Learning item]|[Skill signature]",
          "metadata_source": "canonical taxonomy ids only",
          "learning_items": "APPROVED + student_visible + no_proof only"}'::jsonb)
ON CONFLICT (name, version) DO NOTHING;
