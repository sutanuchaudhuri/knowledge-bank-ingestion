-- mathbank-db learner subsystem — student accounts, attempts, derived mastery.
-- Per mathematics_tutor_db_plan/agent/18_future_student_profile_and_mastery.md
-- and graph/06_similarity_misconceptions_and_student_state.md.
--
-- Scope: this is the Postgres system-of-record for student login + student
-- state. Graph projection of Student/MASTERED/STRUGGLES_WITH nodes/edges
-- (Neo4j side) is handled separately by mathbank-graph/etl/project_from_postgres.py
-- once that projection is extended to read from this schema.

CREATE SCHEMA IF NOT EXISTS learner;

-- One row per registered learner. No PII beyond email/display_name is stored
-- here; the graph projection only ever uses student_id (opaque uuid) so the
-- knowledge graph itself stays PII-free per the privacy requirement (MST-08).
CREATE TABLE IF NOT EXISTS learner.student_profile (
    student_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL, -- bcrypt hash (see mathbank_rest.security.hash_password)
    display_name text,
    status text NOT NULL DEFAULT 'ACTIVE', -- ACTIVE | DISABLED | DELETED (soft-delete for MST-08 erasure)
    created_at timestamptz NOT NULL DEFAULT now(),
    last_login_at timestamptz
);

-- One row per answer submission. This is the append-only event log that
-- concept_mastery/technique_mastery are derived from; never updated in place.
CREATE TABLE IF NOT EXISTS learner.attempt (
    attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    problem_id uuid NOT NULL REFERENCES core.problem,
    is_correct boolean NOT NULL,
    submitted_answer text,
    time_spent_seconds int CHECK (time_spent_seconds IS NULL OR time_spent_seconds >= 0),
    hint_count int NOT NULL DEFAULT 0,
    attempted_at timestamptz NOT NULL DEFAULT now(),
    source text NOT NULL DEFAULT 'web' -- web | agent_chat | import
);

CREATE INDEX IF NOT EXISTS idx_attempt_student ON learner.attempt(student_id, attempted_at DESC);
CREATE INDEX IF NOT EXISTS idx_attempt_problem ON learner.attempt(problem_id);

-- Derived, recomputed-on-write mastery per (student, concept). See
-- mathbank_rest.mastery for the scoring formula (time-decayed, difficulty-weighted
-- accuracy). Rebuildable at any time from learner.attempt + knowledge.problem_concept,
-- so this table is a materialized cache, not a second source of truth.
CREATE TABLE IF NOT EXISTS learner.concept_mastery (
    student_id uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    concept_id uuid NOT NULL REFERENCES knowledge.concept,
    mastery_score numeric NOT NULL CHECK (mastery_score BETWEEN 0 AND 1),
    attempts_count int NOT NULL DEFAULT 0,
    correct_count int NOT NULL DEFAULT 0,
    last_attempt_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, concept_id)
);

CREATE TABLE IF NOT EXISTS learner.technique_mastery (
    student_id uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    technique_id uuid NOT NULL REFERENCES knowledge.technique,
    mastery_score numeric NOT NULL CHECK (mastery_score BETWEEN 0 AND 1),
    attempts_count int NOT NULL DEFAULT 0,
    correct_count int NOT NULL DEFAULT 0,
    last_attempt_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, technique_id)
);

CREATE INDEX IF NOT EXISTS idx_concept_mastery_student ON learner.concept_mastery(student_id);
CREATE INDEX IF NOT EXISTS idx_technique_mastery_student ON learner.technique_mastery(student_id);
