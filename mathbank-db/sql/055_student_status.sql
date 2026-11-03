-- Learner account status lifecycle (requirement 71 WP1, finding LRN-F11).
-- mathbank-rest now rejects the JWT of a DISABLED/DELETED student; this migration makes the status column a
-- closed set and records when an account was disabled or deleted. Additive and idempotent.
ALTER TABLE learner.student_profile ADD COLUMN IF NOT EXISTS disabled_at timestamptz;
ALTER TABLE learner.student_profile ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'learner.student_profile'::regclass AND conname = 'student_profile_status_check'
    ) THEN
        ALTER TABLE learner.student_profile
            ADD CONSTRAINT student_profile_status_check
            CHECK (status IN ('ACTIVE', 'DISABLED', 'DELETED')) NOT VALID;
    END IF;
END $$;

-- Validation scans the table without blocking writes. If a legacy row holds another value the constraint stays
-- NOT VALID (still enforced for new and updated rows) and a warning names the fix.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'learner.student_profile'::regclass
          AND conname = 'student_profile_status_check' AND NOT convalidated
    ) THEN
        BEGIN
            ALTER TABLE learner.student_profile VALIDATE CONSTRAINT student_profile_status_check;
        EXCEPTION WHEN check_violation THEN
            RAISE WARNING 'learner.student_profile has status values outside (ACTIVE, DISABLED, DELETED); '
                          'fix them, then run: ALTER TABLE learner.student_profile VALIDATE CONSTRAINT student_profile_status_check';
        END;
    END IF;
END $$;

COMMENT ON COLUMN learner.student_profile.disabled_at IS 'Set when an admin disables the account; cleared on re-enable.';
COMMENT ON COLUMN learner.student_profile.deleted_at IS 'Set when the account is soft-deleted (erasure); the account can never be re-enabled.';
