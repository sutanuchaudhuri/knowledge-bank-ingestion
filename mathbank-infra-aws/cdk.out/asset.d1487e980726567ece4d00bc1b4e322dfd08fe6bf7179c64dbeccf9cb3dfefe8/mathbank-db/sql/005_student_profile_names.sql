-- Adds first_name/last_name to learner.student_profile for the student
-- profile UI (requirements/12_STUDENT_PROFILE_AND_ADMIN_LOGIN_UI_REQUIREMENTS.md).
-- display_name remains (now derived as "first_name last_name" at write time,
-- kept as its own column rather than computed on read so it still works for
-- any pre-existing rows that only ever had a display_name).
ALTER TABLE learner.student_profile ADD COLUMN IF NOT EXISTS first_name text;
ALTER TABLE learner.student_profile ADD COLUMN IF NOT EXISTS last_name text;
