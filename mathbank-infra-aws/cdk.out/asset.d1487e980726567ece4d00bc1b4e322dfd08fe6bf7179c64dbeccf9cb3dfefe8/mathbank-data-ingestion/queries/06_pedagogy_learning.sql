\ir _session.sql

-- Q101 Pedagogy dimensional profile.
-- Purpose/output: conceptual/technical/insight bands and confidence distribution.
-- Inputs: none. Risk: READ ONLY; shared corpus aggregate.
SELECT conceptual_depth,technical_load,insight_required,count(*) AS problems,avg(confidence) AS mean_confidence
FROM knowledge.problem_pedagogy WHERE review_status='REVIEWED'
GROUP BY conceptual_depth,technical_load,insight_required ORDER BY conceptual_depth,technical_load,insight_required;
-- END Q101

-- Q102 Missing pedagogy dimensions.
-- Purpose/output: accepted records lacking depth/load/insight values.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan.
SELECT problem_id,approval_method FROM knowledge.problem_pedagogy WHERE review_status='REVIEWED'
AND (conceptual_depth IS NULL OR technical_load IS NULL OR insight_required IS NULL)
ORDER BY problem_id LIMIT :'row_limit'::int;
-- END Q102

-- Q103 Textbook enrichment versus actual step count.
-- Purpose/output: declared enrichment count disagrees with canonical pedagogy steps.
-- Inputs: row_limit. Risk: READ ONLY; aggregate join.
SELECT e.problem_id,e.solution_step_count,count(s.solution_step_id) AS actual_steps
FROM pedagogy.problem_enrichment e LEFT JOIN pedagogy.solution_step s USING(problem_id)
GROUP BY e.problem_id HAVING e.solution_step_count<>count(s.solution_step_id)
ORDER BY e.problem_id LIMIT :'row_limit'::int;
-- END Q103

-- Q104 Enrichment taxonomy confidence backlog.
-- Purpose/output: problems with absent or low-confidence taxonomy mapping provenance.
-- Inputs: confidence, row_limit. Risk: READ ONLY; metadata scan.
SELECT problem_id,taxonomy_mapping_basis,taxonomy_confidence FROM pedagogy.problem_enrichment
WHERE taxonomy_confidence IS NULL OR taxonomy_confidence<:'confidence'::numeric
ORDER BY taxonomy_confidence NULLS FIRST,problem_id LIMIT :'row_limit'::int;
-- END Q104

-- Q105 Unresolved enrichment technique-array IDs.
-- Purpose/output: problem technique codes absent from the textbook taxonomy.
-- Inputs: row_limit. Risk: READ ONLY; array expansion and anti-join.
SELECT e.problem_id,t.node_id FROM pedagogy.problem_enrichment e CROSS JOIN LATERAL unnest(e.technique_ids) t(node_id)
WHERE NOT EXISTS(SELECT 1 FROM pedagogy.taxonomy_node n WHERE n.taxonomy_node_id=t.node_id AND n.node_type='TECHNIQUE')
ORDER BY e.problem_id,t.node_id LIMIT :'row_limit'::int;
-- END Q105

-- Q106 Learning-item publication/review inventory.
-- Purpose/output: counts by visibility, approval and transformation type.
-- Inputs: book. Risk: READ ONLY; corpus item aggregate.
SELECT transformation_type,review_status,student_visible,approval_method,count(*) AS items
FROM pedagogy.learning_item WHERE :'book'='' OR book_code=:'book'
GROUP BY transformation_type,review_status,student_visible,approval_method
ORDER BY transformation_type,review_status,student_visible,approval_method;
-- END Q106

-- Q107 Visible learning items without usable questions or answers.
-- Purpose/output: IDs of published exercises missing required content fields.
-- Inputs: row_limit. Risk: READ ONLY; text checks; no solution text.
SELECT learning_item_id,transformation_type FROM pedagogy.learning_item
WHERE student_visible AND (btrim(question_text)='' OR
 (nullif(btrim(correct_answer),'') IS NULL AND nullif(btrim(answer_or_solution_seed),'') IS NULL))
