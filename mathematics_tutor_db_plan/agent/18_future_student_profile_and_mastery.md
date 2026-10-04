> **Status**: fully deferred — no `STUDENT` principal, no `learner.*` schema,
> no mastery-aware retrieval exists in `mathbank-rest`/`mathbank-agent`/
> `mathbank-graph` today. This file is the forward-looking design for the
> next bounded context, expanding on the original deferral note in
> `mathematics_tutor_db_plan/graph/06_similarity_misconceptions_and_student_state.md`
> with concrete attributes and an end-to-end mastery-extraction pipeline.

# 18 — Future Student Profile and Mastery Extraction

## 1. Explicitly deferred

V1 does not contain a student identity or attempt model.

Do not add placeholder nullable `student_id` fields throughout every API merely "for the future."

Instead add personalization later as a new bounded context.

---

## 2. Future principal classes

Later:

```text
ANONYMOUS
STUDENT
ADMIN
```

Potential additional entities:

```text
student_profile
student_attempt
student_problem_state
student_concept_state
student_preference
learning_goal
assignment
```

---

## 3. End-to-end flow: from a solved problem to a grounded, mastery-aware answer

```mermaid
flowchart TD
    A[Student submits an attempt<br/>in mathbank-web UI] --> B[POST /v1/learner/attempts<br/>mathbank-rest]
    B --> C[(core.problem / learner.attempt<br/>Postgres — system of record)]
    C --> D[Nightly / on-demand<br/>mastery aggregation job]
    D --> E[(learner.concept_mastery<br/>materialized view or table)]
    E --> F[mathbank-graph project-remote<br/>projects mastery onto the graph]
    F --> G[(Neo4j: Student)-MASTERED/STRUGGLES_WITH->(Concept)]
    E --> H[mathbank-rest: GET /v1/learner/mastery/summary]
    G --> H
    H --> I[ADK agent tool:<br/>get_student_mastery_summary]
    I --> J[Agent plans retrieval:<br/>exclude mastered concepts,<br/>prioritize weak concepts,<br/>target difficulty band]
    J --> K[search_questions with<br/>personalization policy]
    K --> L[mathbank-rest hybrid RRF search<br/>filtered/boosted by mastery]
    L --> M[Grounded, personalized answer<br/>+ recommended practice set]

    style C fill:#e8f0fe
    style E fill:#e8f0fe
    style G fill:#fce8e6
    style M fill:#e6f4ea
```

Key properties of this flow:

- **Postgres (`learner.*`) is the system of record for attempts** — the graph
  never originates mastery data, matching the governing rule in the root
  `README.md`: *"nothing exists only in the graph."*
- **Mastery is computed, not stored raw** — a scheduled/on-demand aggregation
  job turns raw attempts into a decayed, per-concept mastery score (see
  §5), the same pattern already used for `search.embedding`/`search.chunk`
  derived from `core.problem`/`core.solution`.
