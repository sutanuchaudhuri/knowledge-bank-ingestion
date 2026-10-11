\ir _session.sql

-- Q121 Package registry state inventory.
-- Purpose/output: package state counts, latest update and total imported packages.
-- Inputs: none. Risk: READ ONLY; package aggregate; no source paths.
SELECT status,count(*) AS packages,max(updated_at) AS latest_update,
 count(*) FILTER(WHERE imported_at IS NOT NULL) AS previously_imported
FROM ingest.content_package GROUP BY status ORDER BY status;
-- END Q121

-- Q122 Stalled active package operations.
-- Purpose/output: packages in nonterminal processing states without an update for one hour.
-- Inputs: row_limit. Risk: READ ONLY; timestamp scan.
SELECT content_package_id,package_name,package_version,status,now()-updated_at AS idle_for
FROM ingest.content_package WHERE status IN('VALIDATING','IMPORTING','RECONCILING','EMBEDDING','GRAPH_PROJECTING')
AND updated_at<now()-interval '1 hour' ORDER BY updated_at,content_package_id LIMIT :'row_limit'::int;
-- END Q122

-- Q123 Same package/version with multiple manifests.
-- Purpose/output: repackaged content identities requiring versioning review.
-- Inputs: none. Risk: READ ONLY; registry grouping.
SELECT package_name,package_version,count(*) AS manifests,count(DISTINCT status) AS states
FROM ingest.content_package GROUP BY package_name,package_version HAVING count(*)>1
ORDER BY package_name,package_version;
-- END Q123

-- Q124 Package file size and row-count footprint.
-- Purpose/output: bytes/rows/files by package and file role, useful for import cost estimates.
-- Inputs: row_limit. Risk: READ ONLY; file metadata aggregation.
SELECT content_package_id,file_role,count(*) AS files,sum(byte_size) AS bytes,sum(row_count) AS declared_rows
FROM ingest.package_file GROUP BY content_package_id,file_role
ORDER BY bytes DESC,content_package_id,file_role LIMIT :'row_limit'::int;
-- END Q124

-- Q125 Package file invalid shape/hash metadata.
-- Purpose/output: relative paths with negative sizes/counts or malformed SHA256.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan; no source_root or file bytes.
SELECT content_package_id,relative_path,byte_size,row_count FROM ingest.package_file
WHERE byte_size<0 OR row_count<0 OR sha256 !~ '^[0-9a-fA-F]{64}$'
ORDER BY content_package_id,relative_path LIMIT :'row_limit'::int;
-- END Q125

-- Q126 Staging validation progress.
-- Purpose/output: staging counts by package, entity type and validation status.
-- Inputs: row_limit. Risk: READ ONLY; staging aggregate; raw source_row_json excluded.
SELECT content_package_id,entity_type,validation_status,count(*) AS rows FROM ingest.staging_row
GROUP BY content_package_id,entity_type,validation_status
ORDER BY content_package_id,entity_type,validation_status LIMIT :'row_limit'::int;
-- END Q126

-- Q127 Imported staging rows without canonical target keys.
-- Purpose/output: staging identities needing reconciliation bookkeeping repair.
-- Inputs: row_limit. Risk: READ ONLY; staging metadata scan.
SELECT staging_row_id,content_package_id,entity_type,source_file,source_row_number FROM ingest.staging_row
WHERE validation_status='IMPORTED' AND nullif(btrim(target_key),'') IS NULL
ORDER BY staging_row_id LIMIT :'row_limit'::int;
-- END Q127

-- Q128 Rejected staging rows without validation errors.
-- Purpose/output: rejected rows with empty error arrays or nonarray error structures.
-- Inputs: row_limit. Risk: READ ONLY; guarded JSON shape check; error payloads excluded.
SELECT staging_row_id,entity_type FROM ingest.staging_row WHERE validation_status='REJECTED'
AND CASE WHEN jsonb_typeof(validation_errors)='array' THEN jsonb_array_length(validation_errors)=0 ELSE true END
ORDER BY staging_row_id LIMIT :'row_limit'::int;
-- END Q128

-- Q129 Repeated staging entity identities within a package.
-- Purpose/output: nonempty external IDs repeated across source rows/files.
-- Inputs: row_limit. Risk: READ ONLY; staging aggregate.
SELECT content_package_id,entity_type,external_id,count(*) AS copies FROM ingest.staging_row
WHERE nullif(btrim(external_id),'') IS NOT NULL GROUP BY content_package_id,entity_type,external_id
HAVING count(*)>1 ORDER BY copies DESC,content_package_id,entity_type,external_id LIMIT :'row_limit'::int;
-- END Q129

-- Q130 Open conflict severity/type backlog.
-- Purpose/output: conflict counts by package, severity and conflict type; detail/resolution text excluded.
-- Inputs: row_limit. Risk: READ ONLY; conflict aggregate.
SELECT content_package_id,severity,conflict_type,count(*) AS open_conflicts FROM ingest.import_conflict
WHERE resolution_status='OPEN' GROUP BY content_package_id,severity,conflict_type
ORDER BY open_conflicts DESC,content_package_id,severity,conflict_type LIMIT :'row_limit'::int;
-- END Q130

-- Q131 Resolved conflicts with incomplete decision bookkeeping.
-- Purpose/output: conflict IDs lacking decision or decided_at, including historical automatic resolutions.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan.
SELECT conflict_id,resolution_status,decision,decided_at FROM ingest.import_conflict
WHERE resolution_status IN('RESOLVED','AUTO_RESOLVED') AND (decision IS NULL OR decided_at IS NULL)
ORDER BY conflict_id LIMIT :'row_limit'::int;
-- END Q131

