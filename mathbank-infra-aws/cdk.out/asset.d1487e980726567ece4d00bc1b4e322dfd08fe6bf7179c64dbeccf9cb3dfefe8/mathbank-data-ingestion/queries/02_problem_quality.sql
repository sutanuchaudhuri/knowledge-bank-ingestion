\ir _session.sql

-- Q021 Blank active statements.
-- Purpose/output: canonical codes missing usable question text.
-- Inputs: row_limit. Risk: READ ONLY; text-length scan.
SELECT canonical_code,status FROM core.problem WHERE status='ACTIVE' AND btrim(statement_text)=''
ORDER BY canonical_code LIMIT :'row_limit'::int;
-- END Q021

-- Q022 Short statements for triage.
-- Purpose/output: active statements below 30 characters; length alone does not prove incompleteness.
-- Inputs: row_limit. Risk: READ ONLY; text-length scan; no text emitted.
SELECT canonical_code,length(statement_text) AS characters FROM core.problem
WHERE status='ACTIVE' AND length(btrim(statement_text)) BETWEEN 1 AND 29
ORDER BY characters,canonical_code LIMIT :'row_limit'::int;
-- END Q022

-- Q023 Statement-size distribution.
-- Purpose/output: quartiles and maximum text length for ingestion size checks.
-- Inputs: none. Risk: READ ONLY; full corpus sort.
SELECT percentile_cont(ARRAY[0.25,0.5,0.75,0.95]) WITHIN GROUP(ORDER BY length(statement_text)) AS quartiles_and_p95,
       max(length(statement_text)) AS max_characters FROM core.problem;
-- END Q023

-- Q024 Duplicate nonempty content hashes.
-- Purpose/output: identical hash groups across distinct canonical problems; possible reuse or duplication.
-- Inputs: row_limit. Risk: READ ONLY; corpus aggregate.
SELECT content_hash,count(*) AS copies,array_agg(canonical_code ORDER BY canonical_code) AS codes
FROM core.problem WHERE nullif(btrim(content_hash),'') IS NOT NULL
GROUP BY content_hash HAVING count(*)>1 ORDER BY copies DESC,content_hash LIMIT :'row_limit'::int;
-- END Q024

-- Q025 Repeated normalized statement text.
-- Purpose/output: whitespace/case-normalized duplicates; excludes blank statements, emits only codes.
-- Inputs: row_limit. Risk: READ ONLY; expensive full-text hash aggregate.
SELECT md5(lower(regexp_replace(btrim(statement_text),'\s+',' ','g'))) AS normalized_digest,
       count(*) AS copies,array_agg(canonical_code ORDER BY canonical_code) AS codes
FROM core.problem WHERE btrim(statement_text)<>''
GROUP BY md5(lower(regexp_replace(btrim(statement_text),'\s+',' ','g')))
HAVING count(*)>1 ORDER BY copies DESC,normalized_digest LIMIT :'row_limit'::int;
-- END Q025

-- Q026 Answer completeness by answer type.
-- Purpose/output: total, missing official answer, and missing LaTeX counts.
-- Inputs: none. Risk: READ ONLY; corpus aggregate.
SELECT answer_type,count(*) AS problems,
 count(*) FILTER(WHERE nullif(btrim(official_answer),'') IS NULL) AS missing_answer,
 count(*) FILTER(WHERE nullif(btrim(statement_latex),'') IS NULL) AS missing_latex
FROM core.problem GROUP BY answer_type ORDER BY problems DESC,answer_type;
-- END Q026

-- Q027 Active problems without any solutions.
-- Purpose/output: canonical codes blocked from solution-grounded tutoring.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT q.canonical_code FROM core.problem q WHERE q.status='ACTIVE'
AND NOT EXISTS(SELECT 1 FROM core.solution s WHERE s.problem_id=q.problem_id)
ORDER BY q.canonical_code LIMIT :'row_limit'::int;
-- END Q027

-- Q028 Problems without reviewed concept assertions.
-- Purpose/output: codes with no accepted concept metadata; automatic review is included, not certified.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT p.canonical_code FROM core.problem p WHERE p.status='ACTIVE'
AND NOT EXISTS(SELECT 1 FROM knowledge.problem_concept c WHERE c.problem_id=p.problem_id AND c.review_status='REVIEWED')
ORDER BY p.canonical_code LIMIT :'row_limit'::int;
-- END Q028

-- Q029 Problems without usable technique assertions.
-- Purpose/output: active codes lacking reviewed problem-level techniques.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT p.canonical_code FROM core.problem p WHERE p.status='ACTIVE'
AND NOT EXISTS(SELECT 1 FROM knowledge.problem_technique t WHERE t.problem_id=p.problem_id AND t.review_status='REVIEWED')
ORDER BY p.canonical_code LIMIT :'row_limit'::int;
-- END Q029

-- Q030 Difficulty versus classification coverage.
-- Purpose/output: joint metadata distribution for prioritizing classification backlog.
-- Inputs: none. Risk: READ ONLY; corpus grouping.
SELECT difficulty_band,classification_status,count(*) AS problems FROM core.problem
GROUP BY difficulty_band,classification_status ORDER BY problems DESC,difficulty_band,classification_status;
-- END Q030

-- Q031 Missing stable statement hashes.
-- Purpose/output: per-paper count of nonempty content lacking change-detection hashes.
-- Inputs: row_limit. Risk: READ ONLY; problem grouping.
SELECT paper_id,count(*) AS unhashed FROM core.problem
WHERE btrim(statement_text)<>'' AND nullif(btrim(content_hash),'') IS NULL
GROUP BY paper_id ORDER BY unhashed DESC,paper_id LIMIT :'row_limit'::int;
-- END Q031

