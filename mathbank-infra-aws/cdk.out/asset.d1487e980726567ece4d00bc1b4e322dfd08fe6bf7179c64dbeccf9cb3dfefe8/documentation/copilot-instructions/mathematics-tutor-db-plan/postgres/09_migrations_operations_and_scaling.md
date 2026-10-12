# PostgreSQL 09 — Migrations, Operations, and Scaling

## Migration discipline

Use Alembic or an equivalent migration framework. Every schema change receives an immutable migration. Never edit an already-applied migration in production.

Migration phases for risky changes:

1. expand schema
2. deploy compatible application
3. backfill
4. switch reads/writes
5. validate
6. remove obsolete schema later

## Backups

Minimum production posture:

- automated snapshots
- point-in-time recovery / WAL archiving
- periodic restore drills
- checksums for source artifacts
- separate backup policy for object storage

## Observability

Track:

- transaction latency
- slow queries
- table/index growth
- deadlocks
- connection utilization
- vacuum/analyze health
- vector index build/search performance
- queue depth and oldest pending work item
- stale leases and failed attempts

## Partitioning

Do not partition core tables prematurely. Candidate future partitions:

- audit events by month
- model inference logs by month
- learner attempts by month/year
- very large embeddings by model or entity class

## Connection management

Use PgBouncer or application-side pooling. Cap worker concurrency so batch jobs do not starve API traffic.

## Data retention

Core corpus and accepted knowledge assertions are long-lived. Raw transient model responses and debug payloads can have configurable retention if reproducibility requirements remain satisfied.

## Scaling strategy

Order of operations:

1. fix query/index design
2. add materialized/cached read models
3. separate batch workload
4. add read replicas
5. partition truly large append tables
6. consider specialized analytical stores only after measured need
