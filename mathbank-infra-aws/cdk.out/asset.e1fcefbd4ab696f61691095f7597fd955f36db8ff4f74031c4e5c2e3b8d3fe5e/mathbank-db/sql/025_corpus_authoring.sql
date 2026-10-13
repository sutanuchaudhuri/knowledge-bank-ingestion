-- Review-only authoring. New synthetic questions never acquire official contest identity.
CREATE TABLE IF NOT EXISTS ingest.corpus_draft (
    draft_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL CHECK (kind IN ('TEXT_EDIT','IMAGE','NEW_PROBLEM')),
    problem_id uuid REFERENCES core.problem ON DELETE RESTRICT,
    payload jsonb NOT NULL,
    base_hash text,
    object_key text,
    state text NOT NULL DEFAULT 'DRAFT' CHECK (state IN ('DRAFT','APPROVED','REJECTED')),
    origin text NOT NULL CHECK (origin IN ('ADMIN','AI')),
    provenance jsonb NOT NULL DEFAULT '{}',
    revision int NOT NULL DEFAULT 1 CHECK (revision > 0),
    note text NOT NULL,
    review_note text,
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_at timestamptz,
    CHECK (kind='NEW_PROBLEM' OR problem_id IS NOT NULL),
    CHECK ((kind='IMAGE') = (object_key IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS corpus_draft_state_idx ON ingest.corpus_draft(state,created_at DESC);
ALTER TABLE core.problem ADD COLUMN IF NOT EXISTS admin_edited_at timestamptz;

CREATE OR REPLACE FUNCTION ingest.protect_corpus_draft() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' OR OLD.state <> 'DRAFT' THEN
        RAISE EXCEPTION 'Corpus review records cannot be deleted or changed after review';
    END IF;
    IF NEW.origin IS DISTINCT FROM OLD.origin OR NEW.provenance IS DISTINCT FROM OLD.provenance THEN
        RAISE EXCEPTION 'Corpus draft origin and creation provenance are immutable';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS protect_corpus_draft ON ingest.corpus_draft;
CREATE TRIGGER protect_corpus_draft BEFORE UPDATE OR DELETE ON ingest.corpus_draft
FOR EACH ROW EXECUTE FUNCTION ingest.protect_corpus_draft();

CREATE OR REPLACE FUNCTION core.protect_admin_statement() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.admin_edited_at IS NOT NULL AND NEW.statement_text IS DISTINCT FROM OLD.statement_text
        AND NEW.admin_edited_at IS NOT DISTINCT FROM OLD.admin_edited_at THEN
        RAISE EXCEPTION 'Reviewed admin text cannot be overwritten by ingestion';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS protect_admin_statement ON core.problem;
CREATE TRIGGER protect_admin_statement BEFORE UPDATE ON core.problem
FOR EACH ROW EXECUTE FUNCTION core.protect_admin_statement();
