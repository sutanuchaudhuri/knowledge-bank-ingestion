-- 020: Fluid widget layer + distributed live-session platform
-- (math_tutor_fluid_widget_selected_docs + math_tutor_distributed_platform_copilot_handoff).
-- Additive and idempotent. PostgreSQL stays authoritative: sockets only carry events that are first
-- written here (live.session_event) inside the same transaction as the state change, together with a
-- pipeline.outbox_event row. Agents never write these tables directly; they call REST commands.

CREATE SCHEMA IF NOT EXISTS authoring;
CREATE SCHEMA IF NOT EXISTS live;
CREATE SCHEMA IF NOT EXISTS activity;
CREATE SCHEMA IF NOT EXISTS visual;

-- ------------------------------------------------------------------ authoring (fluid 04/05/06)
-- A presentation plan is versioned: PUBLISHED rows are immutable; edits create a new DRAFT version
-- with the same plan_key (fluid 05 §"Published plans are immutable").
CREATE TABLE IF NOT EXISTS authoring.presentation_plan (
    plan_id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_key                   text NOT NULL,
    version                    integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    parent_plan_id             uuid REFERENCES authoring.presentation_plan ON DELETE SET NULL,
    title                      text NOT NULL,
    description                text,
    status                     text NOT NULL DEFAULT 'DRAFT'
                               CHECK (status IN ('DRAFT', 'APPROVED', 'PUBLISHED', 'SUPERSEDED')),
    course_limit_seconds       integer NOT NULL CHECK (course_limit_seconds > 0),
    interaction_buffer_seconds integer NOT NULL DEFAULT 0 CHECK (interaction_buffer_seconds >= 0),
    hard_limit                 boolean NOT NULL DEFAULT false,
    created_by                 text NOT NULL DEFAULT 'admin',
    created_at                 timestamptz NOT NULL DEFAULT now(),
    updated_at                 timestamptz NOT NULL DEFAULT now(),
    approved_at                timestamptz,
    published_at               timestamptz,
    UNIQUE (plan_key, version)
);

CREATE TABLE IF NOT EXISTS authoring.plan_topic (
    topic_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         uuid NOT NULL REFERENCES authoring.presentation_plan ON DELETE CASCADE,
    ordinal         integer NOT NULL CHECK (ordinal >= 0),
    title           text NOT NULL,
    concept         text,
    problem_ref     text,
    planned_seconds integer NOT NULL CHECK (planned_seconds > 0),
    min_seconds     integer CHECK (min_seconds IS NULL OR min_seconds > 0),
    max_seconds     integer CHECK (max_seconds IS NULL OR max_seconds > 0),
    required        boolean NOT NULL DEFAULT true,
    -- [{scene_id, kind: EXPLAIN|WIDGET|ACTIVITY|POLL|PRACTICE, title, planned_seconds, optional,
    --   widget_spec_id?, activity_id?}] — declarative only, validated by REST.
    scenes          jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(scenes) = 'array'),
    UNIQUE (plan_id, ordinal) DEFERRABLE INITIALLY DEFERRED
);

