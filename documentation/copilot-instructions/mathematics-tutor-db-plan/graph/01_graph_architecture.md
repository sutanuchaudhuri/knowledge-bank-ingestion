# Graph 01 — Graph Architecture

## Purpose

The graph layer answers relationship questions that are awkward or expensive in relational form: prerequisite chains, concept neighborhoods, alternative solution routes, misconception paths, and learner-specific learning sequences.

## Source-of-truth rule

The graph is a **derived projection**. Nodes and relationships are generated from accepted or intentionally included PostgreSQL assertions. Graph-local discoveries must be written back to PostgreSQL as candidate assertions before becoming durable knowledge.

## Candidate technology

Neo4j is a strong initial choice because Cypher is expressive, constraints are mature, and algorithms are available through Graph Data Science. The logical model should remain portable to other property graphs.

## Projection families

Maintain at least two projections:

- **Corpus graph** — curated facts only, used by tutor/retrieval.
- **Exploration graph** — may include unreviewed/model-generated edges, clearly labeled by review status.

## Core graph questions

- What prerequisites lead to this concept?
- Which problems jointly exercise concepts A and B?
- What techniques bridge two otherwise distant topics?
- What is the shortest prerequisite path from learner mastery to target problem?
- Which misconceptions are linked to a failed step?
- What alternative solution families exist for the same problem?
