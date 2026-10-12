-- Explicit deployment only; never executed by application startup.
CREATE SCHEMA IF NOT EXISTS geometry_scene;

CREATE TABLE IF NOT EXISTS geometry_scene.scenes (
    scene_id text PRIMARY KEY,
    owner text NOT NULL,
    current_version integer NOT NULL CHECK (current_version >= 0),
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS geometry_scene_owner_idx ON geometry_scene.scenes(owner);

CREATE TABLE IF NOT EXISTS geometry_scene.versions (
    scene_id text NOT NULL REFERENCES geometry_scene.scenes(scene_id),
    version integer NOT NULL CHECK (version >= 0),
    assets jsonb NOT NULL,
    lineage jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scene_id, version)
);
CREATE TABLE IF NOT EXISTS geometry_scene.receipts (
    owner text NOT NULL,
    key text NOT NULL,
    request_hash text NOT NULL,
    scene_id text NOT NULL,
    version integer NOT NULL,
    PRIMARY KEY (owner, key),
    FOREIGN KEY (scene_id, version) REFERENCES geometry_scene.versions(scene_id, version)
);
CREATE TABLE IF NOT EXISTS geometry_scene.runs (
    owner text NOT NULL,
    run_id text NOT NULL,
    evidence_asset jsonb NOT NULL,
    evidence_hash text NOT NULL,
    review jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner, run_id)
);

CREATE OR REPLACE FUNCTION geometry_scene.reject_accepted_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'accepted geometry versions and receipts are immutable';
END;
$$;
DROP TRIGGER IF EXISTS immutable_geometry_versions ON geometry_scene.versions;
CREATE TRIGGER immutable_geometry_versions BEFORE UPDATE OR DELETE ON geometry_scene.versions
FOR EACH ROW EXECUTE FUNCTION geometry_scene.reject_accepted_mutation();
CREATE OR REPLACE FUNCTION geometry_scene.protect_run_evidence() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR NEW.owner IS DISTINCT FROM OLD.owner
        OR NEW.run_id IS DISTINCT FROM OLD.run_id
        OR NEW.evidence_asset IS DISTINCT FROM OLD.evidence_asset
        OR NEW.evidence_hash IS DISTINCT FROM OLD.evidence_hash
        OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'geometry run evidence is immutable; only review may change';
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS immutable_geometry_run_evidence ON geometry_scene.runs;
CREATE TRIGGER immutable_geometry_run_evidence BEFORE UPDATE OR DELETE ON geometry_scene.runs
FOR EACH ROW EXECUTE FUNCTION geometry_scene.protect_run_evidence();
DROP TRIGGER IF EXISTS immutable_geometry_receipts ON geometry_scene.receipts;
CREATE TRIGGER immutable_geometry_receipts BEFORE UPDATE OR DELETE ON geometry_scene.receipts
FOR EACH ROW EXECUTE FUNCTION geometry_scene.reject_accepted_mutation();
