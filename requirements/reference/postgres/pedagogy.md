# PostgreSQL `pedagogy` schema

**Role:** Imported steps and released instructional routes. Textbook provenance plus reviewed immutable route releases, instructional assets and compiler jobs.

**Access family:** `/v1/admin/textbooks/*`, `/v1/admin/tutoring-routes/*`, `/v1/tutor/*`; source compiler and metadata projector.

**Evidence:** live catalog metadata at 2026-10-08T01:57:54.421824+00:00; source `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

### `pedagogy.chapter_section`

**Kind / use case:** table. Book chapter/section hierarchy and source numbering.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L131); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L64); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L895).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `book_code` | `text` | no | `-` | `- / -` |
| `chapter_number` | `integer` | no | `-` | `- / -` |
| `section_number` | `text` | no | `-` | `- / -` |
| `chapter_title` | `text` | yes | `-` | `- / -` |
| `section_title` | `text` | yes | `-` | `- / -` |
| `paper_id` | `uuid` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `chapter_section_book_code_fkey` / `f` | `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)` | deferrable=False, initially deferred=False, validated=True |
| `chapter_section_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `chapter_section_chapter_number_not_null` / `n` | `NOT NULL chapter_number` | deferrable=False, initially deferred=False, validated=True |
| `chapter_section_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `chapter_section_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `chapter_section_paper_id_fkey` / `f` | `FOREIGN KEY (paper_id) REFERENCES core.paper(paper_id)` | deferrable=False, initially deferred=False, validated=True |
| `chapter_section_pkey` / `p` | `PRIMARY KEY (book_code, chapter_number, section_number)` | deferrable=False, initially deferred=False, validated=True |
| `chapter_section_section_number_not_null` / `n` | `NOT NULL section_number` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `chapter_section_pkey`: `CREATE UNIQUE INDEX chapter_section_pkey ON pedagogy.chapter_section USING btree (book_code, chapter_number, section_number)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.diagram`

