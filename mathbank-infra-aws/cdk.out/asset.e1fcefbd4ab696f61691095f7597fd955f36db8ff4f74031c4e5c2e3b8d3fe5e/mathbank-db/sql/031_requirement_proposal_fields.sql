BEGIN;

-- solution_step_requirement previously stored only the resolved taxonomy_node_id,
-- discarding whether THIS release originally proposed that ID as a brand-new node
-- (proposed_node_type/proposed_name/proposed_description on the Requirement model).
-- Once the proposed node was upserted into taxonomy_node, reloading the release
-- (review/edit/graph/UI) silently lost that flag, making the requirement look like
-- a plain reuse of an already-known ID and desynchronizing program_digest between
-- write time and reload time. Persist the three fields alongside the requirement
-- so round-tripping is exact.
ALTER TABLE pedagogy.solution_step_requirement
    ADD COLUMN IF NOT EXISTS proposed_node_type text NOT NULL DEFAULT '';
ALTER TABLE pedagogy.solution_step_requirement
    ADD COLUMN IF NOT EXISTS proposed_name text NOT NULL DEFAULT '';
ALTER TABLE pedagogy.solution_step_requirement
    ADD COLUMN IF NOT EXISTS proposed_description text NOT NULL DEFAULT '';

COMMIT;
