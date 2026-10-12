BEGIN;

-- Supports progressively authored taxonomy: the route compiler may propose a new
-- concept/subconcept/skill/technique node (with a human-reviewable name/description)
-- when none of the existing canonical nodes genuinely apply to a step. These nodes
-- attach to one fixed synthetic content_package so the existing NOT NULL FK is
-- satisfied without claiming they came from an imported textbook.
ALTER TABLE pedagogy.taxonomy_node ADD COLUMN IF NOT EXISTS proposed_by text;
ALTER TABLE pedagogy.taxonomy_node ADD COLUMN IF NOT EXISTS proposed_at timestamptz;
COMMENT ON COLUMN pedagogy.taxonomy_node.proposed_by IS
    'NULL for curated/imported nodes (e.g. the Prasolov geometry import). Set to '
    '''route_compiler:<generator_version>'' for nodes proposed by the compiler during '
    'ingestion; these are a model proposal, not independently reviewed curriculum, '
    'and should be curated/merged by a human over time.';

INSERT INTO ingest.content_package (package_name, package_version, manifest_hash, status, report)
VALUES (
    'route-compiler-ai-proposed-taxonomy',
    'v1',
    'synthetic-anchor-not-a-real-import',
    'COMPLETED',
    '{"note":"Synthetic anchor package; taxonomy rows here are compiler-proposed, not an imported textbook."}'::jsonb
)
ON CONFLICT (package_name, package_version, manifest_hash) DO NOTHING;

COMMIT;
