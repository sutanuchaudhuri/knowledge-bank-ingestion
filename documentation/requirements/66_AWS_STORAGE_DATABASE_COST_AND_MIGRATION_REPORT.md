# 66. AWS storage and database alternatives: cost and migration report

## 0. Executive decision

**Research and recommendations only, 2026-10-25. No storage backend, database,
schema, account permission or deployed service was changed for this report.**
Source baseline: `a0041e2bc53818b9d06e67d836a5b6d701872fb0`.
Public AWS documentation and the public **us-east-2 price lists** were retrieved.
No Neon/Aura invoice, live table sizes, query logs or private learner records
were inspected. Consequently, **actual dollar savings are not yet established**.

| Question | Finding | Recommendation |
|---|---|---|
| Can S3 Vectors replace pgvector? | Yes for suitable **derived embedding/search-index workloads**, not PostgreSQL joins, lexical search, constraints or source records. Existing search has strict live eligibility checks. | Shadow-test one nonprivate embedding family. Keep relational metadata, lexical retrieval and publication checks in PostgreSQL. |
| Can many PostgreSQL tables move to DynamoDB? | Some key-addressed, disposable or derived workloads fit. Number of tables is not a cost driver; moving a small table may save nothing on the Neon bill. | Prioritize disposable job status and derived notifications/analytics; do not split an ACID learner transition across SQL and DynamoDB. |
| Should AuraDB move to Neptune? | Technically possible, but not a URI swap. Neptune Database Serverless has a running minimum and openCypher differs from Neo4j. | Do not choose Neptune for assumed dev-cost savings. Measure current Aura bill and graph query requirements first. |
| Can an all-AWS relational option be affordable? | Aurora PostgreSQL Serverless v2 can auto-pause at zero ACUs on supported versions/settings; storage/network/IO remain. RDS is another compatible option but generally has provisioned compute cost. | Compare Aurora with actual Neon cost after sizing and pause tests; preserve PostgreSQL rather than rewrite the relational domain into DynamoDB. |
| Must the new Studio wait for migration? | No. Its schema/runtime depends on reliable PostgreSQL transactions, not a storage-provider swap. | Implement [requirement 65](65_ADAPTIVE_SOCRATIC_ADMIN_AND_AGENTCORE.md) against existing providers first. Evaluate migrations independently behind controlled adapters. |

**Recommended near-term shape:** Lambda + Step Functions + AgentCore for the
Socratic control plane; Neon PostgreSQL remains transactional authority; Aura
remains the graph projection until measured otherwise; ordinary S3 for large
objects/archives; optional S3 Vectors shadow index and DynamoDB-derived views.
Do not operate two authoritative copies of the same learner or publication state.

**Expanded scope:** sections 12-17 cover recurring admin insert/update/delete,
batch corpus reindexing, agent-enriched chunk metadata, managed S3 knowledge
options, AWS analytics and SageMaker. The separate
[table-by-table appendix](66A_POSTGRES_TABLE_MIGRATION_ASSESSMENT.md) covers
**all 209 source-defined tables plus 14 dated catalog-only framework/provider
tables**, not just likely migration candidates. No current database was queried.

**Important regional/cost distinction:** Bedrock **Managed Knowledge Base**
is a newer, different offering from a customer-managed Knowledge Base using
S3 Vectors. The retrieved managed-KB regional list does **not** include Ohio.
It offers less infrastructure maintenance, but its retrieval/storage prices
are not the S3 Vectors prices in section 7. Do not combine the two quotations.

## 1. What the previous cost analysis did and did not cover

[Requirement 62](62_AWS_SERVERLESS_DEV_HOSTING_COST_RESEARCH.md) explicitly kept
Neon/Aura unchanged. Its roughly $0.41-$0.70 marginal AWS hosting figure is a
historical, traffic/free-tier-dependent compute/image observation, **not the
total MathBank bill**. It excludes the database providers. The figure includes
an ECR estimate not fully remeasured at its last edit.

[Requirement 63](63_AWS_SERVERLESS_DEPLOYMENT_IMPLEMENTATION.md) and several
READMEs have older deployment counts than doc 62 and
[the current CDK entrypoint](../../mathbank-infra-aws/app.py). Treat them as
dated records; this report did not verify current cloud deployment or billing.

Three different meanings of "S3" must remain separate:

1. Existing Neon S3-compatible storage is not necessarily Amazon S3 billing.
2. Amazon S3 general-purpose buckets store ordinary objects such as PDFs,
   images, rendered videos and archives.
3. **S3 Vectors uses vector buckets/indexes and the `s3vectors` API/IAM
   namespace.** Placing an embedding JSON file into a normal bucket does not
   create a searchable vector index.

The existing no-VPC/no-NAT recommendation depends on public TLS Neon/Aura
endpoints. Private Aurora/Neptune would require a new network design; that
fixed cost can dominate small storage savings.

## 2. Repository evidence and workload inventory

This is a **source-based placement assessment**, not a duplicate schema catalog.
Use the [canonical schema reference](reference/POSTGRES_SCHEMA.md), its
[dated per-schema catalog](reference/postgres/README.md) and root migrations
through [052](../../mathbank-db/sql/052_quiz_question_pool.sql) for exact DDL.
Later source additions must not be represented as applied live tables.

### 2.1 Vector families actually present in source

| Family | Actual records and source | Placement assessment |
|---|---|---|
| Corpus/step search | `search.embedding`, `search.chunk`, `search.representation`, model/preprocessing/retrieval profiles and embedding jobs in [002](../../mathbank-db/sql/002_vector_schema.sql); [problem retrieval](../../mathbank-rest/src/mathbank_rest/db/vector_search.py), [step retrieval](../../mathbank-rest/src/mathbank_rest/db/step_search.py). | Candidate vectors can move; retain chunks, lineage, FTS, source hashes and authoritative eligibility in SQL. Step retrieval is a more difficult parity case than a public corpus ANN demo. |
| Misconception similarity | `knowledge.misconception_embedding` and `knowledge.misconception_similarity` in [040](../../mathbank-db/sql/040_similarity_embeddings.sql), [041 HNSW indexes](../../mathbank-db/sql/041_similarity_embeddings_hnsw_index.sql). | Good nonprivate benchmark candidate. Precomputed neighbor pairs can remain relational even if embeddings move. Batch all-to-all/top-k rebuild cost must be priced, not just interactive queries. |
| Taxonomy similarity | `pedagogy.taxonomy_node_embedding`, `pedagogy.taxonomy_node_similarity`, same migrations. | Another good derived-index candidate; canonical taxonomy/relationships stay relational. Similarity is not approved prerequisite or claim equivalence. |
| Artifact retrieval | `artifact_runtime.artifact_embedding` in [022](../../mathbank-db/sql/022_artifact_runtime.sql), [artifact runtime](../../mathbank-rest/src/mathbank_rest/artifact_runtime.py). | Defer until ownership/disclosure partitioning is proven. Never mix private attempts/artifacts into a public vector index. |
| Theorem retrieval | `knowledge.theorem_embedding` in [046](../../mathbank-db/sql/046_theorem_catalog.sql), [theorem service](../../mathbank-rest/src/mathbank_rest/theorem_service.py). | Source supports an embedding family; [doc 61](61_THEOREM_AXIOM_LEMMA_CATALOG.md) records remaining semantic-search gaps. Verify actual producer/consumer/deployment before assigning savings. |

`vector_search.py` currently uses `text-embedding-3-small`, 1,536 dimensions.
Do not assume switching the storage backend also switches embeddings to Titan
or another Bedrock model. Different embedding models/spaces cannot share
distances; a model change requires re-embedding, separate indexes and a new
quality baseline. Copying existing compatible vectors does not require new
paid embedding generation.

### 2.2 Important retrieval semantics that must survive

- Problem search filters competition/year **before** semantic and lexical
  ranking; verifies ACTIVE representation/model and exact current rendered
  problem text; fuses ranks with reciprocal-rank fusion.
- Step/learning-item retrieval applies taxonomy/technique/anchor/visibility and
  live approval constraints. It currently computes exact semantic distances
  over the filtered eligible set, deliberately avoiding global ANN starvation.
- [Hybrid search](../../mathbank-rest/src/mathbank_rest/db/hybrid_search.py)
  also incorporates reviewed graph evidence. S3 Vectors supplies neither that
  graph evidence nor PostgreSQL `tsvector` ranking.
- [Question pool 052](../../mathbank-db/sql/052_quiz_question_pool.sql) uses
  relational history, concept arrays and trigram topic similarity with a
  unique normalized content hash. It is not a generic vector collection.
- Vector deletion consistency does not make an asynchronous PostgreSQL-to-index
  projection transactionally current. Withdrawal/permission checks must use
  authoritative SQL even if the vector backend itself is strongly consistent.

## 3. S3 Vectors feasibility and target design

### 3.1 Current service facts

The official [overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html)
describes strongly consistent writes and subsecond retrieval, with lower latency
for frequently queried indexes. Those are service descriptions, not measured
MathBank end-to-end SLOs.

The retrieved [limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html)
include 1-4,096 dimensions, up to 40 KB total metadata, 2 KB filterable metadata,
50 metadata keys/vector, and up to ten non-filterable metadata keys/index.
PutVectors accepts up to 500 vectors, subject to a 20 MiB request payload.
Current QueryVectors limits list top-k up to 10,000 with pages up to 100 results.
Do not use old launch limits as current API validation rules.

The 1,536-dimensional search family fits, but schemas permitting dimensions up
to 8,192 do not imply every stored model fits S3 Vectors. Inventory actual
dimension/distance/model combinations first. Query/filter capabilities,
index type, quotas and regional availability must be checked for the precise
implementation; limits can change.

### 3.2 Proposed architecture

```text
PostgreSQL canonical source + approved metadata + transactional outbox
        |
        +-> existing pgvector path (baseline / rollback)
        |
        +-> leased index worker -> S3 vector index (source/model/hash manifest)

REST retrieval request
        +-> embed once in the existing selected model
        +-> S3 vector candidates with supported metadata filters
        +-> PostgreSQL live eligibility/source-hash/ownership recheck
        +-> bounded candidate refill or explicit incomplete/degraded result
        +-> existing lexical + reviewed graph rank fusion
        +-> safe public/student serializer
```

