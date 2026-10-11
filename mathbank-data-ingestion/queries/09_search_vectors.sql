\ir _session.sql

-- Q161 Embedding model registry and coverage.
-- Purpose/output: model metadata and active embedding counts; does not generate embeddings.
-- Inputs: none. Risk: READ ONLY; vector metadata aggregate, vectors not emitted.
SELECT m.embedding_model_id,m.provider,m.model_name,m.model_revision,m.dimensions,m.status,
 count(e.embedding_id) FILTER(WHERE e.status='ACTIVE') AS active_embeddings
FROM search.embedding_model m LEFT JOIN search.embedding e USING(embedding_model_id)
GROUP BY m.embedding_model_id ORDER BY m.provider,m.model_name,m.model_revision;
-- END Q161

-- Q162 Embedding dimension mismatch.
-- Purpose/output: model/count groups where stored vector dimensions differ from model declaration.
-- Inputs: none. Risk: READ ONLY; vector scan; no vector values.
SELECT m.model_name,m.dimensions AS declared_dimensions,vector_dims(e.embedding) AS actual_dimensions,count(*) AS embeddings
FROM search.embedding e JOIN search.embedding_model m USING(embedding_model_id)
GROUP BY m.model_name,m.dimensions,vector_dims(e.embedding)
HAVING m.dimensions<>vector_dims(e.embedding) ORDER BY m.model_name,actual_dimensions;
-- END Q162

-- Q163 Multiple active revisions for a model name.
-- Purpose/output: provider/name groups that could make runtime model selection ambiguous.
-- Inputs: none. Risk: READ ONLY; registry aggregate.
SELECT provider,model_name,count(*) AS active_revisions FROM search.embedding_model
WHERE status='ACTIVE' GROUP BY provider,model_name HAVING count(*)>1 ORDER BY provider,model_name;
-- END Q163

-- Q164 Representation kind/status inventory.
-- Purpose/output: representations and covered source entities by type/kind/state.
-- Inputs: none. Risk: READ ONLY; representation aggregate.
SELECT source_entity_type,representation_kind,status,count(*) AS representations,count(DISTINCT source_entity_id) AS entities
FROM search.representation GROUP BY source_entity_type,representation_kind,status
ORDER BY source_entity_type,representation_kind,status;
-- END Q164

-- Q165 Multiple active representations per source/profile.
-- Purpose/output: potential supersession backlog, retaining representation kind distinctions.
-- Inputs: row_limit. Risk: READ ONLY; representation grouping.
SELECT source_entity_type,source_entity_id,representation_kind,preprocessing_profile_id,count(*) AS active_versions
FROM search.representation WHERE status='ACTIVE'
GROUP BY source_entity_type,source_entity_id,representation_kind,preprocessing_profile_id HAVING count(*)>1
ORDER BY active_versions DESC,source_entity_id,representation_kind,preprocessing_profile_id LIMIT :'row_limit'::int;
-- END Q165

-- Q166 Active problem representations stale versus canonical modification.
-- Purpose/output: canonical codes needing re-rendering; uses source_updated_at, not generated_at.
-- Inputs: row_limit. Risk: READ ONLY; canonical/retrieval timestamp join.
SELECT p.canonical_code,r.representation_id,r.source_updated_at,p.updated_at
FROM search.representation r JOIN core.problem p ON p.problem_id=r.source_entity_id
WHERE r.source_entity_type='PROBLEM' AND r.status='ACTIVE'
AND (r.source_updated_at IS NULL OR r.source_updated_at<p.updated_at)
ORDER BY p.updated_at DESC,r.representation_id LIMIT :'row_limit'::int;
-- END Q166

-- Q167 Orphan polymorphic problem/solution representations.
-- Purpose/output: active UUID sources no longer present in canonical problem/solution tables.
-- Inputs: row_limit. Risk: READ ONLY; anti-joins; text pedagogy surrogate UUIDs deliberately excluded.
SELECT r.representation_id,r.source_entity_type,r.source_entity_id FROM search.representation r
WHERE r.status='ACTIVE' AND
((r.source_entity_type='PROBLEM' AND NOT EXISTS(SELECT 1 FROM core.problem p WHERE p.problem_id=r.source_entity_id))
OR (r.source_entity_type='SOLUTION' AND NOT EXISTS(SELECT 1 FROM core.solution s WHERE s.solution_id=r.source_entity_id)))
ORDER BY r.representation_id LIMIT :'row_limit'::int;
-- END Q167

