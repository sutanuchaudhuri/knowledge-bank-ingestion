\ir _session.sql

-- Q001 Competition inventory with edition/paper/problem coverage.
-- Purpose/output: one row per competition, distinct hierarchy counts (no join inflation).
-- Inputs: competition (external_code; empty = all), row_limit. Risk: READ ONLY; corpus scan.
SELECT c.external_code, c.name, count(DISTINCT e.edition_id) AS editions,
       count(DISTINCT p.paper_id) AS papers, count(q.problem_id) AS problems
FROM core.competition c LEFT JOIN core.competition_edition e USING (competition_id)
LEFT JOIN core.paper p USING (edition_id) LEFT JOIN core.problem q USING (paper_id)
WHERE :'competition' = '' OR c.external_code = :'competition'
GROUP BY c.competition_id ORDER BY problems DESC, c.competition_id LIMIT :'row_limit'::int;
-- END Q001

-- Q002 Edition inventory including undated textbook editions.
-- Purpose/output: edition identities and paper counts; NULL year is legitimate after migration 010.
-- Inputs: competition, row_limit. Risk: READ ONLY; hierarchy scan.
SELECT c.external_code, e.edition_id, e.year, e.season, e.edition_label, count(p.paper_id) AS papers
FROM core.competition c JOIN core.competition_edition e USING (competition_id)
LEFT JOIN core.paper p USING (edition_id)
WHERE :'competition' = '' OR c.external_code = :'competition'
GROUP BY c.external_code, e.edition_id ORDER BY c.external_code, e.year DESC NULLS LAST, e.edition_id
LIMIT :'row_limit'::int;
-- END Q002

-- Q003 Paper roster and declared versus ingested question count.
-- Purpose/output: paper rows with actual count and actual-minus-declared delta.
-- Inputs: competition, row_limit. Risk: READ ONLY; problem aggregation.
SELECT p.paper_id, p.external_code, p.paper_code, p.question_count,
       count(q.problem_id) AS actual_questions, count(q.problem_id)-p.question_count AS count_delta
FROM core.paper p JOIN core.competition_edition e USING (edition_id)
JOIN core.competition c USING (competition_id) LEFT JOIN core.problem q USING (paper_id)
WHERE :'competition' = '' OR c.external_code = :'competition'
GROUP BY p.paper_id ORDER BY p.external_code NULLS LAST, p.paper_id LIMIT :'row_limit'::int;
-- END Q003

-- Q004 Empty competitions.
-- Purpose/output: competitions without any edition; candidates for upstream registry investigation.
-- Inputs: none. Risk: READ ONLY; anti-join.
SELECT c.external_code, c.name FROM core.competition c
WHERE NOT EXISTS (SELECT 1 FROM core.competition_edition e WHERE e.competition_id=c.competition_id)
ORDER BY c.external_code, c.competition_id;
-- END Q004

-- Q005 Editions without papers.
-- Purpose/output: edition identities where hierarchy ingestion has not reached the paper level.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT e.edition_id, c.external_code, e.year, e.edition_label
FROM core.competition_edition e JOIN core.competition c USING (competition_id)
WHERE NOT EXISTS (SELECT 1 FROM core.paper p WHERE p.edition_id=e.edition_id)
ORDER BY c.external_code, e.edition_id LIMIT :'row_limit'::int;
-- END Q005

-- Q006 Empty papers despite nonzero declared questions.
-- Purpose/output: paper identities expected to contain content but containing none.
-- Inputs: row_limit. Risk: READ ONLY; anti-join.
SELECT p.paper_id, p.external_code, p.question_count FROM core.paper p
WHERE p.question_count > 0 AND NOT EXISTS (SELECT 1 FROM core.problem q WHERE q.paper_id=p.paper_id)
ORDER BY p.question_count DESC, p.paper_id LIMIT :'row_limit'::int;
-- END Q006

