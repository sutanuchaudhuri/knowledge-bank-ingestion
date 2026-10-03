# PostgreSQL 04 — Taxonomy and Knowledge Model

## Goal

Represent mathematics at several levels without forcing every question into one rigid tree.

Recommended hierarchy:

- L0 Domain: Mathematics
- L1 Area: Algebra, Geometry, Number Theory, Combinatorics, Probability, Calculus
- L2 Topic: Polynomials, Similarity, Modular Arithmetic, Counting
- L3 Subtopic: Vieta, Power of a Point, CRT, Stars and Bars
- L4 Concept: a precise mathematical idea
- L5 Technique: a reusable problem-solving method
- L6 Pattern: recognizable structural cue
- L7 Misconception / failure mode

The first four may form a curated hierarchy. Concepts and techniques should support a graph/DAG, not only parent-child trees.

## Tables

### `knowledge.taxonomy_node`

Fields: `taxonomy_node_id`, `level_code`, `slug`, `name`, `definition`, `status`.

### `knowledge.taxonomy_edge`

Fields: `parent_id`, `child_id`, `edge_type`, `ordinal`. Use `edge_type='IS_A'` for hierarchy while allowing `RELATED_TO` or `CROSS_LISTED`.

### `knowledge.concept`

Atomic knowledge units such as "Vieta relation between roots and coefficients".

### `knowledge.technique`

Procedural strategy such as "introduce symmetric sums" or "reflect across angle bisector".

### `knowledge.problem_concept` and `knowledge.problem_technique`

Allow multiple concepts/techniques, weighted by role and confidence.

## Assertion model

Every nontrivial classification should include:

- `assertion_source`: HUMAN, IMPORTED, RULE, MODEL
- `asserted_by`: user/model/process identifier
- `model_name` if applicable
- `model_version`
- `schema_version`
- `confidence`
- `review_status`: PENDING, ACCEPTED, REJECTED, SUPERSEDED
- `evidence_locator_id`

Do not turn model confidence directly into truth. A high-confidence machine assertion can still be pending review.

## Prerequisites

Store direct prerequisites only. Transitive prerequisite closure can be computed or materialized.

Important edge types:

- `PREREQUISITE_OF`
- `SUPPORTS`
- `GENERALIZES`
- `SPECIAL_CASE_OF`
- `OFTEN_COMBINED_WITH`
- `COMMONLY_CONFUSED_WITH`
- `ALTERNATIVE_TO`

## Difficulty

Do not collapse difficulty into one field. Keep dimensions such as:

- contest-position proxy
- empirical solve rate
- curated difficulty
- estimated prerequisite depth
- algebraic load
- insight novelty
- computational burden

This allows the tutor to select problems for different learner profiles rather than relying on a single scalar.