-- Q168 Active representations without chunks.
-- Purpose/output: representation IDs that cannot participate in lexical/vector retrieval.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT r.representation_id,r.representation_kind FROM search.representation r WHERE r.status='ACTIVE'
AND NOT EXISTS(SELECT 1 FROM search.chunk c WHERE c.representation_id=r.representation_id)
ORDER BY r.representation_id LIMIT :'row_limit'::int;
-- END Q168

-- Q169 Chunk text metadata drift.
-- Purpose/output: chunk IDs with char_count mismatch, negative token count or blank text.
-- Inputs: row_limit. Risk: READ ONLY; content-length scan; no rendered text.
SELECT chunk_id,chunk_kind,char_count,length(chunk_text) AS actual_characters,token_count FROM search.chunk
WHERE char_count<>length(chunk_text) OR token_count<0 OR btrim(chunk_text)=''
ORDER BY chunk_id LIMIT :'row_limit'::int;
-- END Q169

-- Q170 Chunk ordinal gaps.
-- Purpose/output: representations with noncontiguous chunk ordinals (zero or one base accepted).
-- Inputs: row_limit. Risk: READ ONLY; chunk grouping.
SELECT representation_id,min(chunk_ordinal) AS first_ordinal,max(chunk_ordinal) AS last_ordinal,count(*) AS chunks
FROM search.chunk GROUP BY representation_id HAVING max(chunk_ordinal)-min(chunk_ordinal)+1<>count(*)
ORDER BY representation_id LIMIT :'row_limit'::int;
-- END Q170

-- Q171 Child chunks assigned to a different representation than their parent.
-- Purpose/output: mismatched parent linkage IDs.
-- Inputs: row_limit. Risk: READ ONLY; chunk self-join.
SELECT c.chunk_id,c.parent_chunk_id FROM search.chunk c JOIN search.chunk p ON p.chunk_id=c.parent_chunk_id
WHERE c.representation_id<>p.representation_id ORDER BY c.chunk_id LIMIT :'row_limit'::int;
-- END Q171

-- Q172 Active chunks missing embeddings for active models.
-- Purpose/output: model-level embedding backlog for ACTIVE representations; does not enqueue.
-- Inputs: none. Risk: READ ONLY; model/chunk cross-product may be expensive.
SELECT m.embedding_model_id,m.model_name,count(*) AS missing_chunks
FROM search.embedding_model m CROSS JOIN search.chunk c JOIN search.representation r USING(representation_id)
WHERE m.status='ACTIVE' AND r.status='ACTIVE' AND NOT EXISTS(SELECT 1 FROM search.embedding e
WHERE e.chunk_id=c.chunk_id AND e.embedding_model_id=m.embedding_model_id AND e.status='ACTIVE')
GROUP BY m.embedding_model_id ORDER BY missing_chunks DESC,m.embedding_model_id;
-- END Q172

-- Q173 Active embeddings on superseded representations.
-- Purpose/output: model counts of stale indexed units awaiting cleanup/rebuild.
-- Inputs: none. Risk: READ ONLY; metadata joins.
SELECT e.embedding_model_id,count(*) AS stale_embeddings FROM search.embedding e
JOIN search.chunk c USING(chunk_id) JOIN search.representation r USING(representation_id)
WHERE e.status='ACTIVE' AND r.status<>'ACTIVE' GROUP BY e.embedding_model_id ORDER BY e.embedding_model_id;
-- END Q173

-- Q174 Embedding job retry/stall queue.
-- Purpose/output: incomplete jobs with repeated attempts or stale heartbeat.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan; errors and worker IDs excluded.
SELECT embedding_job_id,status,attempt_count,started_at,heartbeat_at FROM search.embedding_job
WHERE completed_at IS NULL AND (attempt_count>=3 OR
 (started_at<now()-interval '1 hour' AND coalesce(heartbeat_at,started_at)<now()-interval '1 hour'))
