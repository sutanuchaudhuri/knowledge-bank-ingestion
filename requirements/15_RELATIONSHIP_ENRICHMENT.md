# Automatic taxonomy and skill-relationship enrichment

## Scope and semantics

Populate three currently sparse graph views from existing catalog definitions,
without relabelling the problem-enrichment prerequisite edges:

| View | Stored relationship | Meaning and direction |
|---|---|---|
| Skill hierarchy | Skill PART_OF Skill | An observable component action is part of a broader composite action. Not a synonym, topic membership, or prerequisite. |
| Useful prior skills | Skill BUILDS_ON Skill | Prior/supporting action points to a dependent action it usefully supports, but is not strictly required. |
| Concept prerequisites | Concept PREREQUISITE_OF Concept | Prior knowledge points to dependent knowledge for which it is a genuine foundation. Not mere relatedness or containment. |

Machine-approved relationships are provisional estimates with confidence,
source, model, timestamp and retained generation rationale. No learner mastery
or human verification is implied. Empty proposals are allowed when definitions
do not justify a relationship. Never force edges merely to make a graph nonempty.

## Plan

1. Add an independent durable relationship-job table, with separate generation
   and publication state, attempts, error cause and structured output evidence.
   Apply migration 009 explicitly to the live database.
2. For every existing/new skill or concept, assemble a bounded candidate catalog
   (40 neighbors ranked by shared concepts/name similarity; concepts by name
   similarity). Include a small foundation/composite candidate pool. Candidate
   retrieval limits coverage and is not proof that a relationship exists.
3. Request up to four justified relationships per anchor using strict structured
   output with exact catalog slug enums. Every edge must involve the anchor,
   have distinct endpoints, a valid relationship type, confidence >=0.75 and a
   specific rationale. Allow zero proposals with an explicit explanation.
4. Insert proposed new edges under the existing authoring lock and automatic
   writer setting. Reuse full-graph prerequisite/PART_OF cycle validation, and
   validate BUILDS_ON cycles separately. Roll back a whole conflicting proposal;
   return cycle paths to the model within a three-response budget. Do not change
   existing human/rejected/automatic edges on conflict.
   Before import, require an independent skeptical model review of every edge.
   Reject reversed direction, synonyms mistaken for components, optional topics
   mistaken for necessary concept prerequisites, and unsupported rationale.
   Return semantic rejections as correction feedback, never silently trim edges.
   Retain verification verdicts alongside the proposal.
   Relationship generation and independent semantic review default to `gpt-4.1`
   (`RELATIONSHIP_MODEL` and `RELATIONSHIP_VERIFIER_MODEL` can override them).
   The cheaper question-enrichment model remains unchanged. Record
   the verifier model in evidence; this adds paid verification requests.
   PART_OF means an actual distinct substep of a described composite workflow,
   not a requirement that every alternative strategy use that substep.
5. Commit edges, evidence and COMPLETED outbox state atomically. Retry failed
   generation after five minutes up to three job attempts, recover stale claims
   after ten minutes, and revisit completed anchors after seven days only if
   their input/candidate fingerprint changed. New anchors become immediately due.
6. Share the existing four-slot coordinator: at most one relationship task is
   in flight, remaining slots process questions. No competing graph publisher.
   Global pedagogical reconciliation records both question and relationship
   publication completion; relationships stay durable after graph failures.
7. Expose concept relations in authenticated admin review/edit/history/bulk
   surfaces. Preserve audit snapshots and explicit human publish behavior.
   Fix graph wording to distinguish approval from human review.
8. Validate model contracts, cycles, protected decisions, job scheduling,
   publication tracking and coordinator compatibility. Run live paid pilots,
   publish, verify all three API views, then activate the authorized independent
   mixed watcher. Report coverage honestly; nonempty graphs are not calibration.

## Gotchas and acceptance

- A hierarchy edge is not a prerequisite edge. BUILDS_ON direction is prior
  skill to dependent skill, matching the existing starter relationship.
- Shared concept tags and lexical similarity only select candidates; the model
  must justify relationships from objectives/definitions, not names alone.
- The first live pilot exposed semantic errors despite schema/cycle validity
  (reversed prior-skill direction and advanced topics incorrectly called
  prerequisites). Independent semantic verification is mandatory; bad automatic
  pilot assertions are marked REJECTED with audit history, not silently deleted.
  Model agreement is still not human verification or calibrated ground truth.
- Rejected edges are never resurrected. Automatic runs do not overwrite any
  existing natural key. Admin edits/rejections use the existing human audit.
- Full-graph cycle validation runs inside the same locked transaction as writes.
- Global publication can commit before recording in Postgres. Replay is
  idempotent; cross-database atomicity is not claimed.
- New work adds paid model calls and competes for the same bounded worker slots.
  The prior question-only throughput estimate no longer applies unchanged.
- Integration checks must show automatic provenance and real counts in
  skill-hierarchy, concept-prerequisites and skill-builds-on, while preserving
  existing question learning context and admin protections.

Related: [recovery plan](14_AUTOMATIC_ENRICHMENT_RECOVERY.md),
[pedagogical requirements](13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md).

## Implemented and verified

- Migration 009 was applied to live Postgres. All three relationship families
  have real automatic assertions saved in Postgres and projected to Neo4j.
- Generation and independent verification now default to the operator-allowed
  `gpt-4.1`. A paid pilot corrected two invalid responses and saved two verified
  completing-the-square relationships. An unsupported concept proposal exhausted
  correction and remained FAILED rather than being automatically approved.
- Earlier schema-valid but semantically incorrect pilot edges remain REJECTED
  with audit history. Retry claims reset current-attempt inserted/publication
  counters and record the actual model, retaining the previous proposal separately.
  Failed semantic responses and validation causes are retained in job evidence.
- The approved API pilot snapshot had **7 Skill PART_OF**, **5 Concept
  PREREQUISITE_OF**, and **2 Skill BUILDS_ON** edges (one BUILDS_ON is a human
  starter assertion). These counts are snapshots, not complete catalog coverage.
- Authenticated concept-relation queue HTTP checks passed. The admin UI supports
  concept-relation review/edit/history/bulk actions and shows relationship job
  evidence and errors. Automatic estimates are not labelled human-reviewed.
- The skill-hierarchy browser rendered 8 nodes / 7 edges in a 1217 x 540 canvas
  with the approved-only filter. The existing AIME_1983_Q01 learning-context API
  remained HTTP 200 and answer-free.
- Focused backend/authoring/live validation passed **121 tests and 23 subtests**;
  lint and mypy passed. Web proxy/learning/metadata tests passed **13 tests**,
  and the production build passed with 36 generated pages. Mixed scheduler
  regression proves one reserved relationship slot, a combined four-task
  one-shot limit and coordinator-only global publication.
- After activation, a fresh approved-only API snapshot grew to **20 skill
  hierarchy**, **9 concept prerequisite**, and **7 useful-prior-skill** edges.
  Live relationship jobs recorded `gpt-4.1` model evidence and publication.
  Counts can change as the continuous watcher generates and reconciles metadata.
- The authorized independent watcher was activated with
  `--watch --workers 4 --relationships`. Live logs and durable jobs confirm
  concurrent question/relationship generation, semantic correction and graph
  publication. Stop it gracefully by its verified PID before replacing it.
  Watch mode continues after chat exit; it incurs paid generation/review calls.
  No claim is made that the full corpus/catalog is complete or expert-calibrated.
