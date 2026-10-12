-- 035_admin_micro_course_platform.sql
-- Admin micro-course workspace foundations (requirements/43_ADMIN_MICRO_COURSE_AUTHORING_UI.md,
-- requirements/44_MICRO_COURSE_MOBILE_AI_ANALYTICS_PLATFORM.md):
--   1. audit.action_log — a general-purpose, append-only audit trail (the `audit` schema already
--      existed, reserved, since migration 001; this is its first table).
--   2. pedagogy.micro_course gains course-level deactivation, independent of release-level
--      status/immutability — a published course's identity stays immutable (migration 034's
--      guard), but whether it is listed to students is a separate, always-editable flag.
-- Depends on migrations 032-034 already being applied (pedagogy.micro_course,
-- pedagogy.micro_course_release, the published-identity guard function).
BEGIN;

-- 1. Audit trail --------------------------------------------------------------------------------
-- Append-only by convention (like pedagogy.micro_course_review): the service layer only ever
-- INSERTs; no guard trigger is added because nothing should ever UPDATE/DELETE a row here, and a
-- trigger would only add weight without a reachable code path that needs blocking.
CREATE TABLE IF NOT EXISTS audit.action_log (
    action_log_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_type    text NOT NULL CHECK (actor_type IN ('STUDENT', 'ADMIN', 'AI', 'SYSTEM')),
    actor_id      text,
    action        text NOT NULL,
    entity_type   text NOT NULL,
    entity_id     text NOT NULL,
    before_state  jsonb,
    after_state   jsonb,
    request_id    text,
    created_at    timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS action_log_entity_idx
    ON audit.action_log (entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS action_log_request_idx
    ON audit.action_log (request_id) WHERE request_id IS NOT NULL;
COMMENT ON TABLE audit.action_log IS
    'General-purpose, append-only audit trail (requirements/44 MCX-8). One row per traced action; '
    'request_id correlates a single action across this log, pipeline.outbox_event, and ai_usage_event.';

-- 2. Course-level deactivation, independent of release immutability -----------------------------
ALTER TABLE pedagogy.micro_course ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE pedagogy.micro_course ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE pedagogy.micro_course ADD COLUMN IF NOT EXISTS deactivated_by text;
ALTER TABLE pedagogy.micro_course ADD CONSTRAINT micro_course_deactivation_consistent
    CHECK (is_active OR deactivated_at IS NOT NULL);

-- Re-declare the 034 guard, excluding is_active/deactivated_at/deactivated_by from the identity
-- comparison: deactivating/reactivating a published course must always be possible, independent
-- of the published-identity-is-frozen rule.
CREATE OR REPLACE FUNCTION pedagogy.guard_published_micro_course_identity()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pedagogy.micro_course_release
        WHERE micro_course_id=OLD.micro_course_id
          AND status IN ('PUBLISHED','SUPERSEDED','RETIRED')
    ) THEN
        IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'identity of a published micro-course is immutable';
        END IF;
        IF ROW(NEW.canonical_code, NEW.title, NEW.description, NEW.metadata,
               NEW.estimated_minutes, NEW.difficulty_level)
           IS DISTINCT FROM
           ROW(OLD.canonical_code, OLD.title, OLD.description, OLD.metadata,
               OLD.estimated_minutes, OLD.difficulty_level) THEN
            RAISE EXCEPTION 'identity of a published micro-course is immutable';
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

COMMENT ON COLUMN pedagogy.micro_course.is_active IS
    'Course-level visibility to students, independent of release status. A published course''s '
    'release content/identity stays immutable; deactivation only hides it from the student catalog.';

COMMIT;
