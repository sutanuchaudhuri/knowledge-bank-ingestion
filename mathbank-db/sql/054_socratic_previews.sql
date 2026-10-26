-- Additive isolated synthetic previews for Socratic drafts (ledger step 03).
-- No canonical, activity or learner rows are written; previews are staff-owned and synthetic.
CREATE TABLE IF NOT EXISTS orchestration.socratic_preview (
    preview_id uuid PRIMARY KEY,
    owner_id text NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 200),
    workflow_id uuid NOT NULL,
    workflow_revision integer NOT NULL,
    content_hash text NOT NULL CHECK (content_hash ~ '^[a-f0-9]{64}$'),
    -- Private scoring snapshot of every bound activity, pinned at start. Never returned by the API.
    activity_snapshot jsonb NOT NULL CHECK (jsonb_typeof(activity_snapshot) = 'object'),
    state_version integer NOT NULL CHECK (state_version > 0),
    current_node_key text NOT NULL CHECK (length(current_node_key) BETWEEN 1 AND 100),
    status text NOT NULL CHECK (status IN ('ACTIVE', 'COMPLETE')),
    transitions_used integer NOT NULL DEFAULT 0 CHECK (transitions_used >= 0),
    hint_level integer NOT NULL DEFAULT 0 CHECK (hint_level BETWEEN 0 AND 5),
    revealed boolean NOT NULL DEFAULT false,
    feedback text CHECK (feedback IS NULL OR length(feedback) <= 12000),
    synthetic boolean NOT NULL DEFAULT true CHECK (synthetic),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (workflow_id, workflow_revision, content_hash)
        REFERENCES orchestration.socratic_revision(workflow_id, revision, content_hash) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS socratic_preview_owner_idx
    ON orchestration.socratic_preview(owner_id, workflow_id, created_at DESC);

CREATE TABLE IF NOT EXISTS orchestration.socratic_preview_event (
    preview_id uuid NOT NULL REFERENCES orchestration.socratic_preview ON DELETE RESTRICT,
    state_version integer NOT NULL CHECK (state_version > 0),
    action text NOT NULL CHECK (action IN ('START', 'RESPOND', 'ASSIST', 'REVEAL', 'TRANSITION')),
    idempotency_key text CHECK (idempotency_key IS NULL OR length(idempotency_key) BETWEEN 1 AND 128),
    request_hash text NOT NULL CHECK (request_hash ~ '^[a-f0-9]{64}$'),
    node_key text NOT NULL,
    from_key text,
    to_key text,
    outcome text CHECK (outcome IS NULL OR outcome IN ('ALWAYS', 'SUCCESS', 'RETRY', 'UNCERTAIN')),
    rule_id text,
    decision_source text NOT NULL,
    reason text NOT NULL,
    assisted boolean NOT NULL DEFAULT false,
    -- Synthetic response and private scorer evidence; not exposed in the student DTO.
    response jsonb,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(evidence) = 'object'),
    -- Exact DTO returned for this action, so an identical retry replays the same result.
    result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (preview_id, state_version),
    UNIQUE (preview_id, idempotency_key)
);

DROP TRIGGER IF EXISTS socratic_preview_event_immutable ON orchestration.socratic_preview_event;
CREATE TRIGGER socratic_preview_event_immutable BEFORE UPDATE OR DELETE
    ON orchestration.socratic_preview_event FOR EACH ROW
    EXECUTE FUNCTION orchestration.socratic_immutable();