-- Q007 Corpus growth by UTC month.
-- Purpose/output: problem ingestion counts, not competition event dates.
-- Inputs: days. Risk: READ ONLY; bounded timestamp scan.
SELECT date_trunc('month', created_at) AS month, count(*) AS problems
FROM core.problem WHERE created_at >= now()-make_interval(days => :'days'::int)
GROUP BY 1 ORDER BY 1;
-- END Q007

-- Q008 Distribution of competition levels and countries.
-- Purpose/output: corpus catalog coverage by recorded organizational dimensions.
-- Inputs: none. Risk: READ ONLY; small catalog aggregate.
SELECT country, level, count(*) AS competitions, count(DISTINCT organization) AS organizations
FROM core.competition GROUP BY country, level ORDER BY competitions DESC, country, level;
-- END Q008

-- Q009 Unkeyed catalog records.
-- Purpose/output: competition/paper rows missing external natural keys (may be legitimate manual records).
-- Inputs: row_limit. Risk: READ ONLY; catalog scan.
SELECT 'competition' AS entity, competition_id AS id, name AS label
FROM core.competition WHERE nullif(btrim(external_code),'') IS NULL
UNION ALL SELECT 'paper', paper_id, paper_code FROM core.paper WHERE nullif(btrim(external_code),'') IS NULL
ORDER BY entity, id LIMIT :'row_limit'::int;
-- END Q009

-- Q010 Same-named competition records.
-- Purpose/output: normalized name collisions; organization may legitimately distinguish them.
-- Inputs: none. Risk: READ ONLY; normalized catalog aggregation.
SELECT lower(btrim(name)) AS normalized_name, count(*) AS records,
       array_agg(external_code ORDER BY external_code) AS external_codes
FROM core.competition GROUP BY lower(btrim(name)) HAVING count(*)>1 ORDER BY records DESC, normalized_name;
-- END Q010

-- Q011 Nullable edition-key collisions.
-- Purpose/output: duplicated edition identity despite nullable UNIQUE-key components.
-- Inputs: none. Risk: READ ONLY; edition aggregate.
SELECT competition_id, year, season, edition_label, count(*) AS copies
FROM core.competition_edition GROUP BY competition_id, year, season, edition_label
HAVING count(*)>1 ORDER BY copies DESC, competition_id;
-- END Q011

-- Q012 Year gaps within a competition's observed date range.
-- Purpose/output: missing intermediate years; not proof an annual contest existed.
-- Inputs: competition. Risk: READ ONLY; bounded 1900–2200 series.
WITH bounds AS (
 SELECT c.external_code, c.competition_id, min(e.year) AS lo, max(e.year) AS hi
 FROM core.competition c JOIN core.competition_edition e USING (competition_id)
 WHERE :'competition'='' OR c.external_code=:'competition' GROUP BY c.competition_id
)
SELECT b.external_code, g.year AS missing_year FROM bounds b
CROSS JOIN LATERAL generate_series(b.lo,b.hi) AS g(year)
WHERE NOT EXISTS (SELECT 1 FROM core.competition_edition e
                  WHERE e.competition_id=b.competition_id AND e.year=g.year)
ORDER BY b.external_code, g.year;
-- END Q012

-- Q013 Official versus unofficial paper coverage.
-- Purpose/output: paper and problem counts by official flag and paper type.
-- Inputs: none. Risk: READ ONLY; hierarchy aggregate.
SELECT p.official, p.paper_type, count(DISTINCT p.paper_id) AS papers, count(q.problem_id) AS problems
FROM core.paper p LEFT JOIN core.problem q USING (paper_id)
GROUP BY p.official,p.paper_type ORDER BY papers DESC, p.paper_type;
-- END Q013

-- Q014 Paper duration/score metadata anomalies.
-- Purpose/output: nonpositive durations, negative scores or negative question counts.
-- Inputs: row_limit. Risk: READ ONLY; paper scan.
SELECT paper_id, external_code, duration_minutes, max_score, question_count FROM core.paper
WHERE duration_minutes<=0 OR max_score<0 OR question_count<0
ORDER BY paper_id LIMIT :'row_limit'::int;
-- END Q014

