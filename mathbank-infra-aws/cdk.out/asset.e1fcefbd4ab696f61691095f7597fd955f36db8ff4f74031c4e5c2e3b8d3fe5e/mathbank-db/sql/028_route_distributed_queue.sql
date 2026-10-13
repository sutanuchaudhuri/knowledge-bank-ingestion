BEGIN;

-- Shared work identities, independent of per-machine model/run configuration.
CREATE TABLE IF NOT EXISTS pedagogy.route_compile_task (
    task_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    generator_version text NOT NULL,
    solution_id uuid NOT NULL REFERENCES core.solution,
    source_hash text NOT NULL,
    status text NOT NULL DEFAULT 'QUEUED'
        CHECK (status IN ('QUEUED','RUNNING','DONE','FAILED')),
    owner_token uuid,
    owner_run_id uuid REFERENCES pedagogy.route_compiler_run,
    lease_until timestamptz,
    attempts integer NOT NULL DEFAULT 0,
    route_release_id uuid REFERENCES pedagogy.solution_route_release,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    UNIQUE (generator_version,solution_id,source_hash)
);
CREATE INDEX IF NOT EXISTS route_compile_task_claim
    ON pedagogy.route_compile_task(generator_version,status,lease_until,created_at);

COMMIT;