-- Q032 Replacement-character OCR anomalies.
-- Purpose/output: canonical codes and number of Unicode replacement characters.
-- Inputs: row_limit. Risk: READ ONLY; statement scan; no raw text returned.
SELECT canonical_code,length(statement_text)-length(replace(statement_text,chr(65533),'')) AS replacement_characters
FROM core.problem WHERE strpos(statement_text,chr(65533))>0
ORDER BY replacement_characters DESC,canonical_code LIMIT :'row_limit'::int;
-- END Q032

-- Q033 Placeholder-like question statements.
-- Purpose/output: codes matching common ingestion placeholders; manually verify matches.
-- Inputs: row_limit. Risk: READ ONLY; regex corpus scan.
SELECT canonical_code,length(statement_text) AS characters FROM core.problem
WHERE btrim(statement_text) ~* '^(TODO|TBD|placeholder|not available|question text missing)([[:space:].:]|$)'
ORDER BY canonical_code LIMIT :'row_limit'::int;
-- END Q033

-- Q034 Potentially unbalanced dollar delimiters.
-- Purpose/output: codes with odd raw dollar counts; escaped currency can cause false positives, not a LaTeX parser.
-- Inputs: row_limit. Risk: READ ONLY; regex scan.
SELECT canonical_code FROM core.problem
WHERE length(regexp_replace(coalesce(statement_latex,''),'[^$]','','g'))%2=1
ORDER BY canonical_code LIMIT :'row_limit'::int;
-- END Q034

-- Q035 Implausible update timestamps.
-- Purpose/output: problems modified before creation or timestamped over one day in the future.
-- Inputs: row_limit. Risk: READ ONLY; timestamp scan.
SELECT canonical_code,created_at,updated_at FROM core.problem
WHERE updated_at<created_at OR updated_at>now()+interval '1 day'
ORDER BY canonical_code LIMIT :'row_limit'::int;
-- END Q035

-- Q036 Answer-bearing but untyped questions.
-- Purpose/output: codes with an official answer but no answer-type label.
-- Inputs: row_limit. Risk: READ ONLY; text metadata scan.
SELECT canonical_code FROM core.problem WHERE nullif(btrim(official_answer),'') IS NOT NULL
AND nullif(btrim(answer_type),'') IS NULL ORDER BY canonical_code LIMIT :'row_limit'::int;
-- END Q036

-- Q037 One-problem completeness matrix.
-- Purpose/output: booleans for content, solution, image and taxonomy availability, never a correctness certificate.
-- Inputs: problem_code (exact; empty returns none). Risk: READ ONLY; indexed lookup.
SELECT p.canonical_code,btrim(p.statement_text)<>'' AS has_statement,
 nullif(btrim(p.official_answer),'') IS NOT NULL AS has_answer,
 EXISTS(SELECT 1 FROM core.solution s WHERE s.problem_id=p.problem_id) AS has_solution,
 EXISTS(SELECT 1 FROM core.problem_image i WHERE i.problem_id=p.problem_id) AS has_image,
 EXISTS(SELECT 1 FROM knowledge.problem_concept c WHERE c.problem_id=p.problem_id AND c.review_status='REVIEWED') AS has_reviewed_concept
FROM core.problem p WHERE p.canonical_code=:'problem_code';
-- END Q037

-- Q038 Coverage debt by paper.
-- Purpose/output: per-paper missing statements, solutions and concepts, using EXISTS to avoid fan-out.
-- Inputs: row_limit. Risk: READ ONLY; full corpus anti-join aggregation.
SELECT p.paper_id,count(*) AS problems,
 count(*) FILTER(WHERE btrim(p.statement_text)='') AS blank_questions,
 count(*) FILTER(WHERE NOT EXISTS(SELECT 1 FROM core.solution s WHERE s.problem_id=p.problem_id)) AS no_solution,
 count(*) FILTER(WHERE NOT EXISTS(SELECT 1 FROM knowledge.problem_concept c WHERE c.problem_id=p.problem_id)) AS no_concepts
FROM core.problem p GROUP BY p.paper_id ORDER BY blank_questions DESC,no_solution DESC,p.paper_id LIMIT :'row_limit'::int;
-- END Q038

-- Q039 Difficulty-label whitespace inconsistencies.
-- Purpose/output: recorded labels with leading/trailing spaces and their usage counts.
-- Inputs: none. Risk: READ ONLY; label aggregate.
SELECT difficulty_band,count(*) AS problems FROM core.problem
WHERE difficulty_band<>btrim(difficulty_band) GROUP BY difficulty_band ORDER BY problems DESC,difficulty_band;
-- END Q039

-- Q040 Full-text question discovery without model calls.
-- Purpose/output: canonical codes ranked by PostgreSQL English lexical relevance; metadata only.
-- Inputs: query_text, competition, row_limit. Risk: READ ONLY; FTS scan/index depending planner.
SELECT p.canonical_code,ts_rank_cd(to_tsvector('english',p.statement_text),websearch_to_tsquery('english',:'query_text')) AS lexical_rank
FROM core.problem p JOIN core.paper pa USING(paper_id) JOIN core.competition_edition e USING(edition_id)
JOIN core.competition c USING(competition_id)
WHERE p.status='ACTIVE' AND (:'competition'='' OR c.external_code=:'competition')
AND to_tsvector('english',p.statement_text) @@ websearch_to_tsquery('english',:'query_text')
ORDER BY lexical_rank DESC,p.canonical_code LIMIT :'row_limit'::int;
-- END Q040

ROLLBACK;
