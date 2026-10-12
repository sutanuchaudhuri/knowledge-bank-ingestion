# Graph 04 — Query Patterns and Cypher

## Prerequisite neighborhood

`PREREQUISITE_OF` is a `relation_type` value on the generic `CONCEPT_RELATION` edge
(see `graph/02_nodes_edges_and_constraints.md`), not its own edge type:

```cypher
MATCH path=(p:Concept {canonical_id:$id})<-[:CONCEPT_RELATION {relation_type:'PREREQUISITE_OF'}*1..4]-(pre:Concept)
RETURN path;
```

## Problems joining two concepts

```cypher
MATCH (a:Concept {slug:$a})<-[:TESTS]-(p:Problem)-[:TESTS]->(b:Concept {slug:$b})
RETURN p.canonical_id, p.canonical_code;
```

## Techniques used across domains

```cypher
MATCH (t:Technique)<-[:USES_TECHNIQUE]-(p:Problem)-[:TESTS]->(c:Concept)
WITH t, collect(DISTINCT c.name) AS concepts, count(DISTINCT p) AS n
WHERE size(concepts) >= 3
RETURN t.name, concepts, n
ORDER BY n DESC;
```

## Full problem detail (competition → paper → problem → solution)

```cypher
MATCH (comp:Competition)-[:HAS_PAPER]->(pa:Paper)-[:HAS_PROBLEM]->(p:Problem {canonical_code:$code})
OPTIONAL MATCH (p)-[:HAS_SOLUTION]->(s:Solution)
RETURN comp.name, pa.external_code, p, collect(s) AS solutions;
```

`Solution.body_markdown` is not projected — fetch the full text from PostgreSQL by
`s.canonical_id` once the solution node(s) of interest are known.

## Graph query contract

Cypher should live behind a service/repository layer for production. Do not expose arbitrary Cypher to ordinary clients. Define named traversals with bounded depth and explicit limits.