Proposed vector key: stable canonical entity/chunk ID + representation/model
revision. Metadata: family, canonical IDs, release/source hash, model version,
published visibility, competition/year and approved filter fields **within
size limits**. Never store answer keys, raw private responses or bearer tokens.
Use separate private index scope when required; IAM controls service access,
while REST remains responsible for application-owner authorization.

Use versioned index manifests and a verified pointer switch for full rebuilds.
Record missing/failed/deleted keys and checkpoints. Backfill existing vectors
in bounded batches with hashes; do not silently regenerate failed rows.
Retain SQL metadata when removing a vector column; its FKs do not move to S3.

**Critical recall constraint:** live SQL recheck prevents forbidden results but
cannot restore eligible neighbors that global ANN never returned. Oversampling
is not a proof of equivalent filtered search. For highly selective filters,
use supported metadata prefilters plus bounded refill, an exact SQL path, or
an explicitly documented lower-recall contract. Current exact step-search
semantics must not change silently to ANN.

### 3.3 Promotion gates

Proposed acceptance thresholds, subject to product approval before measurement:

| Gate | Threshold / evidence |
|---|---|
| Authorization/disclosure | Zero unauthorized, withdrawn, stale-source or hidden-answer results across the test set, including index lag races. |
| Retrieval quality | At least 0.95 recall@10 against the exact eligible SQL baseline on a representative labeled set; separately report each selective filter family. No averaging away a failing filter. |
| Rank quality | nDCG@10 degradation no more than 0.02 on human-labeled problem/step sets; otherwise explicit product approval of a behavior change. |
| Latency | Proposed p95 end-to-end no more than 1 second for retrieval excluding embedding generation, at agreed concurrency; measure cold and warm paths separately. |
| Completeness | Report candidate truncation, stale filtering, refill exhaustion and graph degradation; never return success-shaped empty results for dependency failures. |
| Operations | Backfill/delete parity, idempotent replay, outage behavior, restoration and rollback drills; no index-only source of truth. |
| Cost | Measured provider bill decreases after adding queries/worker/storage; not merely a cheaper price per GB. |

These benchmarks are **not run**. The first candidate should be public taxonomy
or misconception similarity, not private learner artifacts or the exact
step-recovery path.

## 4. DynamoDB placement assessment

### 4.1 What fits and what does not

DynamoDB is attractive for known partition/sort-key access patterns, conditional
updates, TTL-driven disposable records and bursty traffic without a compute
floor. It does not provide SQL joins, arbitrary relational queries, foreign
keys, PostgreSQL full-text/trigram search or cross-service ACID transactions.

The [constraints](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html)
include a 400 KB item limit and transaction limits; transactions can atomically
change up to 100 items/4 MB within their supported scope, **not PostgreSQL plus
DynamoDB**. Larger content goes in private S3 objects referenced by keys/hashes.
TTL expiry is asynchronous: check `expires_at` during reads and explicitly
delete when an exact privacy deadline requires it. TTL is not a guaranteed
instant deletion clock.

### 4.2 Table/workload placement matrix

Every entry is a recommendation, not a statement that a migration ran.

| Existing table(s) / workload | Candidate | Decision / coupling |
|---|---|---|
| `studio.scene_research_job`, `studio.video_render_job` ([044](../../mathbank-db/sql/044_manim_studio_jobs.sql)) | **Strong candidate** after access-path audit | Disposable job state and TTL suit DynamoDB. Put video/large SceneSpec bytes in S3; conditional leases/status transitions; SQS handles work delivery rather than table polling. Permanent scene promotion remains a separately reviewed SQL transaction. |
| `notification.event` ([043](../../mathbank-db/sql/043_notifications.sql)) | **Strong candidate** as derived inbox | PK recipient, SK ordered event ID; unread query/index and conditional read receipt. SQL-origin triggers enqueue through SQL outbox; no dual-write requirement on grading. |
| `analytics.learner_daily_activity` | **Good derived candidate** | PK learner/cohort+day with bounded rollups; retain idempotent event checkpoints. Historical multi-dimensional analysis belongs in S3/analytics, not broad DynamoDB scans. |
| `pipeline.graph_projection`, `pipeline.run`, `pipeline.work_item` | **Conditional** | Operational history/status can move if queue claims, dashboards, ordering, joins and run completeness are redesigned. Read-only status projection first is safer than moving authoritative job lifecycle. |
| `pipeline.pdf_source` | **Conditional metadata candidate** | Only if actual accesses are by known source/run keys; source relationships/uniqueness and reconciliation may favor keeping SQL. Large files already belong in object storage. |
| `pipeline.outbox_event`, `pipeline.outbox_consumption`, `pipeline.projection_request` | **Keep SQL authority** | Outbox must commit atomically with SQL business state. SQS/DynamoDB delivery/status projection is useful; moving the outbox breaks the guarantee. |
| `live.session_event` | **Conditional/high impact** | Session+sequence ordered event log can fit; sequence allocation, authorization, replay, multi-event transactions and relational instructor views must be preserved. Not a low-risk first move. |
| `live.command_receipt` | **Conditional** | Conditional receipt fits only when the related command side effect has a compatible transaction/idempotency design. A DynamoDB receipt alone cannot atomically protect a SQL command commit. |
| `live.session`, `participant`, `topic_run`, `takeover`, `recommendation` | **Defer** | Operational joins, instructor authorization and takeover transitions form a coupled runtime; move the aggregate only with a dedicated design/benchmark. |
| `agent_sessions.sessions`, `events`, `app_states`, `user_states`, `adk_internal_metadata` | **Defer/framework-owned** | ADK manages this store. Requires a supported session-service adapter, transcript pagination, concurrency and retention parity; not a table-by-table export. AgentCore Memory is not a drop-in ADK SQL store either. |
| `audit.action_log` ([035](../../mathbank-db/sql/035_admin_micro_course_platform.sql)) | **Keep transactional audit; archive copies** | Audit of publication/edits must share the business commit. Export protected immutable archives to S3; do not delete current audit rows until retention/recovery/legal policy is approved. |
| `learner.idempotency_record`, `learner.event` | **Keep SQL authority** | Must remain atomic with attempts, score/mastery and transition state. DynamoDB may store unrelated API request caches, not replace these coupled receipts casually. |
| `learner.student_profile`, `attempt`, `solve_attempt`, `attempt_step_state`, `route_attempt`, `concept_mastery`, `technique_mastery`, `pedagogy_feedback` | **Keep SQL** | Ownership, released-route FKs, evidence, optimistic concurrency, reporting and mastery transactions. Private data also needs precise deletion controls. |
| `learner.micro_course_enrollment`, `micro_course_state_event`, `tutor.micro_course_runtime` | **Keep SQL** | One authoritative course/adaptive transition and evidence transaction. New Socratic execution/decision tables follow the same rule. |
| `core.*`, `knowledge.*` canonical entities/relations, `pedagogy.*` releases/states/reviews/bindings | **Keep SQL** | Canonical integrity, uniqueness, immutable releases and reviewed relationships; cheap lookup replicas may be derived, never competing truth. |
| `activity.definition`, `instance`, `response` and `quiz.paper`, `question`, `solution`, `response`, `exam_diagnosis`, `question_pool` | **Keep SQL initially** | Grading/reveal gates, provenance, ownership, history-based pool exclusion and reporting; `question_pool` uses trigram/array indexes and a unique content hash. |
| `search.chunk`, `representation`, model/profile/job records | **Keep SQL initially** | FTS and eligibility/lineage joins. Move derived vector payloads independently if section 3 succeeds. |
| `attempt_media.*`, `artifact_runtime.*`, `geometry_scene.*`, permanent `visual.*` records | **Keep SQL metadata; S3 bytes** | Private evidence/review/version/ownership and published content FKs; large binary storage can be optimized without changing transaction ownership. |
| `neon_auth.*`, observed `auth`/`public` namespaces | **No automatic move/delete** | Provider/extension-managed or empty at dated observation. "No checked-in consumer found" is not permission to delete auth data. Audit dependencies and provider support separately. |

Moving "many tables" is therefore not the target. **Reduce bytes, hot index
memory, persistent compute and unnecessary work while preserving guarantees.**
Twenty tiny lookup tables may cost less than one large embedding index.

### 4.3 Candidate keys and migration boundaries

| Candidate | Proposed access design | Required guard |
|---|---|---|
| Job status | PK `JOB#<id>`, typed job/status/expiry, optional index for owner+creation; SQS carries job ID. | Conditional status/lease version; deterministic job ID; explicit expiry check; authorized owner/staff read. |
| Notifications | PK `RECIPIENT#<opaque-id>`, SK time+event ID, optional unread index. | Deduplicate source outbox event; server authorization; GSI eventual consistency does not authorize access. |
| Daily rollups | PK opaque learner/cohort, SK date+metric version; bounded retention. | Idempotent delta/checkpoint design; rebuild from authorized source; no private global scans. |
| Operational status replica | PK run/job ID, SK event sequence; publish from SQL outbox. | Event sequence/version prevents stale overwrite; SQL remains source until explicit cutover. |

Do not adopt a generic "single table for everything" design without enumerating
real queries, key cardinality, item sizes, write amplification, GSIs, pagination
and hot-partition behavior. Avoid an expensive scan-based recreation of the
existing relational dashboard.

## 5. AuraDB alternatives and Neptune economics

### 5.1 Neptune is a migration, not a configuration alias

