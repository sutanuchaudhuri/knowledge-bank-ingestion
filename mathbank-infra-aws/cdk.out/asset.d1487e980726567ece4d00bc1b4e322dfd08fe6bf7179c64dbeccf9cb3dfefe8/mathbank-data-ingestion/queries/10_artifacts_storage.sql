\ir _session.sql

-- Q181 Public artifact publishing coverage.
-- Purpose/output: public request/bundle counts by subject/state; learner-owned bundles excluded.
-- Inputs: none. Risk: READ ONLY; public artifact metadata aggregate.
SELECT b.subject,b.status,b.review_state,count(*) AS bundles,count(DISTINCT b.artifact_request_id) AS requests
FROM artifact_runtime.artifact_bundle b JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
WHERE r.owner_student_id IS NULL GROUP BY b.subject,b.status,b.review_state ORDER BY b.subject,b.status,b.review_state;
-- END Q181

-- Q182 Published public bundles without assets.
-- Purpose/output: bundle IDs that cannot render any stored asset.
-- Inputs: row_limit. Risk: READ ONLY; public-only anti-join; object keys excluded.
SELECT b.artifact_bundle_id,b.subject FROM artifact_runtime.artifact_bundle b
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
WHERE r.owner_student_id IS NULL AND b.status='PUBLISHED'
AND NOT EXISTS(SELECT 1 FROM artifact_runtime.artifact_asset a WHERE a.artifact_bundle_id=b.artifact_bundle_id)
ORDER BY b.artifact_bundle_id LIMIT :'row_limit'::int;
-- END Q182

-- Q183 Public artifact validation gaps.
-- Purpose/output: published public bundle IDs with no successful recorded validation.
-- Inputs: row_limit. Risk: READ ONLY; public metadata anti-join.
SELECT b.artifact_bundle_id,b.review_state FROM artifact_runtime.artifact_bundle b
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
WHERE r.owner_student_id IS NULL AND b.status='PUBLISHED'
AND NOT EXISTS(SELECT 1 FROM artifact_runtime.validation_result v WHERE v.artifact_bundle_id=b.artifact_bundle_id AND v.valid)
ORDER BY b.artifact_bundle_id LIMIT :'row_limit'::int;
-- END Q183

-- Q184 Public asset storage budget.
-- Purpose/output: count, total bytes and maximum file size by asset type/MIME.
-- Inputs: none. Risk: READ ONLY; public metadata aggregate; no storage calls.
SELECT a.asset_type,a.mime_type,count(*) AS assets,sum(a.size_bytes::bigint) AS bytes,max(a.size_bytes) AS largest_bytes
FROM artifact_runtime.artifact_asset a JOIN artifact_runtime.artifact_bundle b USING(artifact_bundle_id)
JOIN artifact_runtime.artifact_request r USING(artifact_request_id) WHERE r.owner_student_id IS NULL
GROUP BY a.asset_type,a.mime_type ORDER BY bytes DESC,a.asset_type,a.mime_type;
-- END Q184

-- Q185 Public assets without searchable metadata.
-- Purpose/output: public asset IDs missing artifact_metadata.
-- Inputs: row_limit. Risk: READ ONLY; public-only anti-join.
SELECT a.artifact_asset_id,a.asset_type FROM artifact_runtime.artifact_asset a
JOIN artifact_runtime.artifact_bundle b USING(artifact_bundle_id)
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
WHERE r.owner_student_id IS NULL AND NOT EXISTS(SELECT 1 FROM artifact_runtime.artifact_metadata m
WHERE m.artifact_asset_id=a.artifact_asset_id) ORDER BY a.artifact_asset_id LIMIT :'row_limit'::int;
-- END Q185

-- Q186 Public bundle lineage omissions or wrong request linkage.
-- Purpose/output: bundle IDs without lineage or linked to a different request/parent.
-- Inputs: row_limit. Risk: READ ONLY; public-only integrity join.
SELECT b.artifact_bundle_id FROM artifact_runtime.artifact_bundle b
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
LEFT JOIN artifact_runtime.artifact_lineage l USING(artifact_bundle_id)
WHERE r.owner_student_id IS NULL AND (l.artifact_bundle_id IS NULL OR l.artifact_request_id<>b.artifact_request_id
OR l.parent_bundle_id IS DISTINCT FROM b.parent_bundle_id)
ORDER BY b.artifact_bundle_id LIMIT :'row_limit'::int;
-- END Q186

-- Q187 Public overlay assets belonging to a different bundle.
-- Purpose/output: overlay IDs whose base asset is not owned by their bundle.
-- Inputs: row_limit. Risk: READ ONLY; public-only integrity join.
SELECT o.overlay_state_id,o.artifact_bundle_id FROM artifact_runtime.overlay_state o
JOIN artifact_runtime.artifact_asset a ON a.artifact_asset_id=o.base_asset_id
JOIN artifact_runtime.artifact_bundle b ON b.artifact_bundle_id=o.artifact_bundle_id
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
WHERE r.owner_student_id IS NULL AND o.artifact_bundle_id<>a.artifact_bundle_id
ORDER BY o.overlay_state_id LIMIT :'row_limit'::int;
-- END Q187

