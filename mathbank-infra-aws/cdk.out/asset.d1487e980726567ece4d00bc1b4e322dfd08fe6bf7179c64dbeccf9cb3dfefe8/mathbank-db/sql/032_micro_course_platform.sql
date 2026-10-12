-- 032_micro_course_platform.sql
-- Deterministic admin/teacher-authored micro-course platform (requirements/40_MICRO_COURSE_PLATFORM.md).
-- Extends existing schemas only: knowledge, pedagogy, learner, tutor, pipeline.
-- Reuses knowledge.concept/technique/skill, pedagogy.learning_item, activity.definition,
-- visual.asset. No new taxonomy, no new quiz bank, no new binary store.
BEGIN;

-- 1. Canonical misconception library -----------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge.misconception (
    misconception_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_code      text NOT NULL UNIQUE,
    name                text NOT NULL,
    description         text NOT NULL,
    symptom             text,
    why_wrong           text,
    correct_model       text,
    recognition_pattern jsonb NOT NULL DEFAULT '{}'::jsonb,
    severity            smallint CHECK (severity IS NULL OR severity BETWEEN 1 AND 5),
    level               smallint CHECK (level IS NULL OR level BETWEEN 1 AND 10),
    source              text NOT NULL DEFAULT 'HUMAN',
    review_status       text NOT NULL DEFAULT 'PENDING_REVIEW'
                         CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    approval_method     text CHECK (approval_method IS NULL OR approval_method IN ('automatic','human')),
    approved_at         timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

-- 2. Micro-course identity and canonical targets -----------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course (
    micro_course_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_code    text NOT NULL UNIQUE,
    title             text NOT NULL,
    description       text,
    estimated_minutes integer CHECK (estimated_minutes IS NULL OR estimated_minutes > 0),
    difficulty_level  smallint CHECK (difficulty_level IS NULL OR difficulty_level BETWEEN 1 AND 10),
    created_by        text NOT NULL DEFAULT 'admin',
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pedagogy.micro_course_target (
    micro_course_id uuid NOT NULL REFERENCES pedagogy.micro_course ON DELETE CASCADE,
    target_type     text NOT NULL CHECK (target_type IN ('CONCEPT','TECHNIQUE','SKILL')),
    concept_id      uuid REFERENCES knowledge.concept,
    technique_id    uuid REFERENCES knowledge.technique,
    skill_id        uuid REFERENCES knowledge.skill,
    role            text NOT NULL DEFAULT 'PRIMARY' CHECK (role IN ('PRIMARY','SECONDARY','PREREQUISITE')),
    ordinal         integer NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
    PRIMARY KEY (micro_course_id, target_type, role, ordinal),
    CHECK (
        (target_type = 'CONCEPT'   AND concept_id   IS NOT NULL AND technique_id IS NULL AND skill_id IS NULL) OR
        (target_type = 'TECHNIQUE' AND technique_id IS NOT NULL AND concept_id   IS NULL AND skill_id IS NULL) OR
        (target_type = 'SKILL'     AND skill_id     IS NOT NULL AND concept_id   IS NULL AND technique_id IS NULL)
    )
);

-- 3. Immutable versioned releases ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course_release (
    release_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    micro_course_id        uuid NOT NULL REFERENCES pedagogy.micro_course ON DELETE CASCADE,
    version                integer NOT NULL CHECK (version >= 1),
    parent_release_id      uuid REFERENCES pedagogy.micro_course_release ON DELETE SET NULL,
    status                 text NOT NULL DEFAULT 'DRAFT'
                           CHECK (status IN ('DRAFT','REVIEWED','APPROVED','PUBLISHED','SUPERSEDED','RETIRED')),
    learning_objectives    jsonb NOT NULL DEFAULT '[]'::jsonb,
    prerequisite_summary   jsonb NOT NULL DEFAULT '[]'::jsonb,
    agent_policy           jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_hash           text,
    created_by             text NOT NULL,
    reviewed_by            text,
    approved_by            text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    reviewed_at            timestamptz,
    approved_at            timestamptz,
    published_at           timestamptz,
    UNIQUE (micro_course_id, version)
);
CREATE UNIQUE INDEX IF NOT EXISTS micro_course_one_published
    ON pedagogy.micro_course_release (micro_course_id) WHERE status = 'PUBLISHED';

-- 4. Modules and states ---------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course_module (
    module_id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id         uuid NOT NULL REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,
    module_key         text NOT NULL,
    ordinal            integer NOT NULL CHECK (ordinal >= 0),
    title              text NOT NULL,
    objective          text,
    estimated_seconds  integer CHECK (estimated_seconds IS NULL OR estimated_seconds > 0),
    required           boolean NOT NULL DEFAULT true,
    UNIQUE (release_id, module_key),
    UNIQUE (release_id, ordinal)
);

CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state (
    state_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id         uuid NOT NULL REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,
    module_id          uuid REFERENCES pedagogy.micro_course_module ON DELETE CASCADE,
    state_key          text NOT NULL,
    ordinal            integer NOT NULL CHECK (ordinal >= 0),
    state_type         text NOT NULL CHECK (state_type IN (
                           'ORIENTATION','EXPLANATION','SLIDE','VIDEO','READING','VISUAL','EXAMPLE',
                           'CHECKPOINT','QUIZ','DIAGNOSTIC','REMEDIATION','PRACTICE','SUMMARY','TRANSFER'
                       )),
    title              text NOT NULL,
    objective          text,
    student_instruction text,
    estimated_seconds  integer CHECK (estimated_seconds IS NULL OR estimated_seconds > 0),
    required           boolean NOT NULL DEFAULT true,
    skippable          boolean NOT NULL DEFAULT false,
    agent_policy       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (release_id, state_key),
    UNIQUE (release_id, ordinal)
);

-- 5. FK-backed semantic state bindings --------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_concept (
    state_id    uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    concept_id  uuid NOT NULL REFERENCES knowledge.concept,
    role        text NOT NULL CHECK (role IN ('TEACHES','REQUIRES','REVIEWS','MENTIONS')),
    importance  numeric(3,2) CHECK (importance IS NULL OR importance BETWEEN 0 AND 1),
    PRIMARY KEY (state_id, concept_id, role)
);

CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_technique (
    state_id     uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    technique_id uuid NOT NULL REFERENCES knowledge.technique,
    role         text NOT NULL CHECK (role IN ('TEACHES','REQUIRES','RECOGNIZES','APPLIES','REVIEWS')),
    importance   numeric(3,2) CHECK (importance IS NULL OR importance BETWEEN 0 AND 1),
    PRIMARY KEY (state_id, technique_id, role)
);

CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_skill (
    state_id        uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    skill_id        uuid NOT NULL REFERENCES knowledge.skill,
    role            text NOT NULL CHECK (role IN ('TEACHES','REQUIRES','ASSESSES','REVIEWS')),
    required_level  smallint CHECK (required_level IS NULL OR required_level BETWEEN 1 AND 5),
    PRIMARY KEY (state_id, skill_id, role)
);

CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_misconception (
    state_id         uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    misconception_id uuid NOT NULL REFERENCES knowledge.misconception,
    role             text NOT NULL CHECK (role IN ('WATCH_FOR','ADDRESSES','DIAGNOSES')),
    PRIMARY KEY (state_id, misconception_id, role)
);

-- 6. visual.asset extension (presentation metadata, no new binary store) -----------------------
ALTER TABLE visual.asset ADD COLUMN IF NOT EXISTS asset_kind  text;
ALTER TABLE visual.asset ADD COLUMN IF NOT EXISTS title       text;
ALTER TABLE visual.asset ADD COLUMN IF NOT EXISTS source_url  text;
ALTER TABLE visual.asset ADD COLUMN IF NOT EXISTS rights_note text;
ALTER TABLE visual.asset ADD COLUMN IF NOT EXISTS reviewed_by text;
ALTER TABLE visual.asset ADD COLUMN IF NOT EXISTS reviewed_at timestamptz;

-- 7. State asset attachment ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_asset (
    state_id          uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    asset_id          uuid NOT NULL REFERENCES visual.asset ON DELETE RESTRICT,
    ordinal           integer NOT NULL CHECK (ordinal >= 0),
    presentation_role text NOT NULL CHECK (presentation_role IN ('PRIMARY','SUPPORT','EXAMPLE','REFERENCE','OPTIONAL')),
    PRIMARY KEY (state_id, asset_id),
    UNIQUE (state_id, ordinal)
);

-- 8. Video asset, transcript, segments ------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.video_asset (
    video_asset_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    visual_asset_id    uuid NOT NULL UNIQUE REFERENCES visual.asset ON DELETE RESTRICT,
    provider           text NOT NULL CHECK (provider IN ('YOUTUBE','VIMEO','INTERNAL')),
    external_video_id  text NOT NULL,
    canonical_url      text NOT NULL,
    title              text NOT NULL,
    creator_name       text,
    channel_name       text,
    duration_ms        bigint CHECK (duration_ms IS NULL OR duration_ms > 0),
    retrieved_at       timestamptz,
    metadata_hash      text,
    transcript_status  text NOT NULL DEFAULT 'MISSING'
                        CHECK (transcript_status IN ('MISSING','IMPORTED','TRANSCRIBED','REVIEWED','APPROVED','STALE')),
    review_status      text NOT NULL DEFAULT 'PENDING_REVIEW'
                        CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED','STALE')),
    approved_by        text,
    approved_at        timestamptz,
    UNIQUE (provider, external_video_id)
);

CREATE TABLE IF NOT EXISTS pedagogy.video_transcript (
    transcript_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    video_asset_id  uuid NOT NULL REFERENCES pedagogy.video_asset ON DELETE CASCADE,
    version         integer NOT NULL CHECK (version >= 1),
    language_code   text NOT NULL,
    source_type     text NOT NULL CHECK (source_type IN ('PROVIDER_CAPTIONS','HUMAN','MODEL_TRANSCRIPTION','IMPORTED_FILE')),
    raw_text        text,
    content_hash    text NOT NULL,
    status          text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','REVIEWED','APPROVED','SUPERSEDED')),
    created_by      text NOT NULL,
    reviewed_by     text,
    created_at      timestamptz NOT NULL DEFAULT now(),
    reviewed_at     timestamptz,
    UNIQUE (video_asset_id, version)
);

CREATE TABLE IF NOT EXISTS pedagogy.video_transcript_segment (
    segment_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id    uuid NOT NULL REFERENCES pedagogy.video_transcript ON DELETE CASCADE,
    segment_index    integer NOT NULL CHECK (segment_index >= 0),
    start_ms         bigint NOT NULL CHECK (start_ms >= 0),
    end_ms           bigint NOT NULL CHECK (end_ms > start_ms),
    transcript_text  text NOT NULL CHECK (length(trim(transcript_text)) > 0),
    speaker          text,
    segment_hash     text NOT NULL,
    review_status    text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    UNIQUE (transcript_id, segment_index)
);
CREATE INDEX IF NOT EXISTS video_segment_time_idx
    ON pedagogy.video_transcript_segment (transcript_id, start_ms, end_ms);

-- 9. Segment semantic bindings ---------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.video_segment_concept (
    segment_id   uuid NOT NULL REFERENCES pedagogy.video_transcript_segment ON DELETE CASCADE,
    concept_id   uuid NOT NULL REFERENCES knowledge.concept,
    role         text NOT NULL CHECK (role IN ('EXPLAINS','USES','REQUIRES','RECOGNITION_CUE','EXAMPLE_OF')),
    confidence   numeric(3,2) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    source_type  text NOT NULL DEFAULT 'HUMAN',
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    PRIMARY KEY (segment_id, concept_id, role)
);

CREATE TABLE IF NOT EXISTS pedagogy.video_segment_technique (
    segment_id   uuid NOT NULL REFERENCES pedagogy.video_transcript_segment ON DELETE CASCADE,
    technique_id uuid NOT NULL REFERENCES knowledge.technique,
    role         text NOT NULL CHECK (role IN ('EXPLAINS','USES','REQUIRES','RECOGNITION_CUE','EXAMPLE_OF')),
    confidence   numeric(3,2) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    source_type  text NOT NULL DEFAULT 'HUMAN',
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    PRIMARY KEY (segment_id, technique_id, role)
);

CREATE TABLE IF NOT EXISTS pedagogy.video_segment_skill (
    segment_id   uuid NOT NULL REFERENCES pedagogy.video_transcript_segment ON DELETE CASCADE,
    skill_id     uuid NOT NULL REFERENCES knowledge.skill,
    role         text NOT NULL CHECK (role IN ('EXPLAINS','USES','REQUIRES','RECOGNITION_CUE','EXAMPLE_OF')),
    confidence   numeric(3,2) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    source_type  text NOT NULL DEFAULT 'HUMAN',
    review_status text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    PRIMARY KEY (segment_id, skill_id, role)
);

CREATE TABLE IF NOT EXISTS pedagogy.video_segment_misconception (
    segment_id       uuid NOT NULL REFERENCES pedagogy.video_transcript_segment ON DELETE CASCADE,
    misconception_id uuid NOT NULL REFERENCES knowledge.misconception,
    role             text NOT NULL CHECK (role IN ('MISCONCEPTION_TRIGGER','ADDRESSES','REMEDIATES')),
    confidence       numeric(3,2) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    source_type      text NOT NULL DEFAULT 'HUMAN',
    review_status    text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    PRIMARY KEY (segment_id, misconception_id, role)
);

-- 10. Timeline markers -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.video_timeline_marker (
    marker_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    state_id         uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    video_asset_id   uuid NOT NULL REFERENCES pedagogy.video_asset ON DELETE CASCADE,
    timestamp_ms     bigint NOT NULL CHECK (timestamp_ms >= 0),
    marker_type      text NOT NULL CHECK (marker_type IN (
                         'SEGMENT_START','REQUIRED_PAUSE','OPTIONAL_PAUSE','QUIZ','DIAGNOSTIC',
                         'INTERVENTION','RESUME_POINT'
                     )),
    learning_item_id text REFERENCES pedagogy.learning_item,
    activity_id      uuid REFERENCES activity.definition,
    intervention_id  uuid,  -- FK added below once pedagogy.intervention_script exists
    note             text,
    review_status    text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED'))
);

-- 11. Approved Q&A context --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.state_qa_context (
    qa_context_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    state_id         uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    context_type     text NOT NULL CHECK (context_type IN (
                         'EXPLANATION','DEFINITION','FAQ','DERIVATION','EXAMPLE','COUNTEREXAMPLE',
                         'NOTATION','MISCONCEPTION_RESPONSE'
                     )),
    question_pattern text,
    approved_content text NOT NULL,
    concept_id       uuid REFERENCES knowledge.concept,
    technique_id     uuid REFERENCES knowledge.technique,
    skill_id         uuid REFERENCES knowledge.skill,
    misconception_id uuid REFERENCES knowledge.misconception,
    priority         integer NOT NULL DEFAULT 0,
    review_status    text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    created_by       text NOT NULL,
    approved_by      text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    approved_at      timestamptz
);

-- 12. State-bound quizzes/activities ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_learning_item (
    state_id         uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    learning_item_id text NOT NULL REFERENCES pedagogy.learning_item ON DELETE RESTRICT,
    ordinal          integer NOT NULL CHECK (ordinal >= 0),
    purpose          text NOT NULL CHECK (purpose IN (
                         'ENTRY_CHECK','COMPREHENSION','RECOGNITION','MISCONCEPTION_DIAGNOSTIC',
                         'EXECUTION','EXIT_CHECK','TRANSFER'
                     )),
    required         boolean NOT NULL DEFAULT true,
    PRIMARY KEY (state_id, learning_item_id),
    UNIQUE (state_id, ordinal)
);

CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_activity (
    state_id    uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    activity_id uuid NOT NULL REFERENCES activity.definition ON DELETE RESTRICT,
    ordinal     integer NOT NULL CHECK (ordinal >= 0),
    purpose     text NOT NULL,
    required    boolean NOT NULL DEFAULT true,
    PRIMARY KEY (state_id, activity_id),
    UNIQUE (state_id, ordinal)
);

-- 13. Deterministic transitions -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course_transition (
    transition_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id        uuid NOT NULL REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,
    from_state_id     uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    to_state_id       uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    transition_type   text NOT NULL CHECK (transition_type IN (
                          'NEXT','CORRECT','INCORRECT','RETRY','MISCONCEPTION','PREREQUISITE_GAP',
                          'USER_CONTINUE','USER_BACK','USER_QUESTION_RESOLVED','INTERVENTION_COMPLETE'
                      )),
    condition_type    text NOT NULL DEFAULT 'ALWAYS' CHECK (condition_type IN (
                          'ALWAYS','LEARNING_ITEM_RESULT','ACTIVITY_RESULT','MISCONCEPTION_CODE',
                          'SKILL_STATUS','INTERVENTION_RESULT'
                      )),
    condition_payload jsonb NOT NULL DEFAULT '{}'::jsonb,
    priority          integer NOT NULL DEFAULT 0,
    review_status     text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    CHECK (from_state_id <> to_state_id OR transition_type = 'RETRY')
);

-- 14. Fixed misconception interventions ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.intervention_script (
    intervention_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id             uuid NOT NULL REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,
    canonical_code         text NOT NULL,
    name                   text NOT NULL,
    target_misconception_id uuid REFERENCES knowledge.misconception,
    target_skill_id        uuid REFERENCES knowledge.skill,
    target_technique_id    uuid REFERENCES knowledge.technique,
    entry_state_id         uuid REFERENCES pedagogy.micro_course_state,
    review_status          text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    UNIQUE (release_id, canonical_code)
);

CREATE TABLE IF NOT EXISTS pedagogy.intervention_step (
    intervention_step_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intervention_id       uuid NOT NULL REFERENCES pedagogy.intervention_script ON DELETE CASCADE,
    ordinal               integer NOT NULL CHECK (ordinal >= 0),
    step_type             text NOT NULL CHECK (step_type IN (
                              'ASK','EXPLAIN','SHOW_ASSET','LEARNING_ITEM','ACTIVITY','WAIT_FOR_RESPONSE','RETURN'
                          )),
    prompt_text           text,
    asset_id              uuid REFERENCES visual.asset,
    learning_item_id      text REFERENCES pedagogy.learning_item,
    activity_id           uuid REFERENCES activity.definition,
    expected_response_type text,
    UNIQUE (intervention_id, ordinal)
);

-- Now that intervention_script exists, wire the deferred FK from timeline markers.
ALTER TABLE pedagogy.video_timeline_marker
    ADD CONSTRAINT video_timeline_marker_intervention_fkey
    FOREIGN KEY (intervention_id) REFERENCES pedagogy.intervention_script;

-- 15. Append-only review history -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.micro_course_review (
    review_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    release_id   uuid NOT NULL REFERENCES pedagogy.micro_course_release ON DELETE CASCADE,
    status       text NOT NULL CHECK (status IN ('APPROVED','NEEDS_REVISION','REJECTED')),
    note         text,
    reviewed_by  text NOT NULL,
    reviewed_at  timestamptz NOT NULL DEFAULT now()
);

-- 16. Learner enrollment and runtime pointer -------------------------------------------------------
CREATE TABLE IF NOT EXISTS learner.micro_course_enrollment (
    enrollment_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id      uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    micro_course_id uuid NOT NULL REFERENCES pedagogy.micro_course,
    release_id      uuid NOT NULL REFERENCES pedagogy.micro_course_release,
    status          text NOT NULL DEFAULT 'IN_PROGRESS' CHECK (status IN ('IN_PROGRESS','COMPLETED','ABANDONED')),
    started_at      timestamptz NOT NULL DEFAULT now(),
    completed_at    timestamptz
);

CREATE TABLE IF NOT EXISTS learner.micro_course_state_event (
    event_id      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    enrollment_id uuid NOT NULL REFERENCES learner.micro_course_enrollment ON DELETE CASCADE,
    state_id      uuid REFERENCES pedagogy.micro_course_state,
    event_type    text NOT NULL,
    payload       jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at    timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- Separate from the existing step-solving tutor.runtime_state; micro-course runtime has its
-- own pointer so neither system overloads the other's lifecycle.
CREATE TABLE IF NOT EXISTS tutor.micro_course_runtime (
    enrollment_id          uuid PRIMARY KEY REFERENCES learner.micro_course_enrollment ON DELETE CASCADE,
    current_state_id       uuid NOT NULL REFERENCES pedagogy.micro_course_state,
    current_video_asset_id uuid REFERENCES pedagogy.video_asset,
    current_video_time_ms  bigint,
    active_intervention_id uuid REFERENCES pedagogy.intervention_script,
    state_version          bigint NOT NULL DEFAULT 1,
    updated_at             timestamptz NOT NULL DEFAULT now()
);

-- 17. pipeline.projection_request CHECK vocabulary extension ------------------------------------
ALTER TABLE pipeline.projection_request DROP CONSTRAINT IF EXISTS projection_request_target_check;
ALTER TABLE pipeline.projection_request ADD CONSTRAINT projection_request_target_check
    CHECK (target IN (
        'GRAPH_TEXTBOOK_STEPS','STEP_EMBEDDINGS','LEARNING_ITEM_EMBEDDINGS','GRAPH_LEARNING_ITEMS',
        'GRAPH_MICRO_COURSES'
    ));
ALTER TABLE pipeline.projection_request DROP CONSTRAINT IF EXISTS projection_request_scope_type_check;
ALTER TABLE pipeline.projection_request ADD CONSTRAINT projection_request_scope_type_check
    CHECK (scope_type IN (
        'BOOK','PACKAGE','PROBLEM','STEP','LEARNING_ITEM',
        'MICRO_COURSE','COURSE_RELEASE','VIDEO_ASSET'
    ));

-- 18. Immutability guards (mirrors authoring.guard_published_plan in 020_live_fluid_platform.sql) --
CREATE OR REPLACE FUNCTION pedagogy.guard_published_micro_course_release() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('pedagogy.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status IN ('PUBLISHED','SUPERSEDED') THEN
            RAISE EXCEPTION 'published/superseded micro-course releases are immutable';
        END IF;
        RETURN OLD;
    END IF;
    IF OLD.status IN ('PUBLISHED','SUPERSEDED','RETIRED') THEN
        IF OLD.status = 'PUBLISHED' AND NEW.status IN ('SUPERSEDED','RETIRED')
           AND (NEW.learning_objectives, NEW.prerequisite_summary, NEW.agent_policy, NEW.content_hash)
               IS NOT DISTINCT FROM (OLD.learning_objectives, OLD.prerequisite_summary, OLD.agent_policy, OLD.content_hash)
        THEN RETURN NEW; END IF;
        IF OLD.status = 'SUPERSEDED' AND NEW.status = 'RETIRED'
           AND (NEW.learning_objectives, NEW.prerequisite_summary, NEW.agent_policy, NEW.content_hash)
               IS NOT DISTINCT FROM (OLD.learning_objectives, OLD.prerequisite_summary, OLD.agent_policy, OLD.content_hash)
        THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'published micro-course release content is immutable; create a new draft version';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS micro_course_release_guard ON pedagogy.micro_course_release;
CREATE TRIGGER micro_course_release_guard BEFORE UPDATE OR DELETE ON pedagogy.micro_course_release
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_micro_course_release();

-- Children keyed directly by release_id: block all mutation once the parent release is
-- PUBLISHED/SUPERSEDED/RETIRED (states/modules/transitions/interventions are release-scoped).
CREATE OR REPLACE FUNCTION pedagogy.guard_published_release_child() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE release_status text;
BEGIN
    IF current_setting('pedagogy.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    SELECT status INTO release_status FROM pedagogy.micro_course_release
     WHERE release_id = COALESCE(NEW.release_id, OLD.release_id);
    IF release_status IN ('PUBLISHED','SUPERSEDED','RETIRED') THEN
        RAISE EXCEPTION 'children of a published micro-course release are immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS micro_course_module_guard ON pedagogy.micro_course_module;
CREATE TRIGGER micro_course_module_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_module
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_release_child();

DROP TRIGGER IF EXISTS micro_course_state_guard ON pedagogy.micro_course_state;
CREATE TRIGGER micro_course_state_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_release_child();

DROP TRIGGER IF EXISTS micro_course_transition_guard ON pedagogy.micro_course_transition;
CREATE TRIGGER micro_course_transition_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_transition
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_release_child();

DROP TRIGGER IF EXISTS intervention_script_guard ON pedagogy.intervention_script;
CREATE TRIGGER intervention_script_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.intervention_script
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_release_child();

-- Children keyed by state_id (one join further from release_id): same immutability rule.
CREATE OR REPLACE FUNCTION pedagogy.guard_published_state_child() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE release_status text;
BEGIN
    IF current_setting('pedagogy.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    SELECT r.status INTO release_status
      FROM pedagogy.micro_course_state s
      JOIN pedagogy.micro_course_release r USING (release_id)
     WHERE s.state_id = COALESCE(NEW.state_id, OLD.state_id);
    IF release_status IN ('PUBLISHED','SUPERSEDED','RETIRED') THEN
        RAISE EXCEPTION 'children of a published micro-course state are immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS micro_course_state_concept_guard ON pedagogy.micro_course_state_concept;
CREATE TRIGGER micro_course_state_concept_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_concept
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS micro_course_state_technique_guard ON pedagogy.micro_course_state_technique;
CREATE TRIGGER micro_course_state_technique_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_technique
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS micro_course_state_skill_guard ON pedagogy.micro_course_state_skill;
CREATE TRIGGER micro_course_state_skill_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_skill
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS micro_course_state_misconception_guard ON pedagogy.micro_course_state_misconception;
CREATE TRIGGER micro_course_state_misconception_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_misconception
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS micro_course_state_asset_guard ON pedagogy.micro_course_state_asset;
CREATE TRIGGER micro_course_state_asset_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_asset
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS micro_course_state_learning_item_guard ON pedagogy.micro_course_state_learning_item;
CREATE TRIGGER micro_course_state_learning_item_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_learning_item
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS micro_course_state_activity_guard ON pedagogy.micro_course_state_activity;
CREATE TRIGGER micro_course_state_activity_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_activity
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS state_qa_context_guard ON pedagogy.state_qa_context;
CREATE TRIGGER state_qa_context_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.state_qa_context
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();
DROP TRIGGER IF EXISTS video_timeline_marker_guard ON pedagogy.video_timeline_marker;
CREATE TRIGGER video_timeline_marker_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.video_timeline_marker
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_state_child();

CREATE OR REPLACE FUNCTION pedagogy.guard_published_intervention_child() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE release_status text;
BEGIN
    IF current_setting('pedagogy.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    SELECT r.status INTO release_status
      FROM pedagogy.intervention_script i
      JOIN pedagogy.micro_course_release r USING (release_id)
     WHERE i.intervention_id = COALESCE(NEW.intervention_id, OLD.intervention_id);
    IF release_status IN ('PUBLISHED','SUPERSEDED','RETIRED') THEN
        RAISE EXCEPTION 'steps of a published intervention are immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;
DROP TRIGGER IF EXISTS intervention_step_guard ON pedagogy.intervention_step;
CREATE TRIGGER intervention_step_guard BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.intervention_step
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_intervention_child();

-- Append-only tables: forbid UPDATE entirely (mirrors live.session_event_append_only in 020).
CREATE OR REPLACE FUNCTION pedagogy.forbid_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END $$;
DROP TRIGGER IF EXISTS micro_course_review_append_only ON pedagogy.micro_course_review;
CREATE TRIGGER micro_course_review_append_only BEFORE UPDATE OR DELETE ON pedagogy.micro_course_review
    FOR EACH ROW EXECUTE FUNCTION pedagogy.forbid_update();

CREATE OR REPLACE FUNCTION learner.forbid_update() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END $$;
DROP TRIGGER IF EXISTS micro_course_state_event_append_only ON learner.micro_course_state_event;
CREATE TRIGGER micro_course_state_event_append_only BEFORE UPDATE OR DELETE ON learner.micro_course_state_event
    FOR EACH ROW EXECUTE FUNCTION learner.forbid_update();

-- 19. Indexes/comments -----------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS micro_course_target_concept_idx ON pedagogy.micro_course_target (concept_id) WHERE concept_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS micro_course_target_technique_idx ON pedagogy.micro_course_target (technique_id) WHERE technique_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS micro_course_target_skill_idx ON pedagogy.micro_course_target (skill_id) WHERE skill_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS micro_course_state_release_idx ON pedagogy.micro_course_state (release_id);
CREATE INDEX IF NOT EXISTS video_asset_transcript_status_idx ON pedagogy.video_asset (transcript_status, review_status);
CREATE INDEX IF NOT EXISTS enrollment_student_idx ON learner.micro_course_enrollment (student_id);

COMMENT ON TABLE pedagogy.micro_course_release IS 'Immutable once PUBLISHED; edits create a new DRAFT release via parent_release_id (requirements/40_MICRO_COURSE_PLATFORM.md MCR-3).';
COMMENT ON TABLE pedagogy.video_transcript_segment IS 'Timestamp-grounded Q&A only resolves against APPROVED transcripts/segments (MCR-9).';
COMMENT ON TABLE tutor.micro_course_runtime IS 'Separate from tutor.runtime_state; never overload the step-solving runtime pointer (MCR-14).';

COMMIT;
