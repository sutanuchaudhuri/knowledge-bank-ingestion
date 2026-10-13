-- requirements/64 (continued): links learner.student_profile rows to AWS Cognito
-- identities for mathbank-exam-web's onboarding (signup/login/forgot-password),
-- plus the grade/phone fields collected at onboarding. Additive-only — every existing
-- mathbank-rest JWT-based student row (cognito_sub IS NULL) is completely unaffected;
-- Cognito-backed auth is an alternate identity path into the SAME student_profile
-- table, not a parallel one.

ALTER TABLE learner.student_profile
    ADD COLUMN IF NOT EXISTS cognito_sub text UNIQUE,
    ADD COLUMN IF NOT EXISTS grade text,
    ADD COLUMN IF NOT EXISTS phone text,
    ADD COLUMN IF NOT EXISTS is_anonymous boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_student_profile_cognito_sub ON learner.student_profile(cognito_sub);
