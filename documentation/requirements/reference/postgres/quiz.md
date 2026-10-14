# Quiz and mock-exam schema

## Evidence and boundary

Source-derived from migrations `042_quiz_generation.sql` and
`047_mock_exam_extensions.sql` through `051_exam_resume_state.sql`, plus
`mathbank-rest/src/mathbank_rest/quiz_runtime.py` and the exam integration
router. Current source revision: `99b9c503e3ef1abce15fbc681f087401b78227d5`;
relevant worktree changes are included. This page describes 12
source-defined `quiz` tables; it is not a live catalog observation. Migration
051 has not been applied or verified on a database target. See
[requirement 64](../../64_AWS_BEDROCK_MOCK_EXAM_AGENT.md) for the exam-agent
and frontend lifecycle.

The schema is separate from live classroom `activity.*`, canonical
`core.problem`, and ordinary `learner.attempt`. Quiz responses join existing
mastery through `question_concept` and `question_technique`; there is no graph
projection in this schema contract.

Unless noted otherwise, foreign keys use PostgreSQL's default `NO ACTION`.
Types, defaults and nullable status below follow the migration chain.

## Tables

| Table | Columns, nullability and defaults | Keys, relationships and checks |
|---|---|---|
| `quiz.paper` | `quiz_id uuid NOT NULL DEFAULT gen_random_uuid()`; `student_id uuid NOT NULL`; `style text NOT NULL`; `title text NOT NULL`; `instructions text NOT NULL DEFAULT ''`; `requested_question_count integer NOT NULL`; `requested_question_types text[] NOT NULL`; `target_skill_slugs text[] NOT NULL DEFAULT '{}'`; `target_concept_slugs text[] NOT NULL DEFAULT '{}'`; `difficulty_band text NULL`; `generated_by text NOT NULL DEFAULT 'gpt-4o-mini'`; `object_key text NULL`; `object_sha256 text NULL`; `status text NOT NULL DEFAULT 'GENERATING'`; `error_message text NULL`; `created_at timestamptz NOT NULL DEFAULT now()`; `started_at`, `submitted_at`, `graded_at timestamptz NULL`; migration 047 adds `exam_mode boolean NOT NULL DEFAULT false`, `time_limit_seconds integer NULL`, `agent_framework text NOT NULL DEFAULT 'OPENAI_DIRECT'`; migration 051 adds `resume_question_ordinal integer NULL`. | PK `quiz_id`; FK `student_id` to `learner.student_profile`; `style` in `AIME`, `HMMT`, `PROOF_BASED`, `TOPIC_BASED`, `SKILL_BASED`, `MIXED`; requested count 1–20; status in `GENERATING`, `READY`, `FAILED`, `IN_PROGRESS`, `SUBMITTED`, `GRADED`; `agent_framework` in `OPENAI_DIRECT`, `STRANDS_BEDROCK`; resume ordinal is NULL or > 0. Index `(student_id, created_at DESC)`. |
| `quiz.question` | `question_id uuid NOT NULL DEFAULT gen_random_uuid()`; `quiz_id uuid NOT NULL`; `ordinal integer NOT NULL`; `question_type text NOT NULL`; `prompt_text text NOT NULL`; `prompt_latex text NULL`; `options jsonb NULL`; `correct_answer jsonb NOT NULL`; `points numeric NOT NULL DEFAULT 1`; `inspired_by_problem_id uuid NULL`; `diagram_object_key`, `diagram_sha256 text NULL`; `created_at timestamptz NOT NULL DEFAULT now()`; migration 047 adds `revision_log jsonb NOT NULL DEFAULT '[]'::jsonb`, `difficulty_band text NULL`; migration 048 adds `option_explanations jsonb NOT NULL DEFAULT '{}'::jsonb`; migration 050 adds `complexity_signals jsonb NOT NULL DEFAULT '{}'::jsonb`; migration 052 adds `pool_question_id uuid NULL`. | PK `question_id`; FK `quiz_id` to paper with `ON DELETE CASCADE`; optional FK `inspired_by_problem_id` to `core.problem`; optional FK `pool_question_id` to `quiz.question_pool` (`ON DELETE SET NULL`, partial index); `ordinal > 0`; type in `MCQ`, `FREE_TEXT`, `PROOF`; `points > 0`; unique `(quiz_id, ordinal)`. |
| `quiz.question_concept` | `question_id uuid NOT NULL`; `concept_id uuid NOT NULL`. | Composite PK `(question_id, concept_id)`; question FK cascades on delete; concept FK to `knowledge.concept`. |
| `quiz.question_technique` | `question_id uuid NOT NULL`; `technique_id uuid NOT NULL`. | Composite PK `(question_id, technique_id)`; question FK cascades on delete; technique FK to `knowledge.technique`. |
| `quiz.question_skill` | `question_id uuid NOT NULL`; `skill_id uuid NOT NULL`. | Composite PK `(question_id, skill_id)`; question FK cascades on delete; skill FK to `knowledge.skill`. |
| `quiz.solution` | `question_id uuid NOT NULL`; `solution_text text NOT NULL`; `solution_latex text NULL`; `key_insight text NULL`; `object_key`, `object_sha256 text NULL`; `created_at timestamptz NOT NULL DEFAULT now()`; migration 050 adds `solution_steps jsonb NOT NULL DEFAULT '[]'::jsonb`, `step_count integer NULL`. | PK `question_id`, also FK to question with `ON DELETE CASCADE`. |
| `quiz.response` | `response_id uuid NOT NULL DEFAULT gen_random_uuid()`; `question_id`, `quiz_id`, `student_id uuid NOT NULL`; `response_type text NOT NULL`; `raw_response jsonb NOT NULL`; `object_key`, `object_sha256 text NULL`; `is_correct boolean NULL`; `grading_method text NOT NULL`; `grading_confidence numeric NULL`; `grading_feedback text NULL`; `time_spent_seconds integer NULL`; `submitted_at timestamptz NOT NULL DEFAULT now()`. | PK `response_id`; FKs to question and paper with `ON DELETE CASCADE`, and to `learner.student_profile`; unique `question_id` (one final response per question); response type in `MCQ`, `FREE_TEXT`, `PROOF`; grading method in `EXACT_MATCH`, `LLM_GRADED`, `PENDING_HUMAN_REVIEW`; confidence NULL or 0–1. Index `(student_id, submitted_at DESC)`. |
| `quiz.exam_diagnosis` | `quiz_id uuid NOT NULL`; `time_management_verdict text NOT NULL`; `pacing_notes`, `reasoning_guidance`, `improvement_areas jsonb NOT NULL DEFAULT '[]'::jsonb`; `generated_by text NOT NULL`; `created_at timestamptz NOT NULL DEFAULT now()`. | PK `quiz_id`, FK to paper with `ON DELETE CASCADE`; one holistic report per paper. |
| `quiz.response_event` | `event_id uuid NOT NULL DEFAULT gen_random_uuid()`; `quiz_id`, `question_id`, `student_id uuid NOT NULL`; `event_type text NOT NULL`; `option_key text NULL`; `client_timestamp_ms bigint NULL`; `created_at timestamptz NOT NULL DEFAULT now()`. | PK `event_id`; FKs to paper and question with `ON DELETE CASCADE`, and to student profile; event type in `VIEW`, `SELECT_OPTION`, `DESELECT_OPTION`, `TEXT_CHANGE`, `SKIP`, `FINAL_SUBMIT`. Index `(quiz_id, question_id, created_at)`. |
| `quiz.question_source` | `question_id`, `problem_id uuid NOT NULL`; `rank smallint NOT NULL`; `note text NOT NULL DEFAULT ''`. | Composite PK `(question_id, problem_id)`; question FK cascades on delete; problem FK to `core.problem`; rank 1–5. Index `(question_id, rank)`. Rank 1 is the primary source retained in the legacy `inspired_by_problem_id` field. |
| `quiz.generation_event` | `event_id uuid NOT NULL DEFAULT gen_random_uuid()`; `quiz_id uuid NOT NULL`; `ordinal integer NOT NULL`; `phase`, `status text NOT NULL`; `question_ordinal integer NULL`; `detail text NOT NULL DEFAULT ''`; `created_at timestamptz NOT NULL DEFAULT now()`. | PK `event_id`; paper FK cascades on delete; unique `(quiz_id, ordinal)`; phase in `INTAKE`, `TOPIC_RESOLVE`, `DIFFICULTY_SIGNAL`, `POOL_LOOKUP` (migration 052), `DRAFT_QUESTION`, `CRITIC_REVIEW`, `AGGREGATE_DIVERSITY_CHECK`, `AGGREGATE_FIX`, `PERSIST`, `DONE`, `FAILED`; status in `STARTED`, `DONE`, `FAILED`. Index `(quiz_id, ordinal)`. |
| `quiz.question_pool` | `pool_question_id uuid NOT NULL DEFAULT gen_random_uuid()`; `content_hash text NOT NULL`; `style`, `question_type text NOT NULL`; `difficulty_band text NULL`; `topic_key text NOT NULL DEFAULT ''`; `concept_slugs`, `technique_slugs text[] NOT NULL DEFAULT '{}'`; `question jsonb NOT NULL` (the full finalize-paper question payload, including solution); `source_quiz_id uuid NULL`; `generated_by text NULL`; `times_served integer NOT NULL DEFAULT 0`; `last_served_at timestamptz NULL`; `created_at timestamptz NOT NULL DEFAULT now()`. Migration 052. | PK `pool_question_id`; unique `content_hash` (sha256 of normalized prompt); FK `source_quiz_id` to paper `ON DELETE SET NULL`; type in `MCQ`, `FREE_TEXT`, `PROOF`. Indexes `(style, question_type, difficulty_band)`, GIN `concept_slugs`, GIN trigram `topic_key`. Cache of critic-approved generated questions keyed by the request inputs; served first for near-identical requests and grown on every finalize. |
| `quiz.response_draft` | `quiz_id`, `question_id`, `student_id uuid NOT NULL`; `raw_response jsonb NOT NULL`; `updated_at timestamptz NOT NULL DEFAULT now()`. | Composite PK `(quiz_id, question_id)`; paper and question FKs cascade on delete; student FK to `learner.student_profile`; index `(student_id, updated_at DESC)`. Runtime validates that the question belongs to the paper and that the draft shape matches the question type. |