-- Q015 Problem status by competition.
-- Purpose/output: active/inactive lifecycle mix without reading statements.
-- Inputs: competition. Risk: READ ONLY; hierarchy aggregate.
SELECT c.external_code,q.status,count(*) AS problems FROM core.problem q
JOIN core.paper p USING(paper_id) JOIN core.competition_edition e USING(edition_id)
JOIN core.competition c USING(competition_id)
WHERE :'competition'='' OR c.external_code=:'competition'
GROUP BY c.external_code,q.status ORDER BY c.external_code,q.status;
-- END Q015

-- Q016 Paper numbering bounds.
-- Purpose/output: min/max/count numbering; a range wider than count suggests holes.
-- Inputs: row_limit. Risk: READ ONLY; problem grouping.
SELECT p.external_code,p.paper_id,min(q.problem_number) AS first_number,
       max(q.problem_number) AS last_number,count(q.problem_id) AS questions
FROM core.paper p JOIN core.problem q USING(paper_id)
GROUP BY p.paper_id ORDER BY p.external_code NULLS LAST,p.paper_id LIMIT :'row_limit'::int;
-- END Q016

-- Q017 Missing declared question slots.
-- Purpose/output: expected 1..question_count slots absent from each paper; abnormal huge counts are excluded.
-- Inputs: competition, row_limit. Risk: READ ONLY; series capped at 1000 slots per paper.
SELECT p.external_code,p.paper_id,n.problem_number
FROM core.paper p JOIN core.competition_edition e USING(edition_id)
JOIN core.competition c USING(competition_id)
CROSS JOIN LATERAL generate_series(1,least(p.question_count,1000)) n(problem_number)
WHERE p.question_count BETWEEN 1 AND 1000 AND (:'competition'='' OR c.external_code=:'competition')
AND NOT EXISTS(SELECT 1 FROM core.problem q WHERE q.paper_id=p.paper_id AND q.problem_number=n.problem_number)
ORDER BY p.paper_id,n.problem_number LIMIT :'row_limit'::int;
-- END Q017

-- Q018 Out-of-range problem numbering.
-- Purpose/output: nonpositive or beyond-declared slots; undeclared maximum is not assumed.
-- Inputs: row_limit. Risk: READ ONLY; problem/paper join.
SELECT q.canonical_code,q.problem_number,p.question_count FROM core.problem q JOIN core.paper p USING(paper_id)
WHERE q.problem_number<1 OR (p.question_count>0 AND q.problem_number>p.question_count)
ORDER BY q.canonical_code LIMIT :'row_limit'::int;
-- END Q018

-- Q019 Recent source modifications.
-- Purpose/output: changed problem IDs and age since ingestion; no body content.
-- Inputs: days, row_limit. Risk: READ ONLY; timestamp-filtered scan.
SELECT canonical_code,created_at,updated_at,updated_at-created_at AS modification_lag
FROM core.problem WHERE updated_at>created_at AND updated_at>=now()-make_interval(days => :'days'::int)
ORDER BY updated_at DESC,problem_id LIMIT :'row_limit'::int;
-- END Q019

-- Q020 Largest competition-edition workloads.
-- Purpose/output: edition-sized problem volumes to plan validation batches.
-- Inputs: row_limit. Risk: READ ONLY; hierarchy aggregation.
SELECT c.external_code,e.edition_id,e.year,count(*) AS problems
FROM core.competition c JOIN core.competition_edition e USING(competition_id)
JOIN core.paper p USING(edition_id) JOIN core.problem q USING(paper_id)
GROUP BY c.external_code,e.edition_id ORDER BY problems DESC,e.edition_id LIMIT :'row_limit'::int;
-- END Q020

ROLLBACK;
