-- 036_taxonomy_admin_crud.sql
-- Taxonomy admin CRUD gaps (requirements/45_REST_API_DOCUMENTATION_AND_ADMIN_CRUD_GAPS.md §5):
--   1. knowledge.entity_alias — one shared alias/synonym table for concept/technique/skill/
--      misconception (§5.3), instead of four per-entity alias tables.
--   2. knowledge.concept / knowledge.technique — pin the previously-unenforced 'ACTIVE'/'INACTIVE'
--      status convention with a real CHECK constraint, and add deactivated_at/deactivated_by
--      (§5.4), mirroring migration 035's pedagogy.micro_course pattern.
--   3. knowledge.skill / knowledge.misconception — add a new is_active lifecycle axis; today they
--      only have a pre-publication review_status, with no post-approval activate/deactivate.
-- All changes are additive; no existing column/constraint is removed or renamed.
BEGIN;

-- 1. Shared alias/synonym table -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge.entity_alias (
    alias_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_kind text NOT NULL CHECK (entity_kind IN ('CONCEPT', 'TECHNIQUE', 'SKILL', 'MISCONCEPTION')),
    entity_id   uuid NOT NULL,
    alias       text NOT NULL CHECK (btrim(alias) <> ''),
    created_at  timestamptz NOT NULL DEFAULT now(),
    created_by  text,
    UNIQUE (entity_kind, entity_id, alias)
);
CREATE INDEX IF NOT EXISTS entity_alias_lookup_idx ON knowledge.entity_alias (entity_kind, alias);
COMMENT ON TABLE knowledge.entity_alias IS
    'Shared alias/synonym table for concept/technique/skill/misconception (requirements/45 APID-9). '
    'entity_id is a polymorphic FK (resolved by entity_kind in the application layer, not a DB '
    'constraint) since no single target table spans all four kinds.';

-- 2. Concept/technique: pin the status convention + add deactivation fields ---------------------
ALTER TABLE knowledge.concept ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE knowledge.concept ADD COLUMN IF NOT EXISTS deactivated_by text;
UPDATE knowledge.concept SET status = 'ACTIVE' WHERE status NOT IN ('ACTIVE', 'INACTIVE');
ALTER TABLE knowledge.concept DROP CONSTRAINT IF EXISTS concept_status_check;
ALTER TABLE knowledge.concept ADD CONSTRAINT concept_status_check CHECK (status IN ('ACTIVE', 'INACTIVE'));

ALTER TABLE knowledge.technique ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE knowledge.technique ADD COLUMN IF NOT EXISTS deactivated_by text;
UPDATE knowledge.technique SET status = 'ACTIVE' WHERE status NOT IN ('ACTIVE', 'INACTIVE');
ALTER TABLE knowledge.technique DROP CONSTRAINT IF EXISTS technique_status_check;
ALTER TABLE knowledge.technique ADD CONSTRAINT technique_status_check CHECK (status IN ('ACTIVE', 'INACTIVE'));

-- 3. Skill/misconception: new post-approval activate/deactivate lifecycle axis ------------------
ALTER TABLE knowledge.skill ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE knowledge.skill ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE knowledge.skill ADD COLUMN IF NOT EXISTS deactivated_by text;

ALTER TABLE knowledge.misconception ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
ALTER TABLE knowledge.misconception ADD COLUMN IF NOT EXISTS deactivated_at timestamptz;
ALTER TABLE knowledge.misconception ADD COLUMN IF NOT EXISTS deactivated_by text;

COMMIT;
