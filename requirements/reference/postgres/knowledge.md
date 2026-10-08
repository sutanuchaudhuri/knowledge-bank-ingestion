# PostgreSQL `knowledge` schema

**Role:** Canonical reviewed teaching metadata. Concepts, techniques, measurable skills and assertions, with enrichment/review provenance.

**Access family:** Corpus filters/search, `/v1/concepts`, `/v1/techniques`, `/v1/tutor/*`, `/v1/admin/pedagogy/*`; enrichment/projector jobs.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `knowledge.concept`

**Kind / use case:** table. Canonical concept identity used by corpus filters and graph bridges.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L102); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/mastery.py](../../../mathbank-rest/src/mathbank_rest/mastery.py#L168); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L254); [mathbank-rest/src/mathbank_rest/relationship_enrichment.py](../../../mathbank-rest/src/mathbank_rest/relationship_enrichment.py#L137); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L195); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L31); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L81); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L230); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L23); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L292); [mathbank-db/etl/import_pedagogy.py](../../../mathbank-db/etl/import_pedagogy.py#L189).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `concept_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `slug` | `text` | no | `-` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `description` | `text` | yes | `-` | `- / -` |
| `level` | `integer` | yes | `-` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `concept_concept_id_not_null` / `n` | `NOT NULL concept_id` | deferrable=False, initially deferred=False, validated=True |
| `concept_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `concept_pkey` / `p` | `PRIMARY KEY (concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `concept_slug_key` / `u` | `UNIQUE (slug)` | deferrable=False, initially deferred=False, validated=True |
| `concept_slug_not_null` / `n` | `NOT NULL slug` | deferrable=False, initially deferred=False, validated=True |
| `concept_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `knowledge.concept_relation` / `concept_relation_from_concept_id_fkey`: `FOREIGN KEY (from_concept_id) REFERENCES knowledge.concept(concept_id)`.
- `knowledge.concept_relation` / `concept_relation_to_concept_id_fkey`: `FOREIGN KEY (to_concept_id) REFERENCES knowledge.concept(concept_id)`.
- `knowledge.problem_concept` / `problem_concept_concept_id_fkey`: `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)`.
- `knowledge.skill_concept` / `skill_concept_concept_id_fkey`: `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)`.
- `learner.concept_mastery` / `concept_mastery_concept_id_fkey`: `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)`.
- `pedagogy.taxonomy_node` / `taxonomy_node_concept_id_fkey`: `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)`.
- `search.chunk` / `chunk_concept_id_fkey`: `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `concept_pkey`: `CREATE UNIQUE INDEX concept_pkey ON knowledge.concept USING btree (concept_id)`; valid=True, ready=True.
- `concept_slug_key`: `CREATE UNIQUE INDEX concept_slug_key ON knowledge.concept USING btree (slug)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.concept_relation`

