-- 043_notifications.sql
-- Student/admin notifications platform (requirements/59) — explicitly NOT part of the
-- ml.* schema (requirements/54 §2: notifications is event-driven infrastructure reacting
-- to existing grading paths, not a model). Additive only; no existing table is touched.
--
-- STATUS: scaffolded, NOT applied to any live database in this pass. Apply explicitly via
-- a migration script (see scripts/migrate_notifications.py — also scaffolded, not run)
-- once the trigger wiring in notifications.py is actually implemented; applying the
-- schema alone with no writer is harmless but premature.
BEGIN;

CREATE SCHEMA IF NOT EXISTS notification;

CREATE TABLE notification.event (
    notification_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_type         text NOT NULL CHECK (recipient_type IN ('STUDENT', 'ADMIN')),
    recipient_id           text NOT NULL,
    notification_type      text NOT NULL CHECK (notification_type IN (
        'QUIZ_GRADED',
        'MICRO_COURSE_ITEM_GRADED',
        'MICRO_COURSE_ACTIVITY_GRADED',
        'MASTERY_MILESTONE',
        'ADMIN_DATA_GAP',
        'ADMIN_REVIEW_NEEDED'
    )),
    severity               text NOT NULL DEFAULT 'INFO' CHECK (severity IN ('INFO', 'SUCCESS', 'WARNING', 'ACTION_NEEDED')),
    title                  text NOT NULL,
    body                   text,
    -- TODO (requirements/59 §3): decide whether this should be a typed FK per
    -- notification_type instead of a loose jsonb pointer, once at least one real trigger
    -- (quiz graded, say) is wired and the shape it actually needs is known.
    payload_json           jsonb NOT NULL DEFAULT '{}'::jsonb,
    read_at                timestamptz,
    created_at             timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notification_event_recipient
    ON notification.event (recipient_type, recipient_id, created_at DESC);

CREATE INDEX idx_notification_event_unread
    ON notification.event (recipient_type, recipient_id)
    WHERE read_at IS NULL;

COMMENT ON TABLE notification.event IS
    'requirements/59 — event-driven student/admin notifications. Not an ML concern; '
    'reacts to existing grading/review paths, does not compute anything new.';

COMMIT;

-- TODO (requirements/59 §3): a `notification.preference` table (per-recipient channel
-- opt-in/opt-out) is deferred until at least one real delivery channel beyond in-app
-- exists — do not build preference management for a channel that doesn't exist yet.