-- Q132 Reconciliation discrepancies.
-- Purpose/output: entity/scopes not reconciled or whose valid/imported/database totals disagree.
-- Inputs: row_limit. Risk: READ ONLY; reconciliation scan.
SELECT content_package_id,scope,entity_type,source_count,valid_count,imported_count,present_in_db,reconciled
FROM ingest.reconciliation WHERE NOT reconciled OR valid_count<>imported_count OR imported_count<>present_in_db
ORDER BY content_package_id,scope,entity_type LIMIT :'row_limit'::int;
-- END Q132

-- Q133 Reconciliation disposition arithmetic.
-- Purpose/output: imported totals disagreeing with created+updated+unchanged accounting.
-- Inputs: row_limit. Risk: READ ONLY; arithmetic scan.
SELECT content_package_id,scope,entity_type,imported_count,
 created_count+updated_count+unchanged_count AS accounted_imports FROM ingest.reconciliation
WHERE imported_count<>created_count+updated_count+unchanged_count
ORDER BY content_package_id,scope,entity_type LIMIT :'row_limit'::int;
-- END Q133

-- Q134 Completed packages with unresolved error conflicts.
-- Purpose/output: package IDs marked complete despite remaining severity ERROR conflicts.
-- Inputs: row_limit. Risk: READ ONLY; consistency aggregate.
SELECT p.content_package_id,p.status,count(*) AS open_errors
FROM ingest.content_package p JOIN ingest.import_conflict c USING(content_package_id)
WHERE p.status IN('POSTGRES_COMPLETE','COMPLETED') AND c.severity='ERROR' AND c.resolution_status='OPEN'
GROUP BY p.content_package_id ORDER BY open_errors DESC,p.content_package_id LIMIT :'row_limit'::int;
-- END Q134

-- Q135 Package status transition counts.
-- Purpose/output: observed from/to transitions; no operator detail text.
-- Inputs: days. Risk: READ ONLY; timestamp-bounded event aggregate.
SELECT from_status,to_status,count(*) AS transitions FROM ingest.package_status_event
WHERE created_at>=now()-make_interval(days => :'days'::int)
GROUP BY from_status,to_status ORDER BY transitions DESC,from_status,to_status;
-- END Q135

-- Q136 Package state differing from latest status event.
-- Purpose/output: registry rows whose most recent event to_status disagrees with current status.
-- Inputs: row_limit. Risk: READ ONLY; event ordering; ties broken by event_id.
SELECT p.content_package_id,p.status,e.to_status,e.created_at
FROM ingest.content_package p JOIN LATERAL(
 SELECT to_status,created_at FROM ingest.package_status_event e
 WHERE e.content_package_id=p.content_package_id ORDER BY created_at DESC,event_id DESC LIMIT 1
) e ON true WHERE p.status<>e.to_status ORDER BY p.content_package_id LIMIT :'row_limit'::int;
-- END Q136

-- Q137 Package file declared/staged row-count drift.
-- Purpose/output: source-file metadata mismatched to actual staging rows.
-- Inputs: row_limit. Risk: READ ONLY; potentially large staging join.
SELECT f.content_package_id,f.relative_path,f.row_count,count(s.staging_row_id) AS staged_rows
FROM ingest.package_file f LEFT JOIN ingest.staging_row s
ON s.content_package_id=f.content_package_id AND s.source_file=f.relative_path
WHERE f.row_count IS NOT NULL GROUP BY f.content_package_id,f.relative_path,f.row_count
HAVING f.row_count<>count(s.staging_row_id)
ORDER BY f.content_package_id,f.relative_path LIMIT :'row_limit'::int;
-- END Q137

-- Q138 Admin review action volumes.
-- Purpose/output: daily action counts by target type; no actor, notes or snapshots returned.
-- Inputs: days. Risk: READ ONLY; bounded admin audit aggregate.
SELECT date_trunc('day',created_at) AS day,target_type,action,count(*) AS actions
FROM ingest.admin_review_action WHERE created_at>=now()-make_interval(days => :'days'::int)
GROUP BY 1,target_type,action ORDER BY day,target_type,action;
-- END Q138

-- Q139 Imported taxonomy scope drift.
-- Purpose/output: taxonomy edges whose endpoint packages differ from edge package.
-- Inputs: row_limit. Risk: READ ONLY; provenance integrity joins.
SELECT e.from_node_id,e.to_node_id,e.relationship_type,e.content_package_id
FROM pedagogy.taxonomy_edge e JOIN pedagogy.taxonomy_node a ON a.taxonomy_node_id=e.from_node_id
JOIN pedagogy.taxonomy_node b ON b.taxonomy_node_id=e.to_node_id
WHERE e.content_package_id<>a.content_package_id OR e.content_package_id<>b.content_package_id
ORDER BY e.from_node_id,e.to_node_id,e.relationship_type LIMIT :'row_limit'::int;
-- END Q139

-- Q140 Package import throughput.
-- Purpose/output: package latency and imported entity totals; scope overlaps may duplicate entity counts.
-- Inputs: days, row_limit. Risk: READ ONLY; package/reconciliation aggregate.
SELECT p.content_package_id,p.package_name,p.imported_at-p.created_at AS time_to_import,
 sum(r.imported_count) AS imported_scope_entities FROM ingest.content_package p
LEFT JOIN ingest.reconciliation r USING(content_package_id)
WHERE p.imported_at>=now()-make_interval(days => :'days'::int) GROUP BY p.content_package_id
ORDER BY p.imported_at DESC,p.content_package_id LIMIT :'row_limit'::int;
-- END Q140

ROLLBACK;
