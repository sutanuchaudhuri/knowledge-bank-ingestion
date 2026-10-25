# 66A. PostgreSQL table-by-table AWS placement assessment

## Scope and evidence

Companion to [report 66](66_AWS_STORAGE_DATABASE_COST_AND_MIGRATION_REPORT.md).
**Design assessment, 2026-10-25; not a migration or live database audit.**
Baseline `a0041e2bc53818b9d06e67d836a5b6d701872fb0`.

The inventory reconciles literal `CREATE TABLE` declarations, after removing SQL
comments, in all 52 numbered [root migrations](../../mathbank-db/sql/) and the
[packaged geometry migration](../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql),
against table-kind entries in the [dated catalog](reference/postgres/README.md).
The root SQL directory also contains a database/role bootstrap file; it declares
no tables and is not a 53rd numbered migration.
It names **209 source-defined tables**: 205 root and four packaged tables, with
no overlapping identities. The catalog observed **143 tables on 2026-10-08**:
129 overlap source and 14 are framework/provider-owned additions. The union
below is **223 distinct tables**. The other 80 source-defined tables are not
thereby certified applied, absent today, populated or unused.

Views, sequences, indexes, functions and extensions are not counted as tables.
No application relations were observed in `auth` or `public`; extension and
authentication compatibility still matter for an Aurora restore. This is a
placement register, not a second column/constraint catalog. Consult the linked
DDL and [schema reference](reference/POSTGRES_SCHEMA.md) for exact structures;
obtain an authorized current catalog before executing a migration.

### Decision codes and cost interpretation

| Code | Recommended authority / possible offload | Cost and migration implication |
|---|---|---|
| K | Keep relational authority in PostgreSQL, including an evaluated Aurora target. | Joins, FK/uniqueness, review, grading, ownership or transactional consistency outweigh a speculative small storage saving. DynamoDB requires aggregate/access-pattern redesign, not copying rows. |
| O | Keep relational identity/metadata; put eligible large bytes in private ordinary S3. | Reduces TOAST/backup/transfer pressure only if large inline payloads exist. Existing object keys already externalize some bytes; do not count them twice. Include GET/PUT/KMS/lifecycle/restore cost. |
| V | Derived vector bytes/index are S3 Vectors candidates; retain source lineage/model/eligibility control. | Potential ANN storage/memory reduction; include query processing, index rewrites, recall/filter tests and workers. Not a DynamoDB vector-search replacement. |
| D | Derived copy may use DynamoDB or the S3 analytics lake; retain authoritative source and replay. | Fast keyed views/rollups, not arbitrary joins. Include consumer idempotency, GSIs, reads/writes and deletion propagation; a copy alone does not lower the SQL bill. |
| A | Isolated authoritative DynamoDB aggregate is a plausible pilot, not approved cutover. | Rewrite ownership/lease/status/access APIs; preserve required dependencies and audit. Only useful if measured SQL cost falls or the operational benefit justifies another store. |
| F | Framework/provider-owned; do not migrate with application table tooling. | Supported session-store adapter or explicit identity-provider migration required; credential/session continuity and integration costs dominate table bytes. |

Combined codes preserve the first stated authoritative boundary: `K/O`, for
example, never means move an entire relational row into an opaque object.
No per-table dollar saving is defensible without table/index sizes, update
rates, item distributions, query access patterns and actual provider bills.
The final column identifies the dependency or dominant cost driver to measure.

## 1. Corpus and pipeline

