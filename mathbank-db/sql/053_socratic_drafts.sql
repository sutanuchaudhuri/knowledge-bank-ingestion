-- Additive isolated prototype drafts. No canonical or learner rows are changed.
CREATE SCHEMA IF NOT EXISTS orchestration;

CREATE TABLE IF NOT EXISTS orchestration.socratic_strategy (
    code text PRIMARY KEY,
    domain text NOT NULL,
    label text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status = 'DRAFT'),
    phases jsonb NOT NULL CHECK (jsonb_typeof(phases) = 'array'),
    provenance text NOT NULL
);

CREATE TABLE IF NOT EXISTS orchestration.socratic_workflow (
    workflow_id uuid PRIMARY KEY,
    owner_id text NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 200),
    title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 200),
    domain text NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    content_hash text NOT NULL CHECK (content_hash ~ '^[a-f0-9]{64}$'),
    prototype_only boolean NOT NULL DEFAULT true CHECK (prototype_only),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS socratic_workflow_owner_idx
    ON orchestration.socratic_workflow(owner_id, updated_at DESC, workflow_id);

CREATE TABLE IF NOT EXISTS orchestration.socratic_revision (
    workflow_id uuid NOT NULL REFERENCES orchestration.socratic_workflow ON DELETE RESTRICT,
    revision integer NOT NULL CHECK (revision > 0),
    content_hash text NOT NULL CHECK (content_hash ~ '^[a-f0-9]{64}$'),
    author_id text NOT NULL,
    strategy_code text NOT NULL REFERENCES orchestration.socratic_strategy,
    program jsonb NOT NULL CHECK (program->>'schema_version' = 'socratic.prototype.v1'),
    dependencies jsonb NOT NULL CHECK (jsonb_typeof(dependencies) = 'object'),
    problem_id uuid REFERENCES core.problem ON DELETE RESTRICT,
    solution_id uuid REFERENCES core.solution ON DELETE RESTRICT,
    solution_revision integer CHECK (solution_revision > 0),
    route_release_id uuid REFERENCES pedagogy.solution_route_release ON DELETE RESTRICT,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (workflow_id, revision),
    UNIQUE (workflow_id, revision, content_hash),
    CHECK ((solution_id IS NULL) = (solution_revision IS NULL)),
    CHECK (solution_id IS NULL OR problem_id IS NOT NULL),
    CHECK (route_release_id IS NULL OR solution_id IS NOT NULL)
);
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'orchestration.socratic_workflow'::regclass
        AND conname = 'socratic_workflow_current_revision_fk'
    ) THEN
        ALTER TABLE orchestration.socratic_workflow
        ADD CONSTRAINT socratic_workflow_current_revision_fk
        FOREIGN KEY (workflow_id, revision, content_hash)
        REFERENCES orchestration.socratic_revision(workflow_id, revision, content_hash)
        DEFERRABLE INITIALLY DEFERRED;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'orchestration.socratic_revision'::regclass
        AND conname = 'socratic_revision_program_shape_check'
    ) THEN
        ALTER TABLE orchestration.socratic_revision
        ADD CONSTRAINT socratic_revision_program_shape_check
        CHECK (jsonb_typeof(program) = 'object'
            AND coalesce(program->>'schema_version' = 'socratic.prototype.v1', false));
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS orchestration.socratic_command (
    owner_id text NOT NULL,
    operation text NOT NULL,
    idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 1 AND 128),
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    workflow_id uuid NOT NULL REFERENCES orchestration.socratic_workflow ON DELETE RESTRICT,
    revision integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (owner_id, operation, idempotency_key),
    FOREIGN KEY (workflow_id, revision)
        REFERENCES orchestration.socratic_revision ON DELETE RESTRICT
);

CREATE OR REPLACE FUNCTION orchestration.socratic_immutable()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Socratic draft evidence is immutable' USING ERRCODE = '23514';
END $$;
DROP TRIGGER IF EXISTS socratic_revision_immutable ON orchestration.socratic_revision;
CREATE TRIGGER socratic_revision_immutable BEFORE UPDATE OR DELETE
    ON orchestration.socratic_revision FOR EACH ROW
    EXECUTE FUNCTION orchestration.socratic_immutable();
DROP TRIGGER IF EXISTS socratic_strategy_immutable ON orchestration.socratic_strategy;
CREATE TRIGGER socratic_strategy_immutable BEFORE UPDATE OR DELETE
    ON orchestration.socratic_strategy FOR EACH ROW
    EXECUTE FUNCTION orchestration.socratic_immutable();
DROP TRIGGER IF EXISTS socratic_command_immutable ON orchestration.socratic_command;
CREATE TRIGGER socratic_command_immutable BEFORE UPDATE OR DELETE
    ON orchestration.socratic_command FOR EACH ROW
    EXECUTE FUNCTION orchestration.socratic_immutable();

-- Candidate registry only: not reviewed strategies or runnable pedagogical policies.
INSERT INTO orchestration.socratic_strategy(code, domain, label, phases, provenance)
SELECT code, domain, label, '["Discover","Justify","Transfer","Reflect"]'::jsonb,
       'requirements/65 SOC-DOM-02: candidate registry v1; human review pending'
FROM (VALUES
    ('ARITH_REPRESENT','Arithmetic','Represent quantities'),
    ('ARITH_ESTIMATE','Arithmetic','Estimate and check'),
    ('ALG_PATTERN','Algebra','Explore patterns'),
    ('ALG_EQUIVALENCE','Algebra','Preserve equivalence'),
    ('ALG_INVARIANT','Algebra','Find an invariant'),
    ('COMB_BIJECTION','Combinatorics','Build a bijection'),
    ('COMB_CASES','Combinatorics','Partition into cases'),
    ('COMB_INVARIANT','Combinatorics','Track an invariant'),
    ('PROB_SAMPLE','Probability','Construct the sample space'),
    ('PROB_CONDITION','Probability','Condition on evidence'),
    ('NT_MODULAR','Number theory','Explore residues'),
    ('NT_DIVISIBILITY','Number theory','Use divisibility'),
    ('NT_EXTREMAL','Number theory','Test an extremal case'),
    ('COMPLEX_LOCUS','Complex numbers','Interpret a locus'),
    ('COMPLEX_TRANSFORM','Complex numbers','Explore a transformation'),
    ('PLANE_AUXILIARY','Planar geometry','Propose an auxiliary construction'),
    ('PLANE_SIMILARITY','Planar geometry','Compare similar figures'),
    ('PLANE_AREA','Planar geometry','Compare areas'),
    ('SOLID_SECTION','Solid geometry','Inspect a section'),
    ('SOLID_VOLUME','Solid geometry','Compare volumes')
) AS candidates(code, domain, label)
ON CONFLICT (code) DO NOTHING;