## Runtime and migration boundaries

- Migrations 042, 047, 048, 050 and 051 own the `quiz` tables/columns listed
  above. Migration 049 adds Cognito identity fields to
  `learner.student_profile`; it does not add a `quiz` relation. Application
  of source DDL is not established by this inventory.
- `quiz.response` is the single graded/final answer row. A draft in
  `quiz.response_draft` is unsubmitted and is never treated as a response or
  mastery evidence.
- Exam progress is owner-scoped in `quiz_runtime`: the service validates the
  paper belongs to the supplied student, validates the current ordinal and
  question identity, and validates a draft's allowed fields and question
  type. It saves the resume ordinal and optional draft in one transaction.
- Confirming an answer deletes that question's draft; skipping deletes its
  draft; submitting the paper deletes all of its drafts. The paper, question
  and event FKs cascade relevant child data on deletion.
- The exam-agent's REST integration router is shared-key protected; the agent
  supplies the student identity resolved from the signed-in session. The
  browser does not call the internal REST route directly.
- `quiz.response_event` is interaction telemetry, not grading input.
  `quiz.generation_event` is a separate pre-exam progress log. Neither is
  interchangeable with the answer or draft tables.
- Exam-mode answer/solution withholding is an application-level
  `get_review()` gate, not a database constraint. The student-facing paper
  reader returns only the student's own response/draft state.