**Kind / use case:** table. Directed concept hierarchy/prerequisite/support assertions.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L140); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L253); [mathbank-rest/src/mathbank_rest/relationship_enrichment.py](../../../mathbank-rest/src/mathbank_rest/relationship_enrichment.py#L270); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L132); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L195); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L257); [mathbank-db/etl/import_pedagogy.py](../../../mathbank-db/etl/import_pedagogy.py#L215); [mathbank-db/etl/load_corpus.py](../../../mathbank-db/etl/load_corpus.py#L576); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L58); [mathbank-graph/etl/project_from_postgres.py](../../../mathbank-graph/etl/project_from_postgres.py#L346).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `relation_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `from_concept_id` | `uuid` | no | `-` | `- / -` |
| `to_concept_id` | `uuid` | no | `-` | `- / -` |
| `relation_type` | `text` | no | `-` | `- / -` |
| `strength` | `numeric(5,4)` | yes | `-` | `- / -` |
| `assertion_source` | `text` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `concept_relation_assertion_source_not_null` / `n` | `NOT NULL assertion_source` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_from_concept_id_fkey` / `f` | `FOREIGN KEY (from_concept_id) REFERENCES knowledge.concept(concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_from_concept_id_not_null` / `n` | `NOT NULL from_concept_id` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_from_concept_id_to_concept_id_relation_typ_key` / `u` | `UNIQUE (from_concept_id, to_concept_id, relation_type)` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_pkey` / `p` | `PRIMARY KEY (relation_id)` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_relation_id_not_null` / `n` | `NOT NULL relation_id` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_relation_type_not_null` / `n` | `NOT NULL relation_type` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_to_concept_id_fkey` / `f` | `FOREIGN KEY (to_concept_id) REFERENCES knowledge.concept(concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `concept_relation_to_concept_id_not_null` / `n` | `NOT NULL to_concept_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `concept_relation_from_concept_id_to_concept_id_relation_typ_key`: `CREATE UNIQUE INDEX concept_relation_from_concept_id_to_concept_id_relation_typ_key ON knowledge.concept_relation USING btree (from_concept_id, to_concept_id, relation_type)`; valid=True, ready=True.
- `concept_relation_pkey`: `CREATE UNIQUE INDEX concept_relation_pkey ON knowledge.concept_relation USING btree (relation_id)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.concept_relation FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.concept_relation FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.enrichment_job`

**Kind / use case:** table. Resumable teaching-metadata enrichment queue/status.

**Migration owner:** [008_automatic_metadata.sql](../../../mathbank-db/sql/008_automatic_metadata.sql#L15); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/enrichment.py](../../../mathbank-rest/src/mathbank_rest/enrichment.py#L70); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L201); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L132); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L278).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `attempts` | `integer` | no | `1` | `- / -` |
| `last_error` | `text` | yes | `-` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `published_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `enrichment_job_attempts_not_null` / `n` | `NOT NULL attempts` | deferrable=False, initially deferred=False, validated=True |
| `enrichment_job_pkey` / `p` | `PRIMARY KEY (problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `enrichment_job_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `enrichment_job_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `enrichment_job_status_check` / `c` | `CHECK (status = ANY (ARRAY['IN_PROGRESS'::text, 'COMPLETED'::text, 'FAILED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `enrichment_job_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `enrichment_job_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `enrichment_job_pkey`: `CREATE UNIQUE INDEX enrichment_job_pkey ON knowledge.enrichment_job USING btree (problem_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.metadata_approval_event`

**Kind / use case:** table. Automatic-approval provenance; not mathematical certification.

**Migration owner:** [008_automatic_metadata.sql](../../../mathbank-db/sql/008_automatic_metadata.sql#L8); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** no qualified literal reference found in application/ETL sources.
Framework ORM access, dynamic SQL or unused/reserved tables must not be claimed as a public REST resource.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `event_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `entity_kind` | `text` | no | `-` | `- / -` |
| `before_snapshot` | `jsonb` | yes | `-` | `- / -` |
| `after_snapshot` | `jsonb` | no | `-` | `- / -` |
| `approved_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `metadata_approval_event_after_snapshot_not_null` / `n` | `NOT NULL after_snapshot` | deferrable=False, initially deferred=False, validated=True |
| `metadata_approval_event_approved_at_not_null` / `n` | `NOT NULL approved_at` | deferrable=False, initially deferred=False, validated=True |
| `metadata_approval_event_entity_kind_not_null` / `n` | `NOT NULL entity_kind` | deferrable=False, initially deferred=False, validated=True |
| `metadata_approval_event_event_id_not_null` / `n` | `NOT NULL event_id` | deferrable=False, initially deferred=False, validated=True |
| `metadata_approval_event_pkey` / `p` | `PRIMARY KEY (event_id)` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `metadata_approval_event_pkey`: `CREATE UNIQUE INDEX metadata_approval_event_pkey ON knowledge.metadata_approval_event USING btree (event_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.pedagogy_publication`

**Kind / use case:** table. Recorded teaching-layer graph publication fingerprints.

**Migration owner:** [007_pedagogy_review.sql](../../../mathbank-db/sql/007_pedagogy_review.sql#L17); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L155).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `publication_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `source_fingerprint` | `text` | no | `-` | `- / -` |
| `publisher` | `text` | no | `-` | `- / -` |
| `skills_projected` | `integer` | no | `-` | `- / -` |
| `edges_projected` | `integer` | no | `-` | `- / -` |
| `published_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `pedagogy_publication_edges_projected_not_null` / `n` | `NOT NULL edges_projected` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_publication_pkey` / `p` | `PRIMARY KEY (publication_id)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_publication_publication_id_not_null` / `n` | `NOT NULL publication_id` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_publication_published_at_not_null` / `n` | `NOT NULL published_at` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_publication_publisher_not_null` / `n` | `NOT NULL publisher` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_publication_skills_projected_not_null` / `n` | `NOT NULL skills_projected` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_publication_source_fingerprint_not_null` / `n` | `NOT NULL source_fingerprint` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `pedagogy_publication_pkey`: `CREATE UNIQUE INDEX pedagogy_publication_pkey ON knowledge.pedagogy_publication USING btree (publication_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.pedagogy_review_event`

**Kind / use case:** table. Before/after human metadata review evidence.

**Migration owner:** [007_pedagogy_review.sql](../../../mathbank-db/sql/007_pedagogy_review.sql#L3); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L310).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `review_event_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `entity_kind` | `text` | no | `-` | `- / -` |
| `entity_key` | `jsonb` | no | `-` | `- / -` |
| `before_snapshot` | `jsonb` | no | `-` | `- / -` |
| `after_snapshot` | `jsonb` | no | `-` | `- / -` |
| `reviewer` | `text` | no | `-` | `- / -` |
| `review_note` | `text` | no | `-` | `- / -` |
| `reviewed_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `pedagogy_review_event_after_snapshot_not_null` / `n` | `NOT NULL after_snapshot` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_before_snapshot_not_null` / `n` | `NOT NULL before_snapshot` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_entity_key_not_null` / `n` | `NOT NULL entity_key` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_entity_kind_check` / `c` | `CHECK (entity_kind = ANY (ARRAY['skill'::text, 'skill_concept'::text, 'skill_relation'::text, 'concept_relation'::text, 'problem_skill'::text, 'problem_pedagogy'::text, 'problem_concept'::text, 'problem_technique'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_entity_kind_not_null` / `n` | `NOT NULL entity_kind` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_pkey` / `p` | `PRIMARY KEY (review_event_id)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_review_event_id_not_null` / `n` | `NOT NULL review_event_id` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_review_note_check` / `c` | `CHECK (length(btrim(review_note)) >= 10 AND length(btrim(review_note)) <= 2000)` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_review_note_not_null` / `n` | `NOT NULL review_note` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_reviewed_at_not_null` / `n` | `NOT NULL reviewed_at` | deferrable=False, initially deferred=False, validated=True |
| `pedagogy_review_event_reviewer_not_null` / `n` | `NOT NULL reviewer` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `pedagogy_review_entity_idx`: `CREATE INDEX pedagogy_review_entity_idx ON knowledge.pedagogy_review_event USING btree (entity_kind, reviewed_at DESC)`; valid=True, ready=True.
- `pedagogy_review_event_pkey`: `CREATE UNIQUE INDEX pedagogy_review_event_pkey ON knowledge.pedagogy_review_event USING btree (review_event_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.problem_concept`

**Kind / use case:** table. Problem-to-concept role/assertion evidence.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L119); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/mastery.py](../../../mathbank-rest/src/mathbank_rest/mastery.py#L136); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L110); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L80); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L123); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L24); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L250); [mathbank-db/etl/load_corpus.py](../../../mathbank-db/etl/load_corpus.py#L496); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L982); [mathbank-db/etl/paper_batches.py](../../../mathbank-db/etl/paper_batches.py#L419); [mathbank-graph/etl/project_from_postgres.py](../../../mathbank-graph/etl/project_from_postgres.py#L278).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `concept_id` | `uuid` | no | `-` | `- / -` |
| `role` | `text` | no | `'PRIMARY'::text` | `- / -` |
| `confidence` | `numeric(5,4)` | yes | `-` | `- / -` |
| `assertion_source` | `text` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `asserted_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_concept_asserted_at_not_null` / `n` | `NOT NULL asserted_at` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_assertion_source_not_null` / `n` | `NOT NULL assertion_source` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_concept_id_fkey` / `f` | `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_concept_id_not_null` / `n` | `NOT NULL concept_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_pkey` / `p` | `PRIMARY KEY (problem_id, concept_id, role)` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `problem_concept_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `problem_concept_pkey`: `CREATE UNIQUE INDEX problem_concept_pkey ON knowledge.problem_concept USING btree (problem_id, concept_id, role)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.problem_concept FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.problem_concept FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.problem_pedagogy`

**Kind / use case:** table. Problem teaching dimensions and estimated difficulty/workload.

**Migration owner:** [006_pedagogy.sql](../../../mathbank-db/sql/006_pedagogy.sql#L53); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/enrichment.py](../../../mathbank-rest/src/mathbank_rest/enrichment.py#L247); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L132); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L129); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L281); [mathbank-db/etl/import_pedagogy.py](../../../mathbank-db/etl/import_pedagogy.py#L256); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L58); [mathbank-graph/etl/project_from_postgres.py](../../../mathbank-graph/etl/project_from_postgres.py#L486).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `conceptual_depth` | `integer` | yes | `-` | `- / -` |
| `technical_load` | `integer` | yes | `-` | `- / -` |
| `algebraic_load` | `integer` | yes | `-` | `- / -` |
| `insight_required` | `integer` | yes | `-` | `- / -` |
| `number_of_steps` | `integer` | yes | `-` | `- / -` |
| `prerequisite_depth` | `integer` | yes | `-` | `- / -` |
| `estimated_contest_level` | `text` | yes | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `confidence` | `numeric` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_pedagogy_algebraic_load_check` / `c` | `CHECK (algebraic_load >= 1 AND algebraic_load <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_conceptual_depth_check` / `c` | `CHECK (conceptual_depth >= 1 AND conceptual_depth <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_confidence_check` / `c` | `CHECK (confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_estimated_contest_level_check` / `c` | `CHECK (btrim(estimated_contest_level) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_insight_required_check` / `c` | `CHECK (insight_required >= 1 AND insight_required <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_number_of_steps_check` / `c` | `CHECK (number_of_steps >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_pkey` / `p` | `PRIMARY KEY (problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_prerequisite_depth_check` / `c` | `CHECK (prerequisite_depth >= 0)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING'::text, 'REVIEWED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_source_check` / `c` | `CHECK (btrim(source) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |
| `problem_pedagogy_technical_load_check` / `c` | `CHECK (technical_load >= 1 AND technical_load <= 5)` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `problem_pedagogy_pkey`: `CREATE UNIQUE INDEX problem_pedagogy_pkey ON knowledge.problem_pedagogy USING btree (problem_id)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.problem_pedagogy FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.problem_pedagogy FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.problem_skill`

**Kind / use case:** table. Required/practiced/tested skill evidence and role/importance.

**Migration owner:** [006_pedagogy.sql](../../../mathbank-db/sql/006_pedagogy.sql#L39); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/enrichment.py](../../../mathbank-rest/src/mathbank_rest/enrichment.py#L246); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L132); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L127); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L280); [mathbank-db/etl/import_pedagogy.py](../../../mathbank-db/etl/import_pedagogy.py#L256); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L58).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `skill_id` | `uuid` | no | `-` | `- / -` |
| `relation_type` | `text` | no | `-` | `- / -` |
| `role` | `text` | no | `-` | `- / -` |
| `required_level` | `integer` | yes | `-` | `- / -` |
| `importance` | `numeric` | no | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `confidence` | `numeric` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_skill_confidence_check` / `c` | `CHECK (confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_importance_check` / `c` | `CHECK (importance >= 0::numeric AND importance <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_importance_not_null` / `n` | `NOT NULL importance` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_pkey` / `p` | `PRIMARY KEY (problem_id, skill_id, relation_type, role)` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_relation_type_check` / `c` | `CHECK (relation_type = ANY (ARRAY['REQUIRES'::text, 'PRACTICES'::text, 'TESTS'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_relation_type_not_null` / `n` | `NOT NULL relation_type` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_required_level_check` / `c` | `CHECK (required_level >= 1 AND required_level <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING'::text, 'REVIEWED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_role_check` / `c` | `CHECK (role = ANY (ARRAY['primary'::text, 'supporting'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_skill_id_fkey` / `f` | `FOREIGN KEY (skill_id) REFERENCES knowledge.skill(skill_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_skill_id_not_null` / `n` | `NOT NULL skill_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_source_check` / `c` | `CHECK (btrim(source) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `problem_skill_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `problem_skill_pkey`: `CREATE UNIQUE INDEX problem_skill_pkey ON knowledge.problem_skill USING btree (problem_id, skill_id, relation_type, role)`; valid=True, ready=True.
- `problem_skill_skill_idx`: `CREATE INDEX problem_skill_skill_idx ON knowledge.problem_skill USING btree (skill_id)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.problem_skill FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.problem_skill FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.problem_technique`

**Kind / use case:** table. Problem-to-technique role/assertion evidence.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L130); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L213); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L107); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L28); [mathbank-rest/src/mathbank_rest/db/retrieval_audit.py](../../../mathbank-rest/src/mathbank_rest/db/retrieval_audit.py#L41); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L125); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L185); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L252); [mathbank-db/etl/load_corpus.py](../../../mathbank-db/etl/load_corpus.py#L535); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L986); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L99).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `technique_id` | `uuid` | no | `-` | `- / -` |
| `role` | `text` | no | `'REQUIRED'::text` | `- / -` |
| `confidence` | `numeric(5,4)` | yes | `-` | `- / -` |
| `assertion_source` | `text` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_technique_assertion_source_not_null` / `n` | `NOT NULL assertion_source` | deferrable=False, initially deferred=False, validated=True |
| `problem_technique_pkey` / `p` | `PRIMARY KEY (problem_id, technique_id, role)` | deferrable=False, initially deferred=False, validated=True |
| `problem_technique_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `problem_technique_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_technique_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `problem_technique_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |
| `problem_technique_technique_id_fkey` / `f` | `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_technique_technique_id_not_null` / `n` | `NOT NULL technique_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `problem_technique_pkey`: `CREATE UNIQUE INDEX problem_technique_pkey ON knowledge.problem_technique USING btree (problem_id, technique_id, role)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.problem_technique FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.problem_technique FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.relationship_enrichment_job`

**Kind / use case:** table. Resumable semantic taxonomy relationship generation/status.

**Migration owner:** [009_relationship_enrichment.sql](../../../mathbank-db/sql/009_relationship_enrichment.sql#L2); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/relationship_enrichment.py](../../../mathbank-rest/src/mathbank_rest/relationship_enrichment.py#L140); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L224); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L234); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L294).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `entity_kind` | `text` | no | `-` | `- / -` |
| `anchor_id` | `uuid` | no | `-` | `- / -` |
| `input_hash` | `text` | no | `-` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `attempts` | `integer` | no | `1` | `- / -` |
| `last_error` | `text` | yes | `-` | `- / -` |
| `evidence` | `jsonb` | yes | `-` | `- / -` |
| `edges_inserted` | `integer` | no | `0` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `published_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `relationship_enrichment_job_anchor_id_not_null` / `n` | `NOT NULL anchor_id` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_attempts_not_null` / `n` | `NOT NULL attempts` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_edges_inserted_not_null` / `n` | `NOT NULL edges_inserted` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_entity_kind_check` / `c` | `CHECK (entity_kind = ANY (ARRAY['skill'::text, 'concept'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_entity_kind_not_null` / `n` | `NOT NULL entity_kind` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_input_hash_not_null` / `n` | `NOT NULL input_hash` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_pkey` / `p` | `PRIMARY KEY (entity_kind, anchor_id)` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_status_check` / `c` | `CHECK (status = ANY (ARRAY['IN_PROGRESS'::text, 'COMPLETED'::text, 'FAILED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `relationship_enrichment_job_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `relationship_enrichment_job_pkey`: `CREATE UNIQUE INDEX relationship_enrichment_job_pkey ON knowledge.relationship_enrichment_job USING btree (entity_kind, anchor_id)`; valid=True, ready=True.
- `relationship_enrichment_outbox_idx`: `CREATE INDEX relationship_enrichment_outbox_idx ON knowledge.relationship_enrichment_job USING btree (updated_at) WHERE ((status = 'COMPLETED'::text) AND (published_at IS NULL))`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.skill`

**Kind / use case:** table. Measurable skill objective with review/approval provenance.

**Migration owner:** [006_pedagogy.sql](../../../mathbank-db/sql/006_pedagogy.sql#L4); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/relationship_enrichment.py](../../../mathbank-rest/src/mathbank_rest/relationship_enrichment.py#L134); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L196); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L31); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L226); [mathbank-db/etl/arml_queue.py](../../../mathbank-db/etl/arml_queue.py#L289); [mathbank-db/etl/import_pedagogy.py](../../../mathbank-db/etl/import_pedagogy.py#L188); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L57); [mathbank-graph/etl/project_from_postgres.py](../../../mathbank-graph/etl/project_from_postgres.py#L420).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `skill_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `slug` | `text` | no | `-` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `objective` | `text` | no | `-` | `- / -` |
| `level` | `integer` | yes | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `confidence` | `numeric` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `skill_confidence_check` / `c` | `CHECK (confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `skill_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `skill_level_check` / `c` | `CHECK (level >= 1 AND level <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `skill_name_check` / `c` | `CHECK (btrim(name) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `skill_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `skill_objective_check` / `c` | `CHECK (btrim(objective) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `skill_objective_not_null` / `n` | `NOT NULL objective` | deferrable=False, initially deferred=False, validated=True |
| `skill_pkey` / `p` | `PRIMARY KEY (skill_id)` | deferrable=False, initially deferred=False, validated=True |
| `skill_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING'::text, 'REVIEWED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `skill_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `skill_skill_id_not_null` / `n` | `NOT NULL skill_id` | deferrable=False, initially deferred=False, validated=True |
| `skill_slug_check` / `c` | `CHECK (btrim(slug) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `skill_slug_key` / `u` | `UNIQUE (slug)` | deferrable=False, initially deferred=False, validated=True |
| `skill_slug_not_null` / `n` | `NOT NULL slug` | deferrable=False, initially deferred=False, validated=True |
| `skill_source_check` / `c` | `CHECK (btrim(source) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `skill_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `knowledge.problem_skill` / `problem_skill_skill_id_fkey`: `FOREIGN KEY (skill_id) REFERENCES knowledge.skill(skill_id)`.
- `knowledge.skill_concept` / `skill_concept_skill_id_fkey`: `FOREIGN KEY (skill_id) REFERENCES knowledge.skill(skill_id) ON DELETE CASCADE`.
- `knowledge.skill_relation` / `skill_relation_from_skill_id_fkey`: `FOREIGN KEY (from_skill_id) REFERENCES knowledge.skill(skill_id) ON DELETE CASCADE`.
- `knowledge.skill_relation` / `skill_relation_to_skill_id_fkey`: `FOREIGN KEY (to_skill_id) REFERENCES knowledge.skill(skill_id) ON DELETE CASCADE`.
- `pedagogy.taxonomy_node` / `taxonomy_node_skill_id_fkey`: `FOREIGN KEY (skill_id) REFERENCES knowledge.skill(skill_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `skill_pkey`: `CREATE UNIQUE INDEX skill_pkey ON knowledge.skill USING btree (skill_id)`; valid=True, ready=True.
- `skill_slug_key`: `CREATE UNIQUE INDEX skill_slug_key ON knowledge.skill USING btree (slug)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.skill FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.skill FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.skill_concept`

**Kind / use case:** table. Skill membership in a canonical concept.

**Migration owner:** [006_pedagogy.sql](../../../mathbank-db/sql/006_pedagogy.sql#L16); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/relationship_enrichment.py](../../../mathbank-rest/src/mathbank_rest/relationship_enrichment.py#L174); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L131); [mathbank-db/etl/import_pedagogy.py](../../../mathbank-db/etl/import_pedagogy.py#L255); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L57).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `skill_id` | `uuid` | no | `-` | `- / -` |
| `concept_id` | `uuid` | no | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `confidence` | `numeric` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `skill_concept_concept_id_fkey` / `f` | `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_concept_id_not_null` / `n` | `NOT NULL concept_id` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_confidence_check` / `c` | `CHECK (confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_pkey` / `p` | `PRIMARY KEY (skill_id, concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING'::text, 'REVIEWED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_skill_id_fkey` / `f` | `FOREIGN KEY (skill_id) REFERENCES knowledge.skill(skill_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_skill_id_not_null` / `n` | `NOT NULL skill_id` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_source_check` / `c` | `CHECK (btrim(source) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `skill_concept_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `skill_concept_concept_idx`: `CREATE INDEX skill_concept_concept_idx ON knowledge.skill_concept USING btree (concept_id)`; valid=True, ready=True.
- `skill_concept_pkey`: `CREATE UNIQUE INDEX skill_concept_pkey ON knowledge.skill_concept USING btree (skill_id, concept_id)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.skill_concept FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.skill_concept FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.skill_relation`

**Kind / use case:** table. Directed skill prerequisites, part-of and builds-on assertions.

**Migration owner:** [006_pedagogy.sql](../../../mathbank-db/sql/006_pedagogy.sql#L26); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/relationship_enrichment.py](../../../mathbank-rest/src/mathbank_rest/relationship_enrichment.py#L260); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L131); [mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py](../../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py#L251); [mathbank-db/etl/import_pedagogy.py](../../../mathbank-db/etl/import_pedagogy.py#L198); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L57).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `from_skill_id` | `uuid` | no | `-` | `- / -` |
| `to_skill_id` | `uuid` | no | `-` | `- / -` |
| `relation_type` | `text` | no | `-` | `- / -` |
| `source` | `text` | no | `-` | `- / -` |
| `confidence` | `numeric` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `skill_relation_check` / `c` | `CHECK (from_skill_id <> to_skill_id)` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_confidence_check` / `c` | `CHECK (confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_from_skill_id_fkey` / `f` | `FOREIGN KEY (from_skill_id) REFERENCES knowledge.skill(skill_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_from_skill_id_not_null` / `n` | `NOT NULL from_skill_id` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_pkey` / `p` | `PRIMARY KEY (from_skill_id, to_skill_id, relation_type)` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_relation_type_check` / `c` | `CHECK (relation_type = ANY (ARRAY['PREREQUISITE_OF'::text, 'PART_OF'::text, 'BUILDS_ON'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_relation_type_not_null` / `n` | `NOT NULL relation_type` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING'::text, 'REVIEWED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_source_check` / `c` | `CHECK (btrim(source) <> ''::text)` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_source_not_null` / `n` | `NOT NULL source` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_to_skill_id_fkey` / `f` | `FOREIGN KEY (to_skill_id) REFERENCES knowledge.skill(skill_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `skill_relation_to_skill_id_not_null` / `n` | `NOT NULL to_skill_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `skill_relation_pkey`: `CREATE UNIQUE INDEX skill_relation_pkey ON knowledge.skill_relation USING btree (from_skill_id, to_skill_id, relation_type)`; valid=True, ready=True.
- `skill_relation_target_idx`: `CREATE INDEX skill_relation_target_idx ON knowledge.skill_relation USING btree (to_skill_id)`; valid=True, ready=True.

**Triggers:**

- `automatic_metadata`: `CREATE TRIGGER automatic_metadata BEFORE INSERT OR UPDATE ON knowledge.skill_relation FOR EACH ROW EXECUTE FUNCTION knowledge.apply_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).
- `automatic_metadata_audit`: `CREATE TRIGGER automatic_metadata_audit AFTER INSERT OR UPDATE ON knowledge.skill_relation FOR EACH ROW EXECUTE FUNCTION knowledge.record_automatic_approval()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `knowledge.technique`

**Kind / use case:** table. Canonical technique identity used by corpus filters and graph bridges.

**Migration owner:** [001_schema.sql](../../../mathbank-db/sql/001_schema.sql#L111); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L197); [mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py](../../../mathbank-rest/src/mathbank_rest/db/pedagogy_admin.py#L67); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L22); [mathbank-rest/src/mathbank_rest/db/retrieval_audit.py](../../../mathbank-rest/src/mathbank_rest/db/retrieval_audit.py#L41); [mathbank-rest/src/mathbank_rest/db/learner.py](../../../mathbank-rest/src/mathbank_rest/db/learner.py#L27); [mathbank-db/etl/load_corpus.py](../../../mathbank-db/etl/load_corpus.py#L468); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L812); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L100); [mathbank-graph/etl/project_from_postgres.py](../../../mathbank-graph/etl/project_from_postgres.py#L261).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `technique_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `slug` | `text` | no | `-` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `description` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `technique_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `technique_pkey` / `p` | `PRIMARY KEY (technique_id)` | deferrable=False, initially deferred=False, validated=True |
| `technique_slug_key` / `u` | `UNIQUE (slug)` | deferrable=False, initially deferred=False, validated=True |
| `technique_slug_not_null` / `n` | `NOT NULL slug` | deferrable=False, initially deferred=False, validated=True |
| `technique_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `technique_technique_id_not_null` / `n` | `NOT NULL technique_id` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `knowledge.problem_technique` / `problem_technique_technique_id_fkey`: `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)`.
- `learner.technique_mastery` / `technique_mastery_technique_id_fkey`: `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)`.
- `pedagogy.taxonomy_node` / `taxonomy_node_technique_id_fkey`: `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)`.
- `search.chunk` / `chunk_technique_id_fkey`: `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `technique_pkey`: `CREATE UNIQUE INDEX technique_pkey ON knowledge.technique USING btree (technique_id)`; valid=True, ready=True.
- `technique_slug_key`: `CREATE UNIQUE INDEX technique_slug_key ON knowledge.technique USING btree (slug)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `apply_automatic_approval(-)` | `trigger` | plpgsql / v | False | [008_automatic_metadata.sql](../../../mathbank-db/sql/008_automatic_metadata.sql) |
| `record_automatic_approval(-)` | `trigger` | plpgsql / v | False | [008_automatic_metadata.sql](../../../mathbank-db/sql/008_automatic_metadata.sql) |

### Observed definition: `knowledge.apply_automatic_approval`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION knowledge.apply_automatic_approval()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'UPDATE'
       AND (current_setting('mathbank.automatic_writer', true) = 'on'
            OR (NEW.review_status = 'PENDING'
                AND current_setting('mathbank.human_review', true) IS DISTINCT FROM 'on'))
       AND (OLD.review_status = 'REJECTED' OR OLD.approval_method = 'human') THEN
        RETURN OLD;
    END IF;
    IF NEW.review_status = 'PENDING'
       AND current_setting('mathbank.human_review', true) IS DISTINCT FROM 'on' THEN
        NEW.review_status := 'REVIEWED';
        NEW.approval_method := 'automatic';
    END IF;
    IF current_setting('mathbank.automatic_writer', true) = 'on' THEN
        NEW.approval_method := 'automatic';
    END IF;
    IF current_setting('mathbank.human_review', true) = 'on' THEN
        NEW.approval_method := 'human';
    END IF;
    RETURN NEW;
END $function$
```

### Observed definition: `knowledge.record_automatic_approval`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION knowledge.record_automatic_approval()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.approval_method = 'automatic'
       AND (TG_OP = 'INSERT' OR to_jsonb(NEW) IS DISTINCT FROM to_jsonb(OLD)) THEN
        INSERT INTO knowledge.metadata_approval_event(entity_kind,before_snapshot,after_snapshot)
        VALUES (TG_TABLE_NAME, CASE WHEN TG_OP='UPDATE' THEN to_jsonb(OLD) ELSE NULL END,
                to_jsonb(NEW));
    END IF;
    RETURN NULL;
END $function$
```
