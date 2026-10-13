-- 037_quiz_authoring.sql
-- Micro-course quiz/activity authoring gaps (requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md):
--   1. activity.definition gains target_skill_id (real FK to knowledge.skill, replacing the
--      free-text target_skill for micro-course-authored quizzes — the old column is kept,
--      unchanged, for any existing live/fluid-session caller), source_problem_id (real FK to
--      core.problem, structured alternative to the undocumented source_lineage jsonb bag), and
--      a status/deactivated_at/deactivated_by lifecycle (§2.5), mirroring migration 035's
--      pedagogy.micro_course pattern.
--   2. pedagogy.micro_course_state_activity.purpose gains the same CHECK constraint already
--      present on its micro_course_state_learning_item sibling (§2.2), fixing the inconsistency
--      where one table enforces a real enum and the other accepts any string.
-- All changes are additive; no existing column/constraint is removed or renamed.
BEGIN;

ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS target_skill_id uuid REFERENCES knowledge.skill;
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS source_problem_id uuid REFERENCES core.problem;
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'INACTIVE'));
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE activity.definition ADD COLUMN IF NOT EXISTS deactivated_by text;

-- No backfill needed: every existing pedagogy.micro_course_state_activity.purpose value already
-- conforms (confirmed live: ENTRY_CHECK/COMPREHENSION/TRANSFER only). Skipping any UPDATE here is
-- deliberate — pedagogy.guard_published_state_child() blocks ANY update to a row whose state
-- belongs to a PUBLISHED/SUPERSEDED/RETIRED release regardless of whether the value actually
-- changes, so a backfill UPDATE would fail against this session's real published reference
-- courses. ALTER TABLE ... ADD CONSTRAINT validates existing data via an internal scan, not a
-- per-row UPDATE, so it does not trip that trigger.
ALTER TABLE pedagogy.micro_course_state_activity DROP CONSTRAINT IF EXISTS micro_course_state_activity_purpose_check;
ALTER TABLE pedagogy.micro_course_state_activity ADD CONSTRAINT micro_course_state_activity_purpose_check
    CHECK (purpose IN (
        'ENTRY_CHECK','COMPREHENSION','RECOGNITION','MISCONCEPTION_DIAGNOSTIC','EXECUTION','EXIT_CHECK','TRANSFER'
    ));

COMMIT;
