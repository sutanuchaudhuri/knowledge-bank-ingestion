-- Persist course metadata and attach statically authored interaction instances
-- to lesson states. Object bytes remain private; visual.asset stores the URI,
-- MIME type, content hash, byte size, and review status.
BEGIN;

ALTER TABLE pedagogy.micro_course
    ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE visual.asset
    ADD COLUMN IF NOT EXISTS object_size_bytes bigint;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='pedagogy.micro_course'::regclass
          AND conname='micro_course_metadata_object'
    ) THEN
        ALTER TABLE pedagogy.micro_course
            ADD CONSTRAINT micro_course_metadata_object
            CHECK (jsonb_typeof(metadata)='object');
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid='visual.asset'::regclass
          AND conname='visual_asset_object_size_positive'
    ) THEN
        ALTER TABLE visual.asset
            ADD CONSTRAINT visual_asset_object_size_positive
            CHECK (object_size_bytes IS NULL OR object_size_bytes > 0);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS pedagogy.micro_course_state_interaction (
    state_id               uuid NOT NULL REFERENCES pedagogy.micro_course_state ON DELETE CASCADE,
    interaction_instance_id uuid NOT NULL
        REFERENCES visual.interaction_instance ON DELETE RESTRICT,
    ordinal                integer NOT NULL CHECK (ordinal >= 0),
    required               boolean NOT NULL DEFAULT true,
    PRIMARY KEY (state_id, interaction_instance_id),
    UNIQUE (state_id, ordinal)
);

CREATE INDEX IF NOT EXISTS micro_course_state_interaction_instance_idx
    ON pedagogy.micro_course_state_interaction (interaction_instance_id);

CREATE OR REPLACE FUNCTION pedagogy.guard_micro_course_state_interaction()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    state_release_status text;
BEGIN
    IF current_setting('pedagogy.allow_purge', true)='on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    SELECT r.status INTO state_release_status
    FROM pedagogy.micro_course_state s
    JOIN pedagogy.micro_course_release r USING (release_id)
    WHERE s.state_id=COALESCE(NEW.state_id, OLD.state_id);
    IF state_release_status IN ('PUBLISHED','SUPERSEDED','RETIRED') THEN
        RAISE EXCEPTION 'interactions of a published micro-course release are immutable';
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS micro_course_state_interaction_guard
    ON pedagogy.micro_course_state_interaction;
CREATE TRIGGER micro_course_state_interaction_guard
    BEFORE INSERT OR UPDATE OR DELETE ON pedagogy.micro_course_state_interaction
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_micro_course_state_interaction();

CREATE OR REPLACE FUNCTION pedagogy.guard_published_micro_course_identity()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pedagogy.micro_course_release
        WHERE micro_course_id=OLD.micro_course_id
          AND status IN ('PUBLISHED','SUPERSEDED','RETIRED')
    ) THEN
        IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'identity of a published micro-course is immutable';
        END IF;
        IF ROW(NEW.canonical_code, NEW.title, NEW.description, NEW.metadata,
               NEW.estimated_minutes, NEW.difficulty_level)
           IS DISTINCT FROM
           ROW(OLD.canonical_code, OLD.title, OLD.description, OLD.metadata,
               OLD.estimated_minutes, OLD.difficulty_level) THEN
            RAISE EXCEPTION 'identity of a published micro-course is immutable';
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS micro_course_published_identity_guard ON pedagogy.micro_course;
CREATE TRIGGER micro_course_published_identity_guard
    BEFORE UPDATE OR DELETE ON pedagogy.micro_course
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_micro_course_identity();

CREATE OR REPLACE FUNCTION pedagogy.guard_published_micro_course_asset()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pedagogy.micro_course_state_asset sa
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN pedagogy.micro_course_release r USING (release_id)
        WHERE sa.asset_id=OLD.asset_id
          AND r.status IN ('PUBLISHED','SUPERSEDED','RETIRED')
    ) THEN
        IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'asset used by a published micro-course is immutable';
        END IF;
        IF ROW(NEW.uri, NEW.mime_type, NEW.content_hash, NEW.object_size_bytes,
               NEW.validation_status, NEW.asset_kind, NEW.title, NEW.source_url, NEW.rights_note)
           IS DISTINCT FROM
           ROW(OLD.uri, OLD.mime_type, OLD.content_hash, OLD.object_size_bytes,
               OLD.validation_status, OLD.asset_kind, OLD.title, OLD.source_url, OLD.rights_note) THEN
            RAISE EXCEPTION 'asset used by a published micro-course is immutable';
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS micro_course_published_asset_guard ON visual.asset;
CREATE TRIGGER micro_course_published_asset_guard
    BEFORE UPDATE OR DELETE ON visual.asset
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_micro_course_asset();

CREATE OR REPLACE FUNCTION pedagogy.guard_published_micro_course_interaction()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM pedagogy.micro_course_state_interaction si
        JOIN pedagogy.micro_course_state s USING (state_id)
        JOIN pedagogy.micro_course_release r USING (release_id)
        WHERE si.interaction_instance_id=OLD.interaction_instance_id
          AND r.status IN ('PUBLISHED','SUPERSEDED','RETIRED')
    ) THEN
        IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'interaction used by a published micro-course is immutable';
        END IF;
        IF ROW(NEW.interaction_template_version_id, NEW.canonical_code, NEW.title,
               NEW.instance_config, NEW.initial_state, NEW.learning_objective,
               NEW.success_criteria, NEW.feedback_policy_id, NEW.scene_spec_id,
               NEW.content_hash, NEW.review_status)
           IS DISTINCT FROM
           ROW(OLD.interaction_template_version_id, OLD.canonical_code, OLD.title,
               OLD.instance_config, OLD.initial_state, OLD.learning_objective,
               OLD.success_criteria, OLD.feedback_policy_id, OLD.scene_spec_id,
               OLD.content_hash, OLD.review_status) THEN
            RAISE EXCEPTION 'interaction used by a published micro-course is immutable';
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;

DROP TRIGGER IF EXISTS micro_course_published_interaction_guard
    ON visual.interaction_instance;
CREATE TRIGGER micro_course_published_interaction_guard
    BEFORE UPDATE OR DELETE ON visual.interaction_instance
    FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_published_micro_course_interaction();

COMMENT ON COLUMN pedagogy.micro_course.metadata IS
    'Admin-authored stable course metadata; binary objects stay in private object storage and are referenced through visual.asset.';
COMMENT ON TABLE pedagogy.micro_course_state_interaction IS
    'Ordered binding from an immutable course state to an admin-configured interaction instance and exact published template version.';

COMMIT;
