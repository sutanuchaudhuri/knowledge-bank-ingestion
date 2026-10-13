\ir _session.sql

-- Q061 Solution kinds and verification inventory.
-- Purpose/output: solution counts and distinct covered problems per kind/status.
-- Inputs: none. Risk: READ ONLY; solution aggregate.
SELECT solution_kind,verification_status,count(*) AS solutions,count(DISTINCT problem_id) AS problems
FROM core.solution GROUP BY solution_kind,verification_status ORDER BY solution_kind,verification_status;
-- END Q061

-- Q062 Latest solution revisions for an exact question.
-- Purpose/output: most recent revision of each kind, with body lengths, not body content.
-- Inputs: problem_code. Risk: READ ONLY; indexed lookup.
SELECT DISTINCT ON(s.solution_kind) s.solution_id,s.solution_kind,s.revision,s.verification_status,
 length(s.body_markdown) AS markdown_characters,length(s.body_latex) AS latex_characters
FROM core.solution s JOIN core.problem p USING(problem_id) WHERE p.canonical_code=:'problem_code'
ORDER BY s.solution_kind,s.revision DESC,s.solution_id;
-- END Q062

-- Q063 Empty solution bodies.
-- Purpose/output: solutions with neither usable Markdown nor LaTeX.
-- Inputs: row_limit. Risk: READ ONLY; content-length scan.
SELECT p.canonical_code,s.solution_id,s.solution_kind,s.revision FROM core.solution s JOIN core.problem p USING(problem_id)
WHERE nullif(btrim(s.body_markdown),'') IS NULL AND nullif(btrim(s.body_latex),'') IS NULL
ORDER BY p.canonical_code,s.solution_id LIMIT :'row_limit'::int;
-- END Q063

-- Q064 Solution revision gaps.
-- Purpose/output: kind/problem groups with noncontiguous revisions; deletion may explain gaps.
-- Inputs: row_limit. Risk: READ ONLY; revision grouping.
SELECT problem_id,solution_kind,min(revision) AS first_revision,max(revision) AS latest_revision,count(*) AS versions
FROM core.solution GROUP BY problem_id,solution_kind HAVING max(revision)-min(revision)+1<>count(*)
ORDER BY problem_id,solution_kind LIMIT :'row_limit'::int;
-- END Q064

-- Q065 Core solution-step ordinal integrity.
-- Purpose/output: solution IDs with holes or nonpositive ordinals.
-- Inputs: row_limit. Risk: READ ONLY; core step grouping.
SELECT solution_id,min(ordinal) AS first_ordinal,max(ordinal) AS last_ordinal,count(*) AS steps
FROM core.solution_step GROUP BY solution_id
HAVING min(ordinal)<1 OR max(ordinal)-min(ordinal)+1<>count(*) ORDER BY solution_id LIMIT :'row_limit'::int;
-- END Q065

-- Q066 Blank canonical core steps.
-- Purpose/output: step IDs without explanation or formula; separate from pedagogy.solution_step.
-- Inputs: row_limit. Risk: READ ONLY; metadata/text scan.
SELECT solution_step_id,solution_id,ordinal FROM core.solution_step
WHERE nullif(btrim(explanation),'') IS NULL AND nullif(btrim(formula_latex),'') IS NULL
ORDER BY solution_id,ordinal LIMIT :'row_limit'::int;
-- END Q066

-- Q067 Solution parts with declared step-count drift.
-- Purpose/output: part IDs whose actual pedagogy steps disagree with step_count.
-- Inputs: book, row_limit. Risk: READ ONLY; part/step aggregate.
SELECT p.solution_part_id,p.step_count,count(s.solution_step_id) AS actual_steps
FROM pedagogy.solution_part p LEFT JOIN pedagogy.solution_step s USING(solution_part_id)
WHERE :'book'='' OR p.book_code=:'book' GROUP BY p.solution_part_id
HAVING p.step_count<>count(s.solution_step_id) ORDER BY p.solution_part_id LIMIT :'row_limit'::int;
-- END Q067

