-- Structured reusable artifacts: independent of attempt_media (021).
-- Object bytes remain in the private store; only metadata is persisted here.
CREATE SCHEMA IF NOT EXISTS artifact_runtime;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_request (
    artifact_request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_student_id uuid REFERENCES learner.student_profile(student_id),
    created_by text NOT NULL,
    request_source text NOT NULL,
    subject text NOT NULL CHECK (subject IN ('GEOMETRY','ALGEBRA','COMBINATORICS','NUMBER_THEORY')),
    topic text NOT NULL,
    subtopic text,
    goal_type text NOT NULL,
    linked_problem_id uuid REFERENCES core.problem(problem_id),
    linked_solution_step_id text,
    spec jsonb NOT NULL CHECK (jsonb_typeof(spec) = 'object'),
    status text NOT NULL DEFAULT 'REQUESTED' CHECK (status IN ('REQUESTED','GENERATED')),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_bundle (
    artifact_bundle_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_request_id uuid NOT NULL REFERENCES artifact_runtime.artifact_request,
    parent_bundle_id uuid REFERENCES artifact_runtime.artifact_bundle,
    subject text NOT NULL,
    topic text NOT NULL,
    subtopic text,
    title text NOT NULL,
    summary text NOT NULL,
    difficulty_band text NOT NULL,
    grade_band text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','PUBLISHED')),
    review_state text NOT NULL DEFAULT 'VALIDATED' CHECK (review_state IN ('VALIDATED','APPROVED')),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by_agent text NOT NULL,
    rule_profile_id text NOT NULL,
    annotation_profile_id text NOT NULL,
    search_text text NOT NULL,
    metadata jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz,
    UNIQUE (artifact_request_id, version)
);
CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_asset (
    artifact_asset_id uuid PRIMARY KEY,
    artifact_bundle_id uuid NOT NULL REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    asset_type text NOT NULL CHECK (asset_type IN ('SVG_DIAGRAM','LATEX_CARD','FRAME_SEQUENCE','MANIM_EXPORT_SPEC')),
    object_key text NOT NULL UNIQUE CHECK (object_key ~ '^[0-9a-f]{32}\.[a-z0-9]{1,10}$'),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 26214400),
    mime_type text NOT NULL,
    render_format text NOT NULL,
    width integer,
    height integer,
    element_ids jsonb NOT NULL DEFAULT '[]',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_metadata (
    artifact_asset_id uuid PRIMARY KEY REFERENCES artifact_runtime.artifact_asset ON DELETE CASCADE,
    subject text NOT NULL,
    concept_ids text[] NOT NULL DEFAULT '{}',
    skill_ids text[] NOT NULL DEFAULT '{}',
    theorem_ids text[] NOT NULL DEFAULT '{}',
    step_labels text[] NOT NULL DEFAULT '{}',
    rule_profile_id text NOT NULL,
    annotation_profile_id text NOT NULL,
    search_text text NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_runtime.overlay_state (
    overlay_state_id uuid PRIMARY KEY,
    artifact_bundle_id uuid NOT NULL REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    base_asset_id uuid NOT NULL REFERENCES artifact_runtime.artifact_asset,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    actions jsonb NOT NULL CHECK (jsonb_typeof(actions) = 'array'),
    caption text NOT NULL,
    linked_step_id text,
    UNIQUE (artifact_bundle_id, ordinal)
);
CREATE TABLE IF NOT EXISTS artifact_runtime.frame_sequence (
    frame_sequence_id uuid PRIMARY KEY,
    artifact_bundle_id uuid NOT NULL UNIQUE REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    manifest_asset_id uuid NOT NULL REFERENCES artifact_runtime.artifact_asset,
    ordered_overlay_state_ids uuid[] NOT NULL,
    transition_notes text NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_annotation (
    artifact_annotation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_bundle_id uuid NOT NULL REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    ordinal integer NOT NULL,
    step_number integer NOT NULL CHECK (step_number > 0),
    caption text NOT NULL,
    concept_tag text NOT NULL,
    hint_tag text,
    explanation_text text NOT NULL,
    linked_step_id text,
    UNIQUE (artifact_bundle_id, ordinal)
);
CREATE TABLE IF NOT EXISTS artifact_runtime.validation_result (
    validation_result_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_bundle_id uuid NOT NULL REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    valid boolean NOT NULL,
    validator_version text NOT NULL,
    report jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_lineage (
    artifact_bundle_id uuid PRIMARY KEY REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    artifact_request_id uuid NOT NULL REFERENCES artifact_runtime.artifact_request,
    parent_bundle_id uuid REFERENCES artifact_runtime.artifact_bundle,
    generator_version text NOT NULL,
    source_spec_sha256 text NOT NULL
);
CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_search_tag (
    artifact_bundle_id uuid NOT NULL REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    tag_type text NOT NULL CHECK (tag_type IN ('concept','skill','theorem')),
    tag text NOT NULL,
    PRIMARY KEY (artifact_bundle_id, tag_type, tag)
);
CREATE TABLE IF NOT EXISTS artifact_runtime.artifact_embedding (
    artifact_bundle_id uuid PRIMARY KEY REFERENCES artifact_runtime.artifact_bundle ON DELETE CASCADE,
    model text NOT NULL,
    dimensions integer NOT NULL DEFAULT 1536 CHECK (dimensions BETWEEN 1 AND 8192),
    search_text_sha256 text NOT NULL,
    embedding vector NOT NULL CHECK (vector_dims(embedding) = dimensions),
    indexed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS artifact_bundle_subject_status
    ON artifact_runtime.artifact_bundle(subject, status);
CREATE INDEX IF NOT EXISTS artifact_search_tags
    ON artifact_runtime.artifact_search_tag(tag_type, tag);
CREATE INDEX IF NOT EXISTS artifact_lexical_search
    ON artifact_runtime.artifact_bundle USING gin(to_tsvector('simple', search_text));
