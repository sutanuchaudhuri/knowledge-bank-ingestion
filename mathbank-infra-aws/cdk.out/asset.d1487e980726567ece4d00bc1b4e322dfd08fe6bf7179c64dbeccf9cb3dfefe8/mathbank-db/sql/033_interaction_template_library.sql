-- 033_interaction_template_library.sql
-- Interaction/animation/feedback/misconception-evidence template library
-- (requirements/41_INTERACTION_TEMPLATE_LIBRARY.md). Depends on migration 032
-- (knowledge.misconception, pedagogy.micro_course_state, pedagogy.intervention_script,
-- pedagogy.learning_item) already being applied.
BEGIN;

-- 1-2. Template registry + immutable versioned contract --------------------------------------
CREATE TABLE IF NOT EXISTS visual.interaction_template (
    interaction_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    template_key             text NOT NULL UNIQUE,
    name                     text NOT NULL,
    interaction_family       text NOT NULL,
    description              text,
    status                   text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','DEPRECATED')),
    created_at               timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS visual.interaction_template_version (
    interaction_template_version_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_template_id          uuid NOT NULL REFERENCES visual.interaction_template ON DELETE CASCADE,
    version                          integer NOT NULL CHECK (version >= 1),
    input_schema                     jsonb NOT NULL,
    state_schema                     jsonb NOT NULL,
    event_schema                     jsonb NOT NULL,
    output_schema                    jsonb NOT NULL,
    default_layout                   jsonb NOT NULL DEFAULT '{}'::jsonb,
    allowed_controls                 jsonb NOT NULL DEFAULT '[]'::jsonb,
    allowed_icons                    jsonb NOT NULL DEFAULT '[]'::jsonb,
    diagnostic_capabilities          jsonb NOT NULL DEFAULT '[]'::jsonb,
    animation_slots                  jsonb NOT NULL DEFAULT '[]'::jsonb,
    accessibility_policy             jsonb NOT NULL DEFAULT '{}'::jsonb,
    content_hash                     text NOT NULL,
    status                           text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','REVIEWED','PUBLISHED','DEPRECATED')),
    created_by                       text NOT NULL,
    reviewed_by                      text,
    created_at                       timestamptz NOT NULL DEFAULT now(),
    reviewed_at                      timestamptz,
    published_at                     timestamptz,
    UNIQUE (interaction_template_id, version)
);

-- 2. Reusable control catalog -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS visual.control_template (
    control_template_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    control_key          text NOT NULL UNIQUE,
    control_type         text NOT NULL CHECK (control_type IN (
                             'BUTTON','SLIDER','STEPPER','TOGGLE','RADIO','CHECKBOX','DROPDOWN',
                             'NUMBER_INPUT','TEXT_INPUT','DRAG_HANDLE','TIMELINE','PLAYBACK',
                             'MATRIX_CELL','VECTOR_HANDLE','GRAPH_POINT'
                         )),
    config_schema        jsonb NOT NULL,
    accessibility_schema jsonb NOT NULL,
    status               text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','DEPRECATED'))
);

-- 3. Semantic icon registry --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS visual.icon_token (
    icon_token_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    token_key        text NOT NULL UNIQUE,
    icon_class       text NOT NULL CHECK (icon_class IN ('SEMANTIC','CONTEXTUAL','DECORATIVE')),
    semantic_role    text,
    asset_id         uuid REFERENCES visual.asset,
    accessible_label text NOT NULL,
    allowed_contexts jsonb NOT NULL DEFAULT '[]'::jsonb,
    status           text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','DEPRECATED'))
);

-- 6. Animation templates -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS visual.animation_template (
    animation_template_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    animation_key           text NOT NULL UNIQUE,
    name                    text NOT NULL,
    input_schema            jsonb NOT NULL,
    semantic_output_events  jsonb NOT NULL DEFAULT '[]'::jsonb,
    reduced_motion_behavior jsonb NOT NULL,
    status                  text NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE','DEPRECATED'))
);

-- 7. SceneSpec ------------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS visual.scene_spec (
    scene_spec_id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_code      text NOT NULL,
    version             integer NOT NULL CHECK (version >= 1),
    scene_schema_version text NOT NULL,
    scene_json          jsonb NOT NULL,
    content_hash        text NOT NULL,
    status              text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','SUPERSEDED')),
    created_by          text NOT NULL,
    approved_by         text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    approved_at         timestamptz,
    UNIQUE (canonical_code, version)
);

-- 13-14. Feedback templates and policies ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.feedback_template (
    feedback_template_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    feedback_key           text NOT NULL,
    version                integer NOT NULL CHECK (version >= 1),
    feedback_type          text NOT NULL CHECK (feedback_type IN (
                               'CORRECT','PARTIAL','TRY_AGAIN','PROCEDURAL_ERROR','CONCEPTUAL_ERROR',
                               'MISCONCEPTION_PROBE','MISCONCEPTION_CONFIRMED','PREREQUISITE_GAP',
                               'TRANSFER_SUCCESS','OUT_OF_SCOPE'
                           )),
    approved_content       text NOT NULL,
    icon_token_id          uuid REFERENCES visual.icon_token,
    animation_template_id  uuid REFERENCES visual.animation_template,
    allowed_agent_rephrase boolean NOT NULL DEFAULT false,
    review_status          text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    UNIQUE (feedback_key, version)
);

CREATE TABLE IF NOT EXISTS pedagogy.feedback_policy (
    feedback_policy_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_key         text NOT NULL,
    version            integer NOT NULL CHECK (version >= 1),
    policy_json        jsonb NOT NULL,
    review_status      text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    UNIQUE (policy_key, version)
);

-- 4-5. Interaction instances and FK-backed semantic bindings ---------------------------------------
CREATE TABLE IF NOT EXISTS visual.interaction_instance (
    interaction_instance_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    interaction_template_version_id uuid NOT NULL REFERENCES visual.interaction_template_version,
    canonical_code                   text NOT NULL UNIQUE,
    title                             text NOT NULL,
    instance_config                   jsonb NOT NULL,
    initial_state                     jsonb NOT NULL DEFAULT '{}'::jsonb,
    learning_objective                text NOT NULL,
    success_criteria                  jsonb NOT NULL,
    feedback_policy_id                uuid REFERENCES pedagogy.feedback_policy,
    scene_spec_id                     uuid REFERENCES visual.scene_spec,
    content_hash                      text NOT NULL,
    review_status                     text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED')),
    created_by                        text NOT NULL,
    approved_by                       text,
    created_at                        timestamptz NOT NULL DEFAULT now(),
    approved_at                       timestamptz
);

CREATE TABLE IF NOT EXISTS visual.interaction_instance_concept (
    interaction_instance_id uuid NOT NULL REFERENCES visual.interaction_instance ON DELETE CASCADE,
    concept_id              uuid NOT NULL REFERENCES knowledge.concept,
    role                    text NOT NULL CHECK (role IN ('TEACHES','REQUIRES','PRACTICES','ASSESSES','CAN_REVEAL','REMEDIATES')),
    PRIMARY KEY (interaction_instance_id, concept_id, role)
);

CREATE TABLE IF NOT EXISTS visual.interaction_instance_technique (
    interaction_instance_id uuid NOT NULL REFERENCES visual.interaction_instance ON DELETE CASCADE,
    technique_id            uuid NOT NULL REFERENCES knowledge.technique,
    role                    text NOT NULL CHECK (role IN ('TEACHES','REQUIRES','PRACTICES','ASSESSES','CAN_REVEAL','REMEDIATES')),
    PRIMARY KEY (interaction_instance_id, technique_id, role)
);

CREATE TABLE IF NOT EXISTS visual.interaction_instance_skill (
    interaction_instance_id uuid NOT NULL REFERENCES visual.interaction_instance ON DELETE CASCADE,
    skill_id                uuid NOT NULL REFERENCES knowledge.skill,
    role                    text NOT NULL CHECK (role IN ('TEACHES','REQUIRES','PRACTICES','ASSESSES','CAN_REVEAL','REMEDIATES')),
    PRIMARY KEY (interaction_instance_id, skill_id, role)
);

CREATE TABLE IF NOT EXISTS visual.interaction_instance_misconception (
    interaction_instance_id uuid NOT NULL REFERENCES visual.interaction_instance ON DELETE CASCADE,
    misconception_id        uuid NOT NULL REFERENCES knowledge.misconception,
    role                    text NOT NULL CHECK (role IN ('TEACHES','REQUIRES','PRACTICES','ASSESSES','CAN_REVEAL','REMEDIATES')),
    PRIMARY KEY (interaction_instance_id, misconception_id, role)
);

-- 15. Misconception evidence rules -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pedagogy.misconception_evidence_rule (
    evidence_rule_id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    misconception_id                 uuid NOT NULL REFERENCES knowledge.misconception,
    interaction_template_version_id uuid REFERENCES visual.interaction_template_version,
    semantic_action                  text NOT NULL,
    error_signature                  text NOT NULL,
    predicate_json                   jsonb NOT NULL,
    evidence_weight                  numeric(5,4) NOT NULL CHECK (evidence_weight BETWEEN -1 AND 1),
    severity                         smallint CHECK (severity IS NULL OR severity BETWEEN 1 AND 5),
    requires_probe                   boolean NOT NULL DEFAULT false,
    diagnostic_learning_item_id      text REFERENCES pedagogy.learning_item,
    feedback_template_id             uuid REFERENCES pedagogy.feedback_template,
    intervention_id                  uuid REFERENCES pedagogy.intervention_script,
    review_status                    text NOT NULL DEFAULT 'PENDING_REVIEW' CHECK (review_status IN ('PENDING_REVIEW','APPROVED','REJECTED'))
);

-- 16. Learner event/evidence ledgers (append-only) --------------------------------------------------
CREATE TABLE IF NOT EXISTS learner.interaction_event (
    interaction_event_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id               uuid NOT NULL REFERENCES learner.student_profile,
    enrollment_id            uuid REFERENCES learner.micro_course_enrollment,
    course_state_id          uuid REFERENCES pedagogy.micro_course_state,
    interaction_instance_id uuid NOT NULL REFERENCES visual.interaction_instance,
    event_type               text NOT NULL,
    semantic_action          text NOT NULL,
    control_key              text,
    object_id                text,
    before_state             jsonb,
    action_payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
    after_state              jsonb,
    evaluation_outcome       text,
    error_signature          text,
    created_at               timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS learner.misconception_evidence (
    evidence_id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id            uuid NOT NULL REFERENCES learner.student_profile,
    interaction_event_id uuid REFERENCES learner.interaction_event,
    misconception_id      uuid NOT NULL REFERENCES knowledge.misconception,
    evidence_type         text NOT NULL CHECK (evidence_type IN (
                              'OBSERVED_ERROR','DIAGNOSTIC_RESPONSE','REPEATED_PATTERN',
                              'CORRECTIVE_SUCCESS','TRANSFER_FAILURE'
                          )),
    evidence_weight       numeric(5,4) NOT NULL CHECK (evidence_weight BETWEEN -1 AND 1),
    confidence_before     numeric(5,4),
    confidence_after      numeric(5,4),
    created_at            timestamptz NOT NULL DEFAULT clock_timestamp()
);

-- pipeline.projection_request vocabulary extension for this pack --------------------------------
ALTER TABLE pipeline.projection_request DROP CONSTRAINT IF EXISTS projection_request_target_check;
ALTER TABLE pipeline.projection_request ADD CONSTRAINT projection_request_target_check
    CHECK (target IN (
        'GRAPH_TEXTBOOK_STEPS','STEP_EMBEDDINGS','LEARNING_ITEM_EMBEDDINGS','GRAPH_LEARNING_ITEMS',
        'GRAPH_MICRO_COURSES',
        'GRAPH_INTERACTION_TEMPLATES','GRAPH_INTERACTION_INSTANCES','GRAPH_SCENE_SPECS','GRAPH_FEEDBACK_RULES'
    ));
ALTER TABLE pipeline.projection_request DROP CONSTRAINT IF EXISTS projection_request_scope_type_check;
ALTER TABLE pipeline.projection_request ADD CONSTRAINT projection_request_scope_type_check
    CHECK (scope_type IN (
        'BOOK','PACKAGE','PROBLEM','STEP','LEARNING_ITEM',
        'MICRO_COURSE','COURSE_RELEASE','VIDEO_ASSET',
        'INTERACTION_TEMPLATE','INTERACTION_INSTANCE','SCENE_SPEC','MICRO_COURSE_RELEASE'
    ));

-- Immutability: published template versions / approved SceneSpecs / approved instances are
-- never edited in place; new content requires a new version row (mirrors MCR-3 pattern).
CREATE OR REPLACE FUNCTION visual.guard_published_template_version() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('visual.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'PUBLISHED' THEN RAISE EXCEPTION 'published interaction template versions are immutable'; END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'PUBLISHED' AND NEW.status != 'DEPRECATED' THEN
        RAISE EXCEPTION 'published interaction template versions are immutable; create a new version';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS interaction_template_version_guard ON visual.interaction_template_version;
CREATE TRIGGER interaction_template_version_guard BEFORE UPDATE OR DELETE ON visual.interaction_template_version
    FOR EACH ROW EXECUTE FUNCTION visual.guard_published_template_version();

CREATE OR REPLACE FUNCTION visual.guard_approved_scene_spec() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_setting('visual.allow_purge', true) = 'on' THEN RETURN COALESCE(NEW, OLD); END IF;
    IF TG_OP = 'DELETE' THEN
        IF OLD.status = 'APPROVED' THEN RAISE EXCEPTION 'approved scene specs are immutable'; END IF;
        RETURN OLD;
    END IF;
    IF OLD.status = 'APPROVED' AND NEW.status != 'SUPERSEDED' THEN
        RAISE EXCEPTION 'approved scene specs are immutable; create a new version';
    END IF;
    RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS scene_spec_guard ON visual.scene_spec;
CREATE TRIGGER scene_spec_guard BEFORE UPDATE OR DELETE ON visual.scene_spec
    FOR EACH ROW EXECUTE FUNCTION visual.guard_approved_scene_spec();

-- Append-only learner ledgers.
DROP TRIGGER IF EXISTS interaction_event_append_only ON learner.interaction_event;
CREATE TRIGGER interaction_event_append_only BEFORE UPDATE OR DELETE ON learner.interaction_event
    FOR EACH ROW EXECUTE FUNCTION learner.forbid_update();
DROP TRIGGER IF EXISTS misconception_evidence_append_only ON learner.misconception_evidence;
CREATE TRIGGER misconception_evidence_append_only BEFORE UPDATE OR DELETE ON learner.misconception_evidence
    FOR EACH ROW EXECUTE FUNCTION learner.forbid_update();

-- Indexes/comments -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS interaction_instance_template_version_idx ON visual.interaction_instance (interaction_template_version_id);
CREATE INDEX IF NOT EXISTS interaction_event_instance_idx ON learner.interaction_event (interaction_instance_id);
CREATE INDEX IF NOT EXISTS interaction_event_student_idx ON learner.interaction_event (student_id);
CREATE INDEX IF NOT EXISTS misconception_evidence_student_idx ON learner.misconception_evidence (student_id, misconception_id);
CREATE INDEX IF NOT EXISTS evidence_rule_misconception_idx ON pedagogy.misconception_evidence_rule (misconception_id);
CREATE INDEX IF NOT EXISTS evidence_rule_signature_idx ON pedagogy.misconception_evidence_rule (interaction_template_version_id, error_signature);

COMMENT ON TABLE learner.interaction_event IS 'Append-only raw learner interaction log; never projected to shared Neo4j (requirements/41_INTERACTION_TEMPLATE_LIBRARY.md ITL-14).';
COMMENT ON TABLE learner.misconception_evidence IS 'Append-only evidence ledger; one wrong answer normally only adds weighted evidence, never confirms a misconception alone (ITL-9).';
COMMENT ON TABLE pedagogy.misconception_evidence_rule IS 'Maps a template error_signature to misconception evidence weight/probe/feedback/intervention (ITL-9).';

COMMIT;
