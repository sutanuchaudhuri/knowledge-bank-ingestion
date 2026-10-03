# Graph 02 — Nodes, Edges, and Constraints

## Node labels

Recommended node labels:

- `Competition`
- `Paper`
- `Problem`
- `Solution`
- `SolutionStep`
- `TaxonomyNode`
- `Concept`
- `Technique`
- `Theorem`
- `Formula`
- `Misconception`
- optionally `Learner` and `Attempt` in a separate learner projection

Every node carries `canonical_id` equal to the PostgreSQL UUID plus selected denormalized display properties.

## Edge types

Examples:

- `(Paper)-[:HAS_PROBLEM]->(Problem)`
- `(Problem)-[:TESTS {role, confidence}]->(Concept)`
- `(Problem)-[:USES_TECHNIQUE]->(Technique)`
- `(Concept)-[:PREREQUISITE_OF]->(Concept)`
- `(Concept)-[:GENERALIZES]->(Concept)`
- `(Technique)-[:APPLIES_TO]->(Concept)`
- `(Solution)-[:SOLVES]->(Problem)`
- `(Solution)-[:HAS_STEP]->(SolutionStep)`
- `(SolutionStep)-[:USES]->(Technique)`
- `(Misconception)-[:CONFUSES]->(Concept)`
- `(Problem)-[:VARIANT_OF]->(Problem)`

## Constraints

```cypher
CREATE CONSTRAINT concept_id IF NOT EXISTS
FOR (n:Concept) REQUIRE n.canonical_id IS UNIQUE;

CREATE CONSTRAINT problem_id IF NOT EXISTS
FOR (n:Problem) REQUIRE n.canonical_id IS UNIQUE;
```

Create equivalent constraints for all durable labels.

## Relationship properties

Include only properties required for traversal/filtering, such as confidence, role, review status, and projection version. Rich provenance remains in PostgreSQL and can be fetched by canonical IDs.

## Avoid graph duplication

A concept should not be copied per taxonomy path. Use one Concept node with multiple edges when it belongs in multiple contexts.
