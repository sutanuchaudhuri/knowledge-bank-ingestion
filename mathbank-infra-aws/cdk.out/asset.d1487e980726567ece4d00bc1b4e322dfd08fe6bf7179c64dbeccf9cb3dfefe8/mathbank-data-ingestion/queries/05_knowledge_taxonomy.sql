\ir _session.sql

-- Q081 Concept usage and lifecycle.
-- Purpose/output: concepts with reviewed problem coverage, including unused concepts.
-- Inputs: row_limit. Risk: READ ONLY; catalog/assertion aggregation.
SELECT c.slug,c.name,c.status,count(pc.problem_id) FILTER(WHERE pc.review_status='REVIEWED') AS reviewed_problems
FROM knowledge.concept c LEFT JOIN knowledge.problem_concept pc USING(concept_id)
GROUP BY c.concept_id ORDER BY reviewed_problems DESC,c.slug LIMIT :'row_limit'::int;
-- END Q081

-- Q082 Techniques without problem or taxonomy connections.
-- Purpose/output: technique slugs with neither canonical problem assertions nor textbook bridges.
-- Inputs: row_limit. Risk: READ ONLY; anti-joins.
SELECT t.slug,t.name FROM knowledge.technique t
WHERE NOT EXISTS(SELECT 1 FROM knowledge.problem_technique p WHERE p.technique_id=t.technique_id)
AND NOT EXISTS(SELECT 1 FROM pedagogy.taxonomy_node n WHERE n.technique_id=t.technique_id)
ORDER BY t.slug LIMIT :'row_limit'::int;
-- END Q082

-- Q083 Problem concept assertion trust distribution.
-- Purpose/output: counts by source/status/approval method, with average confidence.
-- Inputs: none. Risk: READ ONLY; metadata aggregate; approval is not mathematical verification.
SELECT assertion_source,review_status,approval_method,count(*) AS assertions,avg(confidence) AS mean_confidence
FROM knowledge.problem_concept GROUP BY assertion_source,review_status,approval_method
ORDER BY assertion_source,review_status,approval_method;
-- END Q083

-- Q084 Low-confidence reviewed techniques.
-- Purpose/output: accepted technique assertions below the requested confidence threshold.
-- Inputs: confidence, row_limit. Risk: READ ONLY; assertion scan.
SELECT p.canonical_code,t.slug,a.confidence,a.approval_method
FROM knowledge.problem_technique a JOIN core.problem p USING(problem_id) JOIN knowledge.technique t USING(technique_id)
WHERE a.review_status='REVIEWED' AND (a.confidence IS NULL OR a.confidence<:'confidence'::numeric)
ORDER BY a.confidence NULLS FIRST,p.canonical_code,t.slug LIMIT :'row_limit'::int;
-- END Q084

-- Q085 Multiple reviewed primary concepts.
-- Purpose/output: problems with more than one PRIMARY concept; taxonomy policy determines validity.
-- Inputs: row_limit. Risk: READ ONLY; assertion aggregate.
SELECT problem_id,count(*) AS primary_concepts FROM knowledge.problem_concept
WHERE role='PRIMARY' AND review_status='REVIEWED' GROUP BY problem_id HAVING count(*)>1
ORDER BY primary_concepts DESC,problem_id LIMIT :'row_limit'::int;
-- END Q085

-- Q086 Reviewed links to inactive concepts.
-- Purpose/output: active problem codes mapped to nonactive concept nodes.
-- Inputs: row_limit. Risk: READ ONLY; lifecycle join.
SELECT p.canonical_code,c.slug,c.status FROM knowledge.problem_concept a
JOIN core.problem p USING(problem_id) JOIN knowledge.concept c USING(concept_id)
WHERE a.review_status='REVIEWED' AND p.status='ACTIVE' AND c.status<>'ACTIVE'
ORDER BY p.canonical_code,c.slug LIMIT :'row_limit'::int;
-- END Q086