Sources: [001](../../mathbank-db/sql/001_schema.sql),
[012](../../mathbank-db/sql/012_step_runtime.sql),
[018](../../mathbank-db/sql/018_outbox_consumers.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `core.competition` | K | Small shared reference catalog; contest joins and natural-key uniqueness. |
| `core.competition_edition` | K | Contest/year identity and paper FK joins; little likely storage saving. |
| `core.paper` | K | Edition membership, authored/imported identities and problem uniqueness. |
| `core.problem` | K | Canonical statement/answer/publication state; admin edits invalidate dependent search and releases. |
| `core.problem_image` | K/O | Keep source/side/ordinal and disclosure metadata; externalize image bytes only if not already object-backed. |
| `core.solution` | K | Revisioned answers and verification; never put unrestricted solutions beside public question chunks. |
| `core.solution_step` | K | Canonical solution ordinal/FK structure; distinct from imported and released route steps. |
| `pipeline.run` | K/O | ETL accounting and references; archive large historical metrics/logs, not current job authority. |
| `pipeline.work_item` | K/D | Retry/source status coordinated with ETL; keyed status projection possible, wholesale move needs new leases. |
| `pipeline.graph_projection` | K/O | Projection completion/watermarks must survive partial rebuilds; archive old detailed logs. |
| `pipeline.pdf_source` | K/O | Source identity, provenance and completion; PDFs belong in private S3, not DynamoDB items. |
| `pipeline.outbox_event` | K/O | Must commit with canonical business mutation; archive retained payloads only after durable delivery/accounting. |
| `pipeline.outbox_consumption` | K | Consumer deduplication with resulting SQL mutation; moving independently breaks atomicity. |
| `pipeline.projection_request` | K/D | Pending scopes and source outbox references; DynamoDB status copy is not authoritative acknowledgement. |

## 2. Search

Sources: [002](../../mathbank-db/sql/002_vector_schema.sql),
[011](../../mathbank-db/sql/011_step_vector_metadata.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `search.embedding_model` | K | Provider/revision/dimension/ACTIVE configuration; tiny control catalog, not vector bytes. |
| `search.preprocessing_profile` | K | Immutable chunk/render configuration and code revision; rebuild lineage. |
| `search.representation` | K/O | Current rendered text/hash and source eligibility; cold historical large text can be object-backed after reader changes. |
| `search.chunk` | K | Canonical step/item FK filters and generated full-text index; S3 metadata is not a replacement for these joins. |
| `search.embedding` | V | Bulk vector/index offload candidate; keep chunk/model mapping, hashes and projection watermarks. |
| `search.embedding_job` | K/D | Input-hash uniqueness and representation/run coupling; status projection possible, lease redesign required for authority. |
| `search.retrieval_profile` | K | Versioned ranking/filter configuration; moving a small catalog adds request/API work without meaningful relief. |

## 3. Knowledge catalogs, approvals and enrichment

Sources: [001](../../mathbank-db/sql/001_schema.sql),
[006](../../mathbank-db/sql/006_pedagogy.sql),
[007](../../mathbank-db/sql/007_pedagogy_review.sql),
[008](../../mathbank-db/sql/008_automatic_metadata.sql),
[009](../../mathbank-db/sql/009_relationship_enrichment.sql),
[032](../../mathbank-db/sql/032_micro_course_platform.sql),
[036](../../mathbank-db/sql/036_taxonomy_admin_crud.sql),
[039](../../mathbank-db/sql/039_misconception_catalog.sql),
[040](../../mathbank-db/sql/040_similarity_embeddings.sql),
[046](../../mathbank-db/sql/046_theorem_catalog.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `knowledge.concept` | K | Curated taxonomy identity; aliases, approvals and graph references. |
| `knowledge.technique` | K | Curated technique identity and pedagogic joins. |
| `knowledge.problem_concept` | K | Approved source classification; FK ownership and review matter more than row size. |
| `knowledge.problem_technique` | K | Source problem/technique edges; DynamoDB would need reverse access indexes. |
| `knowledge.concept_relation` | K/D | Keep reviewed relation authority; derived bounded adjacency may be keyed separately. |
| `knowledge.skill` | K | Curated skill taxonomy, not interchangeable with every taxonomy-node row. |
| `knowledge.skill_concept` | K | Shared classification joins; both-direction DynamoDB reads require extra indexes/copies. |
| `knowledge.skill_relation` | K/D | Approved prerequisite/related semantics; a derived adjacency list is feasible. |
| `knowledge.problem_skill` | K | Role-specific classification including PRACTICES/TESTS; publication and analytics joins. |
| `knowledge.problem_pedagogy` | K/O | Canonical metadata/review coupling; externalize large historical proposal bodies only with traceability. |
| `knowledge.pedagogy_review_event` | K/O | Review history must match publication; archive cold snapshots without losing evidence. |
| `knowledge.pedagogy_publication` | K | Publication boundary must be checked immediately after retrieval. |
| `knowledge.metadata_approval_event` | K/O | Before/after decision evidence; size reduction via cold snapshots, not an uncoordinated audit writer. |
| `knowledge.enrichment_job` | K/D | Problem-keyed jobs are coupled to canonical updates; derived status is easy, authoritative migration is not free. |
| `knowledge.relationship_enrichment_job` | K/D | Anchor/input-hash/evidence/publication coordination; replay and stale-result rejection required. |
| `knowledge.misconception` | K | Curated catalog with review status; preserve deduplication and canonical links. |
| `knowledge.entity_alias` | K | Identity resolution/uniqueness for admin edits and reimports. |
| `knowledge.misconception_taxonomy_link` | K | Curated evidence-linked taxonomy membership; retain FK semantics. |
| `knowledge.route_asset_misconception_link` | K | Canonical dedup link from route assets; do not recreate per-checkpoint duplicates. |
| `knowledge.misconception_embedding` | V | Good initial public-derived vector shadow workload; measure batch similarity rebuilds too. |
| `knowledge.misconception_similarity` | K/D | Rebuildable neighbor pairs can be lake/adjacency copies; not approved prerequisite relationships. |
| `knowledge.theorem` | K | Reviewed theorem/axiom/lemma identity and statement; not model-generated publication authority. |
| `knowledge.theorem_relation` | K/D | Approved theorem links; alternative graph is a derived representation. |
| `knowledge.technique_theorem` | K | Relational evidence links used by content/route consumers. |
| `knowledge.theorem_taxonomy_link` | K | Curated membership and FK validation. |
| `knowledge.theorem_asset` | K/O | Keep disclosure, provenance and asset linkage; large asset bytes may be S3-backed. |
| `knowledge.theorem_embedding` | V | Derived vector family; verify producer/consumer usage before estimating savings. |
| `knowledge.theorem_similarity` | K/D | Neighbor-score projection; compare adjacency/key lookup cost with current SQL index. |
| `knowledge.theorem_source` | K/O | Citation/rights/source identity; source documents can live in S3. |

## 4. Ingestion and authoring

Sources: [010](../../mathbank-db/sql/010_textbook_import.sql),
[019](../../mathbank-db/sql/019_admin_import_review.sql),
[020](../../mathbank-db/sql/020_live_fluid_platform.sql),
[025](../../mathbank-db/sql/025_corpus_authoring.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `ingest.content_package` | K/O | Review/import aggregate; immutable manifest and package bytes in S3, SQL identity/status retained. |
| `ingest.package_status_event` | K/O | Import state history/reconciliation; cold details can be archived with manifest references. |
| `ingest.package_file` | K/O | File/hash/package membership; bytes in S3, references stay relational. |
| `ingest.staging_row` | K/O | Validation/conflict joins and promoted-row accounting; archive settled large raw rows. |
| `ingest.import_conflict` | K | Human reconciliation and canonical source links; avoid eventual conflict-resolution authority. |
| `ingest.reconciliation` | K | Counts, decisions and import transaction acceptance. |
| `ingest.admin_review_action` | K/O | Attributable review history tied to import state; archive only under retention policy. |
| `ingest.corpus_draft` | K/O | Existing private drafts/base hashes/decisions; S3 payload references must preserve revision and CAS. |
| `authoring.presentation_plan` | K | Plan/version/publication aggregate; multi-table topic/patch consistency. |
| `authoring.plan_topic` | K | Ordered topic membership with plan references. |
| `authoring.chat_session` | K/O | Staff authoring context/ownership; externalize cold transcripts only through authorized readers. |
| `authoring.proposed_patch` | K/O | Human approval and source-hash binding; large proposed bodies can be S3-backed. |
| `authoring.chat_message` | K/O | Staff/private provenance; large historical text is object-storage candidate, not public retrieval content. |

## 5. Imported pedagogy and runtime recovery

Sources: [010](../../mathbank-db/sql/010_textbook_import.sql),
[013](../../mathbank-db/sql/013_step_hints.sql),
[014](../../mathbank-db/sql/014_gap_diagnosis.sql),
[015](../../mathbank-db/sql/015_recovery_runtime.sql),
[017](../../mathbank-db/sql/017_step_techniques.sql),
[019](../../mathbank-db/sql/019_admin_import_review.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `pedagogy.source_book` | K/O | Source/rights identity; book files in S3, relational citation retained. |
| `pedagogy.chapter_section` | K | Book hierarchy and ordered scope joins. |
| `pedagogy.taxonomy_node` | K | Imported taxonomy authority; do not silently merge with curated concepts/skills. |
| `pedagogy.taxonomy_edge` | K/D | Canonical typed edges; precomputed bounded adjacency is a possible derived store. |
| `pedagogy.problem_source_ref` | K | Source provenance and problem mapping for reimport/reconciliation. |
| `pedagogy.solution_source_ref` | K | Versioned source-to-solution mapping; preserve citation joins. |
| `pedagogy.problem_enrichment` | K/O | Enriched metadata needs human override and source provenance; large evidence blobs may be S3-backed. |
| `pedagogy.solution_part` | K | Imported solution grouping/order; not a disposable document chunk. |
| `pedagogy.solution_step` | K | Imported text IDs and dependencies; approved student retrieval filters depend on these joins. |
| `pedagogy.solution_step_dependency` | K/D | Canonical DAG authority; derived adjacency possible after cycle/reachability parity. |
| `pedagogy.learning_item` | K | APPROVED/student-visible/no-proof filtering; publication cannot depend solely on stale vector metadata. |
| `pedagogy.learning_item_step_anchor` | K | Step/item binding and hard retrieval eligibility. |
| `pedagogy.diagram` | K/O | Keep source/context/side linkage; diagram bytes in private S3. |
| `pedagogy.step_hint` | K | Ordered hint disclosure and approved step linkage. |
| `pedagogy.gap_diagnosis` | K | Attempt-scoped diagnosis with evidence; not a public shared graph node. |
| `pedagogy.knowledge_gap` | K | Learner-specific gap and recovery references; relational privacy/transaction boundaries. |
| `pedagogy.recovery_plan` | K | Owned stateful intervention with attempts and checkpoints. |
| `pedagogy.recovery_plan_item` | K | Ordered items/completion must agree with recovery state. |
| `pedagogy.solution_step_technique` | K | Reviewed per-step technique associations. |
| `pedagogy.solution_step_technique_run` | K/O | Technique enrichment run/evidence history; archive verbose settled results. |
| `pedagogy.solution_dag_review` | K | Human DAG validation gate; not implied by a successful graph projection. |

## 6. Released routes, micro-courses, media and policies

Sources: [026](../../mathbank-db/sql/026_tutoring_routes.sql),
[028](../../mathbank-db/sql/028_route_distributed_queue.sql),
[032](../../mathbank-db/sql/032_micro_course_platform.sql),
[033](../../mathbank-db/sql/033_interaction_template_library.sql),
[034](../../mathbank-db/sql/034_micro_course_template_bindings.sql),
[040](../../mathbank-db/sql/040_similarity_embeddings.sql),
[046](../../mathbank-db/sql/046_theorem_catalog.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `pedagogy.route_compiler_run` | K/O | Compiler provenance/release references; externalize large diagnostic output. |
| `pedagogy.solution_route_release` | K | Immutable release identity and publication pointer; UUID key retained. |
| `pedagogy.route_compiler_job` | K/D | Existing queue/release coupling; derived status allowed, new authority needs lease/replay redesign. |
| `pedagogy.route_step` | K | Composite release/step key and stable step UUID; downstream composite FKs matter. |
| `pedagogy.solution_step_instruction` | K | Compiled instruction binding and disclosure checks. |
| `pedagogy.route_step_hint` | K | Composite route binding/ordered disclosure; cannot relocate independently of release. |
| `pedagogy.solution_step_requirement` | K | Evaluation requirements must match exact published checkpoint. |
| `pedagogy.route_asset` | K/O | Claims/misconceptions/theory/learning assets have review and provenance; large bodies may use objects. |
| `pedagogy.route_asset_link` | K | Released asset/checkpoint relationships, not unverified inferred graph links. |
| `pedagogy.route_compile_task` | K/D | Distributed task claims/retries/run coupling; DynamoDB projection does not replace current ownership protocol. |
| `pedagogy.micro_course` | K | Canonical course identity and shared runtime contract. |
| `pedagogy.micro_course_target` | K | Approved pedagogic targets/relational references. |
| `pedagogy.micro_course_release` | K | Hash-pinned publication/review; cannot trust asynchronously copied metadata for activation. |
| `pedagogy.micro_course_module` | K | Ordered release composition and module references. |
| `pedagogy.micro_course_state` | K | Released state semantics and transitions; one learner-position authority. |
| `pedagogy.micro_course_state_concept` | K | Release/state taxonomy membership and FK checks. |
| `pedagogy.micro_course_state_technique` | K | Approved technique binding to exact state. |
| `pedagogy.micro_course_state_skill` | K | Approved skill binding and joins. |
| `pedagogy.micro_course_state_misconception` | K | Reviewed state/misconception mapping. |
| `pedagogy.micro_course_state_asset` | K | State/disclosure/asset association; bytes can move separately. |
| `pedagogy.video_asset` | K/O | Media identity/ownership/metadata; video bytes already may be object-backed. |
| `pedagogy.video_transcript` | K/O | Transcript identity/revision; cold long text may be S3-backed after reader adaptation. |
| `pedagogy.video_transcript_segment` | K/O | Time-aligned searchable text; retain SQL segments if consumers need joins/FTS. |
| `pedagogy.video_segment_concept` | K | Time-window taxonomy joins; not a standalone key-value workload. |
| `pedagogy.video_segment_technique` | K | Reviewed technique/time association. |
| `pedagogy.video_segment_skill` | K | Skill/time association and reverse lookup. |
| `pedagogy.video_segment_misconception` | K | Segment/misconception evidence linkage. |
| `pedagogy.video_timeline_marker` | K | Ordered timeline/disclosure semantics. |
| `pedagogy.state_qa_context` | K/O | State-bound eligible QA context; external payloads must retain release/disclosure checks. |
| `pedagogy.micro_course_state_learning_item` | K | Approved item binding and learner visibility. |
| `pedagogy.micro_course_state_activity` | K | Activity revision/scoring binding must be immutable at release. |
| `pedagogy.micro_course_transition` | K | Deterministic eligible transitions and CAS runtime consistency. |
| `pedagogy.intervention_script` | K | Reviewed intervention identity/policy, not autonomous model authority. |
| `pedagogy.intervention_step` | K | Ordered bounded intervention steps tied to script. |
| `pedagogy.micro_course_review` | K/O | Review attestation/hash evidence; archive large simulation snapshots only with retention. |
| `pedagogy.feedback_template` | K | Versioned approved feedback/disclosure rules. |
| `pedagogy.feedback_policy` | K | Evaluation/feedback policy must match activity release. |
| `pedagogy.misconception_evidence_rule` | K | Evidence matching policy, not model confidence as mastery authority. |
| `pedagogy.micro_course_state_interaction` | K | State/template-version bindings and FK integrity. |
| `pedagogy.taxonomy_node_embedding` | V | Rebuildable public-derived index; candidate for S3 Vectors benchmark. |
| `pedagogy.taxonomy_node_similarity` | K/D | Derived top-k similarities; relational pairs or keyed adjacency/lake, not prerequisites. |
| `pedagogy.solution_step_theorem` | K | Reviewed theorem citation/evidence tied to exact step. |

## 7. Learner and tutor transactional state

Sources: [003](../../mathbank-db/sql/003_learner_schema.sql),
[012](../../mathbank-db/sql/012_step_runtime.sql),
[016](../../mathbank-db/sql/016_agent_session_link.sql),
[023](../../mathbank-db/sql/023_pedagogy_feedback.sql),
[026](../../mathbank-db/sql/026_tutoring_routes.sql),
[032](../../mathbank-db/sql/032_micro_course_platform.sql),
[033](../../mathbank-db/sql/033_interaction_template_library.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `learner.student_profile` | K | Ownership/PII and cascading references; identity-provider migration is separate. |
| `learner.attempt` | K | Canonical attempt, answer/result and relational event consistency. |
| `learner.concept_mastery` | K/D | Authoritative update tied to validated events; AWS analytics/serving copy only until whole aggregate redesign. |
| `learner.technique_mastery` | K/D | Same transaction/evidence requirements; eventual copy must display freshness. |
| `learner.solve_attempt` | K | Source/release/learner binding and attempt lifecycle. |
| `learner.attempt_step_state` | K | Current checkpoint state must commit with event/idempotency/outbox. |
| `learner.event` | K/O | Authoritative event/audit trail; cold payload archive or lake copy cannot replace transactional receipt. |
| `learner.idempotency_record` | K | Duplicate request response and state mutation must be one transaction; TTL alone is insufficient. |
| `learner.agent_session_link` | K | Verified learner/session ownership; framework sessions cannot imply app authorization. |
| `learner.pedagogy_feedback` | K/O | Private learner evidence and review context; deidentified analytics copy possible, raw feedback not public. |
| `learner.route_attempt` | K | Released route/version/ownership and current state linkage. |
| `learner.micro_course_enrollment` | K | Single enrollment position/version and restart/resume semantics. |
| `learner.micro_course_state_event` | K/O | Course-transition evidence; archive only after preserving replay/retention and privacy. |
| `learner.interaction_event` | K/O | Activity evidence tied to scoring version and ownership; lake copy is asynchronous. |
| `learner.misconception_evidence` | K | Evidence IDs/learner ownership and mastery interpretation; not shared graph content. |
| `tutor.runtime_state` | K | Atomic current position/evaluation/idempotency boundary. |
| `tutor.micro_course_runtime` | K | Reuse single course runtime; do not create parallel DynamoDB learner position. |

## 8. Live classroom, activities and visual interactions

Sources: [020](../../mathbank-db/sql/020_live_fluid_platform.sql),
[033](../../mathbank-db/sql/033_interaction_template_library.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `live.session` | K | Classroom ownership/state and topic coordination. |
| `live.participant` | K | Membership/role authorization tied to session. |
| `live.session_event` | K/O | Ordered classroom audit/history; large cold event bodies may be archived. |
| `live.command_receipt` | K | Deduplication must agree with commanded state mutation. |
| `live.topic_run` | K | Active topic/plan/runtime consistency. |
| `live.recommendation` | K/D | Advisory keyed projection possible; retain original approval/ownership and source version. |
| `live.takeover` | K | Teacher control/authorization and runtime-state synchronization. |
| `activity.definition` | K | Answer key/scoring policy must be server-side and version-bound. |
| `activity.instance` | K | Owned activity/release/session binding. |
| `activity.response` | K | Atomic scoring/result/event semantics, not an eventual answer cache. |
| `visual.widget_spec` | K/O | Approved specification and validation; large immutable JSON may be object-backed. |
| `visual.widget_state` | K | Runtime ownership/version and interaction consistency; hot reads/writes need measured redesign. |
| `visual.asset` | K/O | Keep asset rights/type/disclosure/ownership; image/media bytes in S3. |
| `visual.interaction_template` | K | Stable approved template identity. |
| `visual.interaction_template_version` | K/O | Immutable reviewed definition; large specifications can be versioned S3 objects. |
| `visual.control_template` | K | Control library/validation contract, small shared reference data. |
| `visual.icon_token` | K | Small validated visual vocabulary; no meaningful SQL saving expected. |
| `visual.animation_template` | K/O | Approved animation configuration; large payloads may be externalized. |
| `visual.scene_spec` | K/O | Scene validation/version identity; move bytes, not publication authority. |
| `visual.interaction_instance` | K | Owned interaction and scoring/template binding. |
| `visual.interaction_instance_concept` | K | Relational semantic binding; downstream learner/evaluation joins. |
| `visual.interaction_instance_technique` | K | Instance-specific reviewed taxonomy association. |
| `visual.interaction_instance_skill` | K | Instance skill/evidence linkage. |
| `visual.interaction_instance_misconception` | K | Instance misconception/diagnostic binding; not global learner state. |

## 9. Attempt media and artifacts

Sources: [021](../../mathbank-db/sql/021_attempt_media.sql),
[022](../../mathbank-db/sql/022_artifact_runtime.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `attempt_media.submission` | K/O | Owned attempt/upload status; large originals use private S3. |
| `attempt_media.media_asset` | K/O | Keep media metadata/ownership; bytes need scoped URLs and retention. |
| `attempt_media.evidence_region` | K | Bounding region/page links tied to private evidence. |
| `attempt_media.transcription_candidate` | K/O | Untrusted OCR/model proposal with provenance; externalize verbose candidates if needed. |
| `attempt_media.step_candidate` | K/O | Unapproved learner-work interpretation; model output cannot become canonical proof. |
| `attempt_media.step_candidate_evidence` | K | Evidence-region associations and ownership. |
| `attempt_media.approval` | K | Human decision must match exact candidate revision. |
| `attempt_media.step_assessment` | K | Assessment/scoring/evidence atomicity; not eventual model-generated feedback authority. |
| `attempt_media.event` | K/O | Private audit and replay; controlled cold archive, not public retrieval. |
| `artifact_runtime.artifact_request` | K/O | Owned request/idempotency/status and provenance; externalize large input bodies selectively. |
| `artifact_runtime.artifact_bundle` | K/O | Validated immutable artifact grouping; package bytes can use S3. |
| `artifact_runtime.artifact_asset` | K/O | Asset identity/disclosure/lineage retained; bytes externalized. |
| `artifact_runtime.artifact_metadata` | K/O | Enriched metadata/review boundaries; large evidence stays versioned and private. |
| `artifact_runtime.overlay_state` | K/O | Owner/version and scene relationships; snapshot bytes possible, current state authority retained. |
| `artifact_runtime.frame_sequence` | K/O | Ordered frames/validation binding; generated media is an object-storage workload. |
| `artifact_runtime.artifact_annotation` | K/O | Private annotations and exact asset/version targets. |
| `artifact_runtime.validation_result` | K/O | Validator/version/evidence must match bundle; archive detailed results with hashes. |
| `artifact_runtime.artifact_lineage` | K | Parent/source/revision linkage needed for invalidation and deletion. |
| `artifact_runtime.artifact_search_tag` | K | Reviewed tags/ownership for retrieval filtering. |
| `artifact_runtime.artifact_embedding` | V | Vector offload only after public/private partition and SQL postfilter tests; do not mix attempt evidence with corpus. |

## 10. Exams, jobs and geometry

Sources: [042](../../mathbank-db/sql/042_quiz_generation.sql),
[044](../../mathbank-db/sql/044_manim_studio_jobs.sql),
[047](../../mathbank-db/sql/047_mock_exam_extensions.sql),
[048](../../mathbank-db/sql/048_mock_exam_event_timeline.sql),
[050](../../mathbank-db/sql/050_exam_generation_sources_and_progress.sql),
[051](../../mathbank-db/sql/051_exam_resume_state.sql),
[052](../../mathbank-db/sql/052_quiz_question_pool.sql),
[packaged geometry DDL](../../mathbank-rest/src/mathbank_rest/migrations/026_geometry_scenes.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `quiz.paper` | K | Owned generated exam, source snapshot, timing and lifecycle. |
| `quiz.question` | K | Exam question/scoring snapshot; admin source edits must not silently alter a submitted exam. |
| `quiz.question_concept` | K | Generated question classification and diagnosis joins. |
| `quiz.question_technique` | K | Exam-specific technique binding. |
| `quiz.question_skill` | K | Exam skill evidence/diagnosis binding. |
| `quiz.solution` | K | Hidden answer/solution disclosure and versioned grading. |
| `quiz.response` | K | Atomic owned submission/scoring and exam progress. |
| `quiz.exam_diagnosis` | K/O | Owned diagnosis/evidence/model provenance; large narratives can be object-backed. |
| `quiz.response_event` | K/O | Authoritative exam event ordering/answer history; cold lake/archive copies require privacy handling. |
| `quiz.question_source` | K | Provenance/reuse/rights and source revision linkage. |
| `quiz.generation_event` | K/O | Generation progress/cost/error history; preserve source/run acceptance before archiving detail. |
| `quiz.response_draft` | K | Resume/last-answer/version ownership; DynamoDB would need whole exam aggregate redesign. |
| `quiz.question_pool` | K/D | Reusable question eligibility/provenance; read projection possible but publication must be rechecked. |
| `studio.scene_research_job` | A/O | Expiring keyed job is a plausible DynamoDB aggregate; enforce expiry and retain required result/audit in durable stores. |
| `studio.video_render_job` | A/O | Same pilot aggregate, including dependency on research job; replace SQL FK semantics explicitly, video already uses object key. |
| `geometry_scene.scenes` | K | Owned scene head/version consistency; not arbitrary unversioned JSON. |
| `geometry_scene.versions` | K/O | Immutable revision/hash and validated scene; large snapshots may use private S3. |
| `geometry_scene.receipts` | K | Idempotent scene operation receipt and committed version must remain atomic. |
| `geometry_scene.runs` | K/O | Solver/render execution provenance and version linkage; externalize large logs/results only. |

## 11. Analytics, notifications and audit

Sources: [001](../../mathbank-db/sql/001_schema.sql),
[018](../../mathbank-db/sql/018_outbox_consumers.sql),
[043](../../mathbank-db/sql/043_notifications.sql).

| Table | Code | Rationale / cost driver |
|---|---|---|
| `analytics.learner_daily_activity` | D | Rebuildable student/day counters suit DynamoDB keyed serving or S3/Athena history; replay dedup and erasure must replace SQL FK cascade. |
| `notification.event` | D | Derived learner inbox can use DynamoDB; enforce owner/read/expiry and reliable outbox fan-out. |
| `audit.action_log` | K/O | Keep mutation/audit atomicity; cold immutable evidence in S3 with approved retention, not asynchronous audit-only writes. |

## 12. Framework/provider-owned catalog-only tables

Evidence: [ADK session catalog](reference/postgres/agent_sessions.md) and
[Neon Auth catalog](reference/postgres/neon_auth.md), observed 2026-10-08.
These are the 14 identities absent from the checked-in application table DDL.

| Table | Code | Rationale / cost driver |
|---|---|---|
| `agent_sessions.adk_internal_metadata` | F | ADK schema version bookkeeping; use supported framework migration, not custom row export. |
| `agent_sessions.app_states` | F | ADK app-scoped state semantics and adapter compatibility. |
| `agent_sessions.events` | F | ADK message/action ordering and REST transcript readers; large private history needs explicit retention and adapter. |
| `agent_sessions.sessions` | F | Framework session lifecycle/ownership and event FK semantics. |
| `agent_sessions.user_states` | F | Framework user-scoped state; migrating agent runtime does not implicitly migrate this store. |
| `neon_auth.account` | F | Provider credentials/account links; no plaintext export or casual DynamoDB copy. |
| `neon_auth.invitation` | F | Provider organization-invitation lifecycle. |
| `neon_auth.jwks` | F | Provider signing-key management; requires supported rotation/identity migration. |
| `neon_auth.member` | F | Provider organization/role membership. |
| `neon_auth.organization` | F | Provider tenant identity and referential continuity. |
| `neon_auth.project_config` | F | Provider configuration ownership, not application key-value metadata. |
| `neon_auth.session` | F | Provider session/token continuity, expiry and revocation semantics. |
| `neon_auth.user` | F | Provider identity mapping; preserve learner/staff subject linkage before replacing provider. |
| `neon_auth.verification` | F | Provider verification/security lifecycle. |

## 13. Conclusions and migration gates

- The strongest immediate candidates are **five vector families**, **two isolated
  Studio job aggregates**, and **derived notification/analytics views**. Many
  large-payload rows may benefit from S3 bytes without moving their metadata.
- That does **not** mean five entire vector-related subsystems or all historical
  event tables should move. Search profiles, chunks, releases, source eligibility,
  SQL outbox and authoritative learner/score evidence remain necessary.
- Most application tables describe relationships or participate in publication,
  grading, ownership or version transactions. A full DynamoDB design is possible
  only with redesigned aggregates, conditional uniqueness items, denormalized
  reverse indexes, new query APIs, controlled cross-aggregate workflows and
  explicit replacement of FK/cascade behavior. It is a major application rewrite.
- `ml.*` names in requirements 54-58 are **planned contracts**, not additional
  `CREATE TABLE` declarations found in this migration inventory. Include them in
  future target design, not in claims about today's storage bill.
- Before any pilot: capture current catalog/size distribution, enumerate actual
  reader/writer call sites, benchmark access patterns, freeze one authoritative
  writer, replay from a watermark and prove restore/deletion/rollback. Updating
  this register does not authorize reading private rows or changing live tables.
