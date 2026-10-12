\ir _session.sql

-- Q141 Pipeline run state and throughput.
-- Purpose/output: run-type/state counts, item counters and latest heartbeat.
-- Inputs: days. Risk: READ ONLY; recent run aggregate.
SELECT run_type,status,count(*) AS runs,sum(completed_items) AS completed_items,
 sum(failed_items) AS failed_items,max(heartbeat_at) AS latest_heartbeat FROM pipeline.run
WHERE started_at>=now()-make_interval(days => :'days'::int) OR started_at IS NULL
GROUP BY run_type,status ORDER BY run_type,status;
-- END Q141

-- Q142 Runs with stale heartbeats.
-- Purpose/output: unfinished runs started over an hour ago without recent heartbeat.
-- Inputs: row_limit. Risk: READ ONLY; timestamp scan; no worker identity.
SELECT run_id,run_type,status,started_at,heartbeat_at FROM pipeline.run
WHERE completed_at IS NULL AND started_at<now()-interval '1 hour'
AND coalesce(heartbeat_at,started_at)<now()-interval '1 hour'
ORDER BY started_at,run_id LIMIT :'row_limit'::int;
-- END Q142

-- Q143 Work-item state versus run counters.
-- Purpose/output: stored run totals alongside actual work-item state counts; vocabulary is explicit.
-- Inputs: row_limit. Risk: READ ONLY; run/work aggregate.
SELECT r.run_id,r.completed_items,r.failed_items,count(w.work_item_id) AS actual_items,
 count(w.work_item_id) FILTER(WHERE w.status='COMPLETED') AS actual_completed,
 count(w.work_item_id) FILTER(WHERE w.status='FAILED') AS actual_failed
FROM pipeline.run r LEFT JOIN pipeline.work_item w USING(run_id) GROUP BY r.run_id
ORDER BY r.started_at DESC NULLS LAST,r.run_id LIMIT :'row_limit'::int;
-- END Q143

-- Q144 Expired owned work leases.
-- Purpose/output: unfinished item IDs whose owner lease has expired; no claim or mutation performed.
-- Inputs: row_limit. Risk: READ ONLY; lease scan.
SELECT work_item_id,run_id,item_type,status,lease_expires_at,attempt_count FROM pipeline.work_item
WHERE lease_owner IS NOT NULL AND lease_expires_at<now() AND completed_at IS NULL
ORDER BY lease_expires_at,work_item_id LIMIT :'row_limit'::int;
-- END Q144

-- Q145 Repeatedly retried work-item backlog.
-- Purpose/output: unfinished items with at least three attempts; last_error excluded.
-- Inputs: row_limit. Risk: READ ONLY; retry-counter scan.
SELECT work_item_id,run_id,item_type,status,attempt_count FROM pipeline.work_item
WHERE attempt_count>=3 AND completed_at IS NULL ORDER BY attempt_count DESC,work_item_id LIMIT :'row_limit'::int;
-- END Q145

-- Q146 Pipeline duration anomalies.
-- Purpose/output: runs/work items with completion earlier than start.
-- Inputs: row_limit. Risk: READ ONLY; timestamp integrity scan.
SELECT 'run' AS entity,run_id AS id,started_at,completed_at FROM pipeline.run WHERE completed_at<started_at
UNION ALL SELECT 'work_item',work_item_id,started_at,completed_at FROM pipeline.work_item WHERE completed_at<started_at
ORDER BY entity,id LIMIT :'row_limit'::int;
-- END Q146

-- Q147 Completed work lacking input/output hashes.
-- Purpose/output: item IDs with incomplete reproducibility metadata.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan.
SELECT work_item_id,run_id,item_type,input_hash IS NULL AS missing_input,output_hash IS NULL AS missing_output
FROM pipeline.work_item WHERE status='COMPLETED' AND (input_hash IS NULL OR output_hash IS NULL)
ORDER BY work_item_id LIMIT :'row_limit'::int;
-- END Q147

-- Q148 PDF pipeline stage funnel.
-- Purpose/output: source counts and ingested questions/solutions by three-stage state combination.
-- Inputs: competition. Risk: READ ONLY; PDF tracker aggregate.
SELECT download_status,parse_status,ingest_status,count(*) AS sources,
 sum(questions_ingested) AS questions,sum(solutions_ingested) AS solutions FROM pipeline.pdf_source
WHERE :'competition'='' OR competition_external_code=:'competition'
GROUP BY download_status,parse_status,ingest_status ORDER BY download_status,parse_status,ingest_status;
-- END Q148

-- Q149 PDF parsed-versus-ingested question drift.
-- Purpose/output: ingested source keys whose parsed question count differs from ingestion count.
-- Inputs: row_limit. Risk: READ ONLY; tracker metadata scan.
SELECT paper_external_code,questions_found,questions_ingested FROM pipeline.pdf_source
WHERE ingest_status='INGESTED' AND questions_found<>questions_ingested
ORDER BY abs(questions_found-questions_ingested) DESC,paper_external_code LIMIT :'row_limit'::int;
-- END Q149

-- Q150 Graph projection freshness and volume.
-- Purpose/output: latest projection for each graph, source watermark age and node/edge counts.
-- Inputs: none. Risk: READ ONLY; projection ordering; does not contact Neo4j.
SELECT DISTINCT ON(graph_name) graph_name,status,source_watermark,now()-source_watermark AS source_age,
 nodes_upserted,edges_upserted,started_at,completed_at FROM pipeline.graph_projection
