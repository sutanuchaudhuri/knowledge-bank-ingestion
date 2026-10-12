-- Operator action (not a migration): automatically approve validated learning items and make them
-- student-visible ("everything auto approved for now"). Idempotent; only PENDING_REVIEW rows are touched,
-- so human REJECTED/NEEDS_REVISION decisions are never overridden, and the importer's upsert guard
-- (updates only PENDING_REVIEW rows) keeps the approval on re-import.
--
-- Validation: an MCQ needs >= 2 choices with the correct answer among them; a subproblem needs a seed;
-- every item must be no-proof and have question text. Invalid items stay PENDING_REVIEW.
-- Afterwards run textbook-vector-remote (paid) and textbook-graph-remote to project/embed them.

\set ON_ERROR_STOP 1

WITH approved AS (
    UPDATE pedagogy.learning_item SET
        review_status = 'APPROVED', student_visible = true, approval_method = 'automatic',
        approved_at = now(), updated_at = now()
    WHERE review_status = 'PENDING_REVIEW' AND no_proof
      AND coalesce(btrim(question_text), '') <> ''
      AND CASE transformed_form
            WHEN 'MCQ' THEN jsonb_typeof(choices) = 'array' AND jsonb_array_length(choices) >= 2
                            AND choices ? correct_answer
            WHEN 'SUBPROBLEM' THEN coalesce(btrim(answer_or_solution_seed), '') <> ''
            ELSE false END
    RETURNING learning_item_id, transformation_type
), published AS (  -- runtime_extension/16: one outbox event per newly published item
    INSERT INTO pipeline.outbox_event (event_type, aggregate_type, aggregate_id, payload)
    SELECT 'LEARNING_ITEM_PUBLISHED', 'learning_item', learning_item_id::text,
           jsonb_build_object('transformation_type', transformation_type, 'approval_method', 'automatic')
      FROM approved
)
SELECT 'approved' AS action, transformation_type, count(*) FROM approved GROUP BY 2 ORDER BY 2;

SELECT review_status, approval_method, student_visible, count(*)
  FROM pedagogy.learning_item GROUP BY 1, 2, 3 ORDER BY 1, 2;
