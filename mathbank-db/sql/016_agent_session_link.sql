-- 016 — Agent session ↔ student linkage (requirements/22_AGENT_SESSION_TRANSCRIPTS.md).
--
-- The ADK agent persists conversations in the framework-owned schema ``agent_sessions``
-- (tables sessions/events created by google-adk's DatabaseSessionService, not by our migrations).
-- ADK only knows an opaque ``user_id`` string. This table is the project-owned, durable mapping
-- student_id → (app_name, agent session id) so a whole conversation can be reconstructed for the
-- student ("my conversations") or for an admin, and so learner deletion cascades to the link.
--
-- No FK into agent_sessions: that schema is framework-managed and may be absent/recreated; the
-- link is a logical reference validated by the REST layer when it is registered.
--
-- Idempotent: safe to re-run.

CREATE TABLE IF NOT EXISTS learner.agent_session_link (
    agent_session_link_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_app_name        text NOT NULL,
    agent_user_id         text NOT NULL,
    agent_session_id      text NOT NULL,
    student_id            uuid NOT NULL REFERENCES learner.student_profile ON DELETE CASCADE,
    surface               text NOT NULL DEFAULT 'HOME_CHAT'
                          CHECK (surface IN ('HOME_CHAT', 'SOLVE_WORKSPACE', 'OTHER')),
    context               jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at            timestamptz NOT NULL DEFAULT now(),
    last_seen_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT agent_session_link_session_uq UNIQUE (agent_app_name, agent_session_id)
);

CREATE INDEX IF NOT EXISTS agent_session_link_student_idx
    ON learner.agent_session_link (student_id, created_at DESC);
