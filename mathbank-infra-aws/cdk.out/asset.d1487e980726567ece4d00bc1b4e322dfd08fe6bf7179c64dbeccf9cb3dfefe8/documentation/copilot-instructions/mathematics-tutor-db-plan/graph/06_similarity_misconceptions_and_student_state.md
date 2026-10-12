# Graph 06 — Similarity, Misconceptions, and Learner State

## Similarity types

Do not use one undifferentiated `SIMILAR_TO` edge. Separate:

- `STRUCTURALLY_SIMILAR_TO`
- `SAME_CORE_IDEA_AS`
- `VARIANT_OF`
- `SOLUTION_ANALOGUE_OF`
- `CONFUSABLE_WITH`

Each requires provenance and a score/threshold method.

## Misconception graph

Model misconceptions as entities when recurring and pedagogically meaningful. Link them to concepts, techniques, and characteristic wrong steps.

Example:

`(Misconception:AssumesIndependentEvents)-[:AFFECTS]->(Concept:ConditionalProbability)`

## Learner graph

Keep personal learner data in a separate projection or database. The shared knowledge graph should not be polluted with learner-specific state.

Possible edges:

- `MASTERED`
- `PRACTICED`
- `STRUGGLED_WITH`
- `MADE_ERROR`

These are derived from learner attempts in PostgreSQL and can expire/decay.

### Concrete node/edge attributes (detailed design)

See [`../agent/18_future_student_profile_and_mastery.md`](../agent/18_future_student_profile_and_mastery.md)
for the full design: a `learner.*` Postgres schema (system of record for
`student_profile`/`attempt`/`concept_mastery`/`technique_mastery`), the
mastery-score formula, and an end-to-end Mermaid flow from a submitted
attempt to a mastery-aware agent answer. Summary of the graph-side additions:

| Element | Kind | Properties | Constraint |
|---|---|---|---|
| `Student` | node | `canonical_id` (no PII — name/email stay in Postgres) | `REQUIRE n.canonical_id IS UNIQUE` |
| `MASTERED` | edge, `(Student)->(Concept\|Technique)` | `score`, `trend`, `as_of` | projected only when `score >= MASTERY_THRESHOLD` |
| `STRUGGLES_WITH` | edge, `(Student)->(Concept\|Technique)` | `score`, `trend`, `as_of` | projected only when `score < STRUGGLE_THRESHOLD` |
| `ATTEMPTED` | edge, `(Student)->(Problem)` | `correctness`, `attempt_count`, `last_attempt_at` | aggregated per (student, problem) |
| `MADE_ERROR` | edge, `(Student)->(Misconception)` | `count`, `last_seen_at` | future — needs error-pattern classification |

## Privacy

Only canonical corpus knowledge should be broadly reusable. Learner-specific graph projections need access controls, deletion semantics, and clear retention policies.
