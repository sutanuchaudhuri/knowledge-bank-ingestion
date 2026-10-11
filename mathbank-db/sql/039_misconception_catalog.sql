-- 039_misconception_catalog.sql
-- Populate knowledge.misconception as a real, deduplicated catalog (requirements/51 ENR-1
-- Phase A) and link it to the taxonomy, closing the "misconception id to id only" gap
-- (requirements/50 BUG-2) at the Postgres source-of-truth level, not just via a derived
-- Neo4j-side join.
--
-- knowledge.misconception already existed with 0 rows (designed, never populated). The
-- real content has always lived in pedagogy.route_asset.content (one row generated fresh
-- per route checkpoint by route_enrichment.py, confirmed live: 80,242 MISCONCEPTION rows,
-- only 69,954-70,018 distinct `description` values -- 12.7 percent are byte-for-byte duplicates).
--
-- This migration is schema-only (additive, no backfill performed here -- the backfill is a
-- separate Python script, migrate_misconception_catalog.py, since it needs application-level
-- dedup logic, not just SQL). Nothing here changes existing behavior until that script runs.
BEGIN;

-- Cleanup: an earlier version of this migration added a `canonical_misconception_id`
-- column directly on pedagogy.route_asset, discovered live to be unusable (see the side
-- table below) before any data was ever written to it. Drop it if present.
ALTER TABLE pedagogy.route_asset DROP COLUMN IF EXISTS canonical_misconception_id;

-- Many-to-many: a canonical misconception can legitimately relate to multiple taxonomy
-- targets (confirmed live in requirements/51 §4 ENR-1: 73 percent of exact-duplicate-description
-- groups span more than one distinct taxonomy_node_id -- the same misconception text
-- genuinely recurs across different skills/concepts, not a single-target relationship).
-- References pedagogy.taxonomy_node directly (not knowledge.concept/technique/skill)
-- because that is where the overwhelming majority of real taxonomy_node_ids already live
-- (confirmed: curated knowledge.* linkage is <=10 percent today, requirements/51 §3) -- this link
-- does not require resolving that separate convergence gap (ENR-5) first.
CREATE TABLE IF NOT EXISTS knowledge.misconception_taxonomy_link (
    misconception_id uuid NOT NULL REFERENCES knowledge.misconception ON DELETE CASCADE,
    taxonomy_node_id  text NOT NULL REFERENCES pedagogy.taxonomy_node,
    derived_via       text NOT NULL DEFAULT 'route_asset.taxonomy_node_ids',
    created_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (misconception_id, taxonomy_node_id)
);

CREATE INDEX IF NOT EXISTS misconception_taxonomy_link_node_idx
    ON knowledge.misconception_taxonomy_link (taxonomy_node_id);

-- Link from each per-checkpoint generated row back to its canonical catalog entry, as a
-- SEPARATE side table rather than a new column on pedagogy.route_asset itself --
-- pedagogy.guard_route_snapshot() (confirmed live) blocks ANY update/insert/delete on a
-- route_asset row once its route_release_id's release leaves DRAFT status, and the
-- overwhelming majority of existing route_asset rows already belong to a reviewed/
-- published release. A side table keyed on asset_id is purely additive and never touches
-- the guarded table, so it works for both already-published and future draft content.
CREATE TABLE IF NOT EXISTS knowledge.route_asset_misconception_link (
    asset_id          uuid NOT NULL REFERENCES pedagogy.route_asset(asset_id) ON DELETE CASCADE PRIMARY KEY,
    misconception_id  uuid NOT NULL REFERENCES knowledge.misconception,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS route_asset_misconception_link_misconception_idx
    ON knowledge.route_asset_misconception_link (misconception_id);

COMMIT;
