\ir _session.sql

-- Q041 Textbook source-book inventory.
-- Purpose/output: book titles and canonical competition/edition links.
-- Inputs: book (empty = all). Risk: READ ONLY; catalog lookup.
SELECT book_code,title,competition_id,edition_id,updated_at FROM pedagogy.source_book
WHERE :'book'='' OR book_code=:'book' ORDER BY book_code;
-- END Q041

-- Q042 Chapter-section mapping coverage.
-- Purpose/output: sections per chapter and missing canonical paper links.
-- Inputs: book. Risk: READ ONLY; source grouping.
SELECT book_code,chapter_number,count(*) AS sections,count(*) FILTER(WHERE paper_id IS NULL) AS unmapped
FROM pedagogy.chapter_section WHERE :'book'='' OR book_code=:'book'
GROUP BY book_code,chapter_number ORDER BY book_code,chapter_number;
-- END Q042

-- Q043 Exact problem provenance without document URLs.
-- Purpose/output: source numbering, chapter, page range and diagram requirements.
-- Inputs: problem_code. Risk: READ ONLY; canonical lookup; public corpus metadata.
SELECT p.canonical_code,r.book_code,r.source_problem_id,r.source_printed_problem_id,
 r.chapter_number,r.section_number,r.source_page_start,r.source_page_end,
 r.problem_requires_diagram,r.solution_requires_diagram
FROM core.problem p JOIN pedagogy.problem_source_ref r USING(problem_id)
WHERE p.canonical_code=:'problem_code';
-- END Q043

-- Q044 Problems with neither textbook provenance nor source URL.
-- Purpose/output: codes lacking both supported source channels.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT p.canonical_code FROM core.problem p WHERE nullif(btrim(p.source_url),'') IS NULL
AND NOT EXISTS(SELECT 1 FROM pedagogy.problem_source_ref r WHERE r.problem_id=p.problem_id)
ORDER BY p.canonical_code LIMIT :'row_limit'::int;
-- END Q044

-- Q045 Source page-range anomalies.
-- Purpose/output: source references with nonpositive or inverted page bounds.
-- Inputs: book, row_limit. Risk: READ ONLY; provenance scan.
SELECT book_code,source_problem_id,source_page_start,source_page_end FROM pedagogy.problem_source_ref
WHERE (:'book'='' OR book_code=:'book')
AND (source_page_start<=0 OR source_page_end<source_page_start OR source_page_end<=0)
ORDER BY book_code,source_problem_id LIMIT :'row_limit'::int;
-- END Q045

-- Q046 Required question diagrams absent from student-safe diagram metadata.
-- Purpose/output: canonical codes requiring a question diagram but lacking STUDENT_PROBLEM assets.
-- Inputs: book, row_limit. Risk: READ ONLY; anti-join; does not read bytes.
SELECT p.canonical_code,r.book_code FROM pedagogy.problem_source_ref r JOIN core.problem p USING(problem_id)
WHERE r.problem_requires_diagram AND (:'book'='' OR r.book_code=:'book')
AND NOT EXISTS(SELECT 1 FROM pedagogy.diagram d WHERE d.problem_id=r.problem_id AND d.visibility='STUDENT_PROBLEM')
ORDER BY p.canonical_code LIMIT :'row_limit'::int;
-- END Q046

-- Q047 Required solution diagrams absent from hidden assets.
-- Purpose/output: canonical codes requiring solution figures with no SOLUTION_HIDDEN record.
-- Inputs: book, row_limit. Risk: READ ONLY; hidden-asset metadata only; not a student-facing query.
SELECT p.canonical_code FROM pedagogy.problem_source_ref r JOIN core.problem p USING(problem_id)
WHERE r.solution_requires_diagram AND (:'book'='' OR r.book_code=:'book')
AND NOT EXISTS(SELECT 1 FROM pedagogy.diagram d WHERE d.problem_id=r.problem_id AND d.visibility='SOLUTION_HIDDEN')
ORDER BY p.canonical_code LIMIT :'row_limit'::int;
-- END Q047

-- Q048 Diagram validation coverage.
-- Purpose/output: counts by visibility, extraction method and validation label.
-- Inputs: book. Risk: READ ONLY; metadata aggregate.
SELECT visibility,extraction_method,validation_status,count(*) AS diagrams FROM pedagogy.diagram
WHERE :'book'='' OR book_code=:'book' GROUP BY visibility,extraction_method,validation_status
ORDER BY visibility,diagrams DESC,extraction_method,validation_status;
-- END Q048

-- Q049 Duplicate diagram-byte hashes across problems.
-- Purpose/output: shared SHA256 groups; potential reused figures, not necessarily an error.
-- Inputs: row_limit. Risk: READ ONLY; metadata grouping; no paths.
SELECT sha256,count(*) AS assets,count(DISTINCT problem_id) AS distinct_problems
FROM pedagogy.diagram WHERE nullif(btrim(sha256),'') IS NOT NULL GROUP BY sha256
HAVING count(DISTINCT problem_id)>1 ORDER BY assets DESC,sha256 LIMIT :'row_limit'::int;
-- END Q049

-- Q050 Diagram records with missing integrity or image linkage.
-- Purpose/output: IDs requiring hash/backfill or canonical image synchronization.
-- Inputs: row_limit. Risk: READ ONLY; metadata scan; local paths not emitted.
SELECT diagram_id,visibility,sha256 IS NULL AS missing_hash,problem_image_id IS NULL AS missing_image_link
FROM pedagogy.diagram WHERE nullif(btrim(sha256),'') IS NULL OR problem_image_id IS NULL
ORDER BY diagram_id LIMIT :'row_limit'::int;
-- END Q050