-- Q087 Skill trust and level inventory.
-- Purpose/output: skill counts by level/review/approval method, average confidence.
-- Inputs: none. Risk: READ ONLY; catalog aggregate.
SELECT level,review_status,approval_method,count(*) AS skills,avg(confidence) AS mean_confidence
FROM knowledge.skill GROUP BY level,review_status,approval_method ORDER BY level,review_status,approval_method;
-- END Q087

-- Q088 Skills without concept grounding.
-- Purpose/output: reviewed skill slugs lacking reviewed skill_concept links.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT s.slug,s.name FROM knowledge.skill s WHERE s.review_status='REVIEWED'
AND NOT EXISTS(SELECT 1 FROM knowledge.skill_concept c WHERE c.skill_id=s.skill_id AND c.review_status='REVIEWED')
ORDER BY s.slug LIMIT :'row_limit'::int;
-- END Q088

-- Q089 Problem skill roles and requirement levels.
-- Purpose/output: accepted skill assertion distribution by pedagogic role and level.
-- Inputs: none. Risk: READ ONLY; metadata aggregate.
SELECT relation_type,role,required_level,count(*) AS assertions,avg(importance) AS mean_importance
FROM knowledge.problem_skill WHERE review_status='REVIEWED'
GROUP BY relation_type,role,required_level ORDER BY relation_type,role,required_level;
-- END Q089

-- Q090 Active questions missing reviewed primary skills.
-- Purpose/output: canonical codes without primary-role accepted skill grounding.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT p.canonical_code FROM core.problem p WHERE p.status='ACTIVE'
AND NOT EXISTS(SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id=p.problem_id
AND s.role='primary' AND s.review_status='REVIEWED') ORDER BY p.canonical_code LIMIT :'row_limit'::int;
-- END Q090

-- Q091 Bidirectional skill prerequisite cycles.
-- Purpose/output: direct reciprocal PREREQUISITE_OF links, not exhaustive graph-cycle search.
-- Inputs: row_limit. Risk: READ ONLY; relation self-join.
SELECT a.from_skill_id,a.to_skill_id FROM knowledge.skill_relation a JOIN knowledge.skill_relation b
ON b.from_skill_id=a.to_skill_id AND b.to_skill_id=a.from_skill_id
WHERE a.from_skill_id<a.to_skill_id AND a.relation_type='PREREQUISITE_OF' AND b.relation_type='PREREQUISITE_OF'
AND a.review_status='REVIEWED' AND b.review_status='REVIEWED'
ORDER BY a.from_skill_id,a.to_skill_id LIMIT :'row_limit'::int;
-- END Q091

-- Q092 Self-linked concept relationships.
-- Purpose/output: reflexive edges allowed by base DDL but potentially semantically invalid.
-- Inputs: none. Risk: READ ONLY; relation scan.
SELECT relation_id,from_concept_id,relation_type,review_status FROM knowledge.concept_relation
WHERE from_concept_id=to_concept_id ORDER BY relation_id;
-- END Q092

-- Q093 Concept relation confidence bounds.
-- Purpose/output: unbounded or absent strengths on reviewed edges, for normalization review.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan.
SELECT relation_id,relation_type,strength FROM knowledge.concept_relation
WHERE review_status='REVIEWED' AND (strength IS NULL OR strength<0 OR strength>1)
ORDER BY relation_id LIMIT :'row_limit'::int;
-- END Q093

-- Q094 Taxonomy bridge coverage.
-- Purpose/output: node-type counts lacking canonical concept/skill/technique bridge.
-- Inputs: none. Risk: READ ONLY; taxonomy aggregate.
SELECT node_type,count(*) AS nodes,count(*) FILTER(WHERE num_nonnulls(concept_id,skill_id,technique_id)=0) AS unbridged
FROM pedagogy.taxonomy_node GROUP BY node_type ORDER BY node_type;
-- END Q094