-- Published plans (and their topics) are immutable; only PUBLISHED -> SUPERSEDED is allowed.
CREATE OR REPLACE FUNCTION authoring.guard_published_plan() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    -- Transaction-local escape hatch for the live test suite's own fixtures only.
    IF current_setting('authoring.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'PUBLISHED' THEN RAISE EXCEPTION 'published presentation plans are immutable'; END IF;
        RETURN OLD;
    END IF;
    IF OLD.status IN ('PUBLISHED', 'SUPERSEDED') THEN
        IF NEW.status = 'SUPERSEDED' AND OLD.status = 'PUBLISHED'
           AND (NEW.title, NEW.course_limit_seconds, NEW.interaction_buffer_seconds, NEW.hard_limit)
               IS NOT DISTINCT FROM (OLD.title, OLD.course_limit_seconds, OLD.interaction_buffer_seconds, OLD.hard_limit)
        THEN RETURN NEW; END IF;
        RAISE EXCEPTION 'published presentation plans are immutable; create a new draft version';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS presentation_plan_guard ON authoring.presentation_plan;
CREATE TRIGGER presentation_plan_guard BEFORE UPDATE OR DELETE ON authoring.presentation_plan
    FOR EACH ROW EXECUTE FUNCTION authoring.guard_published_plan();

CREATE OR REPLACE FUNCTION authoring.guard_published_topic() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE plan_status text;
BEGIN
    IF current_setting('authoring.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    SELECT status INTO plan_status FROM authoring.presentation_plan
     WHERE plan_id = COALESCE(NEW.plan_id, OLD.plan_id);
    IF plan_status IN ('PUBLISHED', 'SUPERSEDED') THEN
        RAISE EXCEPTION 'topics of a published presentation plan are immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;
DROP TRIGGER IF EXISTS plan_topic_guard ON authoring.plan_topic;
CREATE TRIGGER plan_topic_guard BEFORE INSERT OR UPDATE OR DELETE ON authoring.plan_topic
    FOR EACH ROW EXECUTE FUNCTION authoring.guard_published_topic();

-- Admin authoring chat (fluid 04): messages + structured, admin-decided patches.
CREATE TABLE IF NOT EXISTS authoring.chat_session (
    chat_session_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id         uuid NOT NULL REFERENCES authoring.presentation_plan ON DELETE CASCADE,
    actor           text NOT NULL DEFAULT 'admin',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS authoring.proposed_patch (
    patch_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id uuid NOT NULL REFERENCES authoring.chat_session ON DELETE CASCADE,
    plan_id         uuid NOT NULL REFERENCES authoring.presentation_plan ON DELETE CASCADE,
    summary         text NOT NULL,
    operations      jsonb NOT NULL CHECK (jsonb_typeof(operations) = 'array'),
    impact          jsonb NOT NULL DEFAULT '{}'::jsonb,
    validation      jsonb NOT NULL DEFAULT '{}'::jsonb,
    proposer        text NOT NULL DEFAULT 'DETERMINISTIC_PARSER',
    status          text NOT NULL DEFAULT 'PROPOSED'
                    CHECK (status IN ('PROPOSED', 'APPLIED', 'REJECTED', 'SUPERSEDED')),
    result_plan_id  uuid REFERENCES authoring.presentation_plan ON DELETE SET NULL,
    decided_by      text,
    decided_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS proposed_patch_chat_idx ON authoring.proposed_patch (chat_session_id, created_at);

CREATE TABLE IF NOT EXISTS authoring.chat_message (
    message_id      bigserial PRIMARY KEY,
    chat_session_id uuid NOT NULL REFERENCES authoring.chat_session ON DELETE CASCADE,
    role            text NOT NULL CHECK (role IN ('ADMIN', 'ASSISTANT', 'SYSTEM')),
    content         text NOT NULL,
    patch_id        uuid REFERENCES authoring.proposed_patch ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chat_message_session_idx ON authoring.chat_message (chat_session_id, message_id);

-- ------------------------------------------------------------------ live sessions (dist 03/04/20, fluid 06/15)
CREATE TABLE IF NOT EXISTS live.session (
    live_session_id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plan_id                    uuid REFERENCES authoring.presentation_plan ON DELETE SET NULL,
    title                      text NOT NULL,
    join_code                  text NOT NULL UNIQUE,
    status                     text NOT NULL DEFAULT 'SCHEDULED'
                               CHECK (status IN ('SCHEDULED', 'ACTIVE', 'PAUSED', 'COMPLETED', 'CANCELLED')),
    control_mode               text NOT NULL DEFAULT 'AI_ACTIVE'
                               CHECK (control_mode IN ('AI_ACTIVE', 'INSTRUCTOR_ACTIVE')),
    controller                 text,
    agent_locked               boolean NOT NULL DEFAULT false,
    state_version              bigint NOT NULL DEFAULT 1 CHECK (state_version >= 1),
    last_sequence              bigint NOT NULL DEFAULT 0 CHECK (last_sequence >= 0),
    current_topic_index        integer NOT NULL DEFAULT 0,
    current_scene_index        integer NOT NULL DEFAULT 0,
    course_limit_seconds       integer NOT NULL CHECK (course_limit_seconds > 0),
    interaction_buffer_seconds integer NOT NULL DEFAULT 0,
    hard_limit                 boolean NOT NULL DEFAULT false,
    extension_seconds          integer NOT NULL DEFAULT 0,
    started_at                 timestamptz,
    paused_at                  timestamptz,
    paused_total_seconds       integer NOT NULL DEFAULT 0,
    topic_started_at           timestamptz,
    completed_at               timestamptz,
    -- Snapshot of the visible slot (current widget instances, open activity) for fast REST state reads.
    stage                      jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_by                 text NOT NULL DEFAULT 'admin',
    created_at                 timestamptz NOT NULL DEFAULT now(),
    updated_at                 timestamptz NOT NULL DEFAULT now()
);

-- Frozen copy of the plan topics/scenes the session runs against (or ad-hoc topics).
ALTER TABLE live.session ADD COLUMN IF NOT EXISTS topics jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE TABLE IF NOT EXISTS live.participant (
    live_session_id uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    participant_id  text NOT NULL,
    role            text NOT NULL CHECK (role IN ('STUDENT', 'INSTRUCTOR', 'OBSERVER')),
    student_id      uuid REFERENCES learner.student_profile ON DELETE SET NULL,
    display_name    text NOT NULL,
    group_id        text,
    control_mode    text NOT NULL DEFAULT 'AI_ACTIVE' CHECK (control_mode IN ('AI_ACTIVE', 'INSTRUCTOR_ACTIVE')),
    confused        boolean NOT NULL DEFAULT false,
    joined_at       timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (live_session_id, participant_id)
);
CREATE INDEX IF NOT EXISTS participant_student_idx ON live.participant (student_id) WHERE student_id IS NOT NULL;

-- Ordered, append-only replay log; every socket event is a row here first (dist 04 envelope).
CREATE TABLE IF NOT EXISTS live.session_event (
    live_session_id uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    sequence        bigint NOT NULL CHECK (sequence >= 1),
    event_id        uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    event_type      text NOT NULL,
    session_version bigint NOT NULL,
    correlation_id  text,
    causation_id    text,
    actor_type      text NOT NULL CHECK (actor_type IN ('STUDENT', 'INSTRUCTOR', 'ADMIN', 'AI_TUTOR', 'SYSTEM')),
    actor_id        text,
    audience        text NOT NULL DEFAULT 'SESSION' CHECK (audience IN ('SESSION', 'STUDENT', 'INSTRUCTOR', 'GROUP')),
    audience_id     text,
    payload         jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (live_session_id, sequence)
);

CREATE OR REPLACE FUNCTION live.session_event_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'live.session_event is append-only';
END $$;
DROP TRIGGER IF EXISTS session_event_append_only ON live.session_event;
CREATE TRIGGER session_event_append_only BEFORE UPDATE ON live.session_event
    FOR EACH ROW EXECUTE FUNCTION live.session_event_append_only();

-- Idempotent client commands (dist 04: client_command_id + expected_session_version).
CREATE TABLE IF NOT EXISTS live.command_receipt (
    live_session_id   uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    client_command_id text NOT NULL,
    command_type      text NOT NULL,
    actor_type        text NOT NULL,
    actor_id          text,
    status            text NOT NULL CHECK (status IN ('ACCEPTED', 'REJECTED')),
    result            jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (live_session_id, client_command_id)
);

-- Per-topic planned vs actual timing (fluid 06).
CREATE TABLE IF NOT EXISTS live.topic_run (
    live_session_id uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    topic_index     integer NOT NULL,
    title           text NOT NULL,
    planned_seconds integer NOT NULL,
    started_at      timestamptz,
    ended_at        timestamptz,
    actual_seconds  integer,
    status          text NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'ACTIVE', 'DONE', 'SKIPPED')),
    PRIMARY KEY (live_session_id, topic_index)
);

-- AI/instructor-NL/time/poll proposals. Agents only propose; humans (or the deterministic policy for
-- AI_ACTIVE sessions) accept. based_on_version makes stale AI proposals unappliable (dist 20).
CREATE TABLE IF NOT EXISTS live.recommendation (
    recommendation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    live_session_id   uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    source            text NOT NULL CHECK (source IN ('AI_TUTOR', 'INSTRUCTOR_NL', 'TIME_ORCHESTRATOR', 'POLL_BRANCH', 'VISUAL_AGENT')),
    action            jsonb NOT NULL,
    rationale         text,
    based_on_version  bigint NOT NULL,
    status            text NOT NULL DEFAULT 'PROPOSED' CHECK (status IN ('PROPOSED', 'ACCEPTED', 'REJECTED', 'STALE')),
    decided_by        text,
    decided_at        timestamptz,
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS recommendation_session_idx ON live.recommendation (live_session_id, created_at DESC);

-- Instructor takeover (dist 20): one active takeover per scope.
CREATE TABLE IF NOT EXISTS live.takeover (
    takeover_id     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    live_session_id uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    scope           text NOT NULL CHECK (scope IN ('SESSION', 'STUDENT', 'GROUP')),
    scope_id        text NOT NULL DEFAULT '*',
    instructor      text NOT NULL,
    handoff_packet  jsonb NOT NULL DEFAULT '{}'::jsonb,
    started_at      timestamptz NOT NULL DEFAULT now(),
    ended_at        timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS takeover_active_uidx ON live.takeover (live_session_id, scope, scope_id)
    WHERE ended_at IS NULL;

-- ------------------------------------------------------------------ activities (fluid 07/14)
CREATE TABLE IF NOT EXISTS activity.definition (
    activity_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_type      text NOT NULL CHECK (activity_type IN (
        'MCQ', 'MULTISELECT', 'NUMERIC', 'SHORT_RESPONSE', 'SUBPROBLEM', 'STEP_ORDERING',
        'ERROR_DIAGNOSIS', 'CONFIDENCE_CHECK', 'LIVE_POLL')),
    prompt             text NOT NULL,
    options            jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(options) = 'array'),
    correctness_policy jsonb NOT NULL DEFAULT '{}'::jsonb,
    target_skill       text,
    estimated_seconds  integer NOT NULL DEFAULT 60 CHECK (estimated_seconds > 0),
    source_type        text NOT NULL CHECK (source_type IN (
        'PRECOMPILED', 'CORPUS_DERIVED', 'LIVE_AGENT_CREATED', 'INSTRUCTOR_CREATED')),
    source_lineage     jsonb NOT NULL DEFAULT '{}'::jsonb,
    persistence_mode   text NOT NULL DEFAULT 'SESSION' CHECK (persistence_mode IN ('STATIC', 'SESSION', 'EPHEMERAL')),
    created_by         text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS activity.instance (
    activity_instance_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    live_session_id      uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    activity_id          uuid NOT NULL REFERENCES activity.definition ON DELETE RESTRICT,
    status               text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED', 'REVEALED')),
    anonymous            boolean NOT NULL DEFAULT true,
    opened_by            text NOT NULL,
    opened_at            timestamptz NOT NULL DEFAULT now(),
    closes_at            timestamptz,
    closed_at            timestamptz
);
CREATE INDEX IF NOT EXISTS activity_instance_session_idx ON activity.instance (live_session_id, opened_at DESC);

-- One current response per participant per instance; re-submission while OPEN replaces it.
CREATE TABLE IF NOT EXISTS activity.response (
    response_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_instance_id uuid NOT NULL REFERENCES activity.instance ON DELETE CASCADE,
    participant_id       text NOT NULL,
    response             jsonb NOT NULL,
    confidence           smallint CHECK (confidence IS NULL OR confidence BETWEEN 1 AND 5),
    is_correct           boolean,
    client_command_id    text,
    submitted_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (activity_instance_id, participant_id)
);

-- ------------------------------------------------------------------ visual (fluid 08-12/19/20, dist 11-13/16)
CREATE TABLE IF NOT EXISTS visual.widget_spec (
    widget_spec_id  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    widget_type     text NOT NULL,
    spec_version    text NOT NULL DEFAULT '1',
    title           text,
    spec            jsonb NOT NULL,
    lifecycle       text NOT NULL DEFAULT 'VALIDATED' CHECK (lifecycle IN (
        'REQUESTED', 'SPEC_GENERATED', 'VALIDATED', 'READY', 'SHOWN', 'EXPIRED', 'REJECTED',
        'PROMOTION_CANDIDATE', 'PROMOTED_TO_TEMPLATE')),
    persistence     text NOT NULL DEFAULT 'SESSION' CHECK (persistence IN ('STATIC', 'SESSION', 'EPHEMERAL')),
    live_session_id uuid REFERENCES live.session ON DELETE CASCADE,
    source_type     text NOT NULL CHECK (source_type IN ('PRECOMPILED', 'CORPUS_DERIVED', 'LIVE_AGENT_CREATED', 'INSTRUCTOR_CREATED')),
    source_lineage  jsonb NOT NULL DEFAULT '{}'::jsonb,
    validation      jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_hash    text NOT NULL,
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz,
    reviewed_by     text,
    reviewed_at     timestamptz
);
CREATE INDEX IF NOT EXISTS widget_spec_session_idx ON visual.widget_spec (live_session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS widget_spec_lifecycle_idx ON visual.widget_spec (lifecycle, created_at DESC);

CREATE TABLE IF NOT EXISTS visual.widget_state (
    live_session_id    uuid NOT NULL REFERENCES live.session ON DELETE CASCADE,
    widget_instance_id text NOT NULL,
    widget_spec_id     uuid NOT NULL REFERENCES visual.widget_spec ON DELETE CASCADE,
    state              jsonb NOT NULL DEFAULT '{}'::jsonb,
    state_version      bigint NOT NULL DEFAULT 1,
    visible            boolean NOT NULL DEFAULT true,
    updated_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (live_session_id, widget_instance_id)
);

-- Binary visual assets live in object storage; only metadata is here (dist 16).
CREATE TABLE IF NOT EXISTS visual.asset (
    asset_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    uri               text NOT NULL,
    mime_type         text NOT NULL,
    content_hash      text NOT NULL,
    source_problem_id uuid REFERENCES core.problem ON DELETE SET NULL,
    diagram_id        text REFERENCES pedagogy.diagram ON DELETE SET NULL,
    created_by_agent  text,
    persistence_mode  text NOT NULL DEFAULT 'SESSION' CHECK (persistence_mode IN ('STATIC', 'SESSION', 'EPHEMERAL')),
    validation_status text NOT NULL DEFAULT 'PENDING' CHECK (validation_status IN ('PENDING', 'VALID', 'REJECTED')),
    created_at        timestamptz NOT NULL DEFAULT now(),
    expires_at        timestamptz
);
CREATE INDEX IF NOT EXISTS asset_hash_idx ON visual.asset (content_hash);