ORDER BY graph_name,started_at DESC,projection_run_id;
-- END Q150

-- Q151 Graph completed-projection duration distribution.
-- Purpose/output: graph-level median/p95 elapsed seconds for recent completed projections.
-- Inputs: days. Risk: READ ONLY; recent projection sort.
SELECT graph_name,count(*) AS runs,
 percentile_cont(ARRAY[0.5,0.95]) WITHIN GROUP(ORDER BY extract(epoch FROM completed_at-started_at)) AS median_p95_seconds
FROM pipeline.graph_projection WHERE completed_at>=now()-make_interval(days => :'days'::int)
AND completed_at>=started_at GROUP BY graph_name ORDER BY graph_name;
-- END Q151

-- Q152 Outbox event types and oldest unconsumed age.
-- Purpose/output: per-type backlog for an exact named consumer; names are not guessed by the query.
-- Inputs: consumer. Risk: READ ONLY; outbox anti-join aggregate; payload excluded.
SELECT e.event_type,count(*) AS pending,min(e.created_at) AS oldest_event,now()-min(e.created_at) AS oldest_age
FROM pipeline.outbox_event e WHERE NOT EXISTS(SELECT 1 FROM pipeline.outbox_consumption c
WHERE c.outbox_event_id=e.outbox_event_id AND c.consumer_name=:'consumer')
GROUP BY e.event_type ORDER BY oldest_event,e.event_type;
-- END Q152

-- Q153 Consumer processing latency.
-- Purpose/output: consumers' processed count and average/max event-to-consumption delay.
-- Inputs: days. Risk: READ ONLY; recent receipt aggregate.
SELECT c.consumer_name,count(*) AS consumed,avg(c.processed_at-e.created_at) AS mean_delay,
 max(c.processed_at-e.created_at) AS worst_delay FROM pipeline.outbox_consumption c
JOIN pipeline.outbox_event e USING(outbox_event_id)
WHERE c.processed_at>=now()-make_interval(days => :'days'::int)
GROUP BY c.consumer_name ORDER BY worst_delay DESC,c.consumer_name;
-- END Q153

-- Q154 Outbox consumption before event creation.
-- Purpose/output: timestamp inconsistency counts by consumer, not payload/aggregate identities.
-- Inputs: none. Risk: READ ONLY; integrity aggregate.
SELECT c.consumer_name,count(*) AS invalid_timestamps FROM pipeline.outbox_consumption c
JOIN pipeline.outbox_event e USING(outbox_event_id) WHERE c.processed_at<e.created_at
GROUP BY c.consumer_name ORDER BY c.consumer_name;
-- END Q154

-- Q155 Pending projection request backlog.
-- Purpose/output: target/scope counts and oldest request; excludes arbitrary reason/operator text.
-- Inputs: none. Risk: READ ONLY; request aggregate.
SELECT target,scope_type,count(*) AS pending,min(requested_at) AS oldest_request
FROM pipeline.projection_request WHERE status='PENDING' GROUP BY target,scope_type ORDER BY oldest_request,target,scope_type;
-- END Q155

-- Q156 Completed projection requests lacking completion time.
-- Purpose/output: request IDs where DONE is inconsistent with timing metadata.
-- Inputs: row_limit. Risk: READ ONLY; integrity scan.
SELECT projection_request_id,target,scope_type,requested_at FROM pipeline.projection_request
WHERE status='DONE' AND completed_at IS NULL ORDER BY requested_at,projection_request_id LIMIT :'row_limit'::int;
-- END Q156

-- Q157 Problem enrichment publication lag.
-- Purpose/output: completed canonical enrichment jobs awaiting outbox publication, with age.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan; no model calls.
SELECT problem_id,attempts,updated_at,now()-updated_at AS unpublished_age FROM knowledge.enrichment_job
WHERE status='COMPLETED' AND published_at IS NULL ORDER BY updated_at,problem_id LIMIT :'row_limit'::int;
-- END Q157

-- Q158 Relationship enrichment outcome throughput.
-- Purpose/output: entity/state job counts, inserted edges and unpublished completions.
-- Inputs: days. Risk: READ ONLY; recent metadata aggregate.
SELECT entity_kind,status,count(*) AS jobs,sum(edges_inserted) AS inserted_edges,
 count(*) FILTER(WHERE status='COMPLETED' AND published_at IS NULL) AS unpublished
FROM knowledge.relationship_enrichment_job WHERE updated_at>=now()-make_interval(days => :'days'::int)
GROUP BY entity_kind,status ORDER BY entity_kind,status;
-- END Q158

-- Q159 Registered outbox consumer activity.
-- Purpose/output: actual receipt consumer names and activity, to select consumer input for Q152.
-- Inputs: none. Risk: READ ONLY; small distinct consumer inventory.
SELECT consumer_name,count(*) AS receipts,min(processed_at) AS first_processed,max(processed_at) AS last_processed
FROM pipeline.outbox_consumption GROUP BY consumer_name ORDER BY consumer_name;
-- END Q159

-- Q160 Run completion-budget inconsistencies.
-- Purpose/output: runs with negative counters or completed+failed exceeding expected items.
-- Inputs: row_limit. Risk: READ ONLY; run metadata integrity scan.
SELECT run_id,run_type,expected_items,completed_items,failed_items FROM pipeline.run
WHERE completed_items<0 OR failed_items<0 OR expected_items<0
OR completed_items::bigint+failed_items>expected_items
ORDER BY run_id LIMIT :'row_limit'::int;
-- END Q160

ROLLBACK;
