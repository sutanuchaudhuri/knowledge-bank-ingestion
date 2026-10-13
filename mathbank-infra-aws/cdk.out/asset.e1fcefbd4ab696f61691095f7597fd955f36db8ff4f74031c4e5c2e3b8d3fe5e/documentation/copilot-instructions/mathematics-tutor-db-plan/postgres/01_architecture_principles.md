# PostgreSQL 01 — Architecture Principles

## Role of PostgreSQL

PostgreSQL is the authoritative transactional and analytical store for the mathematics corpus. It must answer four questions without consulting another system:

1. What content do we possess?
2. Where did each fact come from?
3. What classification and relationships have been asserted?
4. What was the state and history of every ingestion or backfill run?

Graph, vector, and search layers are projections. If they are deleted, they must be rebuildable from PostgreSQL.

## Design principles

### Stable identity over mutable labels

Every durable entity receives an immutable UUID or ULID. Human-readable names, slugs, contest titles, taxonomy labels, and source paths are mutable attributes or alternate identifiers.

### Normalize authoritative facts; denormalize read models

Core entities and relationships should be normalized enough to preserve provenance and prevent ambiguous updates. Read-heavy use cases can use materialized views, cached projections, or derived tables.

### Append history where meaning changes

Taxonomy assignment, source extraction, solution revision, classification review, and pipeline execution require history. Avoid destructive overwrite for facts whose evolution matters.

### Idempotent ingestion

Every ingestion write must be replayable. Use source checksums, source-native identifiers, deterministic natural keys, and explicit upsert policies.

### Provenance is first-class

Any extracted statement should be traceable to a source document, page/section, parser/extractor version, and run.

### Human and machine assertions are distinct

Store whether a classification came from a human curator, deterministic rule, imported metadata, or model. Preserve model name, prompt/schema version, confidence, and review state.

### Operational state is persistent

A scheduler firing is not evidence that work completed. Runs, work items, leases, heartbeats, attempts, counts, and terminal states are database records.

## PostgreSQL extensions

Recommended:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS btree_gin;
```

Optional later: `citext`, `ltree`, `pg_stat_statements`.

## Schema namespaces

Use separate SQL schemas:

- `core` — contests, papers, problems, solutions, sources
- `knowledge` — concepts, topics, techniques, relations, taxonomy assertions
- `search` — embeddings and retrieval projections
- `pipeline` — ingestion jobs, runs, work items, checkpoints
- `audit` — immutable change/event records
- `learner` — later learner attempts/mastery; keep isolated from corpus truth
- `api` — optional stable views/functions exposed to the service layer

## Transaction boundaries

One source artifact or one work item should be processed in a bounded transaction. Do not place an entire archive backfill in one transaction. Persist progress after each paper or problem so interruption does not erase run visibility.

## Multi-environment policy

Use at least `dev`, `test`, and `prod`. IDs may differ by environment unless imported from a controlled canonical dataset. Migration versions must be identical. Production schema changes are migration-only—no manual DDL.