- **The graph projection is additive, not required** — `mathbank-rest` can
  serve mastery-aware retrieval straight from Postgres; the Neo4j projection
  only becomes necessary once multi-hop queries are needed (e.g. "what
  prerequisite concepts does this student need before attempting X").

---

## 4. New Postgres schema — `learner.*`

Mirrors the `core.*`/`knowledge.*`/`search.*` schema convention already used
in `mathbank-db/sql/001_schema.sql` — additive, nullable-FK-safe, idempotent
migrations.

```sql
CREATE SCHEMA IF NOT EXISTS learner;

CREATE TABLE learner.student_profile (
    student_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    external_auth_subject text UNIQUE,  -- maps to the gateway/IdP's `sub` claim
    display_name text,
    created_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'ACTIVE'  -- ACTIVE | SUSPENDED | DELETED
);

CREATE TABLE learner.attempt (
    attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id uuid NOT NULL REFERENCES learner.student_profile,
    problem_id uuid NOT NULL REFERENCES core.problem,
    started_at timestamptz,
    submitted_at timestamptz NOT NULL DEFAULT now(),
    submitted_answer text,
    correctness text NOT NULL,       -- CORRECT | INCORRECT | PARTIAL | SKIPPED
    time_spent_seconds int,
    hints_used int NOT NULL DEFAULT 0,
    self_reported_confidence text,   -- LOW | MEDIUM | HIGH
    solution_viewed boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_attempt_student ON learner.attempt(student_id, submitted_at DESC);
CREATE INDEX idx_attempt_problem ON learner.attempt(problem_id);

-- Derived, recomputed by the mastery aggregation job — not written directly
-- by the application. One row per (student, concept).
CREATE TABLE learner.concept_mastery (
    student_id uuid NOT NULL REFERENCES learner.student_profile,
    concept_id uuid NOT NULL REFERENCES knowledge.concept,
    mastery_score numeric(5,4) NOT NULL,     -- 0.0–1.0, see §5 formula
    attempts_count int NOT NULL,
    correct_count int NOT NULL,
    last_attempt_at timestamptz NOT NULL,
    decayed_at timestamptz NOT NULL DEFAULT now(),  -- when this row was last recomputed
    trend text,                               -- IMPROVING | STABLE | REGRESSING
    PRIMARY KEY (student_id, concept_id)
);

-- Same shape for techniques (procedural mastery is tracked separately from
-- conceptual mastery — a student can know a concept but misapply a technique).
CREATE TABLE learner.technique_mastery (
    student_id uuid NOT NULL REFERENCES learner.student_profile,
    technique_id uuid NOT NULL REFERENCES knowledge.technique,
    mastery_score numeric(5,4) NOT NULL,
    attempts_count int NOT NULL,
    correct_count int NOT NULL,
    last_attempt_at timestamptz NOT NULL,
    decayed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (student_id, technique_id)
);
```

`learner.student_profile.external_auth_subject` is intentionally the *only*
link to real identity — `attempt`/`concept_mastery` reference the internal
`student_id` UUID, so deleting a student (GDPR-style erasure) is one
`student_profile` row update + cascade, not a corpus-wide scrub.

---

## 5. Mastery score computation

Recommended formula — a time-decayed weighted accuracy, not a raw percentage:

```text
mastery_score(student, concept) =
    Σ over attempts a on problems testing `concept`:
        correctness_weight(a) * recency_weight(a) * difficulty_weight(a)
    ────────────────────────────────────────────────────────────────────
    Σ over same attempts: recency_weight(a) * difficulty_weight(a)

where:
  correctness_weight(a) = 1.0 if CORRECT, 0.3 if PARTIAL, 0.0 if INCORRECT
  recency_weight(a)     = exp(-days_since(a.submitted_at) / HALF_LIFE_DAYS)
  difficulty_weight(a)  = 1.0 + 0.5 * normalized_difficulty(a.problem)
```

- `HALF_LIFE_DAYS` (e.g. 30-60) lets old attempts decay — mastery should
  reflect *current* skill, not lifetime history.
- `difficulty_weight` means correctly solving a hard problem counts more
  than an easy one toward the same concept, using `core.problem.difficulty_band`.
- A problem tests multiple concepts (`knowledge.problem_concept`, one row
  per `role` — `PRIMARY`/`SECONDARY`) — weight each concept's contribution
  by that row's `confidence`/`role`, so a `SECONDARY`-tagged concept moves
  more slowly than the `PRIMARY` one.

`trend` (`IMPROVING`/`STABLE`/`REGRESSING`) compares the mastery score
computed over the last N attempts vs the previous N — useful for the agent
to say *"you've been improving at combinatorics"* rather than just a number.

---

## 6. New graph attributes (Neo4j) — additive, in a **separate learner projection**

Per the existing design principle in `graph/06_similarity_misconceptions_and_student_state.md`
("Keep personal learner data in a separate projection... the shared
knowledge graph should not be polluted with learner-specific state"), these
nodes/edges belong in a **second Neo4j database** (or at minimum a clearly
labeled, separately-access-controlled subgraph), never merged into the
corpus-wide `Concept`/`Problem`/`Technique` nodes that anonymous retrieval
also reads.

### New node label

| Label | Projected from | Properties |
|---|---|---|
| `Student` | `learner.student_profile` | `canonical_id` (= `student_id` UUID), `status` — **no PII** (name/email stay in Postgres only, behind admin-scoped access) |

### New edge types (`Student` ↔ existing `Concept`/`Technique`/`Problem` nodes)

| Edge | Direction | Properties | Projected from |
|---|---|---|---|
| `MASTERED` | `(Student)-->(Concept\|Technique)` | `score`, `trend`, `as_of` | `learner.concept_mastery` / `learner.technique_mastery` where `score >= MASTERY_THRESHOLD` (e.g. 0.8) |
| `STRUGGLES_WITH` | `(Student)-->(Concept\|Technique)` | `score`, `trend`, `as_of` | same tables where `score < STRUGGLE_THRESHOLD` (e.g. 0.4) |
| `ATTEMPTED` | `(Student)-->(Problem)` | `correctness`, `attempt_count`, `last_attempt_at` | `learner.attempt`, aggregated per (student, problem) |
| `MADE_ERROR` | `(Student)-->(Misconception)` | `count`, `last_seen_at` | future: error-pattern classification over `learner.attempt.submitted_answer`, not yet implemented |

### Constraint additions (mirrors `mathbank-graph/etl/project_from_postgres.py`'s `CONSTRAINTS` list)

```cypher
CREATE CONSTRAINT student_id IF NOT EXISTS FOR (n:Student) REQUIRE n.canonical_id IS UNIQUE;
```

### Why `MASTERED`/`STRUGGLES_WITH` are derived edges, not raw scores on every concept

Projecting a `MASTERED`/`STRUGGLES_WITH` edge only above/below a threshold
(rather than a `mastery_score` property on every `(Student)-[:RELATES_TO]-
>(Concept)` edge) keeps the graph sparse and makes Cypher traversal
questions natural, e.g.:

```cypher
// Prerequisite concepts this student struggles with, blocking a target concept
MATCH (s:Student {canonical_id: $student_id})-[:STRUGGLES_WITH]->(weak:Concept)
MATCH (weak)-[:CONCEPT_RELATION {relation_type: 'PREREQUISITE_OF'}]->(target:Concept {slug: $target_slug})
RETURN weak.name, weak.slug;
```

```cypher
// Recommend problems: tests a concept the student doesn't yet master,
// but not ones they've already struggled with repeatedly
MATCH (s:Student {canonical_id: $student_id})
MATCH (p:Problem)-[:TESTS]->(c:Concept)
WHERE NOT (s)-[:MASTERED]->(c)
  AND NOT (s)-[:ATTEMPTED {correctness: 'INCORRECT'}]->(p)
RETURN p.canonical_code, c.name
LIMIT 10;
```

---

## 7. Retrieval extension (REST + agent tool)

The existing corpus search request gains an **optional** policy object —
anonymous/admin generic search remains byte-for-byte unchanged:

```json
{
  "query": "combinatorics",
  "filters": { "...": "..." },
  "personalization": {
    "student_id": "...",
    "mode": "practice_recommendation",
    "exclude_mastered": true,
    "prioritize_struggling": true
  }
}
```

New agent tool (additive to the existing tool catalog in
[`09_agent_tool_design.md`](09_agent_tool_design.md)):

```text
get_student_mastery_summary(student_id) -> {
    mastered_concepts: [...],
    struggling_concepts: [...],
    recent_trend: "...",
}
```

The agent uses this tool's output to bias `search_questions` calls (exclude
mastered concepts' problems, prioritize struggling ones) — it never computes
mastery itself, matching the existing "REST/Postgres decides, LLM asks"
boundary from [`07_system_architecture_and_boundaries.md`](07_system_architecture_and_boundaries.md).

---

## 8. Keep student state out of embeddings by default

Do not create a new embedding of the corpus per student.

Corpus embeddings remain shared (`search.embedding` keyed by
`embedding_model_id`, not by student).

Student state affects:

- filters
- ranking features
- exclusion lists
- prerequisite expansion
- difficulty targeting

This keeps vector storage manageable — one embedding per chunk regardless of
how many students exist.

---

## 9. Attempts are not conversation memory

Student attempts should be first-class structured events (`learner.attempt`
rows, §4), not scraped from chat history.

This can later feed learner-state models beyond the simple decayed-accuracy
formula in §5 (e.g. Bayesian Knowledge Tracing, IRT-style ability
estimates) without changing the ingestion contract — the aggregation job in
§3 is the only thing that would need to change.

---

## 10. Why this separation matters

It lets the current agent/RAG system reach production without prematurely coupling:

```text
retrieval
identity
pedagogy
mastery modeling
```

When student functionality arrives, it composes with the existing corpus API
rather than replacing it — `learner.*` is purely additive to `core.*`/
`knowledge.*`/`search.*`, and the `Student` node/edges are an additive,
separately-scoped graph projection.
