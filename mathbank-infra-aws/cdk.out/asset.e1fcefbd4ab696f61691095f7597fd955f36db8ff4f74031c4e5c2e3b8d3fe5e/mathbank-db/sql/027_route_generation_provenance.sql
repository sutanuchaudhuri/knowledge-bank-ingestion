BEGIN;
ALTER TABLE pedagogy.route_compiler_run
    ADD COLUMN IF NOT EXISTS generation_config jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE pedagogy.route_compiler_job
    ADD COLUMN IF NOT EXISTS generation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE pedagogy.route_step
    ADD COLUMN IF NOT EXISTS generation_metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
COMMENT ON COLUMN pedagogy.route_step.generation_metadata IS
    'Generation provider/model/digest/options/usage/timing/source and validation provenance; empty for historical unknown provenance. Not proof certification.';
COMMIT;