-- Q188 Public frame manifests referencing absent/wrong-bundle overlays.
-- Purpose/output: sequence IDs and invalid ordinal positions; referenced overlay content excluded.
-- Inputs: row_limit. Risk: READ ONLY; public-only UUID-array expansion.
SELECT f.frame_sequence_id,u.ordinal FROM artifact_runtime.frame_sequence f
JOIN artifact_runtime.artifact_bundle b USING(artifact_bundle_id)
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
CROSS JOIN LATERAL unnest(f.ordered_overlay_state_ids) WITH ORDINALITY u(overlay_id,ordinal)
LEFT JOIN artifact_runtime.overlay_state o ON o.overlay_state_id=u.overlay_id
WHERE r.owner_student_id IS NULL AND (o.overlay_state_id IS NULL OR o.artifact_bundle_id<>f.artifact_bundle_id)
ORDER BY f.frame_sequence_id,u.ordinal LIMIT :'row_limit'::int;
-- END Q188

-- Q189 Public annotation step links missing canonical steps.
-- Purpose/output: annotation IDs with dangling text linked_step_id.
-- Inputs: row_limit. Risk: READ ONLY; public-only anti-join; explanation text excluded.
SELECT a.artifact_annotation_id,a.linked_step_id FROM artifact_runtime.artifact_annotation a
JOIN artifact_runtime.artifact_bundle b USING(artifact_bundle_id)
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
WHERE r.owner_student_id IS NULL AND a.linked_step_id IS NOT NULL
AND NOT EXISTS(SELECT 1 FROM pedagogy.solution_step s WHERE s.solution_step_id=a.linked_step_id)
ORDER BY a.artifact_annotation_id LIMIT :'row_limit'::int;
-- END Q189

-- Q190 Public artifact embedding freshness.
-- Purpose/output: bundle IDs missing vectors or whose indexed search-text digest is stale.
-- Inputs: row_limit. Risk: READ ONLY; public-only hash scan; no generation calls or text output.
SELECT b.artifact_bundle_id,e.model,e.indexed_at FROM artifact_runtime.artifact_bundle b
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
LEFT JOIN artifact_runtime.artifact_embedding e USING(artifact_bundle_id)
WHERE r.owner_student_id IS NULL AND b.status='PUBLISHED'
AND (e.artifact_bundle_id IS NULL OR e.search_text_sha256<>encode(sha256(convert_to(b.search_text,'UTF8')),'hex'))
ORDER BY b.artifact_bundle_id LIMIT :'row_limit'::int;
-- END Q190

-- Q191 Public artifact tags with no taxonomy match.
-- Purpose/output: public tags absent from taxonomy IDs; theorem tags intentionally excluded.
-- Inputs: row_limit. Risk: READ ONLY; public-only anti-join.
SELECT t.tag_type,t.tag,count(*) AS bundles FROM artifact_runtime.artifact_search_tag t
JOIN artifact_runtime.artifact_bundle b USING(artifact_bundle_id)
JOIN artifact_runtime.artifact_request r USING(artifact_request_id)
WHERE r.owner_student_id IS NULL AND t.tag_type IN('concept','skill')
AND NOT EXISTS(SELECT 1 FROM pedagogy.taxonomy_node n WHERE n.taxonomy_node_id=t.tag)
GROUP BY t.tag_type,t.tag ORDER BY bundles DESC,t.tag_type,t.tag LIMIT :'row_limit'::int;
-- END Q191

-- Q192 Schema/table disk footprint.
-- Purpose/output: table heap/index/total bytes in application schemas; learner content never inspected.
-- Inputs: row_limit. Risk: READ ONLY; catalog sizes may take locks briefly.
SELECT n.nspname AS schema_name,c.relname AS table_name,pg_table_size(c.oid) AS table_bytes,
 pg_indexes_size(c.oid) AS index_bytes,pg_total_relation_size(c.oid) AS total_bytes
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind IN('r','m') AND n.nspname IN('core','knowledge','pedagogy','ingest','search','pipeline',
'learner','tutor','analytics','artifact_runtime','attempt_media','authoring','live','activity','visual')
ORDER BY total_bytes DESC,n.nspname,c.relname LIMIT :'row_limit'::int;
-- END Q192

-- Q193 Table vacuum/analyze and dead-tuple health.
-- Purpose/output: statistics estimates and maintenance timestamps, not exact private-row counts.
-- Inputs: row_limit. Risk: READ ONLY; pg_stat metadata.
SELECT schemaname,relname,n_live_tup,n_dead_tup,last_autovacuum,last_autoanalyze,
 round(100.0*n_dead_tup/nullif(n_live_tup+n_dead_tup,0),2) AS estimated_dead_pct
FROM pg_stat_user_tables ORDER BY n_dead_tup DESC,schemaname,relname LIMIT :'row_limit'::int;
-- END Q193

-- Q194 Invalid or unready PostgreSQL indexes.
-- Purpose/output: application indexes not ready for queries/writes; no reindex executed.
-- Inputs: none. Risk: READ ONLY; system catalog scan.
SELECT n.nspname,c.relname AS index_name,x.indisvalid,x.indisready FROM pg_index x
JOIN pg_class c ON c.oid=x.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE NOT x.indisvalid OR NOT x.indisready ORDER BY n.nspname,c.relname;
-- END Q194

-- Q195 Required extension availability.
-- Purpose/output: installed vector/trigram extensions and their version; absent extensions yield no corresponding row.
-- Inputs: none. Risk: READ ONLY; catalog lookup; no extension installation.
SELECT extname,extversion FROM pg_extension WHERE extname IN('vector','pg_trgm') ORDER BY extname;
-- END Q195

ROLLBACK;
