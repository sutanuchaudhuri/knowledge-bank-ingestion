-- 019: Admin import / reconciliation / semantic DAG review (runtime_extension/15).
-- Additive and idempotent. Admin edits are recorded in an append-only audit table, protected from
-- package re-import (importer guard on admin_edited_at / approval_method='human') and announced on the
-- outbox (SOLUTION_STEP_CHANGED / LEARNING_ITEM_PUBLISHED) so the projection-request consumer re-projects.

-- Append-only audit of every admin decision made through /v1/admin/imports.
CREATE TABLE IF NOT EXISTS ingest.admin_review_action (
    action_id    bigserial PRIMARY KEY,
    target_type  text NOT NULL CHECK (target_type IN (
        'IMPORT_CONFLICT', 'SOLUTION_STEP', 'STEP_DEPENDENCY', 'SOLUTION_DAG', 'LEARNING_ITEM',
        'PROJECTION_REQUEST')),
    target_id    text NOT NULL,
    action       text NOT NULL,
    before_state jsonb,
    after_state  jsonb,
    note         text,
    actor        text NOT NULL DEFAULT 'admin',
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS admin_review_action_target_idx
    ON ingest.admin_review_action (target_type, target_id, created_at DESC);

CREATE OR REPLACE FUNCTION ingest.admin_review_action_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'ingest.admin_review_action is append-only';
END $$;
DROP TRIGGER IF EXISTS admin_review_action_append_only ON ingest.admin_review_action;
CREATE TRIGGER admin_review_action_append_only BEFORE UPDATE OR DELETE ON ingest.admin_review_action
    FOR EACH ROW EXECUTE FUNCTION ingest.admin_review_action_append_only();

-- Conflict decisions (spec 15 §4): keep existing / accept incoming / merge manually.
ALTER TABLE ingest.import_conflict ADD COLUMN IF NOT EXISTS decision text;
ALTER TABLE ingest.import_conflict ADD COLUMN IF NOT EXISTS decided_at timestamptz;
DO $$ BEGIN
    ALTER TABLE ingest.import_conflict ADD CONSTRAINT import_conflict_decision_check
        CHECK (decision IS NULL OR decision IN ('KEEP_EXISTING', 'ACCEPT_INCOMING', 'MERGE_MANUALLY'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Admin step edits (skill / checkpoint) survive re-import: the importer skips rows with admin_edited_at.
ALTER TABLE pedagogy.solution_step ADD COLUMN IF NOT EXISTS admin_edited_at timestamptz;

-- Semantic DAG approval per solution (spec 15 §7 "approve semantic DAG").
CREATE TABLE IF NOT EXISTS pedagogy.solution_dag_review (
    solution_id  uuid PRIMARY KEY REFERENCES core.solution ON DELETE CASCADE,
    problem_id   uuid NOT NULL REFERENCES core.problem ON DELETE CASCADE,
    status       text NOT NULL CHECK (status IN ('APPROVED', 'NEEDS_REVISION')),
    note         text,
    reviewed_by  text NOT NULL DEFAULT 'admin',
    reviewed_at  timestamptz NOT NULL DEFAULT now()
);

-- Spec 02 dependency vocabulary + the imported NEXT order edge (documentation; not enforced on import rows).
COMMENT ON COLUMN pedagogy.solution_step_dependency.relationship_type IS
    'NEXT | DEPENDS_ON | DERIVES_FROM | USES_RESULT_FROM | ALTERNATIVE_TO | BRANCHES_TO | JOINS_AT | JUSTIFIES '
    '(runtime prerequisites use DEPENDS_ON only; admin edits set approval_method=human)';

-- Projection requests can now also be raised by an admin ("reproject missing").
ALTER TABLE pipeline.projection_request ADD COLUMN IF NOT EXISTS requested_by text;
