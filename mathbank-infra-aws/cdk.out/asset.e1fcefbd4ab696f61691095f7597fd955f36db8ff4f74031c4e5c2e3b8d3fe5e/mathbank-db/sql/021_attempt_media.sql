-- Approved multimodal work extends learner history without treating unassessed
-- work as an incorrect answer. Existing evaluated attempt behavior is unchanged.
ALTER TABLE learner.attempt ALTER COLUMN is_correct DROP NOT NULL;
CREATE SCHEMA IF NOT EXISTS attempt_media;

CREATE TABLE IF NOT EXISTS attempt_media.submission (
    submission_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    problem_id uuid NOT NULL REFERENCES core.problem,
    status text NOT NULL DEFAULT 'RECEIVED' CHECK (status IN
        ('RECEIVED','MEDIA_NORMALIZED','TRANSCRIBING','TRANSCRIPTION_READY',
         'STUDENT_REVIEWING','APPROVED','ALIGNING','CRITIQUING','VISUAL_GROUNDING','READY','FAILED')),
    transcription_version integer NOT NULL DEFAULT 1 CHECK (transcription_version > 0),
    approved_version integer NOT NULL DEFAULT 0 CHECK (approved_version >= 0),
    last_sequence bigint NOT NULL DEFAULT 0,
    error_code text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS submission_owner_idx ON attempt_media.submission(student_id,created_at DESC);

CREATE TABLE IF NOT EXISTS attempt_media.media_asset (
    media_asset_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id uuid NOT NULL REFERENCES attempt_media.submission ON DELETE CASCADE,
    role text NOT NULL DEFAULT 'ORIGINAL' CHECK (role IN ('ORIGINAL','PAGE','KEYFRAME','AUDIO')),
    parent_asset_id uuid REFERENCES attempt_media.media_asset ON DELETE SET NULL,
    asset_type text NOT NULL CHECK (asset_type IN ('IMAGE','PDF','AUDIO','VIDEO')),
    object_key text NOT NULL,
    mime_type text NOT NULL,
    sha256 text NOT NULL,
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    page_count integer CHECK (page_count BETWEEN 1 AND 10),
    duration_ms integer CHECK (duration_ms BETWEEN 1 AND 120000),
    timestamp_ms integer CHECK (timestamp_ms >= 0),
    retention_class text NOT NULL DEFAULT 'RAW_MEDIA',
    purged_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS asset_submission_idx ON attempt_media.media_asset(submission_id);

CREATE TABLE IF NOT EXISTS attempt_media.evidence_region (
    region_id uuid PRIMARY KEY,
    submission_id uuid NOT NULL REFERENCES attempt_media.submission ON DELETE CASCADE,
    media_asset_id uuid NOT NULL REFERENCES attempt_media.media_asset,
    page_number integer CHECK (page_number BETWEEN 1 AND 10),
    x_norm double precision CHECK (x_norm BETWEEN 0 AND 1),
    y_norm double precision CHECK (y_norm BETWEEN 0 AND 1),
    width_norm double precision CHECK (width_norm > 0 AND width_norm <= 1),
    height_norm double precision CHECK (height_norm > 0 AND height_norm <= 1),
    start_ms integer CHECK (start_ms >= 0),
    end_ms integer,
    region_type text NOT NULL,
    reading_order integer NOT NULL CHECK (reading_order >= 0),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    transcription_version integer NOT NULL,
    CHECK (
      (page_number IS NOT NULL AND x_norm IS NOT NULL AND y_norm IS NOT NULL
       AND width_norm IS NOT NULL AND height_norm IS NOT NULL
       AND x_norm+width_norm <= 1.000001 AND y_norm+height_norm <= 1.000001
       AND start_ms IS NULL AND end_ms IS NULL)
      OR (start_ms IS NOT NULL AND end_ms > start_ms AND page_number IS NULL
          AND x_norm IS NULL AND y_norm IS NULL AND width_norm IS NULL AND height_norm IS NULL)
    )
);

CREATE TABLE IF NOT EXISTS attempt_media.transcription_candidate (
    submission_id uuid NOT NULL REFERENCES attempt_media.submission ON DELETE CASCADE,
    version integer NOT NULL,
    source text NOT NULL CHECK (source IN ('MACHINE','STUDENT')),
    machine_output jsonb,
    model_profile text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (submission_id,version)
);
CREATE TABLE IF NOT EXISTS attempt_media.step_candidate (
    submission_id uuid NOT NULL,
    version integer NOT NULL,
    step_id uuid NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    plain_text text NOT NULL,
    latex_text text NOT NULL,
    step_type text NOT NULL,
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    PRIMARY KEY (submission_id,version,step_id),
    UNIQUE (submission_id,version,ordinal),
    FOREIGN KEY (submission_id,version) REFERENCES attempt_media.transcription_candidate ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS attempt_media.step_candidate_evidence (
    submission_id uuid NOT NULL,
    version integer NOT NULL,
    step_id uuid NOT NULL,
    region_id uuid NOT NULL REFERENCES attempt_media.evidence_region,
    PRIMARY KEY (submission_id,version,step_id,region_id),
    FOREIGN KEY (submission_id,version,step_id) REFERENCES attempt_media.step_candidate ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS attempt_media.approval (
    submission_id uuid NOT NULL REFERENCES attempt_media.submission ON DELETE CASCADE,
    approved_version integer NOT NULL,
    transcription_version integer NOT NULL,
    learner_attempt_id uuid NOT NULL UNIQUE REFERENCES learner.attempt,
    approved_at timestamptz NOT NULL DEFAULT now(),
    student_edit_summary text NOT NULL,
    PRIMARY KEY (submission_id,approved_version),
    UNIQUE (submission_id,transcription_version),
    FOREIGN KEY (submission_id,transcription_version)
      REFERENCES attempt_media.transcription_candidate(submission_id,version)
);
-- Approved steps are immutable candidate-version rows referenced by approval;
-- these views avoid duplicating or rewriting the approved mathematical content.
CREATE OR REPLACE VIEW attempt_media.approved_step AS
 SELECT a.approved_version,a.learner_attempt_id,s.*
 FROM attempt_media.approval a JOIN attempt_media.step_candidate s
 ON s.submission_id=a.submission_id AND s.version=a.transcription_version;
CREATE OR REPLACE VIEW attempt_media.approved_step_evidence AS
 SELECT a.approved_version,a.learner_attempt_id,e.*
 FROM attempt_media.approval a JOIN attempt_media.step_candidate_evidence e
 ON e.submission_id=a.submission_id AND e.version=a.transcription_version;

CREATE TABLE IF NOT EXISTS attempt_media.step_assessment (
    assessment_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id uuid NOT NULL,
    transcription_version integer NOT NULL,
    step_id uuid NOT NULL,
    approved_version integer NOT NULL,
    assessment_version integer NOT NULL CHECK (assessment_version > 0),
    source text NOT NULL CHECK (source IN ('AI','INSTRUCTOR')),
    actor_id text NOT NULL,
    correctness text NOT NULL CHECK (correctness IN
      ('CORRECT','PARTIALLY_CORRECT','INCORRECT','UNJUSTIFIED','UNCERTAIN')),
    alignment_type text NOT NULL,
    canonical_solution_step_id text REFERENCES pedagogy.solution_step(solution_step_id),
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    why text NOT NULL,
    failure_mode text NOT NULL,
    next_action text NOT NULL,
    evidence_ids jsonb NOT NULL CHECK (jsonb_typeof(evidence_ids)='array'),
    model_profile text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (submission_id,transcription_version,step_id,assessment_version),
    FOREIGN KEY (submission_id,transcription_version,step_id)
      REFERENCES attempt_media.step_candidate(submission_id,version,step_id),
    FOREIGN KEY (submission_id,approved_version)
      REFERENCES attempt_media.approval(submission_id,approved_version)
);
CREATE OR REPLACE VIEW attempt_media.step_alignment AS
 SELECT assessment_id,submission_id,step_id,transcription_version,approved_version,
 alignment_type,canonical_solution_step_id,confidence FROM attempt_media.step_assessment;
CREATE OR REPLACE VIEW attempt_media.visual_explanation AS
 SELECT assessment_id,submission_id,step_id,transcription_version,approved_version,
 evidence_ids,why,next_action FROM attempt_media.step_assessment;

CREATE TABLE IF NOT EXISTS attempt_media.event (
    submission_id uuid NOT NULL REFERENCES attempt_media.submission ON DELETE CASCADE,
    sequence bigint NOT NULL,
    event_type text NOT NULL,
    transcription_version integer NOT NULL,
    approved_attempt_version integer NOT NULL,
    payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (submission_id,sequence)
);