-- Q051 Cross-problem diagram/image link mismatches.
-- Purpose/output: diagram IDs whose linked canonical image belongs to another problem.
-- Inputs: none. Risk: READ ONLY; integrity join; no bytes or paths.
SELECT d.diagram_id,d.problem_id AS diagram_problem,i.problem_id AS image_problem
FROM pedagogy.diagram d JOIN core.problem_image i USING(problem_image_id)
WHERE d.problem_id<>i.problem_id ORDER BY d.diagram_id;
-- END Q051

-- Q052 Hidden solution diagrams linked to canonical problem images.
-- Purpose/output: metadata IDs to audit leakage guards; linkage alone is not proof of exposure.
-- Inputs: row_limit. Risk: READ ONLY; admin-only hidden metadata.
SELECT diagram_id,problem_id,problem_image_id FROM pedagogy.diagram
WHERE visibility='SOLUTION_HIDDEN' AND problem_image_id IS NOT NULL ORDER BY diagram_id LIMIT :'row_limit'::int;
-- END Q052

-- Q053 Source-aware canonical image coverage.
-- Purpose/output: image counts by source and number of represented problems.
-- Inputs: none. Risk: READ ONLY; metadata aggregate.
SELECT source,count(*) AS images,count(DISTINCT problem_id) AS problems FROM core.problem_image
GROUP BY source ORDER BY images DESC,source;
-- END Q053

-- Q054 Image ordinal holes.
-- Purpose/output: problems with noncontiguous recorded image ordinals, independent of zero/one base.
-- Inputs: row_limit. Risk: READ ONLY; metadata grouping.
SELECT problem_id,min(ordinal) AS first_ordinal,max(ordinal) AS last_ordinal,count(*) AS images
FROM core.problem_image GROUP BY problem_id HAVING max(ordinal)-min(ordinal)+1<>count(*)
ORDER BY problem_id LIMIT :'row_limit'::int;
-- END Q054

-- Q055 Unsafe source-URL shape.
-- Purpose/output: canonical codes with non-HTTP schemes or URL user-info; URL values never emitted.
-- Inputs: row_limit. Risk: READ ONLY; regex scan; no network calls.
SELECT canonical_code FROM core.problem WHERE nullif(btrim(source_url),'') IS NOT NULL
AND (source_url !~* '^https?://[^/[:space:]]+' OR source_url ~* '^https?://[^/]*@')
ORDER BY canonical_code LIMIT :'row_limit'::int;
-- END Q055

-- Q056 PDF source matching via REST canonical-code suffix convention.
-- Purpose/output: exact problem's download/parse/ingest linkage, without paths or URLs.
-- Inputs: problem_code. Risk: READ ONLY; matches problem_sources.py, no filesystem access.
SELECT p.canonical_code,s.paper_external_code,s.link_scope,s.download_status,s.parse_status,s.ingest_status
FROM core.problem p LEFT JOIN pipeline.pdf_source s
ON s.paper_external_code=regexp_replace(p.canonical_code,'_Q[0-9]+$','')
WHERE p.canonical_code=:'problem_code';
-- END Q056

-- Q057 PDF tracker rows not linked to canonical papers.
-- Purpose/output: external paper keys that may not yet have been loaded.
-- Inputs: row_limit. Risk: READ ONLY; natural-key anti-join.
SELECT s.paper_external_code,s.ingest_status FROM pipeline.pdf_source s
WHERE NOT EXISTS(SELECT 1 FROM core.paper p WHERE p.external_code=s.paper_external_code)
ORDER BY s.paper_external_code LIMIT :'row_limit'::int;
-- END Q057

-- Q058 Source solution references inconsistent with canonical ownership.
-- Purpose/output: source-solution identities with differing problem IDs.
-- Inputs: none. Risk: READ ONLY; ownership integrity join.
SELECT r.book_code,r.source_solution_id,r.problem_id AS source_problem,s.problem_id AS canonical_problem
FROM pedagogy.solution_source_ref r JOIN core.solution s USING(solution_id)
WHERE r.problem_id<>s.problem_id ORDER BY r.book_code,r.source_solution_id;
-- END Q058

-- Q059 Repeated printed numbering within textbook sections.
-- Purpose/output: source printed-number collisions, useful for editorial-marker reconciliation.
-- Inputs: book. Risk: READ ONLY; provenance aggregate.
SELECT book_code,chapter_number,section_number,source_printed_problem_id,count(*) AS occurrences
FROM pedagogy.problem_source_ref WHERE source_printed_problem_id IS NOT NULL
AND (:'book'='' OR book_code=:'book')
GROUP BY book_code,chapter_number,section_number,source_printed_problem_id HAVING count(*)>1
ORDER BY book_code,chapter_number,section_number,source_printed_problem_id;
-- END Q059

-- Q060 Section problem-count reconciliation.
-- Purpose/output: sections where recorded expected count differs from linked problem count.
-- Inputs: book. Risk: READ ONLY; source aggregate.
SELECT book_code,chapter_number,section_number,count(*) AS linked_problems,
 min(section_problem_count) AS min_declared,max(section_problem_count) AS max_declared
FROM pedagogy.problem_source_ref WHERE :'book'='' OR book_code=:'book'
GROUP BY book_code,chapter_number,section_number
HAVING min(section_problem_count)<>count(*) OR min(section_problem_count)<>max(section_problem_count)
ORDER BY book_code,chapter_number,section_number;
-- END Q060

ROLLBACK;