ORDER BY learning_item_id LIMIT :'row_limit'::int;
-- END Q107

-- Q108 Approved but hidden learning items.
-- Purpose/output: approved exercise backlog not yet student-visible; intentional hiding is possible.
-- Inputs: book, row_limit. Risk: READ ONLY; publication scan.
SELECT learning_item_id,transformation_type,approved_at FROM pedagogy.learning_item
WHERE review_status='APPROVED' AND NOT student_visible AND (:'book'='' OR book_code=:'book')
ORDER BY approved_at NULLS FIRST,learning_item_id LIMIT :'row_limit'::int;
-- END Q108

-- Q109 Dangling learning-item parent links.
-- Purpose/output: parent_learning_item_id lacks FK; identify references to absent items.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT i.learning_item_id,i.parent_learning_item_id FROM pedagogy.learning_item i
WHERE i.parent_learning_item_id IS NOT NULL
AND NOT EXISTS(SELECT 1 FROM pedagogy.learning_item p WHERE p.learning_item_id=i.parent_learning_item_id)
ORDER BY i.learning_item_id LIMIT :'row_limit'::int;
-- END Q109

-- Q110 Visible exercises without canonical step anchors.
-- Purpose/output: item IDs lacking step-level provenance.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT i.learning_item_id,i.source_problem_id FROM pedagogy.learning_item i
WHERE i.student_visible AND NOT EXISTS(SELECT 1 FROM pedagogy.learning_item_step_anchor a WHERE a.learning_item_id=i.learning_item_id)
ORDER BY i.learning_item_id LIMIT :'row_limit'::int;
-- END Q110

-- Q111 Step anchors crossing source-problem boundaries.
-- Purpose/output: item/step IDs whose source ownership differs.
-- Inputs: row_limit. Risk: READ ONLY; integrity join.
SELECT a.learning_item_id,a.solution_step_id FROM pedagogy.learning_item_step_anchor a
JOIN pedagogy.learning_item i USING(learning_item_id) JOIN pedagogy.solution_step s USING(solution_step_id)
WHERE i.source_problem_id<>s.problem_id ORDER BY a.learning_item_id,a.solution_step_id LIMIT :'row_limit'::int;
-- END Q111

-- Q112 Anchor ordinal duplicates.
-- Purpose/output: items with multiple steps assigned the same ordinal (not prohibited by PK).
-- Inputs: row_limit. Risk: READ ONLY; anchor grouping.
SELECT learning_item_id,anchor_ordinal,count(*) AS steps FROM pedagogy.learning_item_step_anchor
GROUP BY learning_item_id,anchor_ordinal HAVING count(*)>1 ORDER BY learning_item_id,anchor_ordinal LIMIT :'row_limit'::int;
-- END Q112

-- Q113 Learning-item target taxonomy type mismatches.
-- Purpose/output: item IDs linked to non-SKILL/non-CONCEPT/non-SUBCONCEPT targets.
-- Inputs: row_limit. Risk: READ ONLY; taxonomy joins.
SELECT i.learning_item_id FROM pedagogy.learning_item i
LEFT JOIN pedagogy.taxonomy_node s ON s.taxonomy_node_id=i.target_skill_node_id
LEFT JOIN pedagogy.taxonomy_node c ON c.taxonomy_node_id=i.target_concept_node_id
LEFT JOIN pedagogy.taxonomy_node u ON u.taxonomy_node_id=i.target_subconcept_node_id
WHERE s.node_type<>'SKILL' OR c.node_type<>'CONCEPT' OR u.node_type<>'SUBCONCEPT'
ORDER BY i.learning_item_id LIMIT :'row_limit'::int;
-- END Q113

-- Q114 Source-dependent visible items without diagram strategy.
-- Purpose/output: exercises requiring source context but lacking recorded visual reuse policy.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan.
SELECT learning_item_id,source_problem_id FROM pedagogy.learning_item
WHERE student_visible AND requires_source_problem AND nullif(btrim(diagram_strategy),'') IS NULL
ORDER BY learning_item_id LIMIT :'row_limit'::int;
-- END Q114