AWS documents [openCypher access](https://docs.aws.amazon.com/neptune/latest/userguide/access-graph-opencypher.html)
and [Neo4j compatibility differences](https://docs.aws.amazon.com/neptune/latest/userguide/migration-compatibility.html).
Neptune has a Bolt endpoint as well as HTTPS; therefore "it cannot use Bolt" is
not a valid reason to reject it. However:

- Authentication/authorization, endpoint/network setup, query syntax/functions,
  constraints/indexes, bookmarks/consistency and bulk loading need adaptation.
- APOC, arbitrary custom procedures and Neo4j-specific facilities do not become
  available merely because queries use openCypher.
- Current [graph fusion](../../mathbank-rest/src/mathbank_rest/db/hybrid_search.py)
  includes subqueries, list operations and reviewed-edge logic; test all actual
  queries and projectors, not a single `MATCH` demonstration.
- Published ownership-scoped projection deletion, canonical IDs, transactions,
  counts and reviewed-edge semantics must remain identical.
- Do not assume Neo4j GDS/vector/search features, if used elsewhere, map to
  Neptune Database. Neptune Analytics is a distinct product and cost model.

No private learner progress enters a shared graph in either provider.

### 5.2 Running floor and alternatives

The [Neptune pricing page](https://aws.amazon.com/neptune/pricing/) lists a
starting capacity of **1 NCU** for Neptune Database Serverless. The retrieved
Ohio Standard serverless price-list SKU is **$0.1608/NCU-hour**:

```text
1 NCU x 730 hours x $0.1608 = $117.384/month compute
```

This is a **running minimum**, not a complete bill or an HA configuration.
Storage, IO, replicas, backups, network and monitoring are additional. Larger
NCU use costs more. Do not confuse manually stopping a supported dev cluster
with request-driven scale-to-zero or assume no automatic restart conditions;
verify stop/start lifecycle separately before budgeting stopped time.

Neptune Analytics has its own minimum/capacity and paused-pricing behavior;
it is not the default cheap transactional graph replacement. Do not provision
it accidentally while evaluating Neptune Database.

Compare these alternatives before a migration:

| Option | Value | Limitation |
|---|---|---|
| Keep Aura with tuned usage/plan | No application rewrite; known current Cypher/projection behavior. | Actual bill/plan, compute sizing and pause options need authorized inspection. |
| Neptune Database provisioned | A small suitable instance could be cheaper than Serverless's running floor. | Still has compute/storage/network floor and compatibility work; price the actual size/availability model. |
| PostgreSQL adjacency + bounded recursive queries/materialized recommendations | May eliminate a separate graph bill for a small set of fixed traversals. | Benchmark current retrieval, visualization and dependency workloads; not an unbounded graph replacement by assertion. |
| Derived DynamoDB adjacency lists | Efficient known one-hop lookups and precomputed recommendations, true on-demand requests. | No arbitrary openCypher traversal; multi-hop queries become application work, denormalization and extra reads. |
| Local/dev Neo4j with controlled start/stop | Existing local option; low marginal cloud bill. | Not managed production HA; hardware, backup, availability and operations remain real costs. |

**Decision gate:** migration is economical only when steady-state savings exceed
network/operations/rewrite cost and all graph acceptance tests pass. Without the
current Aura invoice, neither "Neptune saves money" nor "Aura is cheaper" is proven.

## 6. Keeping PostgreSQL while moving its provider

### 6.1 Aurora Serverless v2

The official [auto-pause documentation](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-auto-pause.html)
explicitly supports **0 ACUs** on compatible engine versions/configurations.
Older claims that all Aurora Serverless v2 has a permanent 0.5-ACU minimum are
outdated. PostgreSQL support starts at documented releases including 16.3,
15.7, 14.12 and 13.15; verify the exact current region/major/minor compatibility.

Zero minimum does **not** guarantee zero monthly compute:

- Connections, features, jobs, health polling or incompatible settings can
  prevent pause or repeatedly wake a cluster.
- Resume delay must fit the UI/API timeout budget.
- Storage, backup, IO and related network/services can remain charged.
- RDS Proxy/persistent connection behavior must be tested, not assumed to
  improve pause economics.

The documented local/selected snapshot uses PostgreSQL 18.6; do not assume a
target Aurora version supports identical extensions/features or can restore a
newer-major dump unchanged. Audit `vector`, `pg_trgm`, provider-specific
`pg_session_jwt`, grants/auth integration, functions/triggers, migration order
and the ADK session schema. A compatible PostgreSQL engine is lower rewrite risk
than replacing the relational domain with DynamoDB, but still requires migration.

### 6.2 Other candidates

- **RDS PostgreSQL:** compare a small single-AZ development instance and a
  separately priced production HA design. Compute/storage/backups continue
  according to provisioned lifecycle, not individual requests.
- **Aurora DSQL:** not interchangeable with full PostgreSQL/Aurora. Check
  extensions, SQL/transaction/constraint compatibility first; do not assume
  pgvector and current triggers work.
- **Self-managed PostgreSQL on EC2:** potentially lower raw dev compute cost,
  but responsibility for patching, restore, availability and security shifts
  to the team. Not a free managed database.
- **Stay on Neon and optimize:** remove unnecessary indexes/duplicate vectors,
  cap background polling, archive cold payloads and measure autosuspend behavior.
  A migration is unnecessary if the current tier cannot be reduced by offloading.

For all AWS relational options include VPC routing, connection limits/TLS,
secrets, backup/restore and any required NAT or interface endpoints. S3/DynamoDB
gateway endpoints can avoid NAT for those services, but do not automatically
provide private internet access to every Bedrock/AgentCore/SSM dependency.

## 7. Verified unit rates and reproducible cost scenarios

### 7.1 Evidence and assumptions

Rates below are public on-demand **USD, us-east-2**, retrieved 2026-10-25.
They exclude tax, negotiated discounts, commitments, temporary credits and
free-tier consumption shared with other projects. They are **unit prices and
illustrations, not a measured bill**.

Direct public price lists used:

| Service | Public price-list URL | Publication timestamp returned |
|---|---|---|
| S3 including Vectors | [Ohio AmazonS3 JSON](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/us-east-2/index.json) | 2026-10-15T17:35:40Z |
| DynamoDB | [Ohio AmazonDynamoDB JSON](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/us-east-2/index.json) | 2026-09-11T12:44:22Z |
| Neptune | [Ohio AmazonNeptune JSON](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonNeptune/current/us-east-2/index.json) | 2026-09-11T12:44:56Z |
| AgentCore | [Ohio AmazonBedrockAgentCore JSON](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrockAgentCore/current/us-east-2/index.json) | 2026-10-19T23:33:18Z |

The public `current` URLs are mutable. Re-fetch and record the publication
timestamp/SKU before purchasing; do not treat this report as a reserved quote.

| Usage | Retrieved rate |
|---|---:|
| S3 Vectors logical storage | $0.06/GB-month |
| S3 Vectors PUT bytes | $0.20/GB uploaded, minimum 128 KB per PUT per pricing page |
| S3 Vectors query requests | $2.50/million |
| Query processing, first 100k vectors/index | $0.000003906/GB processed (approximately $0.004/TiB) |
| Query processing, next vectors up to 10m/index | $0.000001953/GB processed (approximately $0.002/TiB) |
| Query processing, above 10m/index | $0.000000391/GB processed (approximately $0.0004/TiB) |
| Query returned bytes | $0.01/GB after per-query allowance; minimum size/result applies |
| S3 Vectors other Tier1/Tier2 API requests | $0.055/1,000 requests; classify the actual API usage before budgeting it |
| DynamoDB Standard on-demand writes | $0.625/million WRUs |
| DynamoDB Standard on-demand reads | $0.125/million RRUs |
| DynamoDB Standard storage | $0.25/GB-month beyond shared eligible allowance; scenarios below ignore free storage |
| Neptune Database Serverless Standard | $0.1608/NCU-hour |
| AgentCore consumption Runtime original CPU / memory | $0.0895/vCPU-hour / $0.00945/GB-hour |
| AgentCore consumption Runtime v2 CPU / memory | $0.1276/vCPU-hour / $0.0169/GB-hour |

Sources: [S3 billing examples](https://aws.amazon.com/s3/pricing/),
[DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/),
[DynamoDB unit semantics](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html),
[Neptune pricing](https://aws.amazon.com/neptune/pricing/),
[AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/), and the
regional JSON above.

Runtime prices differ by compute generation/type. The current AgentCore page
explains memory reclamation in v2, I/O-wait CPU behavior and minimum billing;
do not multiply an old CPU rate by a new runtime's memory behavior. Harness,
Gateway, memory, evaluation, model tokens, logs and code/ECR storage may be
separate charges. Pick the actual configuration before estimating its bill.

### 7.2 S3 Vectors scenarios

Assume one index, float32 1,536-dimensional vectors, 1,024 bytes of filterable
metadata and a 64-byte key; no non-filterable metadata:

```text
bytes/vector = 1536 x 4 + 1024 + 64 = 7,232
logical_GiB = N x 7,232 / 2^30
storage = logical_GiB x 0.06
initial_upload = logical_GiB x 0.20
requests = Q x 0.0000025

tier1 = min(N, 100000)
tier2 = max(0, min(N - 100000, 9900000))
tier3 = max(0, N - 10000000)
processing = Q x (7,232 / 2^30) x
             (tier1 x 0.000003906 +
              tier2 x 0.000001953 +
              tier3 x 0.000000391)
```

The JSON labels units GB; binary conversion above matches the AWS page's
logical-vector examples. Use its precise SKU conventions for final billing.

| Illustrative workload | Logical GiB | Storage/month | Initial full PUT | Query/month incl. processing | Recurring storage + query |
|---|---:|---:|---:|---:|---:|
| 100k vectors, 10k queries/month | 0.6735 | $0.0404 | $0.1347 | $0.0513 | **$0.0917** |
| 1m vectors, 100k queries/month | 6.7353 | $0.4041 | $1.3471 | $1.6970 | **$2.1011** |
| 10m vectors, 1m queries/month | 67.3532 | $4.0412 | $13.4706 | $135.3563 | **$139.3975** |

These are deliberately **not claims about current corpus size/traffic**.
Rows are calculated with the retrieved Ohio rates, not an "up to 90%" marketing
claim applied to the Neon bill.

Additional charges/conditions:

- Batched PUTs must meet the payload/dimension limits; small requests below the
  minimum are billed at 128 KB, so one-vector-per-request uploads can cost more.
- Rewrites add PUT bytes. Deleted/overwritten bytes can remain in storage/index
  size accounting until reclamation, even after query results reflect deletion.
- AWS's detailed billing text gives a first **512 KB/query** returned-data
  allowance, minimum 256 bytes/result; its examples also use rounded "500 KB".
  These scenarios assume top-10 key+small metadata responses well below either.
  Returning full vectors/large metadata or broad result sets must be priced
  against actual response accounting separately.
- Query processing is based on index vector count and vector+key+filterable
  metadata bytes, not merely the number of neighbors returned or filter matches.
  Filtering to one topic does not automatically make it a one-topic-sized bill.
- Worker/Lambda, embedding queries, control/list/get operations, KMS/logging,
  transport and SQL hydration are excluded from the table and must be added.
- Retaining pgvector during shadow mode temporarily **increases** cost.
  Offloading has not saved money until the old billed footprint/tier is reduced.

### 7.3 DynamoDB scenarios

Request-unit accounting:

```text
WRUs = writes x ceil(item_KiB / 1) x transaction_multiplier
RRUs = reads x ceil(item_KiB / 4) x consistency_multiplier

consistency_multiplier = 0.5 eventual, 1 strong, 2 transactional
transaction_multiplier = 1 ordinary, 2 transactional
cost = WRUs/1m x 0.625 + RRUs/1m x 0.125
     + billed_storage_GiB x 0.25
     + indexes + backups + streams/exports + network + application work
```

Real Query/Scan cost depends on items/bytes evaluated, pagination, minimums and
filter behavior; it is not simply one point-read unit per HTTP request.
Item size includes attribute names and values. GSIs add storage/write cost.

| Illustration | Requests | Storage | Base monthly subtotal |
|---|---:|---:|---:|
| 100k ordinary <=1 KiB writes; 1m eventually consistent <=4 KiB point reads; 1 GiB stored | $0.125 | $0.25 | **$0.375** |
| 1m ordinary 2 KiB writes; 10m strong <=4 KiB point reads; 20 GiB stored | $2.50 | $5.00 | **$7.50** |

No GSIs, backups, exports or free tiers are assumed in these subtotals.
For perspective, the public pricing example uses PITR at $0.20/GB-month;
20 GB of protected data adds about **$4/month** before any indexes/other
features. Recheck the actual region/SKU and required retention configuration.
Transactional reads/writes cost more; an event+receipt+state transaction
contains multiple billed item operations.

These numbers show why a small disposable inbox can be cheap, not why moving
transactional course/learner tables necessarily reduces total cost.

### 7.4 Compute/workflow cost is additional

AgentCore and Bedrock inference are new spend for the Studio, not savings from
database migration. Per-month estimation must include:

```text
AI invocations = transition_requests x ambiguous_eligible_fraction
               + authoring_jobs x bounded_proposal_and_critic_calls
model_cost = input_tokens x selected_input_rate
           + output_tokens x selected_output_rate
runtime_cost = billed_CPU_hours x selected_CPU_rate
             + billed_memory_hours x selected_memory_rate
workflow_cost = state_transitions_or_Express_requests_and_duration
```

Use [Step Functions pricing](https://aws.amazon.com/step-functions/pricing/) and
the actual execution type/region for a quote. Retries, authoring fan-out and
simulation all multiply usage. Memory during model I/O waits and session
lifetime can still be billable according to runtime generation.

Avoid holding agent sessions/Lambda executions while a student is idle. The
Studio design runs deterministic rules first and uses short transitions.
Budget notifications are not a hard spend ceiling; enforce application quotas,
iteration/token limits and a pause switch.

### 7.5 Total-cost and break-even worksheet

```text
current_monthly =
    actual_Neon_compute_storage_IO_backups_egress
  + actual_Aura_plan_usage_backups_egress
  + existing_AWS_and_external_model_costs

target_monthly =
    remaining_SQL_and_graph_bill
  + S3_objects_and_vectors + DynamoDB_requests_storage_indexes_backups
  + AWS_relational_or_graph_compute_storage_IO_if_selected
  + Lambda_StepFunctions_AgentCore_Bedrock
  + VPC_NAT_endpoints_transfer + KMS_logs_monitoring
  + incremental_operational_cost

net_monthly_saving = current_monthly - target_monthly
payback_months = one_time_migration_cost / net_monthly_saving
                (only meaningful if net_monthly_saving > 0)
```

Offloading vectors can reduce SQL storage and ANN memory pressure, but if Neon
compute is already autosuspending and the remaining relational data keeps the
same minimum paid tier, its bill might barely move. Adding even a small
always-on network/graph component can erase vector savings.

Illustration, **not measured**: $20/month lower Neon bill minus $2.10 vector
storage/query plus $3 worker/other overhead yields $14.90/month net. A $1,000
migration then takes about 67.1 months to repay. If Neon drops by $0, that same
offload increases spend. Engineering time belongs in the decision.

## 8. Measurement required before selecting a target

| Evidence | How to collect with operator approval | Decision it informs |
|---|---|---|
| Neon/Aura invoices and plan limits | Redacted 30-90-day billing/export; committed minimum, storage/compute/backup/transfer lines. | Actual available savings; no provider-plan guess from corpus counts. |
| Table/index/TOAST sizes and growth | Metadata-only SQL snapshot by schema/table; separately inspect embedding/index bytes. | Which bytes dominate; table count is irrelevant. |
| Vector model/dimension/status counts | Aggregate only, by source/model/profile/dimension; include rebuild/write frequency. | S3 index compatibility and cost. |
| Query rates/filters and cold/warm latency | Aggregated application traces/query statistics without private query text; p50/p95/p99 and concurrency. | ANN parity, filtering, sizing and network latency. |
| Graph query/projector features | Inventory used Cypher/procedures/drivers and representative authorized fixtures. | Neptune/DynamoDB/SQL viability. |
| Candidate DynamoDB access patterns | Point read/query/scan rates, item-size distribution, pagination and GSI requirements. | Request/write amplification and hot partitions. |
| Aurora pause/connection behavior | Isolated authorized pilot, selected engine/extension compatibility, cold resume and connection lifetime. | Whether zero ACUs actually occurs. |
| Backup/restore/privacy requirements | RPO/RTO, retention, encryption/deletion, private vs published content and region constraints. | Costs that cannot safely be omitted. |

Example **read-only metadata SQL**, not executed in this pass:

```sql
SELECT schemaname, relname,
       pg_size_pretty(pg_table_size(relid)) AS table_and_toast,
       pg_size_pretty(pg_indexes_size(relid)) AS indexes,
       pg_size_pretty(pg_total_relation_size(relid)) AS total
FROM pg_catalog.pg_statio_user_tables
WHERE schemaname NOT IN ('neon_auth', 'agent_sessions')
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 50;
```

Provider/framework schemas are excluded from that sample to avoid conflating
application ownership; their aggregate size can be reviewed separately under
the appropriate access policy. Do not export row contents, credentials or
private learner prompts to pricing/research tools.

## 9. Staged migration and rollback plan

| Stage | Work | Acceptance / rollback |
|---|---|---|
| M0 Measure | Capture section 8 evidence and approved budgets/SLOs. | No data movement; select candidate only when a bill reduction is plausible. |
| M1 Storage hygiene | Archive approved cold logs/payloads to private S3; tune polling/retention/indexes without removing needed evidence. | Restore drill and retention review; preserve SQL references and current API behavior. |
| M2 Vector shadow | Choose taxonomy/misconception family; backfill existing vectors, outbox projection, compare to pgvector. | Section 3 thresholds; no production reads switched; delete isolated trial resources only after review. |
| M3 Vector canary | Feature-flag a bounded public workload; recheck SQL eligibility; measure cost/quality/latency. | Provider switch back to retained pgvector; preserve source IDs/model hashes; no silent failed-index fallback. |
| M4 DynamoDB pilot | Derived notification inbox or isolated job-status aggregate; outbox/SQS delivery and conditional update tests. | Rebuild from SQL/events; no distributed business transaction; lease/replay/TTL/owner tests. |
| M5 Provider pilot | Only if M0 justifies it: Aurora or Neptune isolated restore/projection, not simultaneous mass cutover. | Exact schema/query/restore/ownership/performance parity and full network quote. |
| M6 Approved cutover | Document writer freeze/high-water mark, replay/catch-up, parity, identity/DNS/config change and canary. | One authoritative writer; predeclared rollback window/checkpoints and restore procedure. |
| M7 Retire old costs | After recovery window and acceptance, operator retires old indexes/provider/resources. | Verify the invoice actually dropped; retain legally required snapshots; never delete a provider account automatically. |

No uncoordinated application dual writes. Use the authoritative store's outbox
and idempotent delivery; derive copies. A cutover of authoritative job storage
requires its own writer/lease freeze and replay plan. Do not remove original
vectors until quality/rebuild/rollback evidence and the recovery window pass.

## 10. Prioritized recommendation register

| ID | Priority | Recommendation | State |
|---|---|---|---|
| COST-01 | P0 | Obtain redacted provider bills and aggregate size/traffic evidence. | Not performed; no access assumed. |
| COST-02 | P0 | Keep Studio transactional state in PostgreSQL; reuse the existing CDK project. | Proposed architecture in doc 65. |
| COST-03 | P1 | Shadow S3 Vectors for one public derived embedding family, with exact-filter/recall/cost tests. | Not implemented. |
| COST-04 | P1 | Move large/disposable bytes to ordinary private S3 where appropriate; verify retention/restore. | Workload-specific audit required. |
| COST-05 | P2 | Trial DynamoDB notification/status projections or isolated disposable jobs, not canonical domain tables. | Not implemented. |
| COST-06 | P2 | Price Aurora PostgreSQL with real pause, extension and network behavior if AWS-only is valuable. | Not benchmarked; no target selected. |
| COST-07 | P3 | Evaluate Neptune only against actual Aura bill and full query/projection parity; compare SQL/precomputed adjacency first. | No cost-saving claim established. |
| COST-08 | P0 before live AI | Meter model/runtime/workflow spend separately; enforce hard application limits and reviewed fallback. | Required by doc 65; not implemented. |
| COST-09 | P0 before recurring corpus updates | Implement reviewed batch CRUD, revision-aware invalidation, locked human metadata and delta reindex/deletion reconciliation. | Sections 12 and 17.4; proposed, not implemented. |
| COST-10 | P1 | Compare low-maintenance MKB with KB+S3 Vectors/direct vectors for the selected workload, including region, metadata rewrite and retrieval fan-out costs. | Section 13; MKB not currently listed in Ohio. |
| COST-11 | P2 | Start AWS analytics with authorized S3/Parquet/Glue/Athena exports; choose Iceberg/S3 Tables when corrections/deletes justify maintenance fees. | Section 16; no warehouse or source-provider move required. |
| COST-12 | P3 | Evaluate existing rules/RAG and small supervised models before custom tutor LLM training; reuse existing ML projects. | Section 17; no dataset, model or endpoint created. |

**Bottom line:** an AWS-native hybrid is feasible, but the economical first move
is targeted derived-storage offload plus measurement, not wholesale replacement
of relational tables or automatic migration from Aura to Neptune.

## 11. Official reference register

All links below were directly retrieved, or are the public regional JSON
sources parsed for this report. Prices/limits remain subject to change.

- [S3 Vectors overview and consistency](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors.html)
- [S3 Vectors limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html)
- [S3 pricing and vector billing examples](https://aws.amazon.com/s3/pricing/)
- [DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)
- [DynamoDB constraints and request units](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Constraints.html)
- [Neptune pricing](https://aws.amazon.com/neptune/pricing/)
- [Neptune openCypher](https://docs.aws.amazon.com/neptune/latest/userguide/access-graph-opencypher.html)
- [Neptune/Neo4j compatibility](https://docs.aws.amazon.com/neptune/latest/userguide/migration-compatibility.html)
- [Aurora PostgreSQL pricing](https://aws.amazon.com/rds/aurora/pricing/)
- [Aurora Serverless v2 zero-ACU auto-pause](https://docs.aws.amazon.com/AmazonRDS/latest/AuroraUserGuide/aurora-serverless-v2-auto-pause.html)
- [AgentCore regional matrix](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agentcore-regions.html)
- [AgentCore pricing and runtime compute types](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [Step Functions AgentCore integration and timeout behavior](https://docs.aws.amazon.com/step-functions/latest/dg/connect-bedrockagentcore.html)
- [Step Functions pricing](https://aws.amazon.com/step-functions/pricing/)

The public AWS service-offer index is
[here](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/index.json).
Select the service, region, exact SKU and OnDemand price dimension, rather than
copying a search summary's estimate or mixing Neptune Analytics with Database,
DynamoDB Standard with Standard-IA, or AgentCore Runtime generations.

## 12. Recurring admin ingestion, correction and batch reindexing

### 12.1 Current behavior and implementation gap

The [ingestion project](../../mathbank-data-ingestion/README.md) crawls,
classifies, reviews and exports local files. Its
[tracking module](../../mathbank-data-ingestion/src/mathbank/db/tracking.py)
records each invocation in local SQLite plus log files; PostgreSQL ETL and
graph projection have separate run tracking. Preserve the distinction between
process exit, processed counts, validated content, accepted import and completed
projection. A clean script exit is not evidence that every source was accepted.

The [existing corpus authoring service](../../mathbank-rest/src/mathbank_rest/corpus_authoring.py)
already provides private drafts, statement-hash conflict detection and human
decisions. Approved text edits mark `PROBLEM_STATEMENT` representations STALE;
the response explicitly says that paid indexing/graph publication was **not**
run. This is not a complete document/solution/image/metadata dependency
invalidation or automatic AWS batch pipeline. The design below is new work,
not a claim that existing CRUD triggers all these stages.

Reuse [import staging/reconciliation](../../mathbank-db/sql/010_textbook_import.sql),
[admin reviews](../../mathbank-db/sql/019_admin_import_review.sql),
[outbox/projection requests](../../mathbank-db/sql/018_outbox_consumers.sql),
existing corpus/step embedding ETL and `mathbank-graph` projectors. Extend
contracts and supported projection targets additively; current enums do not
already represent every proposed AWS task.

[Requirement 57](57_ML_NIGHTLY_REINDEXING_REQUIREMENTS.md) means refreshing ML
features/graph projections, **not** corpus chunk/vector reindexing. Keep their
manifests, watermarks, job types and acceptance separate; a corpus publication
can enqueue a subsequent feature refresh without conflating job success.

### 12.2 Proposed lifecycle and ownership

```text
Staff bulk upload -> private S3 quarantine + immutable import manifest
  -> validate/parse -> staging and conflict report -> human review
  -> REST transaction: accepted revisions + invalidation/tombstones + outbox
  -> coalesced delta manifest -> Step Functions Standard bounded batch
  -> parse/chunk changed units -> agent metadata proposals -> review/merge
  -> embed only changed embedding inputs -> project vectors/graph/FTS
  -> reconcile counts + retrieval probes -> CAS activate verified generation
  -> completion report / failed-item retry / deletion and freshness ledger
```

| Phase | Required behavior |
|---|---|
| Receive | Authorized staff upload via bounded signed URLs; private quarantine, file/type/size checks, malicious-file handling, rights/source citation, content hashes, duplicate/import keys and object-version references. Do not treat bucket notifications as publication permission. |
| Stage | Explicit INSERT/UPDATE/DELETE intent per document/question; identify canonical ID, base revision, package membership, conflict policy, expected counts and affected dependencies. Preview diff and estimated paid work before approval. |
| Review | Validate math/LaTeX, problem/solution/diagram separation, taxonomy IDs, source rights and disclosure. Distinguish reject, revise, approve and mathematical certification. Support item-level decisions within a batch. |
| Commit | `mathbank-rest` alone commits runtime canonical mutation, audit, dependency invalidation and durable outbox in one SQL transaction. Existing authorized offline ETL remains the separate import path; do not give every new Lambda direct database writes. |
| Dispatch | Outbox delivery emits an idempotent batch request; SQS/EventBridge scheduling coalesces repeated edits over a configurable, approved window. Scheduled reconciliation catches missed/stalled work; no always-on polling service is required. |
| Execute | Standard Step Functions, bounded Map concurrency and short task Lambdas. Persist large inputs/results/manifests in S3 rather than state payloads. Long OCR/render/parse jobs exceeding Lambda's 15-minute limit use an approved managed async job or bounded container task, not an oversized Lambda. |
| Enrich | AgentCore/Bedrock produces schema-validated proposals with evidence and input versions. Apply only approved policy/human overrides; it cannot publish content, override a newer edit or award mastery. |
| Project | Reuse existing projection owners. Track FTS/chunks, each vector family, graph and caches separately. Write receipts after verified side effects; a graph partial commit is not a completed generation. |
| Accept | Reconcile expected/new/changed/skipped/failed/deleted counts and revision/hash coverage; execute student-disclosure, filter and retrieval probes. CAS the active generation only if source watermark and selected revisions are still current. |
| Operate | Admin sees queued/running/blocked/partial/failed/completed/cancelled and per-item errors, cost estimates, lag and retry eligibility. Cancellation fences future writes; reconcile any already-running remote job. Never label a partially failed run as complete. |

Use a stable document/question ID and **new immutable revision IDs** on edits.
Keep existing chunk IDs and explicit old-to-new mappings during migration;
for newly generated chunks, derive a stable key from source revision,
representation kind, chunker version and structural locator/content hash.
Store ordinal separately: inserting a paragraph must not silently rebind old
chunk evidence to unrelated text. Preserve page/bounding region, textbook
step, diagram, hint and source spans. Do not split math environments blindly
or merge hidden solutions/keys into a student question chunk.

### 12.3 Changes that require different work

| Dirty reason | Required delta / embedding rule |
|---|---|
| Statement/solution/transcript text changes | Revalidate affected source units and dependent representations; rechunk changed units, embed changed embedding-input hashes, retire old chunks and refresh affected graph/FTS. Do not rebuild the entire corpus for one edit. |
| Diagram/OCR/source correction | Reparse only affected pages/assets and dependent descriptions; regenerate vectors only if their actual text/image embedding inputs change. Recheck source/solution-side disclosure. |
| Filter-only metadata or review state | Update authoritative eligibility immediately and project metadata; reuse vectors when embedding input/model is unchanged. Managed KB exceptions are in section 13. |
| Metadata included in embedding text | A technique/skill-signature or `includeForEmbedding` change is an embedding-input change, not a free filter-only update. |
| New agent proposal/prompt version | Generate new proposal lineage; do not rewrite accepted human metadata automatically. Embed only if accepted embedding inputs change. |
| Taxonomy remap/merge | Review references/aliases, project filter/graph changes, reembed affected semantic signatures only; preserve historical release bindings. |
| Chunker/parser/profile/model change | Separate shadow generation and explicit rebuild scope. New embedding space requires a separate compatible index and full affected-family reembedding. |
| Delete/withdraw/unpublish | SQL tombstone/eligibility denies retrieval immediately; enqueue exact chunk/vector/graph/cache removals and track all acknowledgements. Reimport cannot resurrect a tombstone without an explicit authorized new revision. |
| Reinsert/reimport | Resolve canonical IDs/aliases and base revision; preserve admin edits. Duplicate source content is a no-op or conflict, not unconditional INSERT or overwrite. |

Normal delta jobs, metadata reenrichment, deletion reconciliation, failed-item
retry, full index rebuild and model migration are distinct admin operations.
Require a reason/scope, dry-run counts, cost cap and confirmed authorization
for broad reenrichment/reembedding. A periodic full scan may reconcile hashes
without regenerating all embeddings.

### 12.4 Continuously enriched chunk metadata

Existing [step-vector metadata](../../mathbank-db/sql/011_step_vector_metadata.sql)
already carries canonical step/item/taxonomy IDs; current representation,
chunk and embedding hashes/profiles in
[002](../../mathbank-db/sql/002_vector_schema.sql) are reusable foundations.
Existing [enrichment/approval](../../mathbank-db/sql/008_automatic_metadata.sql)
and [relationship jobs](../../mathbank-db/sql/009_relationship_enrichment.sql)
do not by themselves provide the complete following proposed contract.

| Metadata layer | Required fields / semantics |
|---|---|
| Identity and lineage | Document/question/source revision, representation/chunk IDs, structural locator/page, parent chunk, text/input hash, parser/chunker/preprocessing version, object version and provenance/rights. |
| Retrieval/authorization | Canonical taxonomy IDs, entity/chunk kind, competition/year/book, approved release, audience/disclosure class and ownership partition. Server-derived trusted fields cannot be agent-controlled. |
| Agent proposal | Enrichment ID, input hash/revision, model/provider/version, prompt/schema/taxonomy versions, proposed values, confidence, evidence source spans and validation errors. Confidence is not approval. |
| Human override | Field-level accepted/locked values, actor identity/capability, reason, before/after hashes, review time and base version. Agent reruns preserve locks and expose conflicts for review. |
| Effective metadata | Deterministic merge of approved canonical data and allowed proposals, effective metadata hash/version, review/publication state and explicit provenance per accepted field. |
| Projection | Embedding model/dimension/input hash, index/generation, source watermark, job/attempt, indexed hash/time, deletion status and last error. |

Keep full evidence/proposals in SQL or private versioned S3 with SQL identity
and review records. Project only necessary compact filter attributes into the
vector store: S3 Vectors' 2 KB filterable/40 KB total metadata limits and KB
connector limits make it unsuitable as the full provenance database. Never
truncate required metadata silently; reject/report oversize entries. Exclude
raw learner identity/work from public corpus metadata.

Use proposed idempotency key
`(operation, entity_id, source_revision, input_hash, pipeline_version, target)`.
Leases have an owner/fencing version; retry completion uses CAS. A result for
revision N cannot overwrite admin-approved revision N+1. A deleted source
cannot be republished by a late worker. No SQL+S3+DynamoDB distributed
transaction is assumed: use outbox, idempotent receipts and reconciliation.

For activation, store immutable per-unit generation membership and a verified
manifest. Delta jobs reuse unchanged memberships; full rebuilds use shadow
indexes. A CAS SQL pointer is not an atomic multi-object/vector-store swap:
retrieval must filter/check the selected generation and canonical eligibility
before sending any text to a model. If the selected service cannot isolate
generations, use a shadow KB/index and controlled adapter cutover.

Deletion needs two states: **logically inaccessible** and **physically purged**.
Track source objects/versions, chunks, all embedding families, graph links,
caches, KB documents, analytics snapshots, training exports and backups under
the approved retention/legal policy. DynamoDB TTL and S3 lifecycle are not
immediate erasure acknowledgements. Old immutable releases must not regain
student visibility; retained audit evidence needs restricted access.

## 13. Low-maintenance S3 knowledge: three different options

### 13.1 Feasibility and pros/cons

| Option | Advantages | Disadvantages / acceptance gates |
|---|---|---|
| **Bedrock Managed Knowledge Base (MKB)** | Bedrock owns ingestion, parsing, vector/text storage, managed embeddings/reranking and hybrid retrieval. Native AgentCore Gateway `Retrieve`/`AgenticRetrieveStream`; no vector database administration. Best low-maintenance document-library candidate. | Not currently listed in `us-east-2`; a supported region and residency/network decision are required. No direct customer vector-store access; not a raw copy destination for existing OpenAI 1536-dimensional vectors. Fine-grained metadata, custom pre-split/no-chunking behavior and deletion/generation isolation must pass a pilot. Managed retrieval is not exact SQL-filtered grading retrieval. |
| **Customer-managed Bedrock KB + S3 Vectors** | Managed ingestion/embedding plumbing and incremental S3 sync with a customer-owned serverless vector index. Sidecar metadata and custom transformation Lambda support chunk-level enrichment/custom chunking. Lower database operations burden than a provisioned vector cluster. | You still own source projection, chunk-policy correctness, IAM, target/index configuration and sync reconciliation. Embedding/parser/reranking/generation charges can be additional. Custom transform or CSV metadata edits can force document reembedding. Backend-specific filters/search support must be tested. |
| **Direct canonical chunks + S3 Vectors** | Reuses current math-aware chunks, hashes, model vectors and field-level provenance; precise changed-only embedding and metadata upsert control. Avoids KB reparsing and copying compatible vectors needs no new inference. Strong fit for existing tightly constrained retrieval. | Most application engineering: query embeddings, lexical fusion, metadata packing, index lifecycle, reconciliation and quality tests remain ours. S3 Vectors is not itself a knowledge base, keyword engine or agent. |
| **Retain pgvector/Neon** | Least migration work; existing SQL eligibility/FTS and exact filtered step search remain together. One transactional boundary and known queries. | Potential vector storage/ANN memory pressure and provider separation; not automatically expensive if current compute suspends. Maintenance/total cost must be measured rather than assumed. |

**Recommendation:** keep canonical edits/reviews in PostgreSQL and approved
files in S3. Evaluate MKB for an **admin/reference library** if a supported
region is acceptable. For the current student step/question search, compare
retained pgvector against direct S3 Vectors first; evaluate KB+S3 Vectors when
managed document ingestion saves enough work without losing enriched metadata
or disclosure guarantees. Do not deploy all three in production by default.

AWS's [managed-KB region list](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-regions.html)
includes N. Virginia, Oregon, Ireland, London, Frankfurt, Tokyo, Singapore,
Sydney and GovCloud West at retrieval time, **not Ohio**. General Bedrock or
AgentCore availability in Ohio is not evidence that MKB is available there.
The [managed ingestion guide](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-customize-ingestion.html)
supports DEFAULT/FIXED_SIZE/NONE for text, not semantic chunking; chunking
strategy cannot change after connecting the source. Pre-split approved chunk
objects with NONE are a candidate, not proof that every existing metadata
field/ID survives. Do not assume the customer-managed transformation-Lambda
contract is supported by MKB.

The [managed creation/connector APIs](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-create.html)
use `type: MANAGED` and `MANAGED_KNOWLEDGE_BASE_CONNECTOR`.
Managed `Retrieve` uses `managedSearchConfiguration`, not
`vectorSearchConfiguration`. Native Gateway integration is specifically for
MKB; a customer-managed KB needs our own bounded authorized tool adapter.
Prefer retrieval-only for student grounding: agentic full-document expansion
or generated answers can reveal future hints/solutions before application
checks. Public question, hidden solution, staff reference and learner-private
material require explicit separate access/disclosure boundaries.

### 13.2 Sync, metadata-only updates and deletion traps

For the customer-managed S3 connector,
[incremental sync](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-data-source-sync-ingest.html)
processes added/modified/deleted documents; no-change documents are skipped.
Normally a changed document is reparsed, rechunked, reembedded and reindexed.
AWS documents a metadata-only optimization **only when**:

1. Only sidecar `metadata.json` files changed, not content.
2. Content is not CSV.
3. The source does not use a custom transformation Lambda.

This matters directly to continuous enrichment: the
[custom transformation](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-custom-transformation.html)
can attach **chunk-level** metadata, which overrides colliding file metadata,
but disqualifies that sync optimization. Do not promise metadata-only Bedrock
updates are free of embedding calls in that design. A direct index pipeline
or pre-split objects with sidecars may reduce rewrites; verify exact behavior
and billing for the selected embedding inputs/configuration.

[Sidecars](https://docs.aws.amazon.com/bedrock/latest/userguide/s3-data-source-connector.html)
must be beside the matching content object with `.metadata.json` appended,
and are limited to 10 KB. `includeForEmbedding` changes the semantic input.
Do not confuse document sidecars with arbitrary per-chunk metadata.

[Direct ingestion](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-direct-ingestion.html)
supports the documented S3/custom-source path, including add/update/delete.
For an S3 source, direct KB mutations do **not** update source S3 objects:
reconcile the source too or later sync can undo the change. Do not submit
direct ingestion and `StartIngestionJob` concurrently. Select one serialized
writer protocol per source; do not assume these operations have identical
support across MKB and customer-managed configurations.

Poll job/document statuses with bounded waits/backoff, reconcile statistics
and record errors; `COMPLETE` alone is not corpus acceptance. The sync guide
warns retrieval visibility can lag completion. Test exact update/delete
behavior on the selected backend, rather than inferring KB freshness from S3
Vectors' own strong consistency.

For MKB, the
[connector deletion safeguard](https://docs.aws.amazon.com/bedrock/latest/userguide/kb-managed-connect-ds.html)
can skip the delete phase when the deletion percentage exceeds its configured
threshold (default 15 when enabled). Large admin deletion batches must surface
that condition and use an explicitly approved purge procedure, not report
physical deletion success. SQL tombstones still deny access immediately.
Separately inspect data-source `RETAIN`/`DELETE` policy: deleting a connector
or KB is not a substitute for a verified document-erasure workflow.

### 13.3 Current MKB pricing versus direct vector pricing

The [Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/), retrieved
2026-10-25, lists the following **MKB** public rates. These are website rates,
not Ohio SKU quotations or an account invoice; recheck target-region terms.

| Component | Published rate / inclusion |
|---|---|
| Managed index storage | **$5 per GB of raw data/month**. This is raw-data billing, not vector-byte billing. |
| Standard `Retrieve` | **$1 per 1,000 API calls**. |
| Managed agentic planning | **$4 per 1,000 Agentic Retrieve calls**, plus **$1 per 1,000 underlying Retrieve calls**. |
| Managed parser/embedding/reranker | Included at no extra charge when using service-managed defaults. |
| Custom models / other services | Custom embedding/reranking/planning model charges, Gateway tool calls, CloudWatch, source S3/KMS and other applicable services are additional. |

Illustrative **1 GB raw source + 10,000 standard retrievals/month**:
`1 x $5 + 10,000/1,000 x $1 = $15/month`, before additional services.
For **1 GB + 10,000 agentic calls with three underlying retrievals each**:
`$5 + $40 + $30 = $75/month`, before other applicable charges.
Three retrievals is a scenario assumption, not a service bound. Verify whether
any selected response-generation/model option adds inference charges.

Do not compare those totals directly with section 7's vector-only scenarios
as if they provide identical parsing, embedding, hybrid search, reranking and
model generation. MKB trades higher bundled service pricing for fewer moving
parts. At low traffic engineering/maintenance savings may outweigh the
difference; at high query volume price the full service and fan-out.

### 13.4 Changed-only batch cost worksheet

```text
embed_units = changed_embedding_input_hashes + approved_model_migration_units
enrichment_tokens = selected_dirty_units x mean_proposal_input_output_tokens
custom_batch_cost =
    S3_source_versions_intermediates_requests_KMS
  + parser_OCR_pages_or_media_minutes
  + embedding_input_tokens_or_multimodal_units
  + enrichment_model_input_output_tokens
  + vector_bytes_PUT_and_metadata_rewrites + retrieval_probes
  + Lambda_GB_seconds + workflow_transitions + queue_delivery
  + graph_projection_compute + logs_and_failed_retry_work
```

Apply section 7 rates only to their matching dimensions; KB-managed full
document reingestion may cost more than the dirty-chunk estimate above.
Coalesce frequent edits before paid work, cache accepted results by hash/model,
cap retries and graph top-k recomputation, and use lifecycle rules for temporary
files with a documented debugging/recovery window.

Bedrock's pricing page advertises **50% lower batch inference prices for
select models** versus on-demand. This is useful for deferrable metadata
proposal generation, not synchronous tutoring. Validate selected model,
region, quotas, batch size, turnaround and supported operations first; it is
not a blanket discount for all embeddings, parsers or AgentCore tool loops.
Batch inference reduces token cost but does not remove human review,
per-record validation, idempotency or partial-failure accounting.

## 14. Full PostgreSQL-to-DynamoDB scope and economic decision

The [223-table register](66A_POSTGRES_TABLE_MIGRATION_ASSESSMENT.md) gives each
table its own placement recommendation and cost/coupling rationale. Five
source-defined vector tables are candidates for **S3 Vectors**, not DynamoDB.
The two expiring `studio` job tables are plausible **aggregate** pilots;
notifications and daily analytics are **derived serving views**. Event/audit
tables are not automatically disposable merely because they are append-only.

| Strategy | Pros | Cons / cost test |
|---|---|---|
| Retain current PostgreSQL authority | Existing joins/constraints/transactions; lowest engineering change; reuse autosuspend if effective. | External provider billing/egress; vectors/large JSON may increase memory/storage. Obtain actual invoice and size breakdown. |
| Targeted DynamoDB views/jobs | No idle request-based compute floor for on-demand table traffic; keyed reads and conditional updates, independent scaling. | More IAM/adapters/consumers, GSIs and privacy-deletion paths; SQL base bill may not fall. |
| Broad DynamoDB domain rewrite | Can remove a relational compute bill **only if** all remaining relational workloads are eliminated/redesigned. Good at known key-addressed aggregates. | No SQL joins/FKs/automatic cascades or general pgvector/FTS equivalent. Need denormalization, uniqueness sentinels, access-pattern indexes, new reporting/export design and saga compensation across aggregates. High parity/testing/rollback effort. |
| Aurora PostgreSQL provider migration | Preserves relational model and AWS integration; possible compatible zero-ACU idle behavior. | Version/extension/connection/restore tests, storage/IO/network/backup costs. Not the same project as a DynamoDB rewrite. |

For a genuine authoritative DynamoDB redesign, inventory **every** REST/ETL
reader/writer, lookup/reverse-lookup, sort/range/pagination, uniqueness rule,
CAS/idempotency receipt, cascade, release/evidence relation and transaction.
Model aggregates around atomic learner transitions or publication decisions,
not one DynamoDB table per existing SQL table. Up to 100 items/4 MB per
DynamoDB transaction does not create a SQL+DynamoDB transaction. Conditional
writes, repeated GSI entries, large-item rewrites and transactional operations
can multiply charges; scans are not acceptable replacements for every admin
filter/join. Erasure must traverse duplicated PII and denormalized references.

```text
DDB_monthly =
    sum(rounded_write_units x write_price, including indexes/transactions)
  + sum(rounded_read_units x consistency_price)
  + table_and_GSI_GB x storage_price
  + backups_PITR_restore + streams_consumers_exports
  + S3_analytics + required_search + network_KMS_logs
  + remaining_SQL_bill + operational_cost
```

Use section 7's request examples as **base-table illustrations**, not a full
rewrite quote. For example, 1 million 2 KiB writes plus two equally sized
all-attribute GSIs can raise modeled write units from 2 million to 6 million:
at $0.625/million, write charges go from **$1.25 to $3.75**, before storage,
reads and index-specific behavior. Calculate each actual index entry size;
not every write touches every GSI.

Compare incremental savings with migration effort and annual maintenance.
An illustrative $30/month actual provider reduction and $10/month added AWS
cost yields $20/month net; a $3,000 rewrite takes **150 months** to repay.
These are assumptions, not measured MathBank bills. Moving many tiny tables
while keeping the same PostgreSQL paid capacity saves approximately **zero
compute dollars**, irrespective of their count.

## 15. Neo4j/Aura, Neptune and simpler graph alternatives

Keep the current [graph schema](reference/GRAPH_SCHEMA.md) and
[dated live graph catalog](reference/GRAPH_LIVE_CATALOG.md) as evidence, plus
actual projector/query behavior. Canonical reviewed relationships remain in
SQL; the shared graph is a rebuildable structural projection, not learner
mastery/PII authority. Similarity, prerequisite, theorem citation and
misconception evidence are different edge semantics.

| Choice | Pros | Cons / migration scope |
|---|---|---|
| Retain Neo4j Aura | Least query/projector change; current Cypher/index/driver ecosystem and established UI behavior. | Separate provider/cost; obtain plan, memory limits, actual bill and usage. There is no proven saving without that baseline. |
| Neptune Database, provisioned | AWS IAM/VPC integration and graph engine; can choose capacity appropriate to sustained load. | Provisioned idle compute, networking/IO/storage/backups; openCypher/driver/procedure/index/constraint semantics need porting and load tests. Not a connection-string swap. |
| Neptune Database Serverless | Elastic NCU scaling for variable graph loads; less capacity tuning. | Section 7's Ohio **$117.384/month running compute minimum** before storage/IO/network is material for low-traffic dev. Do not assume zero idle running cost. |
| Neptune Analytics | Managed graph algorithm workloads and separate analytical graph lifecycle. | Separate engine/capacity/import/retention pricing; not a drop-in transactional Aura endpoint or the same Serverless minimum. Avoid holding analytical capacity between occasional jobs unless justified. |
| PostgreSQL edges + bounded recursive queries | No second always-on database; canonical reviewed edges already exist; transactional eligibility stays local. | Complex/high-fan-out traversal or large algorithms may stress OLTP. Limit depth/cardinality/time and compare query plans/latency. |
| DynamoDB precomputed adjacency | Cheap keyed reads for known bounded neighbor/subgraph views; rebuild from canonical SQL. | No general Cypher traversal; fan-out, reverse edges and multi-hop require custom code/multiple requests. Materialization/write amplification and refresh lag; not full graph feature parity. |
| Bedrock graph-based RAG | May help document entity/relation retrieval under its supported managed pipeline. | Extracted entity graphs are not automatically the curated MathBank pedagogic graph. Price its graph/model infrastructure and validate provenance; it does not replace runtime relationship semantics or graph-admin APIs. |

Port inventory must cover every consumed node/edge label/property, canonical
ID, approved/released scope, bulk upsert/delete owner, graph tab, multi-hop
query, procedure/APOC use, full-text/vector behavior, pagination/ranking,
timeouts, retry semantics and failure recovery. Preserve projector batching,
watermarks and independent edge ownership: historical successful rebuilds
have still lost separately projected edges. Test insert/update/withdraw/delete
and interrupted rebuilds, not just node/edge totals.

Choose the smallest representation that passes the actual graph UI and tutor
query suite. If SQL/precomputed adjacency cannot meet it, retain Aura or
evaluate Neptune on measured cost/SLOs. AWS-only analytics does not require
an AWS-only online graph.

## 16. AWS analytics without moving all transactional databases

```text
SQL committed outbox + authorized point-in-time extracts
  + graph projection snapshots + batch/model telemetry
  -> private S3 raw/curated zones + schema/version/watermark manifests
  -> Parquet + Glue catalog + Athena
  -> governed aggregates -> existing ML/admin frontend or QuickSight
  -> approved dataset manifests -> SageMaker Processing/Training
```

Begin with scheduled, bounded exports and outbox delivery. Do not use hot
cross-provider federated joins as the default dashboard path. Neon/Aura can
remain systems of record while AWS owns analytical copies. CDC/DMS or
streaming later requires source support, privileges/replication settings,
snapshot-plus-log consistency, monitoring and a separate cost quote; it is
not automatically available/free on every provider plan. Keep existing
offline authorized extraction distinct from new runtime DB access.

| Option | Pros | Cons / cost controls |
|---|---|---|
| S3 Parquet + Glue + Athena | Serverless, low idle infrastructure burden; compressed columnar/partition-pruned queries; suitable daily corpus/learner aggregates and training exports. | Watermark/dedup/schema/deletion handling is ours; many tiny files and repeated full scans inflate costs. Compact bounded files, partition by useful dates/domains without PII object keys, enforce workgroup scan limits and result lifecycle. |
| S3 Tables / Iceberg | Managed compaction, snapshot management and unreferenced-file cleanup; better fit when ongoing corrections/deletes/upserts/time travel justify table maintenance. | Storage/request/object-monitoring/compaction fees and engine/catalog governance remain. Validate selected Iceberg/engine feature compatibility; table maintenance is not instant privacy erasure. |
| DynamoDB analytical/serving rollups | Fast key-addressed current counters/status for dashboards. | Not ad-hoc cohort SQL; maintain source replay/dedup and history in lake. Export/streams/backups add cost. |
| QuickSight dashboards | Managed visualization, controlled sharing/row-level access and optional SPICE caching. | Author/reader/session/capacity and refresh costs can exceed a small storage bill. Optional; existing `mathbank-ml-frontend` can consume approved aggregates first. |
| Redshift / richer streaming stack later | Useful at demonstrated warehouse concurrency/latency/scale. | More minimum capacity, tuning and pipeline cost; not needed merely to say analytics is on AWS. |

[S3 Tables](https://aws.amazon.com/s3/features/tables/) automates Iceberg
maintenance; it is neither DynamoDB nor a student OLTP replacement.
[Athena pricing](https://aws.amazon.com/athena/pricing/) uses scanned bytes or
selected compute. Its public SQL example is $5/TB: 100 queries scanning
0.01 TB each illustrate **$5**, while 100 full 1 TB scans cost **$500**,
before S3/Glue/results and other services. Confirm target-region pricing and
minimums. Do not claim a fixed analytics monthly total without workload data.

Persist event ID, source version/watermark, event and ingestion times, schema,
release/model versions, tombstone and restricted provenance. Reconcile
duplicates/late events and publish freshness. Apply least-privilege IAM and
Lake Formation where selected; deidentify learner data, restrict small cohorts
and avoid causal claims from observational effectiveness comparisons.
Deletion propagates to raw/curated data, Iceberg snapshots, dashboard caches,
exports and training datasets subject to approved retention/backup policy.
Align with [requirements 58](58_ML_ANALYTICS_AND_COHORT_DASHBOARDS_REQUIREMENTS.md),
whose implementation remains scaffolded, not completed by this report.

## 17. SageMaker scope for a custom IntelliTutor model

### 17.1 Reuse existing projects and start with evidence

Reuse [mathbank-ml-training](../../mathbank-ml-training/README.md) for offline
dataset/features/evaluation/training and
[mathbank-ml-inference](../../mathbank-ml-inference/README.md) for controlled
serving; their current ML pipeline is a scaffold. Follow
[54](54_ML_RL_PLATFORM_ARCHITECTURE_AND_SCAFFOLDING.md),
[55](55_ML_TRAINING_PIPELINE_REQUIREMENTS.md) and
[56](56_ML_INFERENCE_SERVICE_REQUIREMENTS.md), rather than create another ML
project or pretend `ml.*` planned tables already exist. Add SageMaker
resources only through the existing infrastructure app after approval.

| Approach | Potential IntelliTutor value / pros | Cons / readiness gate |
|---|---|---|
| Rules + RAG + existing Bedrock/base model | Fastest baseline; corrected corpus available after reindex without retraining; no dedicated training/endpoint burden. | Retrieval/math/disclosure errors remain; measure quality, latency, tokens and verified learner outcomes. AgentCore is orchestration, not custom model training. |
| Small mastery/success/time/ranking models | BKT/EWMA, calibrated logistic/GBM or learning-to-rank models suit structured learner signals; CPU/batch serving can be inexpensive and interpretable. | Requires representative labels, point-in-time features, calibration and sparse-data abstention. Start here before assuming a custom LLM is needed. |
| Misconception/technique classifier or reranker | Can improve metadata suggestions/retrieval with smaller supervised datasets and targeted metrics. | Agent-generated noisy labels can reinforce errors; require adjudicated gold data and source-family held-out tests. |
| LLM SFT / parameter-efficient tuning such as LoRA | Can improve Socratic style, structured tool outputs and tutoring behavior on licensed reviewed demonstrations. | GPU/data/evaluation cost; base-model license/hosting compatibility, overfitting, hallucinations and answer leakage. Does not guarantee mathematical correctness or eliminate RAG. |
| DPO/preference tuning | Expert-ranked better/worse hints can favor non-revealing, pedagogically useful responses. | Expensive reliable paired preferences; style/reward shortcuts can harm learning. Evaluate safety/math separately from preference win rate. |
| RLVR / broader RL policy training | Verifiable mathematics or simulated bounded policies can improve selected tasks after strong baselines. | Reward hacking, weak simulators, long-horizon credit and costly rollouts. Symbolic correctness alone does not measure pedagogy; never optimize learner engagement or correctness as the sole reward. |
| Train a foundation model from scratch | Maximum architecture/data control in principle. | Very high corpus/compute/operations requirements; no evidence here supports this as a low-cost first step. |

SageMaker [serverless model customization](https://docs.aws.amazon.com/sagemaker/latest/dg/customize-model.html)
supports managed training workflows including SFT/DPO/RLVR and other methods;
supported base models, techniques and regions vary. This is **not** the same
as Serverless Inference. The local planning reference lists N. Virginia,
Oregon, Tokyo and Ireland for serverless customization, not Ohio; treat that
as a planning constraint requiring current official confirmation before a
pilot, not a claim that all SageMaker training is unavailable in Ohio.
Some managed evaluation features may process data across regions within a
geography; verify residency/consent before submitting learner data.

### 17.2 Dataset and model governance

Require licensed source content and consent/retention policy for learner
interactions. Minimize/deidentify PII; do not export production prompts or
private answers to research tools. Separate approved mathematical labels,
teacher demonstrations and validated outcomes from unreviewed agent metadata.
Record dataset ID, object versions/hashes, source revisions/watermarks,
label/feature/prompt versions, exclusions, rights, time window, train/validation/
test membership and code/container/base-model/license versions.

Split by **student and time**, plus held-out **problem/source family** to
prevent near-duplicate problem/solution leakage. Features must reflect what
was known at the prediction time: no future mastery, eventual score or
post-reveal answers. Keep a sealed evaluation set and expert adjudication;
measure mathematical correctness, calibration, retrieval quality, tool/schema
validity, premature answer disclosure, abstention, p95 latency, cost and
pedagogic outcomes, not just training loss.

Register dataset/model lineage and metrics in the approved registry boundary,
require staff deployment approval, shadow/canary with rollback, monitor drift
and record model version on recommendations. Models propose; existing REST
rules still own grading, mastery, publication and allowed transitions.
No online policy exploration on real students is authorized by this report.

RAG/index updates make approved knowledge current; fine-tuned weights do not.
Deleting a source/vector/dataset is **not guaranteed model unlearning**.
Track affected trained models and apply an explicit retraining/retirement/
retention policy; do not promise erasure from weights after deleting an S3 key.

### 17.3 Hosting and total-cost trade-offs

| Serving/training option | Pros | Cons / appropriate use |
|---|---|---|
| SageMaker Processing/Training jobs | Bounded offline execution, reusable containers/lineage, optional checkpointed Managed Spot Training for supported workloads. | Pay for instances/job duration, storage, artifacts, retries and data prep; Spot interruptions need checkpoint recovery. Stop notebooks and do not create idle GPU endpoints for a feasibility study. |
| Batch Transform | No permanently running endpoint between jobs; appropriate offline scoring/enrichment. | Job startup and batch latency; instance charges during job execution, not an interactive tutor. |
| Asynchronous Inference | GPU-capable queued processing; can scale to zero with configured autoscaling. | Cold starts/backlog, storage and notification costs; scale-from-zero policy needs explicit configuration. Useful for deferrable work, not assumed subsecond tutoring. |
| Serverless Inference | CPU models with intermittent traffic, no always-on instance by default. | Current feature matrix has **no GPU support**, payload/runtime and feature constraints; provisioned concurrency costs extra. Not a generic free-idle GPU LLM host. |
| Real-time endpoint | Predictable warm low latency and GPU options. | Quote minimum active capacity/HA, idle hours and autoscaling behavior for the exact deployment; low traffic may make Bedrock per-token cheaper. |
| Bedrock base/custom-model serving where supported | Lower infrastructure operations; per-token or applicable custom-model deployment economics. | Selected model/customization/import availability, inference/throughput/copy billing and portability must be checked separately. SageMaker training does not automatically yield a Bedrock-compatible model. |

The [SageMaker feature matrix](https://docs.aws.amazon.com/sagemaker/latest/dg/model-deploy-feature-matrix.html)
and [async autoscaling guide](https://docs.aws.amazon.com/sagemaker/latest/dg/async-inference-autoscale.html)
ground the GPU/scale-to-zero distinctions above. No exact instance/model
has been selected, so no invented GPU hourly quote or guaranteed saving is used.

```text
experiment_total =
    dataset_extract_processing_label_review
  + sum(training_instances x billable_hours x regional_instance_rate)
  + tuning_trials + evaluation_models/rollouts + checkpoint_storage
  + artifacts_registry_KMS_logs_transfer

monthly_serving =
    warm_capacity_hours + burst_compute_or_request_token_cost
  + storage_monitoring_network + scheduled_retraining_amortization
  + model_operations_and_expert_review

break_even_requests =
    incremental_fixed_monthly_cost /
    (baseline_cost_per_request - custom_variable_cost_per_request)
```

The break-even formula only applies if the denominator is positive and quality/
latency/disclosure gates are met. Compare end-to-end cost per **accepted useful
tutoring outcome**, not cheap tokens alone. Storage migration savings should
not be used to hide new training/endpoint spend.

### 17.4 Proposed acceptance and implementation sequence

All work below remains **not implemented**. Thresholds are proposed release
gates, not benchmark results; approve workload-specific latency/recall/budgets
before a pilot.

| Gate | Measurable evidence |
|---|---|
| DATA-01 Batch CRUD | Fixtures insert, edit, reimport and delete documents/questions; duplicate replay makes zero extra canonical mutations and accounts for every manifest item. |
| DATA-02 Human metadata | Agent rerun cannot alter any locked human field; stale proposal gets a visible conflict; provenance survives projection and rebuild. |
| DATA-03 Changed-only work | Unchanged embedding-input hashes cause zero new embedding calls in the direct pipeline; metadata-only KB cases verify documented optimization eligibility and measured calls. |
| DATA-04 Races/recovery | Kill/retry each stage; N results cannot overwrite N+1; cancelled/deleted sources cannot reactivate; no lost outbox or duplicate learner/audit effects. |
| DATA-05 Visibility/deletion | Zero unauthorized, hidden, withdrawn, wrong-revision or deleted chunks reach a model/student in adversarial retrieval fixtures; physical purge has per-target receipts and unresolved failures remain visible. |
| DATA-06 Retrieval parity | Section 3 exact-filter/recall contracts, math/source spans and lexical fusion are tested against retained baseline; no switch on ANN demos alone. |
| DATA-07 Rebuild/rollback | Shadow rebuild plus concurrent edit/delete, generation activation and rollback preserve canonical eligibility and full manifest coverage; partial jobs never activate. |
| DATA-08 Cost/operations | Bounded concurrency/tokens/retries and approved per-run budget; compare metered paid units and current bills, not table counts. |
| DATA-09 Analytics | Snapshot/outbox watermarks, dedup/late events, schema evolution and erase/replay tests; dashboards show freshness and no raw private data. |
| DATA-10 Custom model | Rights/consent, leakage-safe split, expert gold evaluation, non-reveal/math/latency/cost gates, approved registry and tested rollback before any learner exposure. |

Sequence: (1) measure and agree source/review contracts; (2) extend existing
admin batch staging and durable invalidation/outbox; (3) implement delta
chunk/enrichment/projection reconciliation using current stores; (4) shadow
one S3 Vectors or approved-region MKB workload, not both by default; (5) add
S3/Athena analytics exports; (6) evaluate small supervised ML baselines; (7)
consider a custom tutor LLM only when data and measured baseline gaps justify
training and serving costs. Evaluate authoritative DynamoDB/Aurora/Neptune
migrations independently after their economic and parity gates.
