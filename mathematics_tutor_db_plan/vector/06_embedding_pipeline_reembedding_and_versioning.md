# Vector 06 — Embedding Pipeline, Re-embedding, and Versioning

## 1. Embeddings are rebuildable derived data

The pipeline must support:

- initial corpus backfill;
- incremental new-content embedding;
- source edits;
- chunking changes;
- preprocessing changes;
- new embedding models;
- failed jobs and retries;
- side-by-side model evaluation.

## 2. Pipeline

```text
canonical source changed
        ↓
representation generation/invalidation
        ↓
math-aware chunking
        ↓
content hashing
        ↓
embedding work-item creation
        ↓
embedding generation
        ↓
dimension validation
        ↓
vector insert
        ↓
index availability
        ↓
retrieval validation
```

## 3. Idempotency

A safe embedding-work identity is derived from:

```text
chunk_hash
+ embedding_model_id/model_revision
+ preprocessing/chunking version
```

If these are unchanged, do not call the embedding model again.

## 4. Change detection

A source update does not always require every vector to change.

Examples:

- provenance correction may leave `PROBLEM_STATEMENT` unchanged;
- a solution-step edit changes that step representation;
- taxonomy edits may change `PROBLEM_WITH_TAXONOMY` but not raw statement;
- a new chunking profile creates a new representation lineage.

Generate the representation, hash it, then decide whether embedding work is required.

## 5. Model migration

Never overwrite the active model in place.

```text
Model A ACTIVE
   │
register Model B
   │
backfill B
   │
build B index
   │
quality + latency evaluation
   │
canary retrieval
   │
activate B
   │
retain A for rollback window
   │
retire A
```

This is the central reason to model embedding versions explicitly.

## 6. Durable embedding work

Use the same persistent pipeline semantics as archive backfill:

```text
PENDING
IN_PROGRESS
COMPLETED
FAILED
BLOCKED
STALE
CANCELLED
```

Record:

- worker;
- heartbeat;
- attempts;
- last error;
- input hash;
- input token count;
- provider request ID when available;
- output dimensions;
- latency;
- cost metadata when relevant.

## 7. Completion semantics

A backfill is not complete when requests have merely been issued.

It is complete when:

```text
expected active embeddable chunks
=
active embeddings
+ explicitly excluded chunks
```

and unresolved failures are zero or explicitly waived.

## 8. Reconciliation

Schedule integrity checks for:

```text
active chunks MINUS active embedding for model
```

and for:

```text
active embeddings whose representation is superseded/deleted
```

The first set indicates missing work; the second indicates stale search surface.

## 9. Retry policy

Automatically retry transient failures:

- provider rate limits;
- timeouts;
- temporary network/provider errors.

Do not endlessly retry structural failures:

- dimension mismatch;
- malformed content;
- invalid model configuration;
- missing source entity;
- unsupported token length after configured fallbacks.

Mark those `BLOCKED` or permanent `FAILED` for review.

## 10. Embedding cache

A content-hash cache can eliminate duplicate calls.

```text
(model_revision, chunk_hash) → embedding
```

Provenance/chunk rows remain distinct even if numeric vectors are reused.

## 11. Deletion and licensing

If source content must be removed:

1. deactivate/delete canonical content according to policy;
2. deactivate representations immediately;
3. remove active embeddings from retrieval;
4. purge vector rows if required;
5. retain only audit metadata allowed by policy.

## 12. Backfill observability

Expose at least:

- total active representations;
- total chunks;
- expected embeddings;
- completed;
- pending;
- failed;
- blocked;
- stale;
- embeddings/sec;
- average embedding latency;
- model distribution;
- dimension-validation failures;
- last successful heartbeat.
