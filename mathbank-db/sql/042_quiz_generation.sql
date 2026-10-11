-- requirements/53 QZ-1: AI-generated personalized quiz/question-paper subsystem.
--
-- Deliberately NOT reusing activity.*/core.problem/learner.attempt — see
-- requirements/53_AI_GENERATED_QUIZ_SUBAGENT.md §1 for the live-confirmed reasons each
-- existing table was unsuitable (activity.instance requires a live classroom session;
-- core.problem requires a real paper_id/source_url and is the canonical "real, sourced
-- problem" identity; learner.attempt is hard-FK'd to core.problem). This schema is a
-- parallel, first-class subsystem that FEEDS INTO (not duplicates) the existing mastery
-- tables via question_concept/question_technique junctions mirroring
-- knowledge.problem_concept/problem_technique's own convention exactly.
CREATE SCHEMA IF NOT EXISTS quiz;

CREATE TABLE IF NOT EXISTS quiz.paper (
    quiz_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile(student_id),
    style text NOT NULL CHECK (style IN ('AIME','HMMT','PROOF_BASED','TOPIC_BASED','SKILL_BASED','MIXED')),
    title text NOT NULL,
    instructions text NOT NULL DEFAULT '',
    requested_question_count integer NOT NULL CHECK (requested_question_count BETWEEN 1 AND 20),
    requested_question_types text[] NOT NULL,
    target_skill_slugs text[] NOT NULL DEFAULT '{}',
    target_concept_slugs text[] NOT NULL DEFAULT '{}',
    difficulty_band text,
    generated_by text NOT NULL DEFAULT 'gpt-4o-mini',
    object_key text,
    object_sha256 text,
    status text NOT NULL DEFAULT 'GENERATING'
        CHECK (status IN ('GENERATING','READY','FAILED','IN_PROGRESS','SUBMITTED','GRADED')),
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    submitted_at timestamptz,
    graded_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_quiz_paper_student ON quiz.paper(student_id, created_at DESC);

CREATE TABLE IF NOT EXISTS quiz.question (
    question_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    quiz_id uuid NOT NULL REFERENCES quiz.paper(quiz_id) ON DELETE CASCADE,
    ordinal integer NOT NULL CHECK (ordinal > 0),
    question_type text NOT NULL CHECK (question_type IN ('MCQ','FREE_TEXT','PROOF')),
    prompt_text text NOT NULL,
    prompt_latex text,
    options jsonb,                    -- MCQ: [{"key":"A","text":"..."}, ...]
    correct_answer jsonb NOT NULL,    -- MCQ: {"correct_key":"A"}; FREE_TEXT/PROOF: {"expected_answer":...,"grading_rubric":...}
    points numeric NOT NULL DEFAULT 1 CHECK (points > 0),
    inspired_by_problem_id uuid REFERENCES core.problem(problem_id),
    diagram_object_key text,
    diagram_sha256 text,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (quiz_id, ordinal)
);

CREATE TABLE IF NOT EXISTS quiz.question_concept (
    question_id uuid NOT NULL REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    concept_id uuid NOT NULL REFERENCES knowledge.concept(concept_id),
    PRIMARY KEY (question_id, concept_id)
);
CREATE TABLE IF NOT EXISTS quiz.question_technique (
    question_id uuid NOT NULL REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    technique_id uuid NOT NULL REFERENCES knowledge.technique(technique_id),
    PRIMARY KEY (question_id, technique_id)
);
CREATE TABLE IF NOT EXISTS quiz.question_skill (
    question_id uuid NOT NULL REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    skill_id uuid NOT NULL REFERENCES knowledge.skill(skill_id),
    PRIMARY KEY (question_id, skill_id)
);

CREATE TABLE IF NOT EXISTS quiz.solution (
    question_id uuid PRIMARY KEY REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    solution_text text NOT NULL,
    solution_latex text,
    key_insight text,
    object_key text,
    object_sha256 text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS quiz.response (
    response_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id uuid NOT NULL REFERENCES quiz.question(question_id) ON DELETE CASCADE,
    quiz_id uuid NOT NULL REFERENCES quiz.paper(quiz_id) ON DELETE CASCADE,
    student_id uuid NOT NULL REFERENCES learner.student_profile(student_id),
    response_type text NOT NULL CHECK (response_type IN ('MCQ','FREE_TEXT','PROOF')),
    raw_response jsonb NOT NULL,
    object_key text,
    object_sha256 text,
    is_correct boolean,
    grading_method text NOT NULL CHECK (grading_method IN ('EXACT_MATCH','LLM_GRADED','PENDING_HUMAN_REVIEW')),
    grading_confidence numeric CHECK (grading_confidence IS NULL OR grading_confidence BETWEEN 0 AND 1),
    grading_feedback text,
    time_spent_seconds integer,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (question_id)   -- one response per question; resubmission is a future enhancement, not v1 scope
);
CREATE INDEX IF NOT EXISTS idx_quiz_response_student ON quiz.response(student_id, submitted_at DESC);
