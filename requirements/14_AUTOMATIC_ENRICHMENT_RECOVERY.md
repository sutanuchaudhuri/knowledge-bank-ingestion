# Automatic enrichment recovery plan

## Evidence and invariants

On 2026-10-04 the corpus worker continued generating metadata, but logs showed
cross-corpus prerequisite cycles, invented taxonomy slugs, intermittent Aura
connection failures, graph errors attributed to successful generation, and
failed jobs waiting behind a full corpus snapshot.

Postgres remains authoritative. Automatic approval does not imply human review.
Do not delete existing prerequisites to accommodate a generated proposal. Human
corrections/rejections remain protected. Invalid output must never be silently
trimmed or approved. Graph publication and metadata generation are separate
operations; graph failure must not cause paid regeneration.

## Implementation plan and acceptance criteria

1. **Validate and correct against the complete prerequisite graph.**
   Report an actual directed cycle path, not only a generic cycle error. Put
   atomic import inside the same three-response correction budget as JSON and
   taxonomy validation. On import failure, roll back the entire proposed
   manifest and give the model the conflict path. The importer must still
   validate under its existing table lock, including concurrent writes.
   Acceptance: a locally acyclic proposal closing an existing path is rejected,
   a corrected proposal imports, and exhausted corrections write no metadata.
2. **Constrain taxonomy selection at generation time.**
   Use structured JSON-schema output with catalog-derived slug enums for both
   problem tags and skill concept tags. Keep independent server validation,
   cycle checks and bounded correction feedback. Do not guess equivalent slugs.
   Acceptance: all three catalog-selection surfaces use exact catalog enums;
   exhausted validation failures retain their actionable cause.
3. **Share bounded graph retry handling.**
   Use the same publication helper for learning requests and the corpus worker.
   Retry fingerprint conflicts and transient Neo4j connectivity/transaction
   errors three times with 2/4-second backoff. Recompute fingerprints each time;
   never retry validation/authentication failures as transient failures.
   Acceptance: transient disconnect then success records publication without
   model calls; terminal/exhausted failures are explicit.
   Carry approval provenance inside the atomic teaching-layer replacement.
   Scoped tag stamping must not erase automatic labels for other problems whose
   teaching relationships are recreated by the global reconciliation.
4. **Separate operation errors and recover the durable outbox.**
   Log generation failures with problem, stage and cause; log publication failures
   with batch size and retained Postgres state, never as generation failure.
   Query completed jobs with null `published_at` as the durable outbox, including
   at startup, publish in batches of at most 25, and retry exhausted publication
   after 60 seconds. Bound normal publication delay to 60 seconds between jobs.
   Commit generated metadata and COMPLETED job state in one Postgres transaction.
   Acceptance: saved metadata remains COMPLETED on graph failure; replay does not
   call the model; `published_at` is recorded only for completed jobs.
5. **Reselect work between every problem.**
   Prioritize eligible FAILED jobs ahead of new work, with existing five-minute
   cooldown and three-job-attempt ceiling. Recover abandoned IN_PROGRESS claims
   after ten minutes. The worker must not hold an hours-long corpus snapshot.
   Acceptance: a failed job becoming due is selected before the next fresh job,
   without waiting for corpus completion. In-flight model/import/publication time
   can delay selection; this is not an exact wall-clock scheduler.
6. **Validate and activate deliberately.**
   Run focused model/import/publication/scheduler tests, opt-in rolled-back live
   database fixtures, lint and type checks. Stop only the verified owned worker,
   restart the owned REST service, then resume the authorized independent watcher.
   Verify persistent jobs, successful graph replay and recovery of a failed
   problem. Do not claim full corpus completion while ingestion adds questions.

## Operational gotchas and recovery

- A proposal can be acyclic by itself but cyclic when combined with existing
  skills. Reverse prerequisites are not safely fixed by dropping old edges.
- A model request returning HTTP 200 is not a valid metadata import.
- Model response attempts (up to three) and job attempts (up to three with
  cooldown) are different counters and can incur multiple paid calls.
- `COMPLETED` with null `published_at` means saved but not graph-published.
  Publication replay is idempotent reconciliation, not model regeneration.
- Neo4j may commit before Postgres records publication. Replay is required;
  cross-database atomicity is not claimed. A retry can publish a newer snapshot.
- Watch mode retries publication independently of generation. Terminal graph
  configuration errors remain visible and need operator repair, not infinite
  immediate retries.
- An interrupted worker may leave an IN_PROGRESS lease; allow its ten-minute
  expiry rather than resetting all jobs or overlapping workers.
- Remaining corpus counts can rise while the independent paper pipeline ingests.
- Never print credentials or use port-wide termination during activation.

Related: [pedagogical requirements](13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md),
[operational gotchas](../GOTCHAS.md), and
[worker](../mathbank-rest/scripts/enrich_corpus.py).

## Implementation verification (2026-10-04)

### Bounded parallel batches

The operator authorized four concurrent jobs. `--workers 4` overlaps model
requests in a bounded thread pool while imports retain existing table locks.
One coordinator reselects due work, excludes its in-flight codes, and handles
graph publication. Database compare-and-set claims protect against competing
on-demand requests. Keep one coordinator; concurrency is not permission to run
multiple graph publishers. Default concurrency remains one, maximum eight.
One-shot limits count submitted generation attempts; watch mode is uncapped.
Graceful termination drains active tasks and publishes durable completed jobs.
Acceptance tests use a four-party barrier to prove actual overlap, no duplicate
dispatch, single-thread publication, and shutdown draining. Measure live
throughput after activation instead of promising a fourfold SLA improvement.

- 99 focused tests and 23 subtests passed, including live rolled-back fixtures
  for cross-corpus cycle rollback, atomic COMPLETED/outbox writes, cooldown
  exclusion, exhausted-attempt exclusion and due-retry prioritization.
- Lint, four-file type checks and editor diagnostics passed.
- Previously failed AIME_1985_Q11 and AIME_1990_Q07 were enriched and published;
  their errors cleared and job attempts advanced from one to two.
- Stored publication work replayed without generation. A real fingerprint
  conflict retried and then published successfully.
- Scoped publication for AIME_1990_Q07 retained automatic provenance on unrelated
  AIME_1983_Q01 and AIME_1985_Q11. This check exposed and fixed a pre-existing
  global-replacement/scoped-stamping mismatch.
- The independent watcher was observed selecting overdue failed AIME_1983_Q08
  and AIME_1983_Q09 ahead of fresh corpus work and saving them successfully.

This verifies recovery mechanisms, not full corpus completion. Exhausted model
corrections still require admin intervention; ingestion can increase remaining
question counts while the watcher operates.