-- Q068 Pedagogy step/part ownership inconsistency.
-- Purpose/output: step IDs with mismatched solution, problem or book ownership.
-- Inputs: row_limit. Risk: READ ONLY; integrity join.
SELECT s.solution_step_id,s.solution_part_id FROM pedagogy.solution_step s
JOIN pedagogy.solution_part p USING(solution_part_id)
WHERE s.solution_id<>p.solution_id OR s.problem_id<>p.problem_id OR s.book_code<>p.book_code
ORDER BY s.solution_step_id LIMIT :'row_limit'::int;
-- END Q068

-- Q069 Global pedagogy step order holes.
-- Purpose/output: problem IDs with missing global indices or nonpositive first index.
-- Inputs: book. Risk: READ ONLY; step grouping.
SELECT problem_id,min(global_step_index) AS first_index,max(global_step_index) AS last_index,count(*) AS steps
FROM pedagogy.solution_step WHERE :'book'='' OR book_code=:'book'
GROUP BY problem_id HAVING min(global_step_index)<1 OR max(global_step_index)-min(global_step_index)+1<>count(*)
ORDER BY problem_id;
-- END Q069

-- Q070 Per-part step-index collisions and holes.
-- Purpose/output: part IDs with duplicate/missing step_index_in_part.
-- Inputs: book. Risk: READ ONLY; grouped integrity scan.
SELECT solution_part_id,count(*) AS steps,count(DISTINCT step_index_in_part) AS distinct_indices
FROM pedagogy.solution_step WHERE :'book'='' OR book_code=:'book'
GROUP BY solution_part_id HAVING count(*)<>count(DISTINCT step_index_in_part)
OR max(step_index_in_part)-min(step_index_in_part)+1<>count(*) ORDER BY solution_part_id;
-- END Q070

-- Q071 Published-step checkpoint coverage.
-- Purpose/output: problem IDs with published steps but no checkpoint.
-- Inputs: book, row_limit. Risk: READ ONLY; step aggregate.
SELECT problem_id,count(*) AS steps FROM pedagogy.solution_step WHERE publication_status='PUBLISHED'
AND (:'book'='' OR book_code=:'book') GROUP BY problem_id HAVING NOT bool_or(is_checkpoint)
ORDER BY steps DESC,problem_id LIMIT :'row_limit'::int;
-- END Q071

-- Q072 Step roles and types.
-- Purpose/output: observed tutor_role/step_type/publication combinations and missing skill counts.
-- Inputs: book. Risk: READ ONLY; step aggregate.
SELECT step_type,tutor_role,publication_status,count(*) AS steps,
 count(*) FILTER(WHERE skill_node_id IS NULL) AS missing_skill
FROM pedagogy.solution_step WHERE :'book'='' OR book_code=:'book'
GROUP BY step_type,tutor_role,publication_status ORDER BY steps DESC,step_type,tutor_role,publication_status;
-- END Q072

-- Q073 Cross-problem dependency links.
-- Purpose/output: dependency endpoints from different problems for manual semantic review.
-- Inputs: row_limit. Risk: READ ONLY; DAG join, metadata only.
SELECT d.from_step_id,d.to_step_id,d.relationship_type FROM pedagogy.solution_step_dependency d
JOIN pedagogy.solution_step a ON a.solution_step_id=d.from_step_id
JOIN pedagogy.solution_step b ON b.solution_step_id=d.to_step_id
WHERE a.problem_id<>b.problem_id ORDER BY d.from_step_id,d.to_step_id,d.relationship_type LIMIT :'row_limit'::int;
-- END Q073

-- Q074 NEXT edges conflicting with global order.
-- Purpose/output: same-problem NEXT edges not advancing exactly one index.
-- Inputs: row_limit. Risk: READ ONLY; dependency integrity join.
SELECT d.from_step_id,d.to_step_id,a.global_step_index AS from_index,b.global_step_index AS to_index
FROM pedagogy.solution_step_dependency d
JOIN pedagogy.solution_step a ON a.solution_step_id=d.from_step_id
JOIN pedagogy.solution_step b ON b.solution_step_id=d.to_step_id
WHERE d.relationship_type='NEXT' AND a.problem_id=b.problem_id AND b.global_step_index<>a.global_step_index+1
ORDER BY d.from_step_id,d.to_step_id LIMIT :'row_limit'::int;
-- END Q074

