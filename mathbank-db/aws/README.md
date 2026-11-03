# mathbank-db/aws — PostgreSQL → DynamoDB + S3 + S3 Vectors migration

Implements the data migration of
[requirement 70](../../documentation/requirements/70_DYNAMODB_AND_S3_VECTORS_ADOPTION_PLAN.md).
Rows are copied from the Neon PostgreSQL database (opened **read-only**) into:
- DynamoDB tables, using the per-context designs C1–C6;
- the general-purpose S3 buckets (release snapshots, oversized attributes, archives, manifests);
- S3 Vectors indexes (every pgvector embedding, copied without re-embedding).

PostgreSQL is never written to and nothing is dropped. The application code still reads and writes
PostgreSQL: switching each context over to the new stores (store adapters, flags, freeze-copy-switch)
is a separate step in requirement 70 §7.

## Layout

| Path | What |
|---|---|
| [common.py](common.py) | Config (`--env`, region, profile, resource names), read-only Neon source, type conversion, canonical item hashing |
| [dynamo/spec.py](dynamo/spec.py) | Spec API: `Table`, `Mapping`, `S3Put`, and helpers |
| [dynamo/specs/](dynamo/specs/) | One module per context: `content` (C6), `learner` (C1), `exam` (C2), `live` (C3), `media` (C4: media, artifacts, geometry, jobs), `staff` (C5: socratic, notify, agent-sessions, audit) |
| [dynamo/provision.py](dynamo/provision.py) | Creates/updates tables (on-demand, PITR, deletion protection, streams, TTL, GSIs). Never deletes. |
| [dynamo/migrate.py](dynamo/migrate.py) | Streams each mapping's SQL, transforms, offloads oversized attributes to S3, batch-writes, writes a manifest |
| [dynamo/verify.py](dynamo/verify.py) | Full consistent scan of every table; count plus order-independent sha256 per (table, item type) vs the manifest |
| [s3/provision.py](s3/provision.py) | `mathbank-data-<env>-<account>` and `mathbank-content-<env>-<account>` buckets (private, versioned, SSE, TLS-only), the `mathbank-vectors-<env>` vector bucket and its indexes |
| [sqs/provision.py](sqs/provision.py) | `make aws-sqs`: the Studio job queues `mb-studio-research-<env>`, `mb-studio-render-<env>` (and `mb-geometry-interpret-<env>`) with DLQs `mb-<kind>-dlq-<env>`; idempotent, converges attributes, never deletes |
| [s3/vector_indexes.py](s3/vector_indexes.py) | Vector index catalog: SQL, metadata, filter keys per family |
| [s3/vectors.py](s3/vectors.py) | `copy` (binary `real[]` fetch, PutVectors in batches of 500, plus a Parquet archive) and `verify` (archive SHA-256 check, counts vs the live source, bit-exact sample, tie-aware recall@8 vs exact cosine; `--baseline source` re-reads Neon instead) |
| [runs/](runs/) | Checked-in manifests and verification reports of executed runs (counts and hashes only, no row data) |

## Prerequisites

- AWS profile `aws-sutanu-admin` (account 848941468793, us-east-2), logged in.
- `../mathbank-graph/remote.env` (git-ignored) with `NEON_PG_HOST/PORT/DATABASE/USER/PASSWORD`. It is the same file the Makefile `*-remote` targets use. Credentials are never written by these scripts.
- `make aws-install`, which installs the `aws` extra: boto3 + botocore[crt], numpy, pyarrow.

## Run

```bash
cd mathbank-db
make aws-provision                     # buckets, vector bucket + indexes, DynamoDB tables
make aws-dry-run                       # read + transform everything, write nothing
make aws-migrate                       # copy; prints logs/aws/<run>/dynamo-manifest.json
make aws-verify MANIFEST="logs/aws/<run>/dynamo-manifest.json [newer manifests]"   # newest per table wins
make aws-vectors                       # copy vectors + Parquet archive
make aws-vectors-verify                # archive SHA-256, counts vs live source, fidelity, recall gate
# one context only:  make aws-migrate AWS_ONLY="learner"
```

Every step is idempotent: keys are deterministic, so a re-run overwrites the same items and vectors.
Verification compares a **full** scan against the manifest of the **same** run, so for a clean
report, verify right after a full migrate. Items written later by applications show up as `extra`.

## Large payloads

[migrate.py](dynamo/migrate.py) applies one offload rule for every context. This covers large problem and
solution bodies, student responses (quiz, step, live) and uploaded-artifact payloads.
- **Threshold:** each spec declares `OFFLOAD = {(table, item type): (attr, ...)}`. A listed attribute larger
  than `MB_OFFLOAD_THRESHOLD` (16 KiB) is written to `s3://mathbank-data-<env>-<account>/offload/...`.
- **Reference:** the attribute is replaced in DynamoDB by `<attr>_ref = {bucket, key, sha256, bytes, content_type}`.
- **Student-owned items** are stored under `offload/<table>/students/<student_id>/...`, so erasing a student is a
  single prefix delete. Ownership comes from a `STUDENT#` partition key or an owner attribute on the item.
- **Safety net:** any item still above 350 KB has its largest attributes offloaded the same way.
- **Verification:** `verify` HEADs every referenced object and compares its size and SHA-256.

Items whose `ttl` is already in the past (e.g. expired idempotency records) are not copied. A copy left by an
earlier run is deleted, and the count is recorded as `expired_skipped` in the manifest.

## Results

Executed against `dev` on 2026-11-03. See [runs/](runs/README.md).

| Target | Copied | Verified |
|---|---|---|
| DynamoDB (12 tables) | 394,574 items from 1,551,156 source rows (192 mappings, 172 with source row-count checks) | full scan: count and SHA-256 per (table, item type) equal |
| S3 content bucket | 37,190 release snapshots, 6 catalogue snapshots, 359 images (808 MB) | uploaded with SHA-256 checksums |
| S3 offload | 57 large attributes (3.1 MB) | 57/57 objects match their references |
| S3 Vectors (12 indexes) | 129,529 vectors, no re-embedding, plus 380 MB of Parquet archives | counts exact, samples bit-exact, tie-aware recall@8 >= 0.967 |

## Safety

- The source session runs `SET default_transaction_read_only = on` and checks it before the first query.
- Provisioning never deletes tables, GSIs, buckets or indexes. Tables have deletion protection and PITR.
- To start over in dev, delete the resources manually after disabling deletion protection. No script does this.

## Pydantic models

Every item type and S3 JSON document has a pydantic model in `mathbank-rest/src/mathbank_rest/models` (requirement 71 section 2.10).
`MB_VALIDATE_MODELS=1` (abort) or `warn` makes `aws.dynamo.migrate` validate each item against its model before writing it;
run it with `mathbank-rest/.venv/bin/python` and `PYTHONPATH=mathbank-db`. After a copy, `make -C mathbank-rest ddb-models-validate`
checks everything in the tables.
