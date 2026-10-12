-- Automatic approval is usable metadata, not a claim of human review.
BEGIN;
ALTER TABLE knowledge.pedagogy_review_event
    DROP CONSTRAINT IF EXISTS pedagogy_review_event_entity_kind_check;
ALTER TABLE knowledge.pedagogy_review_event ADD CONSTRAINT pedagogy_review_event_entity_kind_check
    CHECK (entity_kind IN ('skill','skill_concept','skill_relation','problem_skill',
                          'problem_pedagogy','problem_concept','problem_technique'));
CREATE TABLE IF NOT EXISTS knowledge.metadata_approval_event (
    event_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_kind text NOT NULL,
    before_snapshot jsonb,
    after_snapshot jsonb NOT NULL,
    approved_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS knowledge.enrichment_job (
    problem_id uuid PRIMARY KEY REFERENCES core.problem ON DELETE CASCADE,
    status text NOT NULL CHECK(status IN ('IN_PROGRESS','COMPLETED','FAILED')),
    attempts integer NOT NULL DEFAULT 1,
    last_error text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE knowledge.enrichment_job ADD COLUMN IF NOT EXISTS published_at timestamptz;

CREATE OR REPLACE FUNCTION knowledge.apply_automatic_approval() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE'
       AND (current_setting('mathbank.automatic_writer', true) = 'on'
            OR (NEW.review_status = 'PENDING'
                AND current_setting('mathbank.human_review', true) IS DISTINCT FROM 'on'))
       AND (OLD.review_status = 'REJECTED' OR OLD.approval_method = 'human') THEN
        RETURN OLD;
    END IF;
    IF NEW.review_status = 'PENDING'
       AND current_setting('mathbank.human_review', true) IS DISTINCT FROM 'on' THEN
        NEW.review_status := 'REVIEWED';
        NEW.approval_method := 'automatic';
    END IF;
    IF current_setting('mathbank.automatic_writer', true) = 'on' THEN
        NEW.approval_method := 'automatic';
    END IF;
    IF current_setting('mathbank.human_review', true) = 'on' THEN
        NEW.approval_method := 'human';
    END IF;
    RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION knowledge.record_automatic_approval() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.approval_method = 'automatic'
       AND (TG_OP = 'INSERT' OR to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)) THEN
        INSERT INTO knowledge.metadata_approval_event(entity_kind,before_snapshot,after_snapshot)
        VALUES (TG_TABLE_NAME, CASE WHEN TG_OP='UPDATE' THEN to_jsonb(OLD) ELSE NULL END,
                to_jsonb(NEW));
    END IF;
    RETURN NULL;
END $$;

DO $$
DECLARE name text;
BEGIN
    FOREACH name IN ARRAY ARRAY['skill','skill_concept','skill_relation','problem_skill',
        'problem_pedagogy','problem_concept','problem_technique','concept_relation'] LOOP
        EXECUTE format('ALTER TABLE knowledge.%I ADD COLUMN IF NOT EXISTS approval_method text',name);
        EXECUTE format('UPDATE knowledge.%I SET approval_method=''human''
                        WHERE review_status IN (''REVIEWED'',''REJECTED'') AND approval_method IS NULL',name);
        EXECUTE format('DROP TRIGGER IF EXISTS automatic_metadata ON knowledge.%I',name);
        EXECUTE format('CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.%I
                        FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()',name);
        EXECUTE format('DROP TRIGGER IF EXISTS automatic_metadata_audit ON knowledge.%I',name);
        EXECUTE format('CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.%I
                        FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()',name);
        EXECUTE format('UPDATE knowledge.%I SET review_status=''PENDING''
                        WHERE review_status=''PENDING''',name);
    END LOOP;
END $$;
COMMIT;
