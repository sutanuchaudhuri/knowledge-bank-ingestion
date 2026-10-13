BEGIN;

CREATE TABLE IF NOT EXISTS pedagogy.route_compiler_run (
    run_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    generator_version text NOT NULL,
    auto_review_by text,
    requested_limit integer NOT NULL CHECK (requested_limit > 0),
    status text NOT NULL CHECK (status IN ('RUNNING','COMPLETED','PARTIAL','FAILED')),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
ALTER TABLE pedagogy.route_compiler_run ADD COLUMN IF NOT EXISTS auto_review_by text;
ALTER TABLE pedagogy.route_compiler_run DROP CONSTRAINT IF EXISTS route_compiler_run_requested_limit_check;
ALTER TABLE pedagogy.route_compiler_run ADD CONSTRAINT route_compiler_run_requested_limit_check CHECK (requested_limit > 0);

CREATE TABLE IF NOT EXISTS pedagogy.solution_route_release (
    route_release_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    solution_id uuid NOT NULL REFERENCES core.solution,
    problem_id uuid NOT NULL REFERENCES core.problem,
    release_version integer NOT NULL CHECK (release_version > 0),
    source_hash text NOT NULL,
    content_hash text NOT NULL,
    approach_name text NOT NULL,
    approach_summary text NOT NULL,
    difficulty_level integer NOT NULL CHECK (difficulty_level BETWEEN 1 AND 5),
    conceptual_load integer NOT NULL CHECK (conceptual_load BETWEEN 1 AND 5),
    algebraic_load integer NOT NULL CHECK (algebraic_load BETWEEN 1 AND 5),
    insight_load integer NOT NULL CHECK (insight_load BETWEEN 1 AND 5),
    preferred_for_tutoring boolean NOT NULL DEFAULT false,
    route_quality numeric CHECK (route_quality BETWEEN 0 AND 1),
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','REVIEWED','PUBLISHED','RETIRED')),
    generator_version text NOT NULL,
    reviewed_by text,
    reviewed_at timestamptz,
    published_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (solution_id, release_version),
    UNIQUE (solution_id, source_hash, generator_version),
    CHECK (status = 'DRAFT' OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS route_release_problem_status
    ON pedagogy.solution_route_release(problem_id, status);

CREATE TABLE IF NOT EXISTS pedagogy.route_compiler_job (
    run_id uuid NOT NULL REFERENCES pedagogy.route_compiler_run,
    solution_id uuid NOT NULL REFERENCES core.solution,
    source_hash text NOT NULL,
    status text NOT NULL CHECK (status IN ('QUEUED','RUNNING','DRAFT','REUSED','FAILED')),
    route_release_id uuid REFERENCES pedagogy.solution_route_release,
    error_code text,
    error_details jsonb NOT NULL DEFAULT '[]'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    PRIMARY KEY (run_id, solution_id)
);
ALTER TABLE pedagogy.route_compiler_job ADD COLUMN IF NOT EXISTS error_details jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE pedagogy.route_compiler_job DROP CONSTRAINT IF EXISTS route_compiler_job_status_check;
ALTER TABLE pedagogy.route_compiler_job ADD CONSTRAINT route_compiler_job_status_check
    CHECK (status IN ('QUEUED','RUNNING','DRAFT','REUSED','FAILED'));

CREATE TABLE IF NOT EXISTS pedagogy.route_step (
    route_release_id uuid NOT NULL REFERENCES pedagogy.solution_route_release,
    step_index integer NOT NULL CHECK (step_index > 0),
    step_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    mathematical_result text NOT NULL,
    source_quote text NOT NULL,
    depends_on integer[] NOT NULL DEFAULT '{}',
    produces text[] NOT NULL DEFAULT '{}',
    uses_claims text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (route_release_id, step_index)
);

CREATE TABLE IF NOT EXISTS pedagogy.solution_step_instruction (
    route_release_id uuid NOT NULL,
    step_index integer NOT NULL,
    instruction_version integer NOT NULL DEFAULT 1,
    content_hash text NOT NULL,
    content jsonb NOT NULL,
    PRIMARY KEY (route_release_id, step_index),
    FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step
);

CREATE TABLE IF NOT EXISTS pedagogy.route_step_hint (
    route_release_id uuid NOT NULL,
    step_index integer NOT NULL,
    hint_level integer NOT NULL CHECK (hint_level BETWEEN 1 AND 5),
    hint_variant text NOT NULL DEFAULT 'default',
    misconception_key text NOT NULL DEFAULT '',
    content_hash text NOT NULL,
    hint_text text NOT NULL,
    PRIMARY KEY (route_release_id, step_index, hint_level, hint_variant, misconception_key),
    FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step
);

CREATE TABLE IF NOT EXISTS pedagogy.solution_step_requirement (
    route_release_id uuid NOT NULL,
    step_index integer NOT NULL,
    taxonomy_node_id text NOT NULL REFERENCES pedagogy.taxonomy_node,
    role text NOT NULL CHECK (role IN ('REQUIRED','HELPFUL','RECOGNITION','EXECUTION','JUSTIFICATION','USED')),
    required_level integer NOT NULL CHECK (required_level BETWEEN 1 AND 5),
    importance numeric NOT NULL CHECK (importance BETWEEN 0 AND 1),
    blocking boolean NOT NULL,
    PRIMARY KEY (route_release_id, step_index, taxonomy_node_id, role),
    FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step
);

CREATE TABLE IF NOT EXISTS pedagogy.route_asset (
    route_release_id uuid NOT NULL REFERENCES pedagogy.solution_route_release,
    asset_key text NOT NULL,
    asset_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    asset_kind text NOT NULL CHECK (asset_kind IN ('CLAIM','MISCONCEPTION','THEORY','LEARNING_ITEM')),
    content_hash text NOT NULL,
    content jsonb NOT NULL,
    PRIMARY KEY (route_release_id, asset_key)
);

CREATE TABLE IF NOT EXISTS pedagogy.route_asset_link (
    route_release_id uuid NOT NULL,
    step_index integer NOT NULL,
    asset_key text NOT NULL,
    role text NOT NULL CHECK (role IN ('CAN_TRIGGER','CHECKED_BY','EXPLAINED_BY')),
    PRIMARY KEY (route_release_id, step_index, asset_key, role),
    FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step,
    FOREIGN KEY (route_release_id, asset_key) REFERENCES pedagogy.route_asset
);

CREATE TABLE IF NOT EXISTS learner.route_attempt (
    route_attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile,
    route_release_id uuid NOT NULL REFERENCES pedagogy.solution_route_release,
    current_step integer NOT NULL DEFAULT 1 CHECK (current_step > 0),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    tutor_explained_steps integer[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION pedagogy.guard_route_snapshot() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE release_status text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        SELECT status INTO release_status FROM pedagogy.solution_route_release
            WHERE route_release_id = OLD.route_release_id FOR SHARE;
        IF release_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'Reviewed route snapshots cannot be moved to a draft';
        END IF;
    END IF;
    SELECT status INTO release_status FROM pedagogy.solution_route_release
        WHERE route_release_id = COALESCE(NEW.route_release_id, OLD.route_release_id) FOR SHARE;
    IF release_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Reviewed route snapshots are immutable; create a new release';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;

DO $$
DECLARE tab text;
BEGIN
    FOREACH tab IN ARRAY ARRAY['route_step','solution_step_instruction','route_step_hint',
        'solution_step_requirement','route_asset','route_asset_link'] LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS immutable_route_snapshot ON pedagogy.%I', tab);
        EXECUTE format('CREATE TRIGGER immutable_route_snapshot BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.%I '
            'FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_snapshot()', tab);
    END LOOP;
END $$;

CREATE OR REPLACE FUNCTION pedagogy.guard_route_release() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Reviewed releases cannot be deleted';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status <> 'DRAFT' THEN
        IF (to_jsonb(NEW) - ARRAY['status','published_at']) IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['status','published_at']) THEN
            RAISE EXCEPTION 'Reviewed route metadata is immutable';
        END IF;
        IF NOT ((OLD.status = 'REVIEWED' AND NEW.status = 'PUBLISHED') OR
                (OLD.status = 'PUBLISHED' AND NEW.status = 'RETIRED')) THEN
            RAISE EXCEPTION 'Invalid reviewed route lifecycle transition';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'DRAFT' AND NEW.status NOT IN ('DRAFT','REVIEWED') THEN
        RAISE EXCEPTION 'Draft releases require review before publication';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS immutable_route_release ON pedagogy.solution_route_release;
CREATE TRIGGER immutable_route_release BEFORE UPDATE OR DELETE ON pedagogy.solution_route_release
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_release();

COMMIT;
