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

## Privacy

Only canonical corpus knowledge should be broadly reusable. Learner-specific graph projections need access controls, deletion semantics, and clear retention policies.