-- Q115 Malformed multiple-choice shape.
-- Purpose/output: items with nonarray choices or fewer than two choices; NULL means non-MCQ.
-- Inputs: row_limit. Risk: READ ONLY; guarded JSON inspection.
SELECT learning_item_id,jsonb_typeof(choices) AS choices_type FROM pedagogy.learning_item
WHERE choices IS NOT NULL AND CASE WHEN jsonb_typeof(choices)='array'
THEN jsonb_array_length(choices)<2 ELSE true END ORDER BY learning_item_id LIMIT :'row_limit'::int;
-- END Q115

-- Q116 Visible learning-item skill coverage.
-- Purpose/output: skill targets with exercise count and transformation diversity.
-- Inputs: book. Risk: READ ONLY; published corpus aggregate.
SELECT target_skill_node_id,count(*) AS items,count(DISTINCT transformation_type) AS transformation_types
FROM pedagogy.learning_item WHERE student_visible AND review_status='APPROVED' AND no_proof
AND (:'book'='' OR book_code=:'book') GROUP BY target_skill_node_id ORDER BY items DESC,target_skill_node_id;
-- END Q116

-- Q117 Published step skills without eligible exercises.
-- Purpose/output: skill node IDs with canonical steps but no approved visible no-proof exercise.
-- Inputs: row_limit. Risk: READ ONLY; distinct anti-join.
SELECT DISTINCT s.skill_node_id FROM pedagogy.solution_step s WHERE s.publication_status='PUBLISHED'
AND s.skill_node_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM pedagogy.learning_item i
WHERE i.target_skill_node_id=s.skill_node_id AND i.review_status='APPROVED' AND i.student_visible AND i.no_proof)
ORDER BY s.skill_node_id LIMIT :'row_limit'::int;
-- END Q117

-- Q118 Duplicate normalized visible exercise questions.
-- Purpose/output: repeated question digest by source problem, with IDs for editorial review.
-- Inputs: row_limit. Risk: READ ONLY; text hash grouping; no raw question.
SELECT source_problem_id,md5(lower(regexp_replace(btrim(question_text),'\s+',' ','g'))) AS question_digest,
 count(*) AS copies,array_agg(learning_item_id ORDER BY learning_item_id) AS item_ids
FROM pedagogy.learning_item WHERE student_visible AND btrim(question_text)<>''
GROUP BY source_problem_id,md5(lower(regexp_replace(btrim(question_text),'\s+',' ','g')))
HAVING count(*)>1 ORDER BY copies DESC,source_problem_id,question_digest LIMIT :'row_limit'::int;
-- END Q118

-- Q119 Approved exercise metadata missing approval timestamp/method.
-- Purpose/output: IDs with incomplete approval provenance; do not infer human review.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan.
SELECT learning_item_id,approval_method,approved_at FROM pedagogy.learning_item
WHERE review_status='APPROVED' AND (approved_at IS NULL OR approval_method IS NULL)
ORDER BY learning_item_id LIMIT :'row_limit'::int;
-- END Q119

-- Q120 Solution-level pedagogy declared-step drift.
-- Purpose/output: reviewed number_of_steps differs from total core solution steps across all revisions.
-- Inputs: row_limit. Risk: READ ONLY; aggregate; multiple solution methods can explain discrepancy.
SELECT a.problem_id,a.number_of_steps,count(st.solution_step_id) AS core_steps_all_revisions
FROM knowledge.problem_pedagogy a LEFT JOIN core.solution s USING(problem_id)
LEFT JOIN core.solution_step st USING(solution_id) WHERE a.review_status='REVIEWED'
GROUP BY a.problem_id HAVING a.number_of_steps<>count(st.solution_step_id)
ORDER BY a.problem_id LIMIT :'row_limit'::int;
-- END Q120

ROLLBACK;