-- Q075 Opposing reviewed dependency pairs.
-- Purpose/output: direct two-node cycles of the same nonalternative semantic relationship.
-- Inputs: row_limit. Risk: READ ONLY; bounded self-join; not exhaustive cycle detection.
SELECT a.from_step_id,a.to_step_id,a.relationship_type FROM pedagogy.solution_step_dependency a
JOIN pedagogy.solution_step_dependency b ON b.from_step_id=a.to_step_id AND b.to_step_id=a.from_step_id
AND b.relationship_type=a.relationship_type
WHERE a.from_step_id<a.to_step_id AND a.review_status='REVIEWED' AND b.review_status='REVIEWED'
AND a.relationship_type IN('DEPENDS_ON','DERIVES_FROM','NEXT','USES_RESULT_FROM')
ORDER BY a.from_step_id,a.to_step_id LIMIT :'row_limit'::int;
-- END Q075

-- Q076 Dependency approval provenance.
-- Purpose/output: counts separating relationship, status, human/automatic/unknown origin.
-- Inputs: none. Risk: READ ONLY; DAG aggregate.
SELECT relationship_type,review_status,approval_method,source_type,count(*) AS edges
FROM pedagogy.solution_step_dependency GROUP BY relationship_type,review_status,approval_method,source_type
ORDER BY relationship_type,review_status,approval_method,source_type;
-- END Q076

-- Q077 Solution DAG review backlog.
-- Purpose/output: solutions with imported steps and absent/nonapproved semantic DAG review.
-- Inputs: row_limit. Risk: READ ONLY; distinct solution/approval join.
SELECT DISTINCT s.solution_id,s.problem_id,r.status FROM pedagogy.solution_step s
LEFT JOIN pedagogy.solution_dag_review r USING(solution_id)
WHERE r.status IS DISTINCT FROM 'APPROVED' ORDER BY s.solution_id LIMIT :'row_limit'::int;
-- END Q077

-- Q078 Admin-edited steps modified since DAG approval.
-- Purpose/output: solution IDs with newer protected step edits requiring re-review.
-- Inputs: row_limit. Risk: READ ONLY; timestamp integrity join.
SELECT r.solution_id,r.reviewed_at,max(s.admin_edited_at) AS last_admin_edit
FROM pedagogy.solution_dag_review r JOIN pedagogy.solution_step s USING(solution_id)
WHERE r.status='APPROVED' GROUP BY r.solution_id HAVING max(s.admin_edited_at)>r.reviewed_at
ORDER BY last_admin_edit DESC,r.solution_id LIMIT :'row_limit'::int;
-- END Q078

-- Q079 Missing progressive hint levels on published checkpoints.
-- Purpose/output: checkpoint step and missing level; any prompt version satisfies coverage, not quality.
-- Inputs: book, row_limit. Risk: READ ONLY; four-level anti-join.
SELECT s.solution_step_id,l.level FROM pedagogy.solution_step s CROSS JOIN generate_series(1,4) l(level)
WHERE s.is_checkpoint AND s.publication_status='PUBLISHED' AND (:'book'='' OR s.book_code=:'book')
AND NOT EXISTS(SELECT 1 FROM pedagogy.step_hint h WHERE h.solution_step_id=s.solution_step_id AND h.hint_level=l.level)
ORDER BY s.solution_step_id,l.level LIMIT :'row_limit'::int;
-- END Q079

-- Q080 Hint safety/version inventory.
-- Purpose/output: prompt/model/level counts and hints explicitly not leak-checked.
-- Inputs: none. Risk: READ ONLY; shared corpus hints only, no hint text or generation calls.
SELECT prompt_version,model,hint_level,count(*) AS hints,count(*) FILTER(WHERE NOT leak_checked) AS unchecked
FROM pedagogy.step_hint GROUP BY prompt_version,model,hint_level ORDER BY prompt_version,model,hint_level;
-- END Q080

ROLLBACK;