**Kind / use case:** table. Source diagram provenance, problem/solution usage and student visibility.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L329); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L65); [mathbank-rest/src/mathbank_rest/db/problem_images.py](../../../mathbank-rest/src/mathbank_rest/db/problem_images.py#L13); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L1081).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `diagram_id` | `text` | no | `-` | `- / -` |
| `source_diagram_id` | `text` | no | `-` | `- / -` |
| `book_code` | `text` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `usage` | `text` | no | `-` | `- / -` |
| `visibility` | `text` | no | `-` | `- / -` |
| `source_pdf_page` | `integer` | yes | `-` | `- / -` |
| `source_figure_number` | `text` | yes | `-` | `- / -` |
| `source_caption` | `text` | yes | `-` | `- / -` |
| `asset_path` | `text` | no | `-` | `- / -` |
| `local_path` | `text` | no | `-` | `- / -` |
| `sha256` | `text` | yes | `-` | `- / -` |
| `extraction_method` | `text` | yes | `-` | `- / -` |
| `validation_status` | `text` | yes | `-` | `- / -` |
| `problem_image_id` | `uuid` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `diagram_asset_path_not_null` / `n` | `NOT NULL asset_path` | deferrable=False, initially deferred=False, validated=True |
| `diagram_book_code_fkey` / `f` | `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)` | deferrable=False, initially deferred=False, validated=True |
| `diagram_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `diagram_book_code_source_diagram_id_key` / `u` | `UNIQUE (book_code, source_diagram_id)` | deferrable=False, initially deferred=False, validated=True |
| `diagram_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `diagram_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `diagram_diagram_id_not_null` / `n` | `NOT NULL diagram_id` | deferrable=False, initially deferred=False, validated=True |
| `diagram_local_path_not_null` / `n` | `NOT NULL local_path` | deferrable=False, initially deferred=False, validated=True |
| `diagram_pkey` / `p` | `PRIMARY KEY (diagram_id)` | deferrable=False, initially deferred=False, validated=True |
| `diagram_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `diagram_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `diagram_problem_image_id_fkey` / `f` | `FOREIGN KEY (problem_image_id) REFERENCES core.problem_image(problem_image_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `diagram_source_diagram_id_not_null` / `n` | `NOT NULL source_diagram_id` | deferrable=False, initially deferred=False, validated=True |
| `diagram_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |
| `diagram_usage_not_null` / `n` | `NOT NULL usage` | deferrable=False, initially deferred=False, validated=True |
| `diagram_visibility_check` / `c` | `CHECK (visibility = ANY (ARRAY['STUDENT_PROBLEM'::text, 'SOLUTION_HIDDEN'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `diagram_visibility_not_null` / `n` | `NOT NULL visibility` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `visual.asset` / `asset_diagram_id_fkey`: `FOREIGN KEY (diagram_id) REFERENCES pedagogy.diagram(diagram_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `diagram_book_code_source_diagram_id_key`: `CREATE UNIQUE INDEX diagram_book_code_source_diagram_id_key ON pedagogy.diagram USING btree (book_code, source_diagram_id)`; valid=True, ready=True.
- `diagram_pkey`: `CREATE UNIQUE INDEX diagram_pkey ON pedagogy.diagram USING btree (diagram_id)`; valid=True, ready=True.
- `diagram_problem_idx`: `CREATE INDEX diagram_problem_idx ON pedagogy.diagram USING btree (problem_id, usage)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.gap_diagnosis`

**Kind / use case:** table. Attempt/step-specific local failure diagnosis evidence.

**Migration owner:** [014_gap_diagnosis.sql](../../../mathbank-db/sql/014_gap_diagnosis.sql#L11); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L168); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L316).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `gap_diagnosis_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `solve_attempt_id` | `uuid` | no | `-` | `- / -` |
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `trigger` | `text` | no | `-` | `- / -` |
| `recommended_action` | `text` | no | `-` | `- / -` |
| `evidence_fingerprint` | `text` | no | `-` | `- / -` |
| `evidence` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `probes` | `jsonb` | no | `'[]'::jsonb` | `- / -` |
| `diagnoser_version` | `text` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `ai_rerank` | `jsonb` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `gap_diagnosis_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_diagnoser_version_not_null` / `n` | `NOT NULL diagnoser_version` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_evidence_fingerprint_not_null` / `n` | `NOT NULL evidence_fingerprint` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_evidence_not_null` / `n` | `NOT NULL evidence` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_gap_diagnosis_id_not_null` / `n` | `NOT NULL gap_diagnosis_id` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_pkey` / `p` | `PRIMARY KEY (gap_diagnosis_id)` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_probes_not_null` / `n` | `NOT NULL probes` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_recommended_action_check` / `c` | `CHECK (recommended_action = ANY (ARRAY['RETRY_WITH_HINT'::text, 'DIAGNOSTIC_PROBE'::text, 'RECOVERY_DETOUR'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_recommended_action_not_null` / `n` | `NOT NULL recommended_action` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_solve_attempt_id_fkey` / `f` | `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_solve_attempt_id_not_null` / `n` | `NOT NULL solve_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_solve_attempt_id_solution_step_id_evidence_fi_key` / `u` | `UNIQUE (solve_attempt_id, solution_step_id, evidence_fingerprint)` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_trigger_check` / `c` | `CHECK (trigger = ANY (ARRAY['AUTO'::text, 'STUDENT_REQUEST'::text, 'TUTOR'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `gap_diagnosis_trigger_not_null` / `n` | `NOT NULL trigger` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.knowledge_gap` / `knowledge_gap_gap_diagnosis_id_fkey`: `FOREIGN KEY (gap_diagnosis_id) REFERENCES pedagogy.gap_diagnosis(gap_diagnosis_id) ON DELETE CASCADE`.
- `pedagogy.recovery_plan` / `recovery_plan_gap_diagnosis_id_fkey`: `FOREIGN KEY (gap_diagnosis_id) REFERENCES pedagogy.gap_diagnosis(gap_diagnosis_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `gap_diagnosis_pkey`: `CREATE UNIQUE INDEX gap_diagnosis_pkey ON pedagogy.gap_diagnosis USING btree (gap_diagnosis_id)`; valid=True, ready=True.
- `gap_diagnosis_solve_attempt_id_solution_step_id_evidence_fi_key`: `CREATE UNIQUE INDEX gap_diagnosis_solve_attempt_id_solution_step_id_evidence_fi_key ON pedagogy.gap_diagnosis USING btree (solve_attempt_id, solution_step_id, evidence_fingerprint)`; valid=True, ready=True.
- `gap_diagnosis_student_idx`: `CREATE INDEX gap_diagnosis_student_idx ON pedagogy.gap_diagnosis USING btree (student_id, created_at DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.knowledge_gap`

**Kind / use case:** table. Persistent learner gap hypothesis and review/resolution lifecycle.

**Migration owner:** [014_gap_diagnosis.sql](../../../mathbank-db/sql/014_gap_diagnosis.sql#L28); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L582); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L321); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L132).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `knowledge_gap_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `gap_diagnosis_id` | `uuid` | no | `-` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `solve_attempt_id` | `uuid` | no | `-` | `- / -` |
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `rank` | `integer` | no | `-` | `- / -` |
| `failure_location` | `text` | no | `-` | `- / -` |
| `failure_mode` | `text` | no | `-` | `- / -` |
| `target_concept_id` | `text` | yes | `-` | `- / -` |
| `target_subconcept_id` | `text` | yes | `-` | `- / -` |
| `target_skill_id` | `text` | yes | `-` | `- / -` |
| `target_skill_node_id` | `uuid` | yes | `-` | `- / -` |
| `target_label` | `text` | yes | `-` | `- / -` |
| `source_step_id` | `text` | yes | `-` | `- / -` |
| `confidence` | `numeric(4,3)` | no | `-` | `- / -` |
| `evidence` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `status` | `text` | no | `'UNRESOLVED'::text` | `- / -` |
| `status_reason` | `text` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `status_changed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `resolved_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `knowledge_gap_confidence_check` / `c` | `CHECK (confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_evidence_not_null` / `n` | `NOT NULL evidence` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_failure_location_check` / `c` | `CHECK (failure_location = ANY (ARRAY['CONCEPT'::text, 'SUBCONCEPT'::text, 'SKILL'::text, 'TECHNIQUE'::text, 'PREREQUISITE'::text, 'REPRESENTATION'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_failure_location_not_null` / `n` | `NOT NULL failure_location` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_failure_mode_check` / `c` | `CHECK (failure_mode = ANY (ARRAY['NOT_RECOGNIZED'::text, 'MISUNDERSTOOD'::text, 'THEOREM_NOT_RECALLED'::text, 'WRONG_THEOREM_SELECTED'::text, 'CANNOT_EXECUTE'::text, 'PROOF_CONNECTION_MISSING'::text, 'DIAGRAM_MISREAD'::text, 'ALGEBRA_BREAKDOWN'::text, 'CASE_MISSED'::text, 'OVERCOMPLICATED'::text, 'CARELESS'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_failure_mode_not_null` / `n` | `NOT NULL failure_mode` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_gap_diagnosis_id_fkey` / `f` | `FOREIGN KEY (gap_diagnosis_id) REFERENCES pedagogy.gap_diagnosis(gap_diagnosis_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_gap_diagnosis_id_not_null` / `n` | `NOT NULL gap_diagnosis_id` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_gap_diagnosis_id_rank_key` / `u` | `UNIQUE (gap_diagnosis_id, rank)` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_knowledge_gap_id_not_null` / `n` | `NOT NULL knowledge_gap_id` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_pkey` / `p` | `PRIMARY KEY (knowledge_gap_id)` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_rank_check` / `c` | `CHECK (rank >= 1)` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_rank_not_null` / `n` | `NOT NULL rank` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_solve_attempt_id_fkey` / `f` | `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_solve_attempt_id_not_null` / `n` | `NOT NULL solve_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_source_step_id_fkey` / `f` | `FOREIGN KEY (source_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_status_check` / `c` | `CHECK (status = ANY (ARRAY['UNRESOLVED'::text, 'CONFIRMED'::text, 'REJECTED'::text, 'RESOLVED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `knowledge_gap_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.recovery_plan` / `recovery_plan_knowledge_gap_id_fkey`: `FOREIGN KEY (knowledge_gap_id) REFERENCES pedagogy.knowledge_gap(knowledge_gap_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `knowledge_gap_attempt_idx`: `CREATE INDEX knowledge_gap_attempt_idx ON pedagogy.knowledge_gap USING btree (solve_attempt_id)`; valid=True, ready=True.
- `knowledge_gap_gap_diagnosis_id_rank_key`: `CREATE UNIQUE INDEX knowledge_gap_gap_diagnosis_id_rank_key ON pedagogy.knowledge_gap USING btree (gap_diagnosis_id, rank)`; valid=True, ready=True.
- `knowledge_gap_open_idx`: `CREATE INDEX knowledge_gap_open_idx ON pedagogy.knowledge_gap USING btree (student_id, target_skill_id) WHERE (status = ANY (ARRAY['UNRESOLVED'::text, 'CONFIRMED'::text]))`; valid=True, ready=True.
- `knowledge_gap_pkey`: `CREATE UNIQUE INDEX knowledge_gap_pkey ON pedagogy.knowledge_gap USING btree (knowledge_gap_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.learning_item`

**Kind / use case:** table. Derived exercise/theory/recovery material with visibility/review gates.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L289); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L206); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L281); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L61); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L76); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L251); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L1044); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L123); [mathbank-graph/etl/project_textbook_steps.py](../../../mathbank-graph/etl/project_textbook_steps.py#L109).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `learning_item_id` | `text` | no | `-` | `- / -` |
| `source_transformation_id` | `text` | no | `-` | `- / -` |
| `occurrence` | `integer` | no | `1` | `- / -` |
| `book_code` | `text` | no | `-` | `- / -` |
| `source_problem_id` | `uuid` | no | `-` | `- / -` |
| `parent_learning_item_id` | `text` | yes | `-` | `- / -` |
| `transformation_type` | `text` | no | `-` | `- / -` |
| `transformed_form` | `text` | yes | `-` | `- / -` |
| `target_concept_node_id` | `text` | yes | `-` | `- / -` |
| `target_subconcept_node_id` | `text` | yes | `-` | `- / -` |
| `target_skill_node_id` | `text` | yes | `-` | `- / -` |
| `difficulty_direction` | `text` | yes | `-` | `- / -` |
| `question_text` | `text` | no | `-` | `- / -` |
| `choices` | `jsonb` | yes | `-` | `- / -` |
| `correct_answer` | `text` | yes | `-` | `- / -` |
| `answer_or_solution_seed` | `text` | yes | `-` | `- / -` |
| `generation_mode` | `text` | yes | `-` | `- / -` |
| `solution_part_label` | `text` | yes | `-` | `- / -` |
| `requires_source_problem` | `boolean` | yes | `-` | `- / -` |
| `diagram_strategy` | `text` | yes | `-` | `- / -` |
| `no_proof` | `boolean` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'PENDING_REVIEW'::text` | `- / -` |
| `student_visible` | `boolean` | no | `false` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |
| `approved_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `learning_item_approval_method_check` / `c` | `CHECK (approval_method IS NULL OR (approval_method = ANY (ARRAY['automatic'::text, 'human'::text])))` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_book_code_fkey` / `f` | `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_book_code_source_transformation_id_occurrence_key` / `u` | `UNIQUE (book_code, source_transformation_id, occurrence)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_learning_item_id_not_null` / `n` | `NOT NULL learning_item_id` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_no_proof_check` / `c` | `CHECK (no_proof)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_no_proof_not_null` / `n` | `NOT NULL no_proof` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_occurrence_not_null` / `n` | `NOT NULL occurrence` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_pkey` / `p` | `PRIMARY KEY (learning_item_id)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_question_text_not_null` / `n` | `NOT NULL question_text` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING_REVIEW'::text, 'APPROVED'::text, 'REJECTED'::text, 'NEEDS_REVISION'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_source_problem_id_fkey` / `f` | `FOREIGN KEY (source_problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_source_problem_id_not_null` / `n` | `NOT NULL source_problem_id` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_source_transformation_id_not_null` / `n` | `NOT NULL source_transformation_id` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_student_visible_not_null` / `n` | `NOT NULL student_visible` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_target_concept_node_id_fkey` / `f` | `FOREIGN KEY (target_concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_target_skill_node_id_fkey` / `f` | `FOREIGN KEY (target_skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_target_subconcept_node_id_fkey` / `f` | `FOREIGN KEY (target_subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_transformation_type_not_null` / `n` | `NOT NULL transformation_type` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_visible_requires_approval` / `c` | `CHECK (NOT student_visible OR review_status = 'APPROVED'::text)` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.learning_item_step_anchor` / `learning_item_step_anchor_learning_item_id_fkey`: `FOREIGN KEY (learning_item_id) REFERENCES pedagogy.learning_item(learning_item_id) ON DELETE CASCADE`.
- `pedagogy.recovery_plan_item` / `recovery_plan_item_learning_item_id_fkey`: `FOREIGN KEY (learning_item_id) REFERENCES pedagogy.learning_item(learning_item_id)`.
- `search.chunk` / `chunk_learning_item_id_fkey`: `FOREIGN KEY (learning_item_id) REFERENCES pedagogy.learning_item(learning_item_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `learning_item_book_code_source_transformation_id_occurrence_key`: `CREATE UNIQUE INDEX learning_item_book_code_source_transformation_id_occurrence_key ON pedagogy.learning_item USING btree (book_code, source_transformation_id, occurrence)`; valid=True, ready=True.
- `learning_item_pkey`: `CREATE UNIQUE INDEX learning_item_pkey ON pedagogy.learning_item USING btree (learning_item_id)`; valid=True, ready=True.
- `learning_item_problem_idx`: `CREATE INDEX learning_item_problem_idx ON pedagogy.learning_item USING btree (source_problem_id)`; valid=True, ready=True.
- `learning_item_skill_visible_idx`: `CREATE INDEX learning_item_skill_visible_idx ON pedagogy.learning_item USING btree (target_skill_node_id, transformation_type) WHERE student_visible`; valid=True, ready=True.
- `learning_item_subconcept_visible_idx`: `CREATE INDEX learning_item_subconcept_visible_idx ON pedagogy.learning_item USING btree (target_subconcept_node_id, transformation_type) WHERE student_visible`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.learning_item_step_anchor`

**Kind / use case:** table. Ordered learning-item-to-reference-step anchors.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L322); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L71); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L78); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L1065); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L119); [mathbank-graph/etl/project_textbook_steps.py](../../../mathbank-graph/etl/project_textbook_steps.py#L120).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `learning_item_id` | `text` | no | `-` | `- / -` |
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `anchor_ordinal` | `integer` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `learning_item_step_anchor_anchor_ordinal_not_null` / `n` | `NOT NULL anchor_ordinal` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_step_anchor_learning_item_id_fkey` / `f` | `FOREIGN KEY (learning_item_id) REFERENCES pedagogy.learning_item(learning_item_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_step_anchor_learning_item_id_not_null` / `n` | `NOT NULL learning_item_id` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_step_anchor_pkey` / `p` | `PRIMARY KEY (learning_item_id, solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_step_anchor_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `learning_item_step_anchor_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `learning_item_step_anchor_pkey`: `CREATE UNIQUE INDEX learning_item_step_anchor_pkey ON pedagogy.learning_item_step_anchor USING btree (learning_item_id, solution_step_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.problem_enrichment`

**Kind / use case:** table. Package problem taxonomy, skill and technique assignments.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L204); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L208); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L99); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L71); [mathbank-db/etl/derive_step_techniques.py](../../../mathbank-db/etl/derive_step_techniques.py#L146); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L951).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `concept_node_id` | `text` | yes | `-` | `- / -` |
| `subconcept_node_id` | `text` | yes | `-` | `- / -` |
| `primary_skill_node_id` | `text` | yes | `-` | `- / -` |
| `solution_step_skill_ids` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `technique_ids` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `problem_form` | `text` | yes | `-` | `- / -` |
| `difficulty_band_source_order` | `integer` | yes | `-` | `- / -` |
| `solution_step_count` | `integer` | yes | `-` | `- / -` |
| `taxonomy_mapping_basis` | `text` | yes | `-` | `- / -` |
| `taxonomy_confidence` | `numeric` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_enrichment_concept_node_id_fkey` / `f` | `FOREIGN KEY (concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_pkey` / `p` | `PRIMARY KEY (problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_primary_skill_node_id_fkey` / `f` | `FOREIGN KEY (primary_skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_solution_step_skill_ids_not_null` / `n` | `NOT NULL solution_step_skill_ids` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_subconcept_node_id_fkey` / `f` | `FOREIGN KEY (subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_technique_ids_not_null` / `n` | `NOT NULL technique_ids` | deferrable=False, initially deferred=False, validated=True |
| `problem_enrichment_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `problem_enrichment_pkey`: `CREATE UNIQUE INDEX problem_enrichment_pkey ON pedagogy.problem_enrichment USING btree (problem_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.problem_source_ref`

**Kind / use case:** table. Printed problem/book/page/diagram requirement mapping.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L171); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/enrichment.py](../../../mathbank-rest/src/mathbank_rest/enrichment.py#L392); [mathbank-rest/src/mathbank_rest/db/problem_sources.py](../../../mathbank-rest/src/mathbank_rest/db/problem_sources.py#L25); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L60); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L920); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L107).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `book_code` | `text` | no | `-` | `- / -` |
| `source_problem_id` | `text` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `chapter_number` | `integer` | no | `-` | `- / -` |
| `section_number` | `text` | yes | `-` | `- / -` |
| `section_title` | `text` | yes | `-` | `- / -` |
| `source_printed_problem_id` | `text` | yes | `-` | `- / -` |
| `source_editorial_marker` | `text` | yes | `-` | `- / -` |
| `source_numbering_note` | `text` | yes | `-` | `- / -` |
| `source_pdf` | `text` | yes | `-` | `- / -` |
| `source_page_start` | `integer` | yes | `-` | `- / -` |
| `source_page_end` | `integer` | yes | `-` | `- / -` |
| `problem_requires_diagram` | `boolean` | yes | `-` | `- / -` |
| `solution_requires_diagram` | `boolean` | yes | `-` | `- / -` |
| `difficulty_rank_in_section` | `integer` | yes | `-` | `- / -` |
| `section_problem_count` | `integer` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `problem_source_ref_book_code_fkey` / `f` | `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_chapter_number_not_null` / `n` | `NOT NULL chapter_number` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_pkey` / `p` | `PRIMARY KEY (book_code, source_problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_problem_id_key` / `u` | `UNIQUE (problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `problem_source_ref_source_problem_id_not_null` / `n` | `NOT NULL source_problem_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `problem_source_ref_pkey`: `CREATE UNIQUE INDEX problem_source_ref_pkey ON pedagogy.problem_source_ref USING btree (book_code, source_problem_id)`; valid=True, ready=True.
- `problem_source_ref_problem_id_key`: `CREATE UNIQUE INDEX problem_source_ref_problem_id_key ON pedagogy.problem_source_ref USING btree (problem_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.recovery_plan`

**Kind / use case:** table. Attempt-bound remediation plan linked back to original step.

**Migration owner:** [015_recovery_runtime.sql](../../../mathbank-db/sql/015_recovery_runtime.sql#L28); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L485); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L217); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L595).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `recovery_plan_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `student_id` | `uuid` | no | `-` | `- / -` |
| `solve_attempt_id` | `uuid` | no | `-` | `- / -` |
| `origin_problem_id` | `uuid` | no | `-` | `- / -` |
| `origin_step_id` | `text` | no | `-` | `- / -` |
| `gap_diagnosis_id` | `uuid` | yes | `-` | `- / -` |
| `knowledge_gap_id` | `uuid` | yes | `-` | `- / -` |
| `parent_recovery_plan_id` | `uuid` | yes | `-` | `- / -` |
| `trigger` | `text` | no | `-` | `- / -` |
| `target_skill_id` | `text` | yes | `-` | `- / -` |
| `target_subconcept_id` | `text` | yes | `-` | `- / -` |
| `target_label` | `text` | yes | `-` | `- / -` |
| `status` | `text` | no | `'ACTIVE'::text` | `- / -` |
| `current_item_ordinal` | `integer` | yes | `-` | `- / -` |
| `mastery_policy` | `jsonb` | no | `'{"max_help_level_on_final": 1, "transfer_success_required": true, "independent_successes_required": 2}'::jsonb` | `- / -` |
| `outcome` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `planner_version` | `text` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `ended_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `recovery_plan_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_gap_diagnosis_id_fkey` / `f` | `FOREIGN KEY (gap_diagnosis_id) REFERENCES pedagogy.gap_diagnosis(gap_diagnosis_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_knowledge_gap_id_fkey` / `f` | `FOREIGN KEY (knowledge_gap_id) REFERENCES pedagogy.knowledge_gap(knowledge_gap_id) ON DELETE SET NULL` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_mastery_policy_not_null` / `n` | `NOT NULL mastery_policy` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_origin_problem_id_fkey` / `f` | `FOREIGN KEY (origin_problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_origin_problem_id_not_null` / `n` | `NOT NULL origin_problem_id` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_origin_step_id_fkey` / `f` | `FOREIGN KEY (origin_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_origin_step_id_not_null` / `n` | `NOT NULL origin_step_id` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_outcome_not_null` / `n` | `NOT NULL outcome` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_parent_recovery_plan_id_fkey` / `f` | `FOREIGN KEY (parent_recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_pkey` / `p` | `PRIMARY KEY (recovery_plan_id)` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_planner_version_not_null` / `n` | `NOT NULL planner_version` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_recovery_plan_id_not_null` / `n` | `NOT NULL recovery_plan_id` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_solve_attempt_id_fkey` / `f` | `FOREIGN KEY (solve_attempt_id) REFERENCES learner.solve_attempt(solve_attempt_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_solve_attempt_id_not_null` / `n` | `NOT NULL solve_attempt_id` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_status_check` / `c` | `CHECK (status = ANY (ARRAY['ACTIVE'::text, 'SUSPENDED'::text, 'COMPLETED'::text, 'EXHAUSTED'::text, 'ABORTED'::text, 'SUPERSEDED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_student_id_fkey` / `f` | `FOREIGN KEY (student_id) REFERENCES learner.student_profile(student_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_student_id_not_null` / `n` | `NOT NULL student_id` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_trigger_check` / `c` | `CHECK (trigger = ANY (ARRAY['DIAGNOSIS'::text, 'STUDENT_REQUEST'::text, 'TUTOR'::text, 'BRANCH'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_trigger_not_null` / `n` | `NOT NULL trigger` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `learner.solve_attempt` / `solve_attempt_recovery_plan_fk`: `FOREIGN KEY (recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE SET NULL`.
- `pedagogy.recovery_plan` / `recovery_plan_parent_recovery_plan_id_fkey`: `FOREIGN KEY (parent_recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE CASCADE`.
- `pedagogy.recovery_plan_item` / `recovery_plan_item_recovery_plan_id_fkey`: `FOREIGN KEY (recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE CASCADE`.
- `tutor.runtime_state` / `runtime_state_recovery_plan_fk`: `FOREIGN KEY (current_recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `recovery_plan_one_active_idx`: `CREATE UNIQUE INDEX recovery_plan_one_active_idx ON pedagogy.recovery_plan USING btree (solve_attempt_id) WHERE (status = 'ACTIVE'::text)`; valid=True, ready=True.
- `recovery_plan_pkey`: `CREATE UNIQUE INDEX recovery_plan_pkey ON pedagogy.recovery_plan USING btree (recovery_plan_id)`; valid=True, ready=True.
- `recovery_plan_student_idx`: `CREATE INDEX recovery_plan_student_idx ON pedagogy.recovery_plan USING btree (student_id, created_at DESC)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.recovery_plan_item`

**Kind / use case:** table. Ordered theory/exercise/retry actions in a recovery detour.

**Migration owner:** [015_recovery_runtime.sql](../../../mathbank-db/sql/015_recovery_runtime.sql#L57); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L216).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `recovery_plan_item_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `recovery_plan_id` | `uuid` | no | `-` | `- / -` |
| `ordinal` | `integer` | no | `-` | `- / -` |
| `stage` | `text` | no | `-` | `- / -` |
| `item_kind` | `text` | no | `-` | `- / -` |
| `learning_item_id` | `text` | yes | `-` | `- / -` |
| `worked_step_id` | `text` | yes | `-` | `- / -` |
| `is_transfer` | `boolean` | no | `false` | `- / -` |
| `required` | `boolean` | no | `true` | `- / -` |
| `status` | `text` | no | `'PENDING'::text` | `- / -` |
| `tries` | `integer` | no | `0` | `- / -` |
| `independent_success` | `boolean` | yes | `-` | `- / -` |
| `last_response` | `jsonb` | yes | `-` | `- / -` |
| `last_result` | `jsonb` | yes | `-` | `- / -` |
| `added_reason` | `text` | no | `'PLANNED'::text` | `- / -` |
| `presented_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `recovery_plan_item_added_reason_not_null` / `n` | `NOT NULL added_reason` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_check` / `c` | `CHECK ((item_kind = 'LEARNING_ITEM'::text) = (learning_item_id IS NOT NULL))` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_is_transfer_not_null` / `n` | `NOT NULL is_transfer` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_item_kind_check` / `c` | `CHECK (item_kind = ANY (ARRAY['LEARNING_ITEM'::text, 'THEORY'::text, 'RETURN'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_item_kind_not_null` / `n` | `NOT NULL item_kind` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_learning_item_id_fkey` / `f` | `FOREIGN KEY (learning_item_id) REFERENCES pedagogy.learning_item(learning_item_id)` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_ordinal_check` / `c` | `CHECK (ordinal >= 1)` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_ordinal_not_null` / `n` | `NOT NULL ordinal` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_pkey` / `p` | `PRIMARY KEY (recovery_plan_item_id)` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_recovery_plan_id_fkey` / `f` | `FOREIGN KEY (recovery_plan_id) REFERENCES pedagogy.recovery_plan(recovery_plan_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_recovery_plan_id_not_null` / `n` | `NOT NULL recovery_plan_id` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_recovery_plan_id_ordinal_key` / `u` | `UNIQUE (recovery_plan_id, ordinal)` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_recovery_plan_item_id_not_null` / `n` | `NOT NULL recovery_plan_item_id` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_required_not_null` / `n` | `NOT NULL required` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_stage_check` / `c` | `CHECK (stage = ANY (ARRAY['FOUNDATION'::text, 'RECOGNITION'::text, 'ISOLATED_EXECUTION'::text, 'GUIDED_APPLICATION'::text, 'TRANSFER'::text, 'RETURN_TO_STEP'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_stage_not_null` / `n` | `NOT NULL stage` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_status_check` / `c` | `CHECK (status = ANY (ARRAY['PENDING'::text, 'PRESENTED'::text, 'PASSED'::text, 'FAILED'::text, 'SKIPPED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_tries_not_null` / `n` | `NOT NULL tries` | deferrable=False, initially deferred=False, validated=True |
| `recovery_plan_item_worked_step_id_fkey` / `f` | `FOREIGN KEY (worked_step_id) REFERENCES pedagogy.solution_step(solution_step_id)` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `recovery_plan_item_pkey`: `CREATE UNIQUE INDEX recovery_plan_item_pkey ON pedagogy.recovery_plan_item USING btree (recovery_plan_item_id)`; valid=True, ready=True.
- `recovery_plan_item_recovery_plan_id_ordinal_key`: `CREATE UNIQUE INDEX recovery_plan_item_recovery_plan_id_ordinal_key ON pedagogy.recovery_plan_item USING btree (recovery_plan_id, ordinal)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.route_asset`

**Kind / use case:** table. Release-local claim, misconception, theory or purpose-tagged learning item; not a shared canonical library.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L98); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L107); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L317); [mathbank-rest/src/mathbank_rest/route_projection.py](../../../mathbank-rest/src/mathbank_rest/route_projection.py#L74).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_release_id` | `uuid` | no | `-` | `- / -` |
| `asset_key` | `text` | no | `-` | `- / -` |
| `asset_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `asset_kind` | `text` | no | `-` | `- / -` |
| `content_hash` | `text` | no | `-` | `- / -` |
| `content` | `jsonb` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `route_asset_asset_id_key` / `u` | `UNIQUE (asset_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_asset_id_not_null` / `n` | `NOT NULL asset_id` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_asset_key_not_null` / `n` | `NOT NULL asset_key` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_asset_kind_check` / `c` | `CHECK (asset_kind = ANY (ARRAY['CLAIM'::text, 'MISCONCEPTION'::text, 'THEORY'::text, 'LEARNING_ITEM'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_asset_kind_not_null` / `n` | `NOT NULL asset_kind` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_content_hash_not_null` / `n` | `NOT NULL content_hash` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_content_not_null` / `n` | `NOT NULL content` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_pkey` / `p` | `PRIMARY KEY (route_release_id, asset_key)` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_route_release_id_fkey` / `f` | `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.route_asset_link` / `route_asset_link_route_release_id_asset_key_fkey`: `FOREIGN KEY (route_release_id, asset_key) REFERENCES pedagogy.route_asset(route_release_id, asset_key)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_asset_asset_id_key`: `CREATE UNIQUE INDEX route_asset_asset_id_key ON pedagogy.route_asset USING btree (asset_id)`; valid=True, ready=True.
- `route_asset_pkey`: `CREATE UNIQUE INDEX route_asset_pkey ON pedagogy.route_asset USING btree (route_release_id, asset_key)`; valid=True, ready=True.

**Triggers:**

- `immutable_route_snapshot`: `CREATE TRIGGER immutable_route_snapshot BEFORE INSERT OR DELETE OR UPDATE ON pedagogy.route_asset FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_snapshot()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.route_asset_link`

**Kind / use case:** table. Typed checkpoint CAN_TRIGGER/CHECKED_BY/EXPLAINED_BY asset relationships.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L108); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L70); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L384).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_release_id` | `uuid` | no | `-` | `- / -` |
| `step_index` | `integer` | no | `-` | `- / -` |
| `asset_key` | `text` | no | `-` | `- / -` |
| `role` | `text` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `route_asset_link_asset_key_not_null` / `n` | `NOT NULL asset_key` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_link_pkey` / `p` | `PRIMARY KEY (route_release_id, step_index, asset_key, role)` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_link_role_check` / `c` | `CHECK (role = ANY (ARRAY['CAN_TRIGGER'::text, 'CHECKED_BY'::text, 'EXPLAINED_BY'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_link_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_link_route_release_id_asset_key_fkey` / `f` | `FOREIGN KEY (route_release_id, asset_key) REFERENCES pedagogy.route_asset(route_release_id, asset_key)` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_link_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_link_route_release_id_step_index_fkey` / `f` | `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)` | deferrable=False, initially deferred=False, validated=True |
| `route_asset_link_step_index_not_null` / `n` | `NOT NULL step_index` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_asset_link_pkey`: `CREATE UNIQUE INDEX route_asset_link_pkey ON pedagogy.route_asset_link USING btree (route_release_id, step_index, asset_key, role)`; valid=True, ready=True.

**Triggers:**

- `immutable_route_snapshot`: `CREATE TRIGGER immutable_route_snapshot BEFORE INSERT OR DELETE OR UPDATE ON pedagogy.route_asset_link FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_snapshot()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.route_compiler_job`

**Kind / use case:** table. Per-run solution/source hash, resumable QUEUED/RUNNING/DRAFT/REUSED/FAILED state and safe error class.
Incremental full-corpus migration source adds `error_details` and QUEUED below;
the remaining catalog fields retain the original observation.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L40); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L80).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `run_id` | `uuid` | no | `-` | `- / -` |
| `solution_id` | `uuid` | no | `-` | `- / -` |
| `source_hash` | `text` | no | `-` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `route_release_id` | `uuid` | yes | `-` | `- / -` |
| `error_code` | `text` | yes | `-` | `- / -` |
| `error_details` | `jsonb` | no | `'[]'::jsonb` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `route_compiler_job_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_pkey` / `p` | `PRIMARY KEY (run_id, solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_route_release_id_fkey` / `f` | `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_run_id_fkey` / `f` | `FOREIGN KEY (run_id) REFERENCES pedagogy.route_compiler_run(run_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_run_id_not_null` / `n` | `NOT NULL run_id` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_source_hash_not_null` / `n` | `NOT NULL source_hash` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_job_status_check` / `c` | `CHECK (status IN ('QUEUED','RUNNING','DRAFT','REUSED','FAILED'))` | Source-derived full-corpus extension |
| `route_compiler_job_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_compiler_job_pkey`: `CREATE UNIQUE INDEX route_compiler_job_pkey ON pedagogy.route_compiler_job USING btree (run_id, solution_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.route_compiler_run`

**Kind / use case:** table. Frozen bounded/full-corpus source cohort, compiler version, operator bulk approval policy and aggregate ingestion outcome.
Incremental full-corpus migration source adds `auto_review_by` and lifts the
10,000-source constraint below; other fields retain the original observation.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L3); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L415).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `run_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `generator_version` | `text` | no | `-` | `- / -` |
| `auto_review_by` | `text` | yes | `-` | `- / -` |
| `requested_limit` | `integer` | no | `-` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `completed_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `route_compiler_run_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_run_generator_version_not_null` / `n` | `NOT NULL generator_version` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_run_pkey` / `p` | `PRIMARY KEY (run_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_run_requested_limit_check` / `c` | `CHECK (requested_limit > 0)` | Source-derived full-corpus extension |
| `route_compiler_run_requested_limit_not_null` / `n` | `NOT NULL requested_limit` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_run_run_id_not_null` / `n` | `NOT NULL run_id` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_run_status_check` / `c` | `CHECK (status = ANY (ARRAY['RUNNING'::text, 'COMPLETED'::text, 'PARTIAL'::text, 'FAILED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `route_compiler_run_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.route_compiler_job` / `route_compiler_job_run_id_fkey`: `FOREIGN KEY (run_id) REFERENCES pedagogy.route_compiler_run(run_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_compiler_run_pkey`: `CREATE UNIQUE INDEX route_compiler_run_pkey ON pedagogy.route_compiler_run USING btree (run_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.route_step`

**Kind / use case:** table. Release-owned 1-based atomic mathematical result, exact source excerpt and earlier claim/dependency references.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L52); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L47); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L331); [mathbank-rest/src/mathbank_rest/route_projection.py](../../../mathbank-rest/src/mathbank_rest/route_projection.py#L66); [mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L73).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_release_id` | `uuid` | no | `-` | `- / -` |
| `step_index` | `integer` | no | `-` | `- / -` |
| `step_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `mathematical_result` | `text` | no | `-` | `- / -` |
| `source_quote` | `text` | no | `-` | `- / -` |
| `depends_on` | `integer[]` | no | `'{}'::integer[]` | `- / -` |
| `produces` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `uses_claims` | `text[]` | no | `'{}'::text[]` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `route_step_depends_on_not_null` / `n` | `NOT NULL depends_on` | deferrable=False, initially deferred=False, validated=True |
| `route_step_mathematical_result_not_null` / `n` | `NOT NULL mathematical_result` | deferrable=False, initially deferred=False, validated=True |
| `route_step_pkey` / `p` | `PRIMARY KEY (route_release_id, step_index)` | deferrable=False, initially deferred=False, validated=True |
| `route_step_produces_not_null` / `n` | `NOT NULL produces` | deferrable=False, initially deferred=False, validated=True |
| `route_step_route_release_id_fkey` / `f` | `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_step_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |
| `route_step_source_quote_not_null` / `n` | `NOT NULL source_quote` | deferrable=False, initially deferred=False, validated=True |
| `route_step_step_id_key` / `u` | `UNIQUE (step_id)` | deferrable=False, initially deferred=False, validated=True |
| `route_step_step_id_not_null` / `n` | `NOT NULL step_id` | deferrable=False, initially deferred=False, validated=True |
| `route_step_step_index_check` / `c` | `CHECK (step_index > 0)` | deferrable=False, initially deferred=False, validated=True |
| `route_step_step_index_not_null` / `n` | `NOT NULL step_index` | deferrable=False, initially deferred=False, validated=True |
| `route_step_uses_claims_not_null` / `n` | `NOT NULL uses_claims` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.route_asset_link` / `route_asset_link_route_release_id_step_index_fkey`: `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)`.
- `pedagogy.route_step_hint` / `route_step_hint_route_release_id_step_index_fkey`: `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)`.
- `pedagogy.solution_step_instruction` / `solution_step_instruction_route_release_id_step_index_fkey`: `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)`.
- `pedagogy.solution_step_requirement` / `solution_step_requirement_route_release_id_step_index_fkey`: `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_step_pkey`: `CREATE UNIQUE INDEX route_step_pkey ON pedagogy.route_step USING btree (route_release_id, step_index)`; valid=True, ready=True.
- `route_step_step_id_key`: `CREATE UNIQUE INDEX route_step_step_id_key ON pedagogy.route_step USING btree (step_id)`; valid=True, ready=True.

**Triggers:**

- `immutable_route_snapshot`: `CREATE TRIGGER immutable_route_snapshot BEFORE INSERT OR DELETE OR UPDATE ON pedagogy.route_step FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_snapshot()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.route_step_hint`

**Kind / use case:** table. Precomputed H1-H4 and H5 current-step reveal, scoped by immutable release/step/variant/misconception.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L74); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L79); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L361).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_release_id` | `uuid` | no | `-` | `- / -` |
| `step_index` | `integer` | no | `-` | `- / -` |
| `hint_level` | `integer` | no | `-` | `- / -` |
| `hint_variant` | `text` | no | `'default'::text` | `- / -` |
| `misconception_key` | `text` | no | `''::text` | `- / -` |
| `content_hash` | `text` | no | `-` | `- / -` |
| `hint_text` | `text` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `route_step_hint_content_hash_not_null` / `n` | `NOT NULL content_hash` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_hint_level_check` / `c` | `CHECK (hint_level >= 1 AND hint_level <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_hint_level_not_null` / `n` | `NOT NULL hint_level` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_hint_text_not_null` / `n` | `NOT NULL hint_text` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_hint_variant_not_null` / `n` | `NOT NULL hint_variant` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_misconception_key_not_null` / `n` | `NOT NULL misconception_key` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_pkey` / `p` | `PRIMARY KEY (route_release_id, step_index, hint_level, hint_variant, misconception_key)` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_route_release_id_step_index_fkey` / `f` | `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)` | deferrable=False, initially deferred=False, validated=True |
| `route_step_hint_step_index_not_null` / `n` | `NOT NULL step_index` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_step_hint_pkey`: `CREATE UNIQUE INDEX route_step_hint_pkey ON pedagogy.route_step_hint USING btree (route_release_id, step_index, hint_level, hint_variant, misconception_key)`; valid=True, ready=True.

**Triggers:**

- `immutable_route_snapshot`: `CREATE TRIGGER immutable_route_snapshot BEFORE INSERT OR DELETE OR UPDATE ON pedagogy.route_step_hint FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_snapshot()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_dag_review`

**Kind / use case:** table. Admin approval/needs-revision record for an imported solution DAG.

**Migration owner:** [019_admin_import_review.sql](../../../mathbank-db/sql/019_admin_import_review.sql#L44); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L300).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `status` | `text` | no | `-` | `- / -` |
| `note` | `text` | yes | `-` | `- / -` |
| `reviewed_by` | `text` | no | `'admin'::text` | `- / -` |
| `reviewed_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_dag_review_pkey` / `p` | `PRIMARY KEY (solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_reviewed_at_not_null` / `n` | `NOT NULL reviewed_at` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_reviewed_by_not_null` / `n` | `NOT NULL reviewed_by` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_status_check` / `c` | `CHECK (status = ANY (ARRAY['APPROVED'::text, 'NEEDS_REVISION'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solution_dag_review_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_dag_review_pkey`: `CREATE UNIQUE INDEX solution_dag_review_pkey ON pedagogy.solution_dag_review USING btree (solution_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_part`

**Kind / use case:** table. Ordered reference-solution grouping with stable source/occurrence identity.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L220); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L268); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L338); [mathbank-rest/src/mathbank_rest/step_tutor.py](../../../mathbank-rest/src/mathbank_rest/step_tutor.py#L206); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L72); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L1004); [mathbank-graph/etl/project_textbook_steps.py](../../../mathbank-graph/etl/project_textbook_steps.py#L76).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_part_id` | `text` | no | `-` | `- / -` |
| `source_part_id` | `text` | no | `-` | `- / -` |
| `occurrence` | `integer` | no | `1` | `- / -` |
| `book_code` | `text` | no | `-` | `- / -` |
| `solution_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `part_label` | `text` | yes | `-` | `- / -` |
| `part_ordinal` | `integer` | no | `-` | `- / -` |
| `step_count` | `integer` | no | `-` | `- / -` |
| `source_step_count` | `integer` | yes | `-` | `- / -` |
| `source_page` | `integer` | yes | `-` | `- / -` |
| `part_text_normalized` | `text` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_part_book_code_fkey` / `f` | `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_book_code_source_part_id_occurrence_key` / `u` | `UNIQUE (book_code, source_part_id, occurrence)` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_occurrence_not_null` / `n` | `NOT NULL occurrence` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_part_ordinal_not_null` / `n` | `NOT NULL part_ordinal` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_pkey` / `p` | `PRIMARY KEY (solution_part_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_solution_part_id_not_null` / `n` | `NOT NULL solution_part_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_source_part_id_not_null` / `n` | `NOT NULL source_part_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_step_count_not_null` / `n` | `NOT NULL step_count` | deferrable=False, initially deferred=False, validated=True |
| `solution_part_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `learner.solve_attempt` / `solve_attempt_current_solution_part_id_fkey`: `FOREIGN KEY (current_solution_part_id) REFERENCES pedagogy.solution_part(solution_part_id)`.
- `pedagogy.solution_step` / `solution_step_solution_part_id_fkey`: `FOREIGN KEY (solution_part_id) REFERENCES pedagogy.solution_part(solution_part_id) ON DELETE CASCADE`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_part_book_code_source_part_id_occurrence_key`: `CREATE UNIQUE INDEX solution_part_book_code_source_part_id_occurrence_key ON pedagogy.solution_part USING btree (book_code, source_part_id, occurrence)`; valid=True, ready=True.
- `solution_part_pkey`: `CREATE UNIQUE INDEX solution_part_pkey ON pedagogy.solution_part USING btree (solution_part_id)`; valid=True, ready=True.
- `solution_part_problem_idx`: `CREATE INDEX solution_part_problem_idx ON pedagogy.solution_part USING btree (problem_id, part_ordinal)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_route_release`

**Kind / use case:** table. Solution-owned versioned teaching route; source/content hashes and separate review/publication lifecycle.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L12); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L19); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L45); [mathbank-rest/src/mathbank_rest/route_projection.py](../../../mathbank-rest/src/mathbank_rest/route_projection.py#L33); [mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py](../../../mathbank-rest/src/mathbank_rest/routers/tutoring_routes.py#L74).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_release_id` | `uuid` | no | `gen_random_uuid()` | `- / -` |
| `solution_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `release_version` | `integer` | no | `-` | `- / -` |
| `source_hash` | `text` | no | `-` | `- / -` |
| `content_hash` | `text` | no | `-` | `- / -` |
| `approach_name` | `text` | no | `-` | `- / -` |
| `approach_summary` | `text` | no | `-` | `- / -` |
| `difficulty_level` | `integer` | no | `-` | `- / -` |
| `conceptual_load` | `integer` | no | `-` | `- / -` |
| `algebraic_load` | `integer` | no | `-` | `- / -` |
| `insight_load` | `integer` | no | `-` | `- / -` |
| `preferred_for_tutoring` | `boolean` | no | `false` | `- / -` |
| `route_quality` | `numeric` | yes | `-` | `- / -` |
| `status` | `text` | no | `'DRAFT'::text` | `- / -` |
| `generator_version` | `text` | no | `-` | `- / -` |
| `reviewed_by` | `text` | yes | `-` | `- / -` |
| `reviewed_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `published_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_route_release_algebraic_load_check` / `c` | `CHECK (algebraic_load >= 1 AND algebraic_load <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_algebraic_load_not_null` / `n` | `NOT NULL algebraic_load` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_approach_name_not_null` / `n` | `NOT NULL approach_name` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_approach_summary_not_null` / `n` | `NOT NULL approach_summary` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_check` / `c` | `CHECK (status = 'DRAFT'::text OR reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_conceptual_load_check` / `c` | `CHECK (conceptual_load >= 1 AND conceptual_load <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_conceptual_load_not_null` / `n` | `NOT NULL conceptual_load` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_content_hash_not_null` / `n` | `NOT NULL content_hash` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_difficulty_level_check` / `c` | `CHECK (difficulty_level >= 1 AND difficulty_level <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_difficulty_level_not_null` / `n` | `NOT NULL difficulty_level` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_generator_version_not_null` / `n` | `NOT NULL generator_version` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_insight_load_check` / `c` | `CHECK (insight_load >= 1 AND insight_load <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_insight_load_not_null` / `n` | `NOT NULL insight_load` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_pkey` / `p` | `PRIMARY KEY (route_release_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_preferred_for_tutoring_not_null` / `n` | `NOT NULL preferred_for_tutoring` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_release_version_check` / `c` | `CHECK (release_version > 0)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_release_version_not_null` / `n` | `NOT NULL release_version` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_route_quality_check` / `c` | `CHECK (route_quality >= 0::numeric AND route_quality <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_solution_id_release_version_key` / `u` | `UNIQUE (solution_id, release_version)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_solution_id_source_hash_generator_ve_key` / `u` | `UNIQUE (solution_id, source_hash, generator_version)` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_source_hash_not_null` / `n` | `NOT NULL source_hash` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_status_check` / `c` | `CHECK (status = ANY (ARRAY['DRAFT'::text, 'REVIEWED'::text, 'PUBLISHED'::text, 'RETIRED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solution_route_release_status_not_null` / `n` | `NOT NULL status` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `learner.route_attempt` / `route_attempt_route_release_id_fkey`: `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)`.
- `pedagogy.route_asset` / `route_asset_route_release_id_fkey`: `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)`.
- `pedagogy.route_compiler_job` / `route_compiler_job_route_release_id_fkey`: `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)`.
- `pedagogy.route_step` / `route_step_route_release_id_fkey`: `FOREIGN KEY (route_release_id) REFERENCES pedagogy.solution_route_release(route_release_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `route_release_problem_status`: `CREATE INDEX route_release_problem_status ON pedagogy.solution_route_release USING btree (problem_id, status)`; valid=True, ready=True.
- `solution_route_release_pkey`: `CREATE UNIQUE INDEX solution_route_release_pkey ON pedagogy.solution_route_release USING btree (route_release_id)`; valid=True, ready=True.
- `solution_route_release_solution_id_release_version_key`: `CREATE UNIQUE INDEX solution_route_release_solution_id_release_version_key ON pedagogy.solution_route_release USING btree (solution_id, release_version)`; valid=True, ready=True.
- `solution_route_release_solution_id_source_hash_generator_ve_key`: `CREATE UNIQUE INDEX solution_route_release_solution_id_source_hash_generator_ve_key ON pedagogy.solution_route_release USING btree (solution_id, source_hash, generator_version)`; valid=True, ready=True.

**Triggers:**

- `immutable_route_release`: `CREATE TRIGGER immutable_route_release BEFORE DELETE OR UPDATE ON pedagogy.solution_route_release FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_release()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_source_ref`

**Kind / use case:** table. Printed solution identity/page linked to canonical solution.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L192); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L63); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L943).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `book_code` | `text` | no | `-` | `- / -` |
| `source_solution_id` | `text` | no | `-` | `- / -` |
| `solution_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `solution_first_step` | `text` | yes | `-` | `- / -` |
| `source_page` | `integer` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_source_ref_book_code_fkey` / `f` | `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_pkey` / `p` | `PRIMARY KEY (book_code, source_solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_solution_id_key` / `u` | `UNIQUE (solution_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_source_ref_source_solution_id_not_null` / `n` | `NOT NULL source_solution_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_source_ref_pkey`: `CREATE UNIQUE INDEX solution_source_ref_pkey ON pedagogy.solution_source_ref USING btree (book_code, source_solution_id)`; valid=True, ready=True.
- `solution_source_ref_solution_id_key`: `CREATE UNIQUE INDEX solution_source_ref_solution_id_key ON pedagogy.solution_source_ref USING btree (solution_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_step`

**Kind / use case:** table. Imported atomic reference moves, hidden step text and ordered learning metadata.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L239); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/attempt_media.py#L390); [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L169); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L183); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L196); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L522); [mathbank-rest/src/mathbank_rest/step_tutor.py](../../../mathbank-rest/src/mathbank_rest/step_tutor.py#L206); [mathbank-rest/src/mathbank_rest/routers/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L552); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L37); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L97); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L73).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `source_step_id` | `text` | no | `-` | `- / -` |
| `occurrence` | `integer` | no | `1` | `- / -` |
| `book_code` | `text` | no | `-` | `- / -` |
| `solution_part_id` | `text` | no | `-` | `- / -` |
| `solution_id` | `uuid` | no | `-` | `- / -` |
| `problem_id` | `uuid` | no | `-` | `- / -` |
| `global_step_index` | `integer` | no | `-` | `- / -` |
| `step_index_in_part` | `integer` | no | `-` | `- / -` |
| `step_text` | `text` | no | `-` | `- / -` |
| `step_type` | `text` | no | `-` | `- / -` |
| `tutor_role` | `text` | yes | `-` | `- / -` |
| `concept_node_id` | `text` | yes | `-` | `- / -` |
| `subconcept_node_id` | `text` | yes | `-` | `- / -` |
| `skill_node_id` | `text` | yes | `-` | `- / -` |
| `skill_name` | `text` | yes | `-` | `- / -` |
| `hint_level` | `smallint` | yes | `-` | `- / -` |
| `is_checkpoint` | `boolean` | no | `false` | `- / -` |
| `source_previous_step_id` | `text` | yes | `-` | `- / -` |
| `source_next_step_id` | `text` | yes | `-` | `- / -` |
| `source_page` | `integer` | yes | `-` | `- / -` |
| `source_metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `publication_status` | `text` | no | `'PUBLISHED'::text` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `admin_edited_at` | `timestamp with time zone` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_step_book_code_fkey` / `f` | `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_book_code_source_step_id_occurrence_key` / `u` | `UNIQUE (book_code, source_step_id, occurrence)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_concept_node_id_fkey` / `f` | `FOREIGN KEY (concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_global_step_index_not_null` / `n` | `NOT NULL global_step_index` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_hint_level_check` / `c` | `CHECK (hint_level >= 1 AND hint_level <= 4)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_is_checkpoint_not_null` / `n` | `NOT NULL is_checkpoint` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_occurrence_not_null` / `n` | `NOT NULL occurrence` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_pkey` / `p` | `PRIMARY KEY (solution_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_problem_id_fkey` / `f` | `FOREIGN KEY (problem_id) REFERENCES core.problem(problem_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_problem_id_global_step_index_key` / `u` | `UNIQUE (problem_id, global_step_index)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_problem_id_not_null` / `n` | `NOT NULL problem_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_publication_status_not_null` / `n` | `NOT NULL publication_status` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_skill_node_id_fkey` / `f` | `FOREIGN KEY (skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_id_fkey` / `f` | `FOREIGN KEY (solution_id) REFERENCES core.solution(solution_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_id_not_null` / `n` | `NOT NULL solution_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_part_id_fkey` / `f` | `FOREIGN KEY (solution_part_id) REFERENCES pedagogy.solution_part(solution_part_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_part_id_not_null` / `n` | `NOT NULL solution_part_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_source_metadata_not_null` / `n` | `NOT NULL source_metadata` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_source_step_id_not_null` / `n` | `NOT NULL source_step_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_step_index_in_part_not_null` / `n` | `NOT NULL step_index_in_part` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_step_text_not_null` / `n` | `NOT NULL step_text` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_step_type_not_null` / `n` | `NOT NULL step_type` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_subconcept_node_id_fkey` / `f` | `FOREIGN KEY (subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `attempt_media.step_assessment` / `step_assessment_canonical_solution_step_id_fkey`: `FOREIGN KEY (canonical_solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `learner.attempt_step_state` / `attempt_step_state_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `learner.event` / `event_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `learner.solve_attempt` / `solve_attempt_current_solution_step_id_fkey`: `FOREIGN KEY (current_solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `pedagogy.gap_diagnosis` / `gap_diagnosis_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `pedagogy.knowledge_gap` / `knowledge_gap_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `pedagogy.knowledge_gap` / `knowledge_gap_source_step_id_fkey`: `FOREIGN KEY (source_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `pedagogy.learning_item_step_anchor` / `learning_item_step_anchor_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE`.
- `pedagogy.recovery_plan` / `recovery_plan_origin_step_id_fkey`: `FOREIGN KEY (origin_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `pedagogy.recovery_plan_item` / `recovery_plan_item_worked_step_id_fkey`: `FOREIGN KEY (worked_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.
- `pedagogy.solution_step_dependency` / `solution_step_dependency_from_step_id_fkey`: `FOREIGN KEY (from_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE`.
- `pedagogy.solution_step_dependency` / `solution_step_dependency_to_step_id_fkey`: `FOREIGN KEY (to_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE`.
- `pedagogy.solution_step_technique` / `solution_step_technique_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE`.
- `pedagogy.solution_step_technique_run` / `solution_step_technique_run_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE`.
- `pedagogy.step_hint` / `step_hint_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE`.
- `search.chunk` / `chunk_solution_step_id_fkey`: `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE`.
- `tutor.runtime_state` / `runtime_state_current_step_id_fkey`: `FOREIGN KEY (current_step_id) REFERENCES pedagogy.solution_step(solution_step_id)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_step_book_code_source_step_id_occurrence_key`: `CREATE UNIQUE INDEX solution_step_book_code_source_step_id_occurrence_key ON pedagogy.solution_step USING btree (book_code, source_step_id, occurrence)`; valid=True, ready=True.
- `solution_step_part_idx`: `CREATE INDEX solution_step_part_idx ON pedagogy.solution_step USING btree (solution_part_id, step_index_in_part)`; valid=True, ready=True.
- `solution_step_pkey`: `CREATE UNIQUE INDEX solution_step_pkey ON pedagogy.solution_step USING btree (solution_step_id)`; valid=True, ready=True.
- `solution_step_problem_id_global_step_index_key`: `CREATE UNIQUE INDEX solution_step_problem_id_global_step_index_key ON pedagogy.solution_step USING btree (problem_id, global_step_index)`; valid=True, ready=True.
- `solution_step_skill_idx`: `CREATE INDEX solution_step_skill_idx ON pedagogy.solution_step USING btree (skill_node_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_step_dependency`

**Kind / use case:** table. Directed solution DAG edges; runtime interprets hard dependencies.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L272); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_runtime.py](../../../mathbank-rest/src/mathbank_rest/step_runtime.py#L174); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L230); [mathbank-rest/src/mathbank_rest/routers/attempt_media.py](../../../mathbank-rest/src/mathbank_rest/routers/attempt_media.py#L567); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L74); [mathbank-rest/src/mathbank_rest/db/import_admin.py](../../../mathbank-rest/src/mathbank_rest/db/import_admin.py#L295); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L1032); [mathbank-graph/etl/project_textbook_steps.py](../../../mathbank-graph/etl/project_textbook_steps.py#L98).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `from_step_id` | `text` | no | `-` | `- / -` |
| `to_step_id` | `text` | no | `-` | `- / -` |
| `relationship_type` | `text` | no | `-` | `- / -` |
| `logical_dependency` | `text` | yes | `-` | `- / -` |
| `confidence` | `numeric` | yes | `-` | `- / -` |
| `source_type` | `text` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'REVIEWED'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `content_package_id` | `uuid` | yes | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_step_dependency_check` / `c` | `CHECK (from_step_id <> to_step_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_confidence_check` / `c` | `CHECK (confidence IS NULL OR confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_from_step_id_fkey` / `f` | `FOREIGN KEY (from_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_from_step_id_not_null` / `n` | `NOT NULL from_step_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_pkey` / `p` | `PRIMARY KEY (from_step_id, to_step_id, relationship_type)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_relationship_type_not_null` / `n` | `NOT NULL relationship_type` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING'::text, 'REVIEWED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_source_type_not_null` / `n` | `NOT NULL source_type` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_to_step_id_fkey` / `f` | `FOREIGN KEY (to_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_dependency_to_step_id_not_null` / `n` | `NOT NULL to_step_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_step_dependency_pkey`: `CREATE UNIQUE INDEX solution_step_dependency_pkey ON pedagogy.solution_step_dependency USING btree (from_step_id, to_step_id, relationship_type)`; valid=True, ready=True.
- `solution_step_dependency_to_idx`: `CREATE INDEX solution_step_dependency_to_idx ON pedagogy.solution_step_dependency USING btree (to_step_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_step_instruction`

**Kind / use case:** table. Private complete goal, student prompt, expected response, recognition, reasoning and current-step explanation snapshot.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L64); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L48); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L348).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_release_id` | `uuid` | no | `-` | `- / -` |
| `step_index` | `integer` | no | `-` | `- / -` |
| `instruction_version` | `integer` | no | `1` | `- / -` |
| `content_hash` | `text` | no | `-` | `- / -` |
| `content` | `jsonb` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_step_instruction_content_hash_not_null` / `n` | `NOT NULL content_hash` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_instruction_content_not_null` / `n` | `NOT NULL content` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_instruction_instruction_version_not_null` / `n` | `NOT NULL instruction_version` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_instruction_pkey` / `p` | `PRIMARY KEY (route_release_id, step_index)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_instruction_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_instruction_route_release_id_step_index_fkey` / `f` | `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_instruction_step_index_not_null` / `n` | `NOT NULL step_index` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_step_instruction_pkey`: `CREATE UNIQUE INDEX solution_step_instruction_pkey ON pedagogy.solution_step_instruction USING btree (route_release_id, step_index)`; valid=True, ready=True.

**Triggers:**

- `immutable_route_snapshot`: `CREATE TRIGGER immutable_route_snapshot BEFORE INSERT OR DELETE OR UPDATE ON pedagogy.solution_step_instruction FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_snapshot()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_step_requirement`

**Kind / use case:** table. Canonical taxonomy prerequisite/use role, level, importance and blocking requirement.

**Migration owner:** [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql#L86); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L60); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L375).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `route_release_id` | `uuid` | no | `-` | `- / -` |
| `step_index` | `integer` | no | `-` | `- / -` |
| `taxonomy_node_id` | `text` | no | `-` | `- / -` |
| `role` | `text` | no | `-` | `- / -` |
| `required_level` | `integer` | no | `-` | `- / -` |
| `importance` | `numeric` | no | `-` | `- / -` |
| `blocking` | `boolean` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_step_requirement_blocking_not_null` / `n` | `NOT NULL blocking` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_importance_check` / `c` | `CHECK (importance >= 0::numeric AND importance <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_importance_not_null` / `n` | `NOT NULL importance` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_pkey` / `p` | `PRIMARY KEY (route_release_id, step_index, taxonomy_node_id, role)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_required_level_check` / `c` | `CHECK (required_level >= 1 AND required_level <= 5)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_required_level_not_null` / `n` | `NOT NULL required_level` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_role_check` / `c` | `CHECK (role = ANY (ARRAY['REQUIRED'::text, 'HELPFUL'::text, 'RECOGNITION'::text, 'EXECUTION'::text, 'JUSTIFICATION'::text, 'USED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_role_not_null` / `n` | `NOT NULL role` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_route_release_id_not_null` / `n` | `NOT NULL route_release_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_route_release_id_step_index_fkey` / `f` | `FOREIGN KEY (route_release_id, step_index) REFERENCES pedagogy.route_step(route_release_id, step_index)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_step_index_not_null` / `n` | `NOT NULL step_index` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_taxonomy_node_id_fkey` / `f` | `FOREIGN KEY (taxonomy_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_requirement_taxonomy_node_id_not_null` / `n` | `NOT NULL taxonomy_node_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_step_requirement_pkey`: `CREATE UNIQUE INDEX solution_step_requirement_pkey ON pedagogy.solution_step_requirement USING btree (route_release_id, step_index, taxonomy_node_id, role)`; valid=True, ready=True.

**Triggers:**

- `immutable_route_snapshot`: `CREATE TRIGGER immutable_route_snapshot BEFORE INSERT OR DELETE OR UPDATE ON pedagogy.solution_step_requirement FOR EACH ROW EXECUTE FUNCTION pedagogy.guard_route_snapshot()`; enabled `O` (O=origin, A=always, R=replica, D=disabled).

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_step_technique`

**Kind / use case:** table. Reviewed step-to-technique evidence bridged through taxonomy.

**Migration owner:** [017_step_techniques.sql](../../../mathbank-db/sql/017_step_techniques.sql#L17); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L261); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L51); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L100); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L82); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L19); [mathbank-rest/src/mathbank_rest/db/retrieval_audit.py](../../../mathbank-rest/src/mathbank_rest/db/retrieval_audit.py#L35); [mathbank-db/etl/derive_step_techniques.py](../../../mathbank-db/etl/derive_step_techniques.py#L4); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L103); [mathbank-graph/etl/project_textbook_steps.py](../../../mathbank-graph/etl/project_textbook_steps.py#L127).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `technique_node_id` | `text` | no | `-` | `- / -` |
| `confidence` | `numeric(3,2)` | no | `-` | `- / -` |
| `source_type` | `text` | no | `-` | `- / -` |
| `evidence` | `text` | yes | `-` | `- / -` |
| `derivation_version` | `text` | no | `-` | `- / -` |
| `review_status` | `text` | no | `'APPROVED'::text` | `- / -` |
| `approval_method` | `text` | yes | `-` | `- / -` |
| `approved_at` | `timestamp with time zone` | yes | `-` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_step_technique_approval_method_check` / `c` | `CHECK (approval_method IS NULL OR (approval_method = ANY (ARRAY['automatic'::text, 'human'::text])))` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_confidence_check` / `c` | `CHECK (confidence >= 0::numeric AND confidence <= 1::numeric)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_confidence_not_null` / `n` | `NOT NULL confidence` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_derivation_version_not_null` / `n` | `NOT NULL derivation_version` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_pkey` / `p` | `PRIMARY KEY (solution_step_id, technique_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_review_status_check` / `c` | `CHECK (review_status = ANY (ARRAY['PENDING_REVIEW'::text, 'APPROVED'::text, 'REJECTED'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_review_status_not_null` / `n` | `NOT NULL review_status` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_source_type_check` / `c` | `CHECK (source_type = ANY (ARRAY['RULE_STEP_TEXT_IN_PROBLEM'::text, 'RULE_STEP_TEXT_NAMED'::text, 'RULE_STEP_FORMULA'::text, 'LLM'::text, 'RUNTIME'::text, 'HUMAN'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_source_type_not_null` / `n` | `NOT NULL source_type` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_technique_node_id_fkey` / `f` | `FOREIGN KEY (technique_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_technique_node_id_not_null` / `n` | `NOT NULL technique_node_id` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_step_technique_pkey`: `CREATE UNIQUE INDEX solution_step_technique_pkey ON pedagogy.solution_step_technique USING btree (solution_step_id, technique_node_id)`; valid=True, ready=True.
- `solution_step_technique_technique_idx`: `CREATE INDEX solution_step_technique_technique_idx ON pedagogy.solution_step_technique USING btree (technique_node_id) WHERE (review_status = 'APPROVED'::text)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.solution_step_technique_run`

**Kind / use case:** table. Technique derivation execution provenance and status.

**Migration owner:** [017_step_techniques.sql](../../../mathbank-db/sql/017_step_techniques.sql#L40); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-db/etl/derive_step_techniques.py](../../../mathbank-db/etl/derive_step_techniques.py#L168).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `derivation_version` | `text` | no | `-` | `- / -` |
| `outcome` | `text` | no | `-` | `- / -` |
| `candidate_ids` | `text[]` | no | `'{}'::text[]` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `solution_step_technique_run_candidate_ids_not_null` / `n` | `NOT NULL candidate_ids` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_run_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_run_derivation_version_not_null` / `n` | `NOT NULL derivation_version` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_run_outcome_check` / `c` | `CHECK (outcome = ANY (ARRAY['TAGGED'::text, 'NO_MATCH'::text, 'NO_PROBLEM_TECHNIQUE'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_run_outcome_not_null` / `n` | `NOT NULL outcome` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_run_pkey` / `p` | `PRIMARY KEY (solution_step_id, derivation_version)` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_run_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `solution_step_technique_run_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `solution_step_technique_run_pkey`: `CREATE UNIQUE INDEX solution_step_technique_run_pkey ON pedagogy.solution_step_technique_run USING btree (solution_step_id, derivation_version)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.source_book`

**Kind / use case:** table. Imported book identity and package/source metadata.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L118); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/problem_sources.py](../../../mathbank-rest/src/mathbank_rest/db/problem_sources.py#L26); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L875).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `book_code` | `text` | no | `-` | `- / -` |
| `external_book_id` | `text` | no | `-` | `- / -` |
| `title` | `text` | no | `-` | `- / -` |
| `author` | `text` | yes | `-` | `- / -` |
| `translator_editor` | `text` | yes | `-` | `- / -` |
| `source_file` | `text` | yes | `-` | `- / -` |
| `competition_id` | `uuid` | yes | `-` | `- / -` |
| `edition_id` | `uuid` | yes | `-` | `- / -` |
| `metadata` | `jsonb` | no | `'{}'::jsonb` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `source_book_book_code_not_null` / `n` | `NOT NULL book_code` | deferrable=False, initially deferred=False, validated=True |
| `source_book_competition_id_fkey` / `f` | `FOREIGN KEY (competition_id) REFERENCES core.competition(competition_id)` | deferrable=False, initially deferred=False, validated=True |
| `source_book_edition_id_fkey` / `f` | `FOREIGN KEY (edition_id) REFERENCES core.competition_edition(edition_id)` | deferrable=False, initially deferred=False, validated=True |
| `source_book_external_book_id_key` / `u` | `UNIQUE (external_book_id)` | deferrable=False, initially deferred=False, validated=True |
| `source_book_external_book_id_not_null` / `n` | `NOT NULL external_book_id` | deferrable=False, initially deferred=False, validated=True |
| `source_book_metadata_not_null` / `n` | `NOT NULL metadata` | deferrable=False, initially deferred=False, validated=True |
| `source_book_pkey` / `p` | `PRIMARY KEY (book_code)` | deferrable=False, initially deferred=False, validated=True |
| `source_book_title_not_null` / `n` | `NOT NULL title` | deferrable=False, initially deferred=False, validated=True |
| `source_book_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.chapter_section` / `chapter_section_book_code_fkey`: `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)`.
- `pedagogy.diagram` / `diagram_book_code_fkey`: `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)`.
- `pedagogy.learning_item` / `learning_item_book_code_fkey`: `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)`.
- `pedagogy.problem_source_ref` / `problem_source_ref_book_code_fkey`: `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)`.
- `pedagogy.solution_part` / `solution_part_book_code_fkey`: `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)`.
- `pedagogy.solution_source_ref` / `solution_source_ref_book_code_fkey`: `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)`.
- `pedagogy.solution_step` / `solution_step_book_code_fkey`: `FOREIGN KEY (book_code) REFERENCES pedagogy.source_book(book_code)`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `source_book_external_book_id_key`: `CREATE UNIQUE INDEX source_book_external_book_id_key ON pedagogy.source_book USING btree (external_book_id)`; valid=True, ready=True.
- `source_book_pkey`: `CREATE UNIQUE INDEX source_book_pkey ON pedagogy.source_book USING btree (book_code)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.step_hint`

**Kind / use case:** table. Durable shared hint cache keyed by step, level and prompt version.

**Migration owner:** [013_step_hints.sql](../../../mathbank-db/sql/013_step_hints.sql#L11); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/step_tutor.py](../../../mathbank-rest/src/mathbank_rest/step_tutor.py#L229).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `solution_step_id` | `text` | no | `-` | `- / -` |
| `hint_level` | `integer` | no | `-` | `- / -` |
| `prompt_version` | `text` | no | `-` | `- / -` |
| `hint_text` | `text` | no | `-` | `- / -` |
| `model` | `text` | no | `-` | `- / -` |
| `leak_checked` | `boolean` | no | `true` | `- / -` |
| `created_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `step_hint_created_at_not_null` / `n` | `NOT NULL created_at` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_hint_level_check` / `c` | `CHECK (hint_level >= 1 AND hint_level <= 4)` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_hint_level_not_null` / `n` | `NOT NULL hint_level` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_hint_text_check` / `c` | `CHECK (length(hint_text) > 0)` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_hint_text_not_null` / `n` | `NOT NULL hint_text` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_leak_checked_not_null` / `n` | `NOT NULL leak_checked` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_model_not_null` / `n` | `NOT NULL model` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_pkey` / `p` | `PRIMARY KEY (solution_step_id, hint_level, prompt_version)` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_prompt_version_not_null` / `n` | `NOT NULL prompt_version` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_solution_step_id_fkey` / `f` | `FOREIGN KEY (solution_step_id) REFERENCES pedagogy.solution_step(solution_step_id) ON DELETE CASCADE` | deferrable=False, initially deferred=False, validated=True |
| `step_hint_solution_step_id_not_null` / `n` | `NOT NULL solution_step_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `step_hint_pkey`: `CREATE UNIQUE INDEX step_hint_pkey ON pedagogy.step_hint USING btree (solution_step_id, hint_level, prompt_version)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.taxonomy_edge`

**Kind / use case:** table. Package-authored taxonomy relations and provenance.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L159); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L142); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L69); [mathbank-db/etl/import_textbook_package.py](../../../mathbank-db/etl/import_textbook_package.py#L835); [mathbank-db/etl/embed_textbook_steps.py](../../../mathbank-db/etl/embed_textbook_steps.py#L203).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `from_node_id` | `text` | no | `-` | `- / -` |
| `to_node_id` | `text` | no | `-` | `- / -` |
| `relationship_type` | `text` | no | `-` | `- / -` |
| `source_basis` | `text` | yes | `-` | `- / -` |
| `confidence` | `numeric` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `taxonomy_edge_check` / `c` | `CHECK (from_node_id <> to_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_from_node_id_fkey` / `f` | `FOREIGN KEY (from_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_from_node_id_not_null` / `n` | `NOT NULL from_node_id` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_pkey` / `p` | `PRIMARY KEY (from_node_id, to_node_id, relationship_type)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_relationship_type_not_null` / `n` | `NOT NULL relationship_type` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_to_node_id_fkey` / `f` | `FOREIGN KEY (to_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_edge_to_node_id_not_null` / `n` | `NOT NULL to_node_id` | deferrable=False, initially deferred=False, validated=True |

**Indexes** (including constraint-backed indexes and partial predicates):

- `taxonomy_edge_pkey`: `CREATE UNIQUE INDEX taxonomy_edge_pkey ON pedagogy.taxonomy_edge USING btree (from_node_id, to_node_id, relationship_type)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

### `pedagogy.taxonomy_node`

**Kind / use case:** table. Text-ID package taxonomy plus UUID bridges to knowledge nodes.

**Migration owner:** [010_textbook_import.sql](../../../mathbank-db/sql/010_textbook_import.sql#L142); subsequent ALTERs may change the catalog below.

**Direct source access evidence:** [mathbank-rest/src/mathbank_rest/enrichment.py](../../../mathbank-rest/src/mathbank_rest/enrichment.py#L379); [mathbank-rest/src/mathbank_rest/step_recovery.py](../../../mathbank-rest/src/mathbank_rest/step_recovery.py#L183); [mathbank-rest/src/mathbank_rest/step_diagnosis.py](../../../mathbank-rest/src/mathbank_rest/step_diagnosis.py#L209); [mathbank-rest/src/mathbank_rest/route_runtime.py](../../../mathbank-rest/src/mathbank_rest/route_runtime.py#L231); [mathbank-rest/src/mathbank_rest/route_compiler.py](../../../mathbank-rest/src/mathbank_rest/route_compiler.py#L33); [mathbank-rest/src/mathbank_rest/route_projection.py](../../../mathbank-rest/src/mathbank_rest/route_projection.py#L44); [mathbank-rest/src/mathbank_rest/db/step_search.py](../../../mathbank-rest/src/mathbank_rest/db/step_search.py#L82); [mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py](../../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py#L31); [mathbank-rest/src/mathbank_rest/db/textbook_admin.py](../../../mathbank-rest/src/mathbank_rest/db/textbook_admin.py#L67); [mathbank-rest/src/mathbank_rest/db/queries.py](../../../mathbank-rest/src/mathbank_rest/db/queries.py#L21).

These are literal table references, not proof that every endpoint in the schema's access family reads this relation.
Reads/writes and authorization are enforced in those callers, not inferred from SQL grants.

**Row-level security:** enabled `False`, forced `False`. Application ownership checks remain necessary regardless of this flag.

| Column | PostgreSQL type | Nullable | Default | Identity / generated |
|---|---|---|---|---|
| `taxonomy_node_id` | `text` | no | `-` | `- / -` |
| `node_type` | `text` | no | `-` | `- / -` |
| `name` | `text` | no | `-` | `- / -` |
| `parent_node_id` | `text` | yes | `-` | `- / -` |
| `chapter_number` | `integer` | yes | `-` | `- / -` |
| `section_number` | `text` | yes | `-` | `- / -` |
| `source_basis` | `text` | yes | `-` | `- / -` |
| `description` | `text` | yes | `-` | `- / -` |
| `concept_id` | `uuid` | yes | `-` | `- / -` |
| `skill_id` | `uuid` | yes | `-` | `- / -` |
| `technique_id` | `uuid` | yes | `-` | `- / -` |
| `content_package_id` | `uuid` | no | `-` | `- / -` |
| `updated_at` | `timestamp with time zone` | no | `now()` | `- / -` |

**Constraints** (PK, unique, check, FK; default FK action omitted by PostgreSQL means NO ACTION):

| Name / kind | Definition | Deferred / validated |
|---|---|---|
| `taxonomy_node_check` / `c` | `CHECK (num_nonnulls(concept_id, skill_id, technique_id) <= 1)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_concept_id_fkey` / `f` | `FOREIGN KEY (concept_id) REFERENCES knowledge.concept(concept_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_content_package_id_fkey` / `f` | `FOREIGN KEY (content_package_id) REFERENCES ingest.content_package(content_package_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_content_package_id_not_null` / `n` | `NOT NULL content_package_id` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_name_not_null` / `n` | `NOT NULL name` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_node_type_check` / `c` | `CHECK (node_type = ANY (ARRAY['DOMAIN'::text, 'CONCEPT'::text, 'SUBCONCEPT'::text, 'SKILL'::text, 'TECHNIQUE'::text]))` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_node_type_not_null` / `n` | `NOT NULL node_type` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_pkey` / `p` | `PRIMARY KEY (taxonomy_node_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_skill_id_fkey` / `f` | `FOREIGN KEY (skill_id) REFERENCES knowledge.skill(skill_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_taxonomy_node_id_not_null` / `n` | `NOT NULL taxonomy_node_id` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_technique_id_fkey` / `f` | `FOREIGN KEY (technique_id) REFERENCES knowledge.technique(technique_id)` | deferrable=False, initially deferred=False, validated=True |
| `taxonomy_node_updated_at_not_null` / `n` | `NOT NULL updated_at` | deferrable=False, initially deferred=False, validated=True |

**Incoming foreign keys:**

- `pedagogy.learning_item` / `learning_item_target_concept_node_id_fkey`: `FOREIGN KEY (target_concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.learning_item` / `learning_item_target_skill_node_id_fkey`: `FOREIGN KEY (target_skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.learning_item` / `learning_item_target_subconcept_node_id_fkey`: `FOREIGN KEY (target_subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.problem_enrichment` / `problem_enrichment_concept_node_id_fkey`: `FOREIGN KEY (concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.problem_enrichment` / `problem_enrichment_primary_skill_node_id_fkey`: `FOREIGN KEY (primary_skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.problem_enrichment` / `problem_enrichment_subconcept_node_id_fkey`: `FOREIGN KEY (subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.solution_step` / `solution_step_concept_node_id_fkey`: `FOREIGN KEY (concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.solution_step` / `solution_step_skill_node_id_fkey`: `FOREIGN KEY (skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.solution_step` / `solution_step_subconcept_node_id_fkey`: `FOREIGN KEY (subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.solution_step_requirement` / `solution_step_requirement_taxonomy_node_id_fkey`: `FOREIGN KEY (taxonomy_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.solution_step_technique` / `solution_step_technique_technique_node_id_fkey`: `FOREIGN KEY (technique_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.taxonomy_edge` / `taxonomy_edge_from_node_id_fkey`: `FOREIGN KEY (from_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `pedagogy.taxonomy_edge` / `taxonomy_edge_to_node_id_fkey`: `FOREIGN KEY (to_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id)`.
- `search.chunk` / `chunk_concept_node_id_fkey`: `FOREIGN KEY (concept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE SET NULL`.
- `search.chunk` / `chunk_skill_node_id_fkey`: `FOREIGN KEY (skill_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE SET NULL`.
- `search.chunk` / `chunk_subconcept_node_id_fkey`: `FOREIGN KEY (subconcept_node_id) REFERENCES pedagogy.taxonomy_node(taxonomy_node_id) ON DELETE SET NULL`.

**Indexes** (including constraint-backed indexes and partial predicates):

- `taxonomy_node_pkey`: `CREATE UNIQUE INDEX taxonomy_node_pkey ON pedagogy.taxonomy_node USING btree (taxonomy_node_id)`; valid=True, ready=True.

**Triggers:**

No user-defined triggers observed.

**Visible grants:** current runtime role: DELETE (grantable=YES); current runtime role: INSERT (grantable=YES); current runtime role: REFERENCES (grantable=YES); current runtime role: SELECT (grantable=YES); current runtime role: TRIGGER (grantable=YES); current runtime role: TRUNCATE (grantable=YES); current runtime role: UPDATE (grantable=YES).
Role identities are intentionally not exported; this is not a full cluster-role/grant audit.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `guard_route_release(-)` | `trigger` | plpgsql / v | False | [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql) |
| `guard_route_snapshot(-)` | `trigger` | plpgsql / v | False | [026_tutoring_routes.sql](../../../mathbank-db/sql/026_tutoring_routes.sql) |

### Observed definition: `pedagogy.guard_route_release`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION pedagogy.guard_route_release()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    IF TG_OP = 'DELETE' AND OLD.status <> 'DRAFT' THEN
        RAISE EXCEPTION 'Reviewed releases cannot be deleted';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status <> 'DRAFT' THEN
        IF (to_jsonb(NEW) - ARRAY['status','published_at']) IS DISTINCT FROM
           (to_jsonb(OLD) - ARRAY['status','published_at']) THEN
            RAISE EXCEPTION 'Reviewed route metadata is immutable';
        END IF;
        IF NOT ((OLD.status = 'REVIEWED' AND NEW.status = 'PUBLISHED') OR
                (OLD.status = 'PUBLISHED' AND NEW.status = 'RETIRED')) THEN
            RAISE EXCEPTION 'Invalid reviewed route lifecycle transition';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.status = 'DRAFT' AND NEW.status NOT IN ('DRAFT','REVIEWED') THEN
        RAISE EXCEPTION 'Draft releases require review before publication';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $function$
```

### Observed definition: `pedagogy.guard_route_snapshot`

Screened catalog definition; metadata only, never executed by this refresh.

```sql
CREATE OR REPLACE FUNCTION pedagogy.guard_route_snapshot()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE release_status text;
BEGIN
    IF TG_OP = 'UPDATE' THEN
        SELECT status INTO release_status FROM pedagogy.solution_route_release
            WHERE route_release_id = OLD.route_release_id FOR SHARE;
        IF release_status IS DISTINCT FROM 'DRAFT' THEN
            RAISE EXCEPTION 'Reviewed route snapshots cannot be moved to a draft';
        END IF;
    END IF;
    SELECT status INTO release_status FROM pedagogy.solution_route_release
        WHERE route_release_id = COALESCE(NEW.route_release_id, OLD.route_release_id) FOR SHARE;
    IF release_status IS DISTINCT FROM 'DRAFT' THEN
        RAISE EXCEPTION 'Reviewed route snapshots are immutable; create a new release';
    END IF;
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END $function$
```
