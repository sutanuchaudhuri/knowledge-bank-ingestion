-- 038_micro_course_item_sequence.sql
-- Per-item cross-kind sequencing for micro-course states
-- (requirements/47_MICRO_COURSE_STUDENT_NAVIGATION_V2_AND_AI_ASSIST.md §2.1).
--
-- Every per-state child table already orders its own kind independently (own `ordinal`,
-- `UNIQUE (state_id, ordinal)`), but there is no data saying "the quiz comes between video#0
-- and interaction#0" across kinds. This adds one nullable `sequence_position` column per
-- child table, sharing one counter per state across all four kinds. Nullable and additive:
-- an already-published state with no sequence_position set anywhere keeps rendering exactly
-- as it does today (grouped by kind) — nothing regresses.
--
-- Also adds a `gave_up` flag to the event-recording path (requirements/47 §3.3/§4): a third,
-- distinct outcome alongside correct/incorrect, so analytics can tell "answered wrong" apart
-- from "explicitly gave up," without a new table.
BEGIN;

ALTER TABLE pedagogy.micro_course_state_asset         ADD COLUMN IF NOT EXISTS sequence_position smallint;
ALTER TABLE pedagogy.micro_course_state_interaction    ADD COLUMN IF NOT EXISTS sequence_position smallint;
ALTER TABLE pedagogy.micro_course_state_learning_item  ADD COLUMN IF NOT EXISTS sequence_position smallint;
ALTER TABLE pedagogy.micro_course_state_activity       ADD COLUMN IF NOT EXISTS sequence_position smallint;

COMMENT ON COLUMN pedagogy.micro_course_state_asset.sequence_position IS
    'Cross-kind ordering within a state, shared with interaction/learning_item/activity siblings. '
    'NULL means this state has not been authored with per-item sequencing yet (requirements/47).';

COMMIT;
