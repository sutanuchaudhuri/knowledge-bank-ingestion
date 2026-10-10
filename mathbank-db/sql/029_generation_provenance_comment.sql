BEGIN;
-- Documentation-only: clarifies the generation_metadata jsonb contract.
-- Re-running COMMENT ON COLUMN is idempotent and never modifies stored rows.
COMMENT ON COLUMN pedagogy.route_step.generation_metadata IS
    'Generation provider/model/digest/options/usage/timing/source and validation '
    'provenance for this step, recorded at persistence time. Always includes '
    '"generation_started_at" (ISO 8601 UTC timestamp when generation began for '
    'this release) and "model" (the generator model/identity used). "critic_model" '
    'is an explicit JSON null when no independent critic model evaluated this run '
    '(the default); when an operator enables a critic (make routes-ingest '
    'ROUTE_CRITIC=1 ROUTE_CRITIC_MODEL=<model>), it holds that different model''s '
    'name and the nested "critic" key holds its per-step evaluation. Empty object '
    'for historical rows predating this provenance. Not proof certification.';
COMMENT ON COLUMN pedagogy.route_compiler_job.generation_metadata IS
    'Per-job generation/critic provenance mirroring the fields on route_step for '
    'this solution''s attempt; "critic_model" is null unless a critic was enabled '
    'for this run. Historical rows predating this provenance remain an empty object.';
COMMENT ON COLUMN pedagogy.route_compiler_run.generation_config IS
    'Frozen provider/model/options for this run, including "critic_model" (null '
    'unless an independent critic model was enabled) and "critic" (its full '
    'configuration when enabled). Historical rows predating this provenance '
    'remain an empty object.';
COMMIT;
