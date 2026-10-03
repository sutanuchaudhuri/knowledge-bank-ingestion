# Graph 04 — Query Patterns and Cypher

## Prerequisite neighborhood

```cypher
MATCH path=(p:Concept {canonical_id:$id})<-[:PREREQUISITE_OF*1..4]-(pre:Concept)
RETURN path;
```

## Problems joining two concepts

```cypher
MATCH (a:Concept {slug:$a})<-[:TESTS]-(p:Problem)-[:TESTS]->(b:Concept {slug:$b})
RETURN p.canonical_id, p.code;
```

## Techniques used across domains

```cypher
MATCH (t:Technique)<-[:USES_TECHNIQUE]-(p:Problem)-[:TESTS]->(c:Concept)
WITH t, collect(DISTINCT c.area) AS areas, count(DISTINCT p) AS n
WHERE size(areas) >= 3
RETURN t.name, areas, n
ORDER BY n DESC;
```

## Alternative solution routes

```cypher
MATCH (p:Problem)<-[:SOLVES]-(s:Solution)-[:HAS_STEP]->(:SolutionStep)-[:USES]->(t:Technique)
RETURN s.canonical_id, collect(DISTINCT t.name) AS techniques;
```

## Graph query contract

Cypher should live behind a service/repository layer for production. Do not expose arbitrary Cypher to ordinary clients. Define named traversals with bounded depth and explicit limits.
