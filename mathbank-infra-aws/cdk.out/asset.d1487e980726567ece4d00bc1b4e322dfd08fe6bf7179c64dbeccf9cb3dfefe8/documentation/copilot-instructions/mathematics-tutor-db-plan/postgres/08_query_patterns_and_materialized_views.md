# PostgreSQL 08 — Query Patterns and Materialized Views

## Representative questions

The schema should efficiently answer queries such as:

- All AMC 10 geometry problems from 2010–2025 involving cyclic quadrilaterals.
- AIME problems that require modular arithmetic and have a Chinese Remainder Theorem solution.
- Problems related to a given concept but not using a particular technique.
- Concepts most frequently paired with generating functions.
- Problems awaiting taxonomy review.
- Archive papers requested but not successfully completed.

## Curated problem view

Create `api.problem_summary_v` joining problem, paper, edition, competition, accepted concepts, accepted techniques, and source status. This gives the API a stable contract independent of physical table refinements.

## Materialized statistics

Potential materialized views:

- `knowledge.mv_problem_taxonomy_flat`
- `knowledge.mv_concept_problem_counts`
- `knowledge.mv_technique_pair_frequency`
- `pipeline.mv_run_progress`
- `core.mv_archive_coverage`

Refresh incrementally when possible; otherwise refresh after a batch.

## Example taxonomy query

```sql
SELECT p.canonical_code, p.statement_text
FROM core.problem p
JOIN knowledge.problem_concept pc ON pc.problem_id = p.problem_id
JOIN knowledge.concept c ON c.concept_id = pc.concept_id
JOIN core.paper pa ON pa.paper_id = p.paper_id
JOIN core.competition_edition e ON e.edition_id = pa.edition_id
JOIN core.competition co ON co.competition_id = e.competition_id
WHERE co.name = 'AMC 10'
  AND e.year BETWEEN 2010 AND 2025
  AND c.slug = 'cyclic-quadrilateral'
  AND pc.review_status = 'ACCEPTED'
ORDER BY e.year, pa.paper_code, p.problem_number;
```

## Coverage query

A coverage dashboard should compare the expected archive inventory to actual ingested/validated papers. Store the expected inventory explicitly; do not infer missing items from gaps in imported data.

## Avoid premature OLAP complexity

PostgreSQL materialized views are sufficient initially. Introduce a warehouse only when query volume, retention, or analytics workload proves that need.
