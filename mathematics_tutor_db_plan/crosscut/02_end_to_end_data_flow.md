# Cross-cutting 02 — End-to-End Data Flow

## Example: ingesting one competition paper

1. Register or locate `source_document` using checksum and source namespace.
2. Resolve competition, edition, and paper identity.
3. Create/claim pipeline work item.
4. Extract problem boundaries and source locators.
5. Upsert each problem using canonical code and content hash.
6. Extract answers and solutions as separately sourceable records.
7. Validate expected problem count and required fields.
8. Generate machine taxonomy candidate assertions.
9. Apply deterministic validation and review rules.
10. Persist accepted/pending assertions in PostgreSQL.
11. Generate/reuse embeddings for changed chunks.
12. Mark paper work item complete only after reconciliation.
13. Projection worker updates the graph from accepted PostgreSQL assertions.
14. REST/search layers immediately expose canonical data; graph-dependent features expose the graph projection watermark.

## Mutation direction

Preferred write direction:

`API/worker -> PostgreSQL -> outbox/projection -> graph/search caches`

Never:

`client -> graph -> undocumented backfill into PostgreSQL`.

## Failure isolation

A graph outage must not prevent canonical corpus ingestion. An embedding provider outage should leave work retriable without marking the source paper successfully complete if embeddings are a required stage; otherwise mark the stage separately and allow corpus completion.
