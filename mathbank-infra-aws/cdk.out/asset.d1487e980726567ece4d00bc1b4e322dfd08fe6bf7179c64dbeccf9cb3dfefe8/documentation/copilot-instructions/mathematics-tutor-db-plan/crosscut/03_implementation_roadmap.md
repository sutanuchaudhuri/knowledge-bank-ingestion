# Cross-cutting 03 — Implementation Roadmap

## Phase 0 — Inventory and mapping

- Freeze a sample of current corpus/taxonomy artifacts.
- Enumerate source formats and current identifiers.
- Produce a column-to-canonical-field mapping.
- Define expected paper inventory for initial competitions.

## Phase 1 — PostgreSQL foundation

- Create schemas and migrations.
- Implement competitions/editions/papers/problems/sources.
- Implement taxonomy concepts/techniques/assertions.
- Implement pipeline run/work-item/attempt/checkpoint tables.
- Build idempotent importers for one competition.

Exit criterion: a full competition year can be reimported without duplicates and every problem has provenance.

## Phase 2 — Operational backfill

- Implement worker claiming with leases.
- Add heartbeats, retries, stale detection, reconciliation counts.
- Build run dashboard/API.
- Resume historical archive processing.

Exit criterion: interrupted runs resume safely and status is trustworthy.

## Phase 3 — Search and embeddings

- FTS/trigram indexes.
- Embedding table and content-hash invalidation.
- Hybrid retrieval endpoint.

## Phase 4 — REST stabilization

- Read APIs, curator writes, bulk ingestion.
- ETags/revisions and audit.
- Security and observability.

## Phase 5 — Graph projection

- Implement accepted-knowledge projection.
- Add reconciliation and rebuild test.
- Add prerequisite and neighborhood endpoints.

## Phase 6 — Tutor intelligence

- Learning-path service.
- Misconception mapping.
- Student-state projection.
- Retrieval evaluation and feedback loops.

## Suggested first vertical slice

Take one corpus slice such as AIME 2023–2025 or one Math Prize for Girls cycle. Implement source->problem->taxonomy->REST->graph end-to-end before broad archive migration.
