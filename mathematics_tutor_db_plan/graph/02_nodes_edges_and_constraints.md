# Graph 02 — Nodes, Edges, and Constraints

## Node labels

### Implemented (corpus graph — see `mathbank-graph/etl/project_from_postgres.py`)

| Label | Projected from | Key properties (beyond `canonical_id`) |
|---|---|---|
| `Competition` | `core.competition` | `external_code`, `name`, `level` |
| `Paper` | `core.paper` | `external_code`, `paper_code`, `question_count`, `year` |
| `Problem` | `core.problem` | `canonical_code`, `problem_number`, `official_answer`, `source_url`, `difficulty_band`, `classification_status` |
| `Solution` | `core.solution` | `solution_kind`, `revision`, `verification_status` — **not** `body_markdown`; the full text stays in PostgreSQL and is fetched by `canonical_id` |
| `Concept` | `knowledge.concept` | `slug`, `name`, `level` |
| `Technique` | `knowledge.technique` | `slug`, `name` |

Every node carries `canonical_id` equal to the PostgreSQL UUID of its source row.

### Planned / not yet implemented

These labels appear in earlier design discussion but have no projection code yet. Treat them as future work, not current schema:

- `SolutionStep` (would project from `core.solution_step`, which exists in PostgreSQL but is not yet populated or projected)
- `TaxonomyNode`, `Theorem`, `Formula`, `Misconception`
- `Learner`, `Attempt` — explicitly a **separate** learner projection, never merged into the shared corpus graph (see `graph/06_similarity_misconceptions_and_student_state.md`)

## Edge types

### Implemented (corpus graph)

| Edge | Direction | Properties |
|---|---|---|
| `HAS_PAPER` | `(Competition)-->(Paper)` | — |
| `HAS_PROBLEM` | `(Paper)-->(Problem)` | — |
| `HAS_SOLUTION` | `(Problem)-->(Solution)` | — |
| `TESTS` | `(Problem)-->(Concept)` | `role`, `confidence` |
| `USES_TECHNIQUE` | `(Problem)-->(Technique)` | `role`, `confidence` |
| `CONCEPT_RELATION` | `(Concept)-->(Concept)` | `relation_type` (e.g. `PREREQUISITE_OF`, `GENERALIZES` — a free-text value from `knowledge.concept_relation.relation_type`, not a distinct edge type per value), `strength` |

### Planned / not yet implemented

- `(Solution)-[:HAS_STEP]->(SolutionStep)-[:USES]->(Technique)` — depends on `core.solution_step` being populated
- `(Technique)-[:APPLIES_TO]->(Concept)`
- `(Misconception)-[:CONFUSES]->(Concept)`
- `(Problem)-[:VARIANT_OF]->(Problem)` and the other similarity edges in `graph/06_similarity_misconceptions_and_student_state.md`

Note: earlier drafts of this document showed `(Solution)-[:SOLVES]->(Problem)` with the arrow reversed from what's implemented — the actual direction is `(Problem)-[:HAS_SOLUTION]->(Solution)`, matching how `core.solution` references `core.problem`.

## Constraints

The ETL creates one uniqueness constraint per implemented label, all keyed on `canonical_id`:

```cypher
CREATE CONSTRAINT competition_id IF NOT EXISTS FOR (n:Competition) REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT paper_id       IF NOT EXISTS FOR (n:Paper)       REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT problem_id     IF NOT EXISTS FOR (n:Problem)     REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT concept_id     IF NOT EXISTS FOR (n:Concept)     REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT technique_id   IF NOT EXISTS FOR (n:Technique)   REQUIRE n.canonical_id IS UNIQUE;
CREATE CONSTRAINT solution_id    IF NOT EXISTS FOR (n:Solution)    REQUIRE n.canonical_id IS UNIQUE;
```

Add an equivalent constraint for any new label before its first projection run.

## Relationship properties

Include only properties required for traversal/filtering, such as confidence, role, review status, and projection version. Rich provenance remains in PostgreSQL and can be fetched by canonical IDs.

## Avoid graph duplication

A concept should not be copied per taxonomy path. Use one Concept node with multiple edges when it belongs in multiple contexts.

