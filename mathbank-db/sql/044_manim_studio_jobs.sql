-- 044_manim_studio_jobs.sql
-- Manim Video Studio research/render job queues (requirements/60). Explicitly NOT part of
-- the canonical `visual.scene_spec`/`interaction_instance` catalog (requirements/41
-- ITL-1/ITL-4) — these are disposable, single-session drafts with a 1-day TTL, not
-- admin-reviewed published content. Additive only; no existing table is touched.
BEGIN;

CREATE SCHEMA IF NOT EXISTS studio;

CREATE TABLE studio.scene_research_job (
    scene_research_job_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status                text NOT NULL DEFAULT 'PENDING'
                          CHECK (status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')),
    topic                 text NOT NULL,
    context_json          jsonb NOT NULL DEFAULT '{}'::jsonb,
    result_scene_spec     jsonb,
    result_explanation    text,
    error_message         text,
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    expires_at            timestamptz NOT NULL DEFAULT (now() + interval '1 day')
);

CREATE TABLE studio.video_render_job (
    video_render_job_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status                 text NOT NULL DEFAULT 'PENDING'
                           CHECK (status IN ('PENDING', 'RUNNING', 'DONE', 'FAILED')),
    source_research_job_id uuid
                           REFERENCES studio.scene_research_job(scene_research_job_id)
                           ON DELETE SET NULL,
    scene_spec_json        jsonb NOT NULL,
    video_object_key       text,
    video_duration_ms      integer,
    error_message          text,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now(),
    expires_at             timestamptz NOT NULL DEFAULT (now() + interval '1 day')
);

CREATE INDEX idx_scene_research_job_expires ON studio.scene_research_job (expires_at);
CREATE INDEX idx_video_render_job_expires ON studio.video_render_job (expires_at);
CREATE INDEX idx_video_render_job_source ON studio.video_render_job (source_research_job_id);

COMMENT ON TABLE studio.scene_research_job IS
    'requirements/60 — topic+context to SceneSpec JSON generation jobs. Ephemeral: '
    'expires_at is 1 day from creation, enforced by scripts/cleanup_expired_jobs.py, not '
    'a database-level TTL extension.';

COMMENT ON TABLE studio.video_render_job IS
    'requirements/60 — SceneSpec JSON to real Manim-rendered .mp4 jobs. video_object_key '
    'points into the shared object store; scripts/cleanup_expired_jobs.py deletes the '
    'object as well as the row once expired.';

COMMIT;
