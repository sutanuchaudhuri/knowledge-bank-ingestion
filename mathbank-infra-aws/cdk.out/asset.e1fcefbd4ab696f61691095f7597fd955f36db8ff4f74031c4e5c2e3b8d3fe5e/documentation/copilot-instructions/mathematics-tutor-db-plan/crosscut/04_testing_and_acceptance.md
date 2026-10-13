# Cross-cutting 04 — Testing and Acceptance

## Database tests

- uniqueness and FK constraints
- valid state transitions
- upsert idempotency
- content-hash invalidation
- retry history preservation
- transaction rollback behavior

## Corpus integrity tests

For each paper:

- expected question count matches observed
- problem numbers are unique and complete where expected
- answer presence matches source expectations
- source locators resolve
- accepted taxonomy IDs exist

## Pipeline failure tests

Simulate:

- worker crash after claim
- crash after some problem inserts
- timeout during model call
- duplicate scheduler invocation
- stale lease
- partial source download
- graph outage

The system must produce a truthful state and allow safe resume.

## API contract tests

- stable error schema
- pagination correctness
- idempotency replay
- stale ETag conflict
- permission boundaries
- graph depth/result bounds

## Graph reconciliation tests

Given a fixed PostgreSQL snapshot, rebuild graph and compare node/edge counts and selected deterministic traversals.

## Acceptance gates before large backfill

1. Reimport produces no duplicates.
2. Every completed work item has reconciliation metrics.
3. Failed items are visible and retryable.
4. Provenance resolves for every imported problem.
5. Graph can be rebuilt from PostgreSQL.
6. REST can answer archive coverage without consulting scheduler logs.
