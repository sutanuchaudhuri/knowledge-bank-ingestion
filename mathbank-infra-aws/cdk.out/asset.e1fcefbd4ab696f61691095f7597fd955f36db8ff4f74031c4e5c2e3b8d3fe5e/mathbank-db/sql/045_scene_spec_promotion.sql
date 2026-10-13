-- 045_scene_spec_promotion.sql
-- Links the ephemeral Manim Video Studio job queue (requirements/60, migration 044) to
-- the canonical interaction-template-library catalog (requirements/41 ITL-1/ITL-4).
-- Promotion itself is a deliberate, explicit admin action (mathbank-rest's new
-- scene_spec_promotion service) — this migration only adds the columns that action
-- needs; it does not promote anything itself.
BEGIN;

-- The canonical scene_spec row now optionally carries a rendered-video asset reference
-- and a lineage pointer back to the ephemeral job it was promoted from (plain text, no
-- FK, since studio.video_render_job rows are expected to expire and be deleted —
-- requirements/60 §4 — while an APPROVED scene_spec is immutable/permanent).
ALTER TABLE visual.scene_spec
    ADD COLUMN IF NOT EXISTS rendered_video_asset_id uuid REFERENCES visual.asset,
    ADD COLUMN IF NOT EXISTS source_studio_job_id text;

CREATE INDEX IF NOT EXISTS scene_spec_source_studio_job_idx
    ON visual.scene_spec (source_studio_job_id)
    WHERE source_studio_job_id IS NOT NULL;

-- The ephemeral render job records which canonical scene_spec it became, purely so the
-- Manim Video Studio's own candidate list can hide already-promoted jobs. A real FK is
-- safe here (same physical Postgres instance) even though the two tables belong to
-- different services' schemas.
ALTER TABLE studio.video_render_job
    ADD COLUMN IF NOT EXISTS promoted_scene_spec_id uuid REFERENCES visual.scene_spec(scene_spec_id);

COMMIT;