-- Q095 Broken taxonomy parent references.
-- Purpose/output: parent IDs are text without FK; list children pointing to absent parents.
-- Inputs: row_limit. Risk: READ ONLY; taxonomy anti-join.
SELECT n.taxonomy_node_id,n.parent_node_id FROM pedagogy.taxonomy_node n
WHERE n.parent_node_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM pedagogy.taxonomy_node p WHERE p.taxonomy_node_id=n.parent_node_id)
ORDER BY n.taxonomy_node_id LIMIT :'row_limit'::int;
-- END Q095

-- Q096 Wrong canonical bridge type.
-- Purpose/output: taxonomy nodes whose linked canonical entity does not match node_type.
-- Inputs: none. Risk: READ ONLY; catalog integrity scan.
SELECT taxonomy_node_id,node_type,concept_id,skill_id,technique_id FROM pedagogy.taxonomy_node
WHERE (concept_id IS NOT NULL AND node_type NOT IN('DOMAIN','CONCEPT','SUBCONCEPT'))
OR (skill_id IS NOT NULL AND node_type<>'SKILL') OR (technique_id IS NOT NULL AND node_type<>'TECHNIQUE')
ORDER BY taxonomy_node_id;
-- END Q096

-- Q097 Ambiguous normalized taxonomy names.
-- Purpose/output: collisions under REST topic_key normalization; unique exact match is required.
-- Inputs: row_limit. Risk: READ ONLY; regex catalog aggregate.
WITH names AS (
 SELECT taxonomy_node_id,btrim(regexp_replace(
 regexp_replace(lower(name),'[^a-z0-9]+',' ','g'),'\m(a|an|the|of)\M[ ]*','','g')) AS topic_key
 FROM pedagogy.taxonomy_node WHERE node_type IN('CONCEPT','SUBCONCEPT','SKILL','TECHNIQUE')
)
SELECT topic_key,count(*) AS nodes,array_agg(taxonomy_node_id ORDER BY taxonomy_node_id) AS node_ids
FROM names WHERE topic_key<>'' GROUP BY topic_key HAVING count(*)>1
ORDER BY nodes DESC,topic_key LIMIT :'row_limit'::int;
-- END Q097

-- Q098 Taxonomy edge quality by relationship.
-- Purpose/output: source/type edge counts with absent or out-of-bounds confidence.
-- Inputs: none. Risk: READ ONLY; edge aggregate.
SELECT relationship_type,source_basis,count(*) AS edges,
 count(*) FILTER(WHERE confidence IS NULL OR confidence NOT BETWEEN 0 AND 1) AS suspect_confidence
FROM pedagogy.taxonomy_edge GROUP BY relationship_type,source_basis ORDER BY relationship_type,source_basis;
-- END Q098

-- Q099 Step technique derivation coverage.
-- Purpose/output: derivation-version outcome counts, exposing NO_MATCH and NO_PROBLEM_TECHNIQUE backlog.
-- Inputs: none. Risk: READ ONLY; metadata aggregate; no derivation/model execution.
SELECT derivation_version,outcome,count(*) AS steps FROM pedagogy.solution_step_technique_run
GROUP BY derivation_version,outcome ORDER BY derivation_version,outcome;
-- END Q099

-- Q100 Technique assertions attached to wrong-type taxonomy nodes.
-- Purpose/output: step technique links whose target is not TECHNIQUE.
-- Inputs: row_limit. Risk: READ ONLY; integrity join.
SELECT a.solution_step_id,a.technique_node_id,n.node_type FROM pedagogy.solution_step_technique a
JOIN pedagogy.taxonomy_node n ON n.taxonomy_node_id=a.technique_node_id
WHERE n.node_type<>'TECHNIQUE' ORDER BY a.solution_step_id,a.technique_node_id LIMIT :'row_limit'::int;
-- END Q100

ROLLBACK;