ORDER BY attempt_count DESC,embedding_job_id LIMIT :'row_limit'::int;
-- END Q174

-- Q175 Search index definitions and sizes.
-- Purpose/output: actual search-schema PostgreSQL indexes, access methods and disk sizes.
-- Inputs: none. Risk: READ ONLY; system catalog metadata; no migration.
SELECT t.relname AS table_name,i.relname AS index_name,am.amname AS access_method,
 pg_size_pretty(pg_relation_size(i.oid)) AS index_size,pg_get_indexdef(i.oid) AS definition
FROM pg_index x JOIN pg_class t ON t.oid=x.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_am am ON am.oid=i.relam
WHERE n.nspname='search' ORDER BY t.relname,i.relname;
-- END Q175

-- Q176 Lexical published-step search with live eligibility.
-- Purpose/output: matching step IDs and rank; reproduces REST's publication hard filter, no model call.
-- Inputs: query_text, row_limit. Risk: READ ONLY; FTS eligible-candidate scan.
SELECT c.solution_step_id,max(ts_rank_cd(c.textsearch,websearch_to_tsquery('english',:'query_text'))) AS lexical_rank
FROM search.chunk c JOIN search.representation r USING(representation_id)
JOIN pedagogy.solution_step s USING(solution_step_id)
WHERE r.status='ACTIVE' AND r.representation_kind='SOLUTION_STEP' AND s.publication_status='PUBLISHED'
AND c.textsearch @@ websearch_to_tsquery('english',:'query_text')
GROUP BY c.solution_step_id ORDER BY lexical_rank DESC,c.solution_step_id LIMIT :'row_limit'::int;
-- END Q176

-- Q177 Indexed learning items failing runtime eligibility.
-- Purpose/output: active representation chunks whose live exercise is hidden/rejected/proof-based.
-- Inputs: row_limit. Risk: READ ONLY; visibility audit; no hidden exercise text.
SELECT c.chunk_id,c.learning_item_id,i.review_status,i.student_visible,i.no_proof
FROM search.chunk c JOIN search.representation r USING(representation_id)
JOIN pedagogy.learning_item i USING(learning_item_id) WHERE r.status='ACTIVE'
AND NOT(i.review_status='APPROVED' AND i.student_visible AND i.no_proof)
ORDER BY c.chunk_id LIMIT :'row_limit'::int;
-- END Q177

-- Q178 Step chunk taxonomy-filter drift.
-- Purpose/output: chunk IDs whose hard-filter taxonomy differs from the canonical step.
-- Inputs: row_limit. Risk: READ ONLY; canonical metadata comparison.
SELECT c.chunk_id,c.solution_step_id FROM search.chunk c JOIN pedagogy.solution_step s USING(solution_step_id)
WHERE c.skill_node_id IS DISTINCT FROM s.skill_node_id
OR c.concept_node_id IS DISTINCT FROM s.concept_node_id OR c.subconcept_node_id IS DISTINCT FROM s.subconcept_node_id
ORDER BY c.chunk_id LIMIT :'row_limit'::int;
-- END Q178

-- Q179 Preprocessing/retrieval profile version inventory.
-- Purpose/output: available pipeline configuration identities, no configuration secrets/content.
-- Inputs: none. Risk: READ ONLY; registry union.
SELECT 'preprocessing' AS kind,name,version,created_at FROM search.preprocessing_profile
UNION ALL SELECT 'retrieval',name,version,created_at FROM search.retrieval_profile
ORDER BY kind,name,version;
-- END Q179

-- Q180 Zero-norm embedding health.
-- Purpose/output: model counts of zero vectors unsuitable for cosine distance.
-- Inputs: none. Risk: READ ONLY; full vector arithmetic scan; no vector output.
SELECT embedding_model_id,count(*) AS zero_vectors FROM search.embedding
WHERE status='ACTIVE' AND (embedding <#> embedding)=0
GROUP BY embedding_model_id ORDER BY embedding_model_id;
-- END Q180

ROLLBACK;
