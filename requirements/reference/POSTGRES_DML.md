# PostgreSQL DML and query behavior reference

## Evidence

- Evidence mode: source-derived access/transaction behavior; complete selected
  live metadata is separately recorded in the [catalog](postgres/README.md).
- Current source revision: `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`, clean source
  tree before documentation changes. Older incremental revision records below
  are retained as history.
- Sources: `mathbank-db/sql/001_schema.sql` through `024_feedback_evidence.sql`; corpus/import/embed ETL under `mathbank-db/etl/`; REST DB and runtime write paths under `mathbank-rest/src/mathbank_rest/`; and `attempt_media.py`, `attempt_media_models.py`, `media_processing.py`, `artifact_runtime.py`, `object_store.py`, `runtime_ai.py`, `routers/attempt_media.py`, `routers/artifacts.py`, `db/learner.py`, and `mastery.py`.
- No DML was executed for this documentation task.

## Relation-level access and use cases

### Full-corpus tutoring routes and operator bulk approval

Incremental source evidence: migration
[026](../../mathbank-db/sql/026_tutoring_routes.sql),
[compiler](../../mathbank-rest/src/mathbank_rest/route_compiler.py) and
[shared review validator](../../mathbank-rest/src/mathbank_rest/route_runtime.py);
includes current worktree changes. See
[requirement 39](../39_PRECOMPILED_TUTORING_ROUTES.md) for authorization and
dated live operational results, separately from this source-derived description.

| Operation | Transaction / access | Boundary |
|---|---|---|
| `compile --all` | Freeze every remaining solution ID/source hash in QUEUED jobs; direct run lease; 1-8 workers | No short/long-source or 10,000-row exclusion; unchanged same-version releases reused, existing textbook steps preserved |
| Per-source persistence | Source rows share-locked/rehashed; solution advisory lock; release/steps/assets/H1-H5/job update atomically committed | Stale source or invalid program fails explicitly; no partial approved snapshot |
| `--approve-by` | Run stores `auto_review_by`; shared hash/source/taxonomy/DAG validator transitions DRAFT to REVIEWED in the persistence transaction | Explicit operator bulk approval, not independent mathematical certification; never PUBLISHED |
| `approve-drafts` | Snapshot current draft IDs; validate and review each in its own transaction | Rejected/stale draft remains unapproved with an explicit failure; previously reviewed snapshots untouched |
| Resume/status | Retry frozen unfinished jobs; inherit approval policy; whole-cohort job/release counts | Job DRAFT means generated snapshot exists; release status independently records REVIEWED/PUBLISHED |
| Failure | Persist safe `error_code` and JSON `error_details`; no raw provider body | At most one repair per attempt; invalid sources never turn into empty successful steps |

Publication, Neo4j projection and embeddings remain separate operations.

Every observed table/view has its purpose, migration/framework/provider owner,
source-access links and exact relationships in the
[20-schema catalog](postgres/README.md). The
[209-operation REST inventory](REST_ENDPOINTS.md) links the actual mounted
handlers, dependencies, parameters and request/response schemas. Schema route
families are not one-to-one table CRUD claims: join tables, worker queues and
private evidence often have only internal callers.

### Atomic reference steps, guidance and caches

| Operation family | Persisted records / transaction | Important boundary |
|---|---|---|
| Package import | Staging/conflicts/reconciliation; core problem/solution; pedagogy source refs/parts/steps/dependencies/items/diagrams | Authored source steps are imported, not universally generated; several phase commits |
| Admin step metadata | Locked step update + ingest.admin_review_action + pipeline.outbox_event in one transaction | Only skill/checkpoint/note; no prose/split/merge/reorder or revision guard |
| Dependency change/reject | Scoped endpoints, cycle check, human provenance/audit/outbox | Runtime uses prerequisite from -> dependent to; only hard DEPENDS_ON cycles checked |
| DAG approval | solution_dag_review + audit | Not a runtime publication gate; no immutable release pinning |
| Start/resume | Advisory lock; owned solve_attempt, attempt_step_state, runtime_state, events/outbox/idempotency | PUBLISHED steps by problem; absent steps cause 409, not generation |
| Learner response | Attempt/runtime row locks, response event/idempotency and version bump commit first | Evaluator runs outside that transaction; verdict/version checks commit separately |
| Help escalation | Attempt state/help/version/event transaction, then separate cache lookup/generation | Provider failure does not undo help use or fabricate text |
| Hint content | step_hint INSERT ON CONFLICT DO NOTHING | Shared step/level/prompt key; no content-hash invalidation; level 5 reads reference directly |
| Guidance roadmap | Private reference SELECT; safe stages/checkpoint response | No canonical-step INSERT; may call paid model; source verification unchanged |
| Widget compose/store | Deterministic transient composition or admin visual.widget_spec INSERT | No automatic canonical step attachment |
| Artifact preview | Typed deterministic plan/render in memory | No request/bundle/index persistence or paid generation |
| Artifact request/generate | artifact_runtime metadata + private object assets | Staff generate/publish/index; logical step links, no complete step FK/resolver contract |
| Projection consumption | outbox_consumer receipt + projection_request in same SQL transaction | Graph/vector execution is separate, explicit and not globally atomic |

Full UI/REST examples, persistence matrix, source-diagram/video boundaries and
the proposed complete generator/editor are in
[requirement 36](../36_STEP_GENERATOR_AND_AUTHORING.md). It must not be confused
with the existing original-practice drafts in
[requirement 35](../35_CORPUS_REPAIR_AND_AUTHORING.md).

### Safe read examples (illustrative only; not executed)

Bind `:problem_code` and `:student_id` using the existing SQLAlchemy caller.
Staff-only queries may read reference text; do not relay it as a student
“next hint” without the runtime reveal checks.

```sql
-- Staff reference preview: canonical problem -> selected solution -> parts/steps.
SELECT p.canonical_code, s.solution_id, s.revision, s.verification_status,
       sp.solution_part_id, sp.part_ordinal, st.solution_step_id,
       st.global_step_index, st.step_text, st.publication_status
FROM core.problem p
JOIN core.solution s USING (problem_id)
LEFT JOIN pedagogy.solution_part sp USING (solution_id)
LEFT JOIN pedagogy.solution_step st USING (solution_part_id)
WHERE p.canonical_code = :problem_code
ORDER BY s.revision DESC, sp.part_ordinal, st.global_step_index;

-- Ownership-scoped learner attempt metadata; not a source-step disclosure.
SELECT a.solve_attempt_id, a.status, a.current_solution_step_id,
       r.state_version, r.current_mode
FROM learner.solve_attempt a
JOIN tutor.runtime_state r USING (solve_attempt_id)
WHERE a.student_id = CAST(:student_id AS uuid)
  AND a.problem_id = CAST(:problem_id AS uuid);
```

ADK-owned tables are accessed by framework ORM/session services and read-only
transcript reconstruction; Neon Auth tables have no checked-in MathBank REST
consumer identified. Do not manufacture application write examples for those
provider tables. Empty audit/auth namespaces do not imply missing audit rows:
actual audit evidence belongs to knowledge/ingest/learner/live tables.

## High-level write boundaries

### Geometry scene system

Incremental source revision `2bb4c2f682bf205556b8d6e895c868b10cdcc7a7`
with geometry worktree changes; inspected migration 026, geometry storage,
orchestration and routers. [Complete table/access reference](postgres/geometry_scene.md)
documents columns and every operation family. Receipt preflight avoids paid
work on accepted retries; immutable versions and a final owner/version CAS
publish only replay-validated candidates. Candidate run evidence is private,
and staff review updates cannot publish a rejected candidate.
No solution-step completion, grading, mastery, graph or vector writes occur.
The repository explicitly cleans tracked uploaded assets on transaction rollback;
it does not pretend SQL and private object storage form one distributed transaction.

### Reviewed corpus authoring

Incremental source revision `77eb6784a000a9cc6077526fa4accc7c4111afac` plus
related worktree changes; inspected `corpus_authoring.py`,
`routers/admin_corpus.py`, migration 025, `db/problem_images.py`,
`routers/step_runtime.py`, `object_store.py`, and `etl/pdf_assets.py`.

All corpus-admin endpoints require the shared admin API key. Browser mutations
add signed-session and same-origin checks; neither identifies an individual
reviewer. SQL operations use bound parameters and a single `engine.begin`
transaction per operation. Inventory reads distinguish heuristic figure
references from verified student-safe image metadata; a zero count alone
does not prove a missing required diagram.

| Operation | Tables / effects | Conflict and safety behavior |
|---|---|---|
| Save text draft | Read `core.problem`; insert `ingest.corpus_draft` with old/new text and base hash | Submitted hash must match current canonical text; no public edit yet |
| Upload image draft | Validate bounded PNG/JPEG dimensions before decode; normalize at native pixel resolution; write immutable private object; insert IMAGE draft | Rights consent and matching source hash required; classification is problem/solution; unreviewed bytes are admin-only |
| Save/generate new draft | Insert NEW_PROBLEM draft only | Generation requires explicit paid consent and available schema before calling the configured provider; retains AI origin/model/creation note |
| Edit pending new draft | Lock draft; replace payload/note; increment revision | Expected revision and DRAFT/NEW_PROBLEM required; immutable origin/provenance retained |
| Reject | Lock draft; set REJECTED, review note/time | No canonical problem, image or solution writes |
| Approve text | Lock draft and problem; update statement/hash/timestamps, clear `statement_latex`; mark PROBLEM_STATEMENT representations linked by `search.chunk` STALE | Source hash and expected draft revision must match; existing canonical identity and solution records are retained |
| Approve image | Lock problem; allocate next ordinal; insert `core.problem_image` metadata | Object key is stored as an internal `object-store:` locator; source is ADMIN_SOURCE_DIAGRAM or ADMIN_SOLUTION_DIAGRAM |
| Approve new practice | Upsert dedicated generated competition/edition; insert nonofficial paper, fresh GENERATED problem and ADMIN_AUTHORED solution; attach draft to new problem | Never overwrites an official contest identity; solution verification stays UNVERIFIED |

Approval and rejection lock the draft. An identical repeated state/note/version
returns the existing result, without duplicate publication; conflicting review
or changed content returns 409. After review the SQL trigger forbids changing
or deleting the record. New-problem approval requires a worked solution and
no declared absent required diagram; there is no correctness certification.

Approved solution figures are excluded from both normal image metadata and
public UUID-image serving. Their admin review remains available; linking them
into solution Markdown is not automatic. Source images use the same public
UUID route, reading through the existing private storage client rather than
revealing storage keys.

`pdf_assets.store_images` excludes admin-image sources from conflict updates.
The migration-025 trigger blocks source ingestion from silently replacing
admin-reviewed text; a conflicting importer fails explicitly. Source-index
STALENESS is transactional with text approval. No embeddings, graph writes,
classification, mastery or outbox publication are performed automatically;
operator indexing/publication is separate. Object storage is not atomic with
SQL: local save failures attempt targeted object cleanup, while commit failures
may leave an unreferenced private object, never a public draft.

The [210-query library](../../mathbank_data_ingestion/queries/README.md)
adds explained SELECT/WITH diagnostics, read-only transaction guards and
aggregate learner privacy thresholds. PREPARE-only checks verified all 210
against the selected configured REST database; result semantics, scan costs
and privileges on other deployments remain unverified.

### Profile theme coverage (read-only)

Current incremental source: `db/learner.get_practice_progress` and shared
`queries.technique_problem_evidence_sql`, plus authenticated router/proxy callers.
No DDL or graph change. Reads all concept/technique identities, direct concept
problem tags, published/approved step technique support and eligible reviewed
problem technique tags. The technique CTE is shared with corpus filtering;
human approval/step-evidence/legacy eligibility behavior is unchanged.
Joins corpus paper/edition/competition identities for parity with practice lists.
An authenticated `:student_id` scopes distinct `learner.attempt.problem_id`
records, regardless of correctness. Aggregation counts distinct eligible
problems to avoid inflation from repeated attempts or multiple evidence rows.
Themes with no eligible practice return zeros. No mastery recomputation,
attempt writes, publication, provider calls or migration occurs.

### Private solution-reference planning

Incremental source revision `1582f808a731e571e79b588d4c73e717eefc7956` plus related
worktree changes; inspected `solution_guidance.py`, `pedagogy.coach`, router and
agent callers. The parameterized read joins `core.problem` to nonempty
`core.solution`, preferring Markdown with LaTeX as an alternative. It retains
all-record count but returns at most six records, VERIFIED first, then kind,
descending revision and ID. Each private body is capped at 12,000 characters;
bounded/excerpted evidence is reported, not asserted complete.

`official_answer` is read only for a limited output-withholding check. Private
bodies go to the REST planner/coach, never the ADK/browser tool result. Public
metadata includes IDs, kind/revision and verification status; the output plan
is PENDING. No ingestion, annotation, publication, audit/outbox, attempt or
mastery write occurs. The safe selected conversation plan is retained through
existing ADK session JSON, distinct from temporary workspace state and from a
reviewed solution-DAG. No DML was executed during this documentation phase.

### Guided-workspace reads and private-work handoff

Incremental source revision `1582f808a731e571e79b588d4c73e717eefc7956`, plus
related worktree changes; examined `guided_orientation.py`, `guided_visuals.py`, pedagogy
statement/routes, workspace/upload, existing attempt-media snapshot and
same-origin proxy. `POST /v1/tutor/micro-check` runs the parameterized canonical
statement SELECT and safe diagram listing. It reads no official answer/solution
body, writes nothing, calls no model/enrichment and returns stateless authored
orientation. Client indices/self-reported stages are not learner evidence.

`GET /v1/tutor/workspace/{code}` uses the same canonical statement/safe-image
read, without graph/enrichment/publication dependencies. Source-verified visual
definitions and typed intents are in-memory calculations. They create no
submission, artifact, assessment, outbox event or mastery write. The UI loads
the full context independently, while authored checks/writing remain usable.

Existing learning-context GET still calls `ensure_learning_metadata`, so
missing teaching metadata may invoke the prior enrichment/publication path;
it must not be described as universally read-only. Private upload creates an
existing authenticated submission and original asset, then requires explicit
transcription, review/approval and analysis. Temporary typed drafts are not
silently persisted or promoted into mastery. No DML was executed during this
documentation refresh. See [34](../34_GUIDED_PROBLEM_WORKSPACE.md).

### Topic lessons, practice ranking and correction evidence

Incremental source evidence at `c79060ac0771175baa6e04b37bede840f8c30ee1`
including related worktree changes. Sources: migration 024, `db/topic_pedagogy.py`,
`db/retrieval_audit.py`, `practice_selection.py` / profiles, textbook importer,
shared structural audit, `step_recovery.py`, tutor session/lesson/audit tools.
No DML was executed for this documentation phase.

- Exact-topic practice reads at most 100 canonical published-step candidates,
  excludes pending/rejected assertions and matching **human-resolved IRRELEVANT**
  reports, then ranks within that set using the versioned `topic-fit-v1` profile.
  Minimum confidence is 0.8; confidence is the maximum qualifying step confidence,
  unlike the listing union's minimum. Signed-in exposure uses actual solve/legacy
  attempts; unresolved/confirmed gap skill IDs supply misconception relevance.
  Source-order difficulty and taxonomy/form/skill diversity are proxies, not
  measured contest difficulty or mathematical equivalence. Missing semantic,
  prerequisite or exposure evidence remains unknown. No embedding/model call.
- Feedback INSERT computes a bounded server-side source/step/annotation audit.
  Snapshot contains canonical node, challenged mappings, supporting step IDs,
  structural signatures, version and provisional error kind; no solution bodies,
  identity/token or fabricated retrieval scores. An exact duplicate retains its
  original audit/status instead of reopening or overwriting reviewed evidence.
  The row is a PENDING correction candidate, not a canonical annotation.
- Human report resolution updates note/time/verdict/error kind in one pending-row
  transaction. RESOLVED classified rows are available as retriever evaluation
  evidence. Only IRRELEVANT rows exclude a problem for the audited canonical
  node. UNCLASSIFIED/DISMISSED complaints are not negatives. No training occurs.
  Labels do not automatically invalidate when source taxonomy changes; review
  and vector/graph/cache follow-up remain separate operator work.
- Future textbook imports preserve the staged Power tag but flag missing
  structural support as `TECHNIQUE_EVIDENCE_MISSING` in import conflicts; the
  canonical problem-technique bridge **withholds new unsupported tags**.
  The shared detector checks circle context plus product/power reasoning.
  Absence is a heuristic review flag, not a proof of irrelevance or an automatic
  rejection. Existing human/rejected rows remain protected. No bulk reimport,
  retrospective retagging or paid automatic-enrichment revalidation was run.
- Existing remediation still selects approved imported learning items,
  excludes origin/hidden content, and now excludes questions copying hidden
  solution seeds via the existing solution-leakage heuristic. A given copied
  from the source statement is not treated as a leaked solution. This does not
  implement a new validated generated-item factory.
- ADK appends lesson/checkpoint state through DatabaseSessionService events.
  Revision checks reject stale checkpoint submissions; wrong authored choices
  or numeric answers stay at the same stage. Skip/jump/hint actions retain
  distinct stage status and accumulated interaction time without marking
  mastery. Review restarts instruction without clearing conversation exposure.
  This state neither mutates corpus annotations nor certifies mastery.
  Four-frame geometry previews reuse reset-to-base rendering, privately and
  ephemerally, without object-store, graph or artifact-publication writes.
- Private written work remains linked to a canonical `problem_id` in
  `attempt_media.submission`. Image/PDF upload creates the existing submission
  and media asset; paid transcription and analysis are separate explicit
  actions. The analysis classifier must verify problem context before critique;
  false or unverified context, or all-irrelevant step alignment, fails closed.
  No lesson/upload control writes to PostgreSQL other than the existing
  attempt-media lifecycle.

General technique listings remain canonical membership views; they share the
published-step union but do **not** apply feedback-specific practice exclusions.
The ranking endpoint and final complete-problem display perform distinct gates.

### Incremental topic/feedback behavior (source-derived, 2026-10-07 UTC)

Revision `c79060ac0771175baa6e04b37bede840f8c30ee1` plus related worktree changes.
Sources: migration 023, `db/topic_pedagogy.py`, `db/queries.py`, and textbook importer.
Student reports INSERT SELECT the canonical problem with JWT-derived student ID;
duplicate keys do a no-op topic update and return the original status/ID.
Admin review UPDATE is restricted to PENDING, sets note/time, and conflicts if no
row changes. These separate transactions never change graph, approved tags or
mastery. Resolving feedback is not proof that a graph correction was published.

Topic examples come from `_TAXONOMY_DETAILS`: published solution-step ownership
or APPROVED technique links. No solution text is returned. Textbook automatic
problem-technique listings require this step support; human mappings are retained.
Technique listings and corpus technique filters share `technique_evidence`.
Published/approved step-only matches appear as computed `role=STEP_SUPPORTED`,
with the minimum supporting confidence, not a newly written canonical assertion.
Existing pending/rejected mappings are never resurrected by this fallback.
Exact taxonomy technique examples also exclude explicitly rejected mappings.
Canonical detail excludes rejected technique rows. Textbook import now preserves
both human decisions and rejected records instead of overwriting their confidence.
Correction remains revision-checked `problem_technique` review plus explicit graph
publication. PostgreSQL and Neo4j corrections are non-atomic and must be checked
separately; an annotation status alone does not prove a stale graph edge is gone.

| Boundary | Canonical store | Derived/follow-up store |
|---|---|---|
| Corpus import | `core.*`, `knowledge.concept/technique/problem_*`, `pipeline.run` | Neo4j corpus projection; `search.*` vector representations/embeddings |
| Reviewable pedagogy metadata | `knowledge.skill*`, `knowledge.problem_skill`, `knowledge.problem_pedagogy`, `knowledge.pedagogy_review_event` | Neo4j pedagogy projection after explicit publish |
| Textbook package import | `ingest.*`, `pedagogy.*`, selected `core.*` and `knowledge.*` bridge rows | Neo4j `solution_steps` projection; `search.*` step/item vectors |
| Learner state | `learner.attempt` append log; `learner.*_mastery` caches | Future graph learner projection is not implemented in current projectors |
| Step-solving runtime | `learner.solve_attempt`, `learner.attempt_step_state`, append-only `learner.event`, `learner.idempotency_record`, `tutor.runtime_state`, `pipeline.outbox_event`; Phase 8 hint cache in `pedagogy.step_hint`; Phase 9 diagnoses in `pedagogy.gap_diagnosis` and `pedagogy.knowledge_gap`; Phase 10 recovery detours in `pedagogy.recovery_plan` and `pedagogy.recovery_plan_item` | Async consumers mark `pipeline.outbox_consumption`; completion writes one legacy `learner.attempt` row for mastery; cached hint rows are shared by step/level/prompt version; diagnosis rows are reused by evidence fingerprint and hypothesis rows are status-mutated only; recovery plans are idempotent, adaptive, and return to the exact origin step without directly writing mastery |
| Admin import review (migration 019) | `ingest.admin_review_action` (append-only), `ingest.import_conflict.decision`, `pedagogy.solution_step(_dependency)`, `pedagogy.solution_dag_review`, `pedagogy.learning_item` review fields | Outbox → `pipeline.projection_request` → graph projector (free) / embeddings (paid, manual) |
| Outbox consumers (migration 018) | `pipeline.outbox_consumption` | `analytics.learner_daily_activity` (rebuildable), `pipeline.projection_request` |
| Agent sessions | ADK-owned tables in `agent_sessions` (framework DML); project-owned `learner.agent_session_link` (migration 016) | Read-only transcript rebuild from `agent_sessions.sessions/events` |
| Multimodal learner evidence (migration 021) | `attempt_media.*`, approved but unassessed `learner.attempt` | Private object store for media; small identifier/version-only transactional outbox events; no graph projection |
| Reusable teaching artifacts (migration 022) | `artifact_runtime.*` metadata/validation/lineage/tags/embeddings | Private object store for generated bytes; no automatic indexing or graph publication |

## Core corpus ETL (`mathbank-db/etl/load_corpus.py`)

| Operation | Tables touched | Keys/idempotency | Notes |
|---|---|---|---|
| Start/end import run | `pipeline.run` | Inserts `run_type='load_corpus'`; updates status/`completed_items` or failure metadata by `run_id` | Run row can remain running if process dies before failure handling. |
| Competitions | `core.competition` | `ON CONFLICT (external_code) DO UPDATE name, level` | Spreadsheet mirror natural key. |
| Editions | `core.competition_edition` | Attempts `ON CONFLICT (competition_id, year, season, edition_label) DO NOTHING`, then SELECTs matching row | Because nullable fields are part of the unique key, SQL NULL semantics can permit duplicates; code selects by NULL season/label. |
| Papers | `core.paper` | `ON CONFLICT (external_code) DO UPDATE question_count/paper_code` | Paper external code is the import key. |
| Problems | `core.problem` | `ON CONFLICT (canonical_code) DO UPDATE` statement/answer/source/classification/hash fields | `canonical_code` is stable question id. |
| AoPS crawl enrichment | `core.problem`, `core.solution`, `core.problem_image` | Updates problem by code; solutions by `(problem_id, solution_kind, revision)`; images by `(problem_id, ordinal)` | Filters decorative repeated image filenames. |
| PDF crawl import | `core.competition_edition`, `core.paper`, `core.problem`, `core.problem_image`, `core.solution` | paper `external_code`; problem `canonical_code`; solution natural key; image `(problem_id, ordinal)` | Reads already-split Markdown artifacts; no network. |
| Concepts/techniques | `knowledge.concept`, `knowledge.technique` | Concept `slug` DO NOTHING; technique `slug` DO UPDATE description | Slugs normalized to lowercase/kebab. |
| Problem concepts/techniques | `knowledge.problem_concept`, `knowledge.problem_technique` | `ON CONFLICT DO NOTHING` on composite PK | Inserts PENDING assertions; automatic approval triggers may later convert PENDING to REVIEWED after migration 008. |
| Concept relations | `knowledge.concept_relation` | `ON CONFLICT DO NOTHING` on `(from, to, relation_type)` | PENDING raw relation assertions. |

## PDF/admin pipeline (`pdf_pipeline.py` and REST admin DB)

| Path | Tables touched | Idempotency / conflict keys | Effects |
|---|---|---|---|
| `pdf_pipeline.py discover` | `pipeline.pdf_source` | `ON CONFLICT (paper_external_code) DO UPDATE` URLs/link scope | Registers direct-link paper sources. |
| REST `POST /v1/admin/competitions` | `core.competition` | `ON CONFLICT (external_code) DO UPDATE` | Authenticated by `X-Admin-Api-Key`. |
| REST `POST /v1/admin/papers` and batch | `pipeline.pdf_source` | `ON CONFLICT (paper_external_code) DO UPDATE problem_url, solution_url, source_kind, link_scope` | Registers a PENDING work source; does not run ingestion. |
| `pdf_pipeline.py reconcile` | `pipeline.pdf_source` | Updates by `paper_external_code` | Derives download/parse status and question counts from filesystem artifacts. |
| `pdf_pipeline.py ingest` | `pipeline.run`, `pipeline.work_item`, `pipeline.pdf_source`, `core.competition_edition`, `core.paper`, `core.problem`, `core.problem_image`, `core.solution` | Work item key `(run_id,'pdf_paper',paper_external_code)`; paper/problem/solution/image keys as above | Marks paper INGESTED and records counts. |
| REST retry paper | `pipeline.pdf_source` | Updates by `paper_external_code` | Only failed stage columns reset to PENDING; succeeded stage columns are preserved. |
| REST status | `pipeline.pdf_source`, `pipeline.run`, `pipeline.work_item`, `pipeline.graph_projection` | read-only | Joins latest end-to-end batch item by started time. |

Parameterized example (documentation only):

```sql
-- Write path shape used by paper registration; values are placeholders.
INSERT INTO pipeline.pdf_source
  (paper_external_code, competition_external_code, crawl_dir, problem_url, solution_url, source_kind, link_scope)
VALUES (:paper_external_code, :competition_external_code, :crawl_dir, :problem_url, :solution_url, :source_kind, :link_scope)
ON CONFLICT (paper_external_code) DO UPDATE
  SET problem_url = EXCLUDED.problem_url,
      solution_url = EXCLUDED.solution_url,
      source_kind = EXCLUDED.source_kind,
      link_scope = EXCLUDED.link_scope,
      updated_at = now();
```

## Pedagogy authoring/review/publication

| Path | Tables touched | Idempotency/protection |
|---|---|---|
| `import_pedagogy.py validate` | read-only DB checks when needed | Validates manifest schema, keys, cycles; dry-run uses read-only transaction. |
| `import_pedagogy.py import` | `knowledge.skill`, `skill_concept`, `skill_relation`, `problem_skill`, `problem_pedagogy` | Locks authoring tables; upserts by table natural/composite key; validates references and cycles before import. |
| Automatic metadata trigger | metadata tables + `knowledge.metadata_approval_event` | Trigger changes PENDING to REVIEWED unless human review context is set; protects human decisions/rejections from automatic writers. |
| Admin queue/history | metadata tables, review/publication/job tables | read-only inventory plus fingerprint. |
| Admin review/bulk/approve-starter | `knowledge.*` metadata table, `knowledge.pedagogy_review_event` | Locks authoring tables; checks expected SHA-256 revision; records before/after snapshots; validates reviewed dependencies/cycles. |
| Admin edit | selected editable metadata columns and `knowledge.pedagogy_review_event` | Requires expected revision; sets `mathbank.human_review='on'`, protecting edited rows from automatic replacement. |
| Admin publish | Neo4j graph plus `knowledge.pedagogy_publication`, `knowledge.enrichment_job.published_at`, `relationship_enrichment_job.published_at` | Checks source fingerprint; projects corpus nodes if target problems are missing; projects classification and pedagogy; then records publication. Cross-store transaction is not atomic. |
| Admin reclassify | `knowledge.enrichment_job`, automatic metadata tables; may later publish | Calls model-backed enrichment when invoked; docs task did not execute. |

Review DML example:

```sql
-- Shape only: actual code validates key shape, locks tables, and records snapshots.
UPDATE knowledge.problem_skill
   SET review_status = :status
 WHERE problem_id = :problem_id
   AND skill_id = :skill_id
   AND relation_type = :relation_type
   AND role = :role;
INSERT INTO knowledge.pedagogy_review_event
  (entity_kind, entity_key, before_snapshot, after_snapshot, reviewer, review_note)
VALUES (:kind, CAST(:key_json AS jsonb), CAST(:before AS jsonb), CAST(:after AS jsonb), :reviewer, :note);
```

## Automatic enrichment and relationship enrichment

These paths are implemented but model-backed. They are documented from source only.

| Path | Tables touched | Idempotency / retry |
|---|---|---|
| `enrichment.enrich_problem` | `knowledge.enrichment_job`, `knowledge.skill*`, `knowledge.problem_skill`, `knowledge.problem_pedagogy`, `knowledge.problem_concept`, `knowledge.problem_technique` | Claims by `problem_id`; stale `IN_PROGRESS` older than 10 minutes can be reclaimed; attempts increment; failure writes `FAILED` + error. |
| `persist_metadata(force=False)` | metadata tables via `import_pedagogy.import_manifest`; problem concepts/techniques | `SET LOCAL mathbank.automatic_writer='on'`; manifest upserts; problem concept/technique inserts `ON CONFLICT DO NOTHING`. |
| `persist_metadata(force=True)` | automatic rows for a problem | Deletes only automatic, non-rejected `problem_skill` and problem concept/technique rows before reinsert; human/rejected rows are preserved. |
| `relationship_enrichment.enrich_relationships` | `knowledge.relationship_enrichment_job`, `skill_relation` or `concept_relation` | Claim by `(entity_kind, anchor_id)`; stale/failed/due rows retried; unchanged completed catalog only updates `updated_at`; accepted proposal inserts `ON CONFLICT DO NOTHING`. |
| Relationship job failure | `knowledge.relationship_enrichment_job` | Records validation failures in `evidence` and error in `last_error`. |

## Vector/embedding DML

| Path | Tables touched | Idempotency / notes |
|---|---|---|
| `embed_corpus.py ensure_model_and_profile` | `search.embedding_model`, `search.preprocessing_profile` | model unique `(provider, model_name, model_revision)`; default profile unique `(name, version)`. |
| `build_representations_and_chunks` | `search.representation`, `search.chunk` | Supersedes ACTIVE representations with different hash; inserts/reuses current by unique representation key; chunks upsert by `(representation_id, chunk_ordinal)`. |
| `embed_pending_chunks` | `pipeline.run`, `search.embedding`, `search.embedding_job` | Selects chunks lacking embedding for model; inserts/updates embedding by `(chunk_id, embedding_model_id)`; job by `(representation_id, embedding_model_id, input_hash)`; records failures per chunk. Calls OpenAI when run. |
| `embed_corpus.py index` | HNSW index on `search.embedding` | DDL index creation, not regular DML. |
| `embed_textbook_steps.py build` | `search.representation`, `search.chunk`, temporary `pedagogy_vector_stage`, package report on backfill | Uses deterministic UUIDv5 surrogate for text pedagogy IDs; supersedes no-longer-eligible step/item/taxonomy reps; also stages one `TAXONOMY_NODE` representation per `pedagogy.taxonomy_node` (`problem_id` NULL; text = name + parent path + chapter/section + taxonomy-edge neighbours capped at 15; `metadata.taxonomy_node_id`; CONCEPT/SUBCONCEPT/SKILL nodes fill their own hard-filter column); chunks carry hard-filter taxonomy columns. Build itself has no paid calls. |
| `embed_textbook_steps.py backfill` | same plus `search.embedding`, `search.embedding_job`, `ingest.content_package.report` | Calls embedding provider through `embed_corpus.embed_pending_chunks`; records reconciliation report. |

Step/item/taxonomy eligibility: every `pedagogy.taxonomy_node`; `pedagogy.solution_step.publication_status='PUBLISHED'`; learning items require `review_status='APPROVED'`, `student_visible`, and `no_proof`. Phase 10 stores how learning items became eligible using `approval_method`/`approved_at`.

## Textbook package import (`import_textbook_package.py`)

| Stage | Tables touched | Keys/idempotency |
|---|---|---|
| Register package | `ingest.content_package`, `ingest.package_file`, `ingest.package_status_event` | Package unique `(package_name, package_version, manifest_hash)`; package files keyed `(content_package_id, relative_path)`. |
| Stage/validate | `ingest.staging_row`, `ingest.import_conflict` | Deletes old staging rows for package before COPY; conflicts upsert by `(content_package_id, entity_type, external_id, conflict_type)`. |
| Taxonomy bridge | `pedagogy.taxonomy_node`, `pedagogy.taxonomy_edge`, `knowledge.concept`, `knowledge.skill`, `knowledge.technique` as needed by import plan | Upsert helper COPYs to temp table and avoids rewriting unchanged rows. Knowledge-lock order matches pedagogy importer to avoid deadlocks. |
| Book/chapter/problem/solution | `pedagogy.source_book`, `chapter_section`, `core.competition`, `core.competition_edition`, `core.paper`, `core.problem`, `core.solution`, `problem_source_ref`, `solution_source_ref` | Uses source book/problem/solution IDs mapped to canonical problem/solution keys. Textbooks use nullable edition year and edition labels. |
| Solution DAG | `pedagogy.solution_part`, `solution_step`, `solution_step_dependency` | Text IDs with occurrence suffixes where source IDs repeat; step dependency cycles rejected in plan before import. |
| Learning items/diagrams | `pedagogy.learning_item`, `learning_item_step_anchor`, `diagram`, optionally `core.problem_image` for student-visible problem diagrams | Visibility constraints prevent unapproved items from being student-visible; solution-hidden diagrams remain in `pedagogy.diagram`. |
| Reconcile/report | `ingest.reconciliation`, package status/report | Counts created/updated/unchanged/rejected/conflicts and transitions package status to `POSTGRES_COMPLETE` or failure. |
| Operator auto-approval (`sql/ops/approve_learning_items_auto.sql`, Makefile `textbook-approve-learning-items-remote`) | `pedagogy.learning_item` | DML-only operator action. Updates only `PENDING_REVIEW` rows that are `no_proof`, have nonblank question text, and have valid MCQ choices/correct answer or subproblem seed. Sets `review_status='APPROVED'`, `student_visible=true`, `approval_method='automatic'`, `approved_at=now()`, `updated_at=now()`. Human `REJECTED`/`NEEDS_REVISION` decisions are not overwritten. |

## Graph projection DML in Postgres

Projectors write Neo4j and record Postgres run rows:

- `project_from_postgres.py`: inserts `pipeline.graph_projection(graph_name='corpus_graph', status='IN_PROGRESS')`, then updates `COMPLETED` with node/edge counts or `FAILED` with error.
- `project_textbook_steps.py`: inserts `pipeline.graph_projection(graph_name='textbook_step_graph')`, updates status/counts/error, and merges a `graph_projection` summary into `ingest.content_package.report`.

These are not atomic with Neo4j writes; a failure may require retry/reconciliation.

## Learner write paths

| REST/db function | Tables touched | Behavior |
|---|---|---|
| Register learner | `learner.student_profile` | Inserts email/password hash/name/display name; router pre-checks duplicate email and returns 409. No upsert. |
| Login | `learner.student_profile` | Reads by email, verifies bcrypt hash, updates `last_login_at` by `student_id`. |
| Submit attempt | `learner.attempt`, then mastery caches | Inserts attempt append-only; recomputes mastery for all concepts/techniques linked to problem. |
| Recompute concept/technique mastery | `learner.concept_mastery`, `learner.technique_mastery` | Reads all attempts for student+concept/technique; `INSERT ... ON CONFLICT DO UPDATE` score/count/last attempt/updated_at. |
| Read profile/attempts/mastery/improvement plan | `learner.*`, `core.*`, `knowledge.*` | Read-only; improvement plan calls problem lookup helpers. |

Attempt insert shape:

```sql
INSERT INTO learner.attempt
  (student_id, problem_id, is_correct, submitted_answer, time_spent_seconds, hint_count, source)
VALUES (:student_id, :problem_id, :is_correct, :submitted_answer, :time_spent_seconds, :hint_count, :source)
RETURNING attempt_id, attempted_at;
```


## Step-solving runtime write paths (`mathbank_rest/step_runtime.py`)

All route mutations run inside `engine.begin()` transactions. Student-facing mutations require a bearer JWT and only allow the token subject to access their own attempts. Mutations accept `Idempotency-Key`; if the key was used with the same operation/request hash, the stored JSON response is replayed from `learner.idempotency_record`; if the request hash differs, the runtime returns `IDEMPOTENCY_KEY_REUSED` (422). Mutating operations also require the caller's last `state_version`; stale versions return `STATE_VERSION_CONFLICT` (409). The runtime never returns canonical `pedagogy.solution_step.step_text` to students.

| Runtime function / route | Tables touched | Transaction and side effects |
|---|---|---|
| `start_attempt` / `POST /v1/students/{student_id}/problems/{problem_ref}/attempts` | `core.problem` read, `learner.idempotency_record`, `learner.solve_attempt`, `tutor.runtime_state`, `learner.event`, `learner.attempt_step_state`, `pipeline.outbox_event` | Resolves problem UUID or canonical code. Takes `pg_advisory_xact_lock(hashtext('solve:{student}:{problem}'))`. Reuses any open attempt; otherwise inserts next `attempt_number`, creates runtime state, emits `ATTEMPT_STARTED` and first `STEP_PRESENTED`, sets current step, writes outbox. Fails if no published solution steps exist. |
| `get_runtime` / `GET /v1/attempts/{attempt_id}` and `/runtime` | `learner.solve_attempt`, `tutor.runtime_state`, `core.problem`, `pedagogy.solution_step`, `pedagogy.solution_part`, `learner.attempt_step_state` | Read-only safe view: current step metadata, student-visible `goal`, own responses, redacted `last_evaluation`, timeline, and progress counts. Future locked steps reveal only opaque timeline metadata; completed steps expose `reference_text` as established solution history. |
| `submit_step_response` / `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/responses` | `learner.idempotency_record`, locked `solve_attempt`/`runtime_state`, `learner.attempt_step_state`, `learner.event`, `tutor.runtime_state`; after commit reads `pedagogy.solution_step` context and may call the evaluator before writing outcome state | Requires current step and matching `state_version`; first commits the student's response (`ATTEMPTED`, attempt count, `STEP_RESPONSE_SUBMITTED`, bumped version). Router then evaluates outside the row lock unless `evaluate=false`, applies `record_step_outcome` with the saved version, and returns `evaluation_status` `EVALUATED`, `PENDING` on a superseded/stale apply, or `UNAVAILABLE` when model/network grading failed after saving. Student-facing evaluation is filtered to result/verdict/feedback/redaction fields. |
| `request_hint` / `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/hint` | runtime/idempotency tables; after commit reads/writes `pedagogy.step_hint` through `step_tutor.get_or_create_hint` | Requires current step/version; increments `help_level_used` to max 5, emits `HINT_REQUESTED`, bumps version. The router then returns `hint_text`/`hint_source`: levels 1–4 are generated or read from the shared cache keyed by `(solution_step_id, hint_level, prompt_version)`; level 5 returns the canonical step as `REFERENCE_STEP` and is not cached. Any help prevents independent success by table CHECK/state logic. |
| `list_hints` / `GET /v1/attempts/{attempt_id}/steps/{step_id:path}/hints` | `get_runtime` read plus `pedagogy.step_hint` reads/cache inserts as needed | Restores already revealed hints for refresh/reload: determines the student's current `help_level_used` from the safe timeline, then returns levels `1..help_level_used`. Missing cached levels can be generated using the same leak-checked hint writer; 404 if the step is not part of the attempt. |
| `record_step_outcome` / `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/outcome` | locked runtime tables, `learner.attempt_step_state`, `learner.event`, `pipeline.outbox_event`, `tutor.runtime_state`, and on completion `learner.attempt` + `learner.solve_attempt` | Internal/admin-key route; actor must be `TUTOR`, `AGENT`, `SYSTEM` or `ADMIN`. Maps `SUCCESS/FAILED/SKIPPED` plus help level to final step state, stores full evaluator evidence in `last_evaluation` and the `STEP_EVALUATED` event payload, writes outbox, chooses next eligible step from published solution order and `DEPENDS_ON` prerequisites, presents it, or completes the attempt. Completion writes exactly one legacy `learner.attempt` with `source='step_runtime'` so existing mastery recomputation works. Calls Phase 9 diagnosis hooks inside a savepoint: open gap statuses may move based on the evaluated result, and repeated failed/currently high-help steps may be auto-diagnosed. Diagnosis hook failures are logged and do not block the outcome transaction. Router then calls `mastery.recompute_mastery_for_problem` when not replayed. |
| `diagnose_step` / `POST /v1/attempts/{attempt_id}/steps/{step_id:path}/diagnose` | locked runtime attempt, `pedagogy.solution_step`/dependency/taxonomy reads, learner step-state/history reads, optional `pedagogy.learning_item` and same-skill step reads, `pedagogy.gap_diagnosis`, `pedagogy.knowledge_gap`, `learner.event`, `pipeline.outbox_event` | Student-owned route. Scores deterministic gap hypotheses (local skill, predecessor-step skills, subconcept and concept prerequisites), computes an evidence fingerprint, reuses an existing diagnosis for identical evidence, otherwise inserts diagnosis and ranked hypotheses, emits `GAP_HYPOTHESIS_CREATED` and `GAP_DIAGNOSED`, writes outbox, and returns a redacted student view. Probe selection now prefers approved/student-visible learning items before same-skill practice steps. It does not change runtime mode, mastery or `state_version`; optional `DIAGNOSIS_LLM_RERANK` stores best-effort AI order/rationale in `gap_diagnosis.ai_rerank` without overwriting rule ranks. |
| `list_diagnoses` / `GET /v1/attempts/{attempt_id}/diagnoses` and admin variant | `learner.solve_attempt`, `pedagogy.gap_diagnosis`, `pedagogy.knowledge_gap` | Student route verifies ownership and returns redacted diagnosis views newest first; admin-key route returns full rows with failure modes, confidence and evidence. |
| `list_student_gaps` / `GET /v1/admin/students/{student_id}/knowledge-gaps` | `pedagogy.knowledge_gap` | Admin-key read across a student's hypotheses, optional exact status filter, limit clamped 1..500. |
| `admin_gap_overview` / `GET /v1/admin/knowledge-gaps` | `pedagogy.knowledge_gap`, `pedagogy.gap_diagnosis`, `learner.student_profile`, `learner.solve_attempt`, `core.problem`, latest `pedagogy.recovery_plan` | Admin-key read; returns status totals, top open targets, and recent hypotheses. Optional status filter and email-substring/student-UUID filter; includes latest recovery plan id/status per gap. |
| `create_plan` / `POST /v1/attempts/{attempt_id}/recovery-plans` | locked attempt/runtime rows, `pedagogy.gap_diagnosis`, `pedagogy.knowledge_gap`, `pedagogy.solution_step`, approved `pedagogy.learning_item`, `pedagogy.recovery_plan`, `pedagogy.recovery_plan_item`, `learner.attempt_step_state`, `learner.event`, `pipeline.outbox_event`, `learner.idempotency_record` | Student-owned route requiring fresh `state_version`; returns an existing active detour when already in recovery. Picks approved visible non-proof learning items for the target skill/subconcept, excludes the origin problem and cross-reference stubs, optionally adds a worked example, writes the full plan before presentation, marks the origin step `DETOURED`, sets runtime mode `RECOVERY`, emits `RECOVERY_PLAN_CREATED` and first `RECOVERY_ITEM_PRESENTED`. |
| `answer_recovery_item` / `POST /v1/recovery-plans/{plan_id}/items/{item_id}/responses` | recovery plan/item rows, locked attempt/runtime rows, `learner.event`, `pipeline.outbox_event`, `learner.idempotency_record`; reads learning item/problem context; subproblems may call evaluator before applying | Validates ownership/current item/version before grading. MCQs grade deterministically; theory items acknowledge; subproblems use the step evaluator outside the lock. Applying a result records student-safe and teacher evidence, emits submit/evaluate events, adapts by retry/advance/confirmation/alternate/branch, bumps `state_version`, may set plan `COMPLETED`/`EXHAUSTED`, and updates linked gap status to `RESOLVED` or `CONFIRMED`. |
| `leave_recovery` / `POST /v1/recovery-plans/{plan_id}/resume` and `/abort` | recovery family rows/items, locked attempt/runtime rows, origin `learner.attempt_step_state`, `learner.event`, `learner.idempotency_record` | Resume requires no active/suspended plan; abort ends open plan family as `ABORTED`. Both return to the exact origin step, clear `current_recovery_plan_id`, set mode `SOLVING`, mark return/skipped items, emit `RETURNED_TO_ORIGINAL_STEP` and `STEP_PRESENTED`. |
| `admin_plans` / `GET /v1/admin/recovery-plans` and detail | `pedagogy.recovery_plan`, `recovery_plan_item`, `learner.student_profile`, `core.problem`, `pedagogy.solution_step` | Admin-key read-only summaries/details; detail exposes teacher evidence stored in item `last_result`. |
| `submit_attempt` / `POST /v1/attempts/{attempt_id}/submit` | locked runtime tables, `learner.event`, `tutor.runtime_state`, `learner.idempotency_record` | Student submits early; sets `solve_attempt.status='SUBMITTED'`, `submitted_at`, emits `ATTEMPT_SUBMITTED`, sets runtime mode `REVIEW`, bumps version. It does not create the legacy outcome row; completion does. |
| `list_events` / `GET /v1/students/{student_id}/events` | `learner.event` | Read-only event feed for the student's own events, optionally filtered by solve attempt; limit clamped 1..500. |
| `similar_steps_for_step` / `GET /v1/solution-steps/{step_id:path}/practice` | `pedagogy.solution_step`, `search.chunk`, `search.representation`, `search.embedding`, `search.embedding_model`, step-search detail queries | Authenticated read. Uses the anchor step's stored active embedding as the query vector, so it does not make a paid embedding call. Falls back to lexical-only when no embedding is available. Excludes the anchor problem, optionally filters to same skill, never returns step text. |
| `list_problem_diagrams` / `GET /v1/problems/by-code/{code}/diagrams` | `core.problem`, `core.problem_image` | Public read of problem-statement diagram image IDs/ordinals for the solve workspace; does not expose solution-hidden `pedagogy.diagram` rows. |
| `get_problem_image` / `GET /v1/problem-images/{image_id}` | `core.problem_image` | Public file response for a stored problem image. Resolves `local_path`, requires an existing file under the repository root, and returns 404 otherwise; no DB write. |

Runtime idempotency shape:

```sql
INSERT INTO learner.idempotency_record (student_id, idempotency_key, operation, request_hash, response)
VALUES (:student_id, :key, :operation, :request_hash, CAST(:response_json AS jsonb));
```

Append-only event shape:

```sql
INSERT INTO learner.event
  (student_id, solve_attempt_id, event_type, actor_type, solution_step_id, payload, idempotency_key)
VALUES (:student_id, :solve_attempt_id, :event_type, :actor_type, :solution_step_id,
        CAST(:payload_json AS jsonb), :idempotency_key);
```

Phase 8 hint-cache read/write shape:

```sql
-- Read shared cached hints before model generation.
SELECT hint_text
  FROM pedagogy.step_hint
 WHERE solution_step_id = :solution_step_id
   AND hint_level = :hint_level
   AND prompt_version = :prompt_version;

-- Cache generated/fallback levels 1..4. Concurrent writers are harmless.
INSERT INTO pedagogy.step_hint (solution_step_id, hint_level, prompt_version, hint_text, model)
VALUES (:solution_step_id, :hint_level, :prompt_version, :hint_text, :model)
ON CONFLICT DO NOTHING;
```


Phase 9 gap-diagnosis write/reuse shape:

```sql
-- Reuse protects idempotency by evidence, independent of HTTP Idempotency-Key.
SELECT gap_diagnosis_id
  FROM pedagogy.gap_diagnosis
 WHERE solve_attempt_id = :solve_attempt_id
   AND solution_step_id = :solution_step_id
   AND evidence_fingerprint = :evidence_fingerprint;

INSERT INTO pedagogy.gap_diagnosis
  (student_id, solve_attempt_id, solution_step_id, trigger, recommended_action,
   evidence_fingerprint, evidence, probes, diagnoser_version)
VALUES (:student_id, :solve_attempt_id, :solution_step_id, :trigger, :recommended_action,
        :evidence_fingerprint, CAST(:evidence_json AS jsonb), CAST(:probes_json AS jsonb), :version);

-- Optional, best-effort AI re-rank; rule ranks in knowledge_gap.rank stay unchanged.
UPDATE pedagogy.gap_diagnosis
   SET ai_rerank = CAST(:ai_rerank_json AS jsonb)
 WHERE gap_diagnosis_id = :gap_diagnosis_id
   AND ai_rerank IS NULL;

UPDATE pedagogy.knowledge_gap
   SET status = :new_status,
       status_reason = :reason,
       status_changed_at = now(),
       resolved_at = CASE WHEN :new_status IN ('REJECTED', 'RESOLVED') THEN now() END
 WHERE knowledge_gap_id = :knowledge_gap_id;
```

Phase 10 recovery-plan write shape:

```sql
INSERT INTO pedagogy.recovery_plan
  (student_id, solve_attempt_id, origin_problem_id, origin_step_id,
   gap_diagnosis_id, knowledge_gap_id, trigger, target_skill_id,
   target_subconcept_id, target_label, mastery_policy, planner_version)
VALUES (:student_id, :solve_attempt_id, :origin_problem_id, :origin_step_id,
        :gap_diagnosis_id, :knowledge_gap_id, :trigger, :target_skill_id,
        :target_subconcept_id, :target_label, CAST(:policy_json AS jsonb), :planner_version)
RETURNING recovery_plan_id;

INSERT INTO pedagogy.recovery_plan_item
  (recovery_plan_id, ordinal, stage, item_kind, learning_item_id, worked_step_id, is_transfer, required)
VALUES (:recovery_plan_id, :ordinal, :stage, :item_kind, :learning_item_id, :worked_step_id,
        :is_transfer, :required);

UPDATE tutor.runtime_state
   SET current_recovery_plan_id = :recovery_plan_id,
       current_mode = 'RECOVERY',
       state_version = state_version + 1,
       updated_at = now()
 WHERE solve_attempt_id = :solve_attempt_id;
```

`step_tutor.load_step_context` reads the problem statement, current canonical step, previous published steps, latest student response and help level. `evaluate_step` is read-only until the router applies its returned verdict through `record_step_outcome`; `sanitize_feedback` redacts student feedback that copies secret step text. `get_or_create_hint` leak-checks levels 1–3, retries once with stricter wording, then falls back to templates if needed.

## Step → technique derivation (`mathbank-db/etl/derive_step_techniques.py`, migration 017)

| Operation | Tables | Behavior |
|---|---|---|
| Rule-tier upsert | `pedagogy.solution_step_technique` | `INSERT … VALUES (…, 'APPROVED', 'automatic', now()) ON CONFLICT (solution_step_id, technique_node_id) DO UPDATE` **only when** the existing row is not `HUMAN`, not `REJECTED`, not an `LLM` row being replaced by a non-rule source, and the values actually differ (no churn on re-run). |
| Outcome log | `pedagogy.solution_step_technique_run` | Upsert on `(solution_step_id, derivation_version)` with `TAGGED` / `NO_MATCH` / `NO_PROBLEM_TECHNIQUE` and candidate ids. |
| Prune | `pedagogy.solution_step_technique` | Deletes `RULE_%` rows of the selected `--book` that the current run no longer produces (temp table `_keep` loaded by `COPY`); never touches `HUMAN`, `LLM` or `REJECTED` rows. |
| Paid tier | same | `--llm --max-calls N` only; writes `source_type='LLM'`. Not run. |

Scope is one book per run (default the Prasolov book); other corpora have no `solution_step` rows. Graph follow-up: `project_textbook_steps.py` reads `APPROVED` rows into `(:SolutionStep)-[:USES_TECHNIQUE]->(:Technique)`; diagnosis reads them in `step_diagnosis.py`.

## Outbox consumers and lifecycle jobs (`mathbank_rest/outbox_worker.py`, migration 018)

| Operation | Tables | Behavior |
|---|---|---|
| Claim batch | `pipeline.outbox_event`, `pipeline.outbox_consumption` | Selects events of the consumer's types with no consumption row for that `consumer_name`, `ORDER BY created_at … FOR UPDATE OF o SKIP LOCKED`. |
| `learner_analytics` | `analytics.learner_daily_activity` | `INSERT … ON CONFLICT (student_id, activity_date) DO UPDATE SET <counter> = <counter> + 1` (UTC day of the event); skipped when the student no longer exists. |
| `projection_requests` | `pipeline.projection_request` | Maps `CONTENT_PACKAGE_IMPORTED`, `SOLUTION_STEP_CHANGED`, `LEARNING_ITEM_PUBLISHED`, `LEARNING_ITEM_WITHDRAWN` to targets; `ON CONFLICT (target, scope_type, scope_id) WHERE status='PENDING' DO NOTHING` coalesces. |
| Mark consumed | `pipeline.outbox_consumption` | `INSERT … ON CONFLICT DO NOTHING` in the **same transaction** as the side effect, so replays are no-ops. |
| Stale attempts (`step_runtime.abandon_stale_attempts`) | `learner.solve_attempt`, `pedagogy.recovery_plan`, `learner.event`, `pipeline.outbox_event` | Attempts `IN_PROGRESS` with no event for N days (`FOR UPDATE … SKIP LOCKED`) → `ABANDONED`; open plans → `ABORTED` with `ended_at`; appends `ATTEMPT_ABANDONED` event + outbox row. |
| Queue drain (`mathbank-db/etl/run_projection_requests.py`) | `pipeline.projection_request` | After `make textbook-graph-remote` succeeds, `UPDATE … SET status='DONE', completed_at=now(), completed_by=…` for graph targets; embedding targets are only listed unless `--allow-paid`. |

## Admin import / reconciliation / DAG review (`mathbank_rest/db/import_admin.py`, migration 019)

Every write runs in one `engine.begin()` transaction and appends one `ingest.admin_review_action` row (`before_state`/`after_state` JSON, `note`, `actor`). The audit table is append-only (trigger).

| Operation | Tables | Behavior |
|---|---|---|
| Conflict decision | `ingest.import_conflict` | Sets `decision` (`KEEP_EXISTING`/`ACCEPT_INCOMING`/`MERGE_MANUALLY`), `decided_at`, `resolution_status='RESOLVED'`. **Recorded only**; the data change happens on the next re-import or DAG edit. |
| Projection request | `pipeline.projection_request` | Insert with `requested_by`; coalesces on the open-request index. |
| Learning-item review | `pedagogy.learning_item`, `pipeline.outbox_event` | `FOR UPDATE`, then sets `review_status`, `student_visible = (status='APPROVED')`, `approval_method='human'`, `approved_at`; emits `LEARNING_ITEM_PUBLISHED` or `LEARNING_ITEM_WITHDRAWN` only when visibility/status changed. |
| Step edit | `pedagogy.solution_step`, `pipeline.outbox_event` | Updates skill / checkpoint fields, sets `admin_edited_at`; emits `SOLUTION_STEP_CHANGED`. Re-import skips rows with `admin_edited_at` (`import_textbook_package.py` guard). |
| Dependency upsert / retype | `pedagogy.solution_step_dependency` | Both steps must belong to the same problem; `DEPENDS_ON` is rejected with 409 if a recursive CTE over non-rejected `DEPENDS_ON` edges finds a cycle; a type change deletes the old-type row then upserts with `approval_method='human'` (importer guard `approval_method IS DISTINCT FROM 'human'`); emits `SOLUTION_STEP_CHANGED` for the target step. |
| Dependency reject | `pedagogy.solution_step_dependency` | `review_status='REJECTED'`, `approval_method='human'`; the projector excludes and prunes it; emits `SOLUTION_STEP_CHANGED`. |
| DAG review | `pedagogy.solution_dag_review` | `INSERT … ON CONFLICT (solution_id) DO UPDATE` (status, note, reviewer, time). |

Illustrative read (documentation only, synthetic placeholder):

```sql
-- READ: audit history for one problem DAG
SELECT action, note, created_at FROM ingest.admin_review_action
 WHERE target_type = 'SOLUTION_DAG' AND target_id = :problem_id
 ORDER BY created_at, action_id;
```

## Live classroom command path (`mathbank_rest/live_runtime.py`, migration 020)

| Operation | Caller | Tables / effect | Idempotency / conflict |
|---|---|---|---|
| Create session | `POST /v1/live/sessions` → `create_session` | Requires an APPROVED/PUBLISHED plan. INSERT `live.session` (topics snapshot, random `join_code`), INSERT `live.topic_run` per topic, INSERT the creator into `live.participant` as INSTRUCTOR (`ON CONFLICT DO NOTHING`), and emit `session.created`. | A new row on every call. |
| Join | `POST /v1/live/sessions/join` → `join_session` | INSERT `live.participant` (`student:{uuid}`, role STUDENT, `student_id`); emit `participant.joined`. | `ON CONFLICT (live_session_id, participant_id) DO UPDATE SET last_seen_at` → a rejoin is safe. |
| Any command | `execute_command` (all live mutations, gateway ops, AI tutor) | 1) SELECT `live.command_receipt` by `(session, client_command_id)`; a hit returns the stored result plus `duplicate: true`. 2) `SELECT … FOR UPDATE` the session row. 3) SAVEPOINT. 4) `_authorise` (role/command matrix, takeover/lock). 5) Version check for non-student actors (`expected_session_version`; AI must always send it). 6) `_dispatch` writes. 7) `emit`. 8) The savepoint commits; on a `LiveError` it rolls back. 9) INSERT `live.command_receipt` with status ACCEPTED or REJECTED. | The receipt PK makes retries exactly-once. A rejected command still stores a REJECTED receipt and leaves no partial writes. |
| `emit` | All accepted commands | UPDATE `live.session` `last_sequence += 1`, plus `state_version += 1` when `bump`. INSERT `live.session_event` (monotonic `sequence`, envelope fields). INSERT `pipeline.outbox_event` (`event_type='LIVE_EVENT'`, `aggregate_type='live_session'`, payload `{event_type, sequence, event_id}` only). | Same transaction as the command. The append-only trigger blocks UPDATE of events. |
| Transition / pause / resume / overrides | `_dispatch` | UPDATE `live.session` (topic index, status, timers, control mode, `agent_locked`, `extension_seconds`). UPDATE `live.topic_run` (ACTIVE/DONE/SKIPPED, `actual_seconds`). INSERT/UPDATE `live.takeover` (the partial unique index enforces one active takeover per scope). Takeover/lock marks PROPOSED `live.recommendation` rows STALE. | Session row lock plus version check. |
| Activities | `_dispatch` / `activity_definition` | INSERT `activity.definition` and `activity.instance`. UPDATE instance status CLOSED/REVEALED. Reveal also stores a `POLL_RESULT` widget spec and INSERTs a `POLL_BRANCH` recommendation (≥0.8 CONTINUE, ≥0.5 REINFORCE, else PREREQUISITE). | Responses use `ON CONFLICT (activity_instance_id, participant_id) DO UPDATE`, so a resubmit while OPEN replaces the earlier answer. |
| Student signals | `_dispatch` | `MARK_CONFUSED` UPDATEs `live.participant.confused`. `QUESTION_ASK`/`HINT_REQUEST`/`WIDGET_INTERACT` only emit INSTRUCTOR-audience events. | Through the receipt. |
| Widgets in session | `store_widget_spec`, `_dispatch` | Validate, then INSERT `visual.widget_spec` (lifecycle VALIDATED, `content_hash`, `expires_at = now()+1 day` for EPHEMERAL). Show/state/hide upsert `visual.widget_state` (`ON CONFLICT (live_session_id, widget_instance_id)`), set `visible`, increment `state_version`, and UPDATE spec lifecycle to SHOWN. | Invalid specs raise 422 before any write. |
| Recommendations | `propose_ai_action`, NL compiler, `decide` | INSERT `live.recommendation` (`based_on_version`). AUTO_APPLY actions run through `execute_command` when AI_ACTIVE. A decision UPDATEs status ACCEPTED/REJECTED; accepting runs the action as a command. A version mismatch marks it STALE. | A decided recommendation returns 409 `RECOMMENDATION_DECIDED`. |

## Authoring write paths (`mathbank_rest/authoring.py`, migration 020)

| Operation | Tables / effect | Guards |
|---|---|---|
| Create plan | INSERT `authoring.presentation_plan` (DRAFT) plus `plan_topic` rows. | Validation 422 `INVALID_PLAN`. |
| Replace topics / timing | `_write_topics`: DELETE all `plan_topic` rows for the plan, then INSERT the new ones (the deferred unique ordinal allows reorder). UPDATE plan limits. | The plan is read `FOR UPDATE`. App-level 409 `PLAN_IMMUTABLE` plus the DB trigger `guard_published_topic`. |
| Approve / publish | UPDATE status APPROVED/PUBLISHED with timestamps. Publish first UPDATEs the previous PUBLISHED plan with the same `plan_key` to SUPERSEDED (the trigger allows only this transition). | 409 `NOT_APPROVED`. |
| New version | INSERT a copy of the plan (version+1, `parent_plan_id`) and its topics as DRAFT. | — |
| Chat / patches | INSERT `chat_session`, `chat_message` (ADMIN and ASSISTANT rows), `proposed_patch` (PROPOSED, operations/impact/validation). A decision UPDATEs the patch: APPLY and MODIFY (with replacement operations; 422 `INVALID_PATCH` if none) → APPLIED. All operations are applied atomically to the DRAFT plan, or to a new draft version when the plan is PUBLISHED/SUPERSEDED, and `result_plan_id` is set. REJECT → REJECTED. ASK_FOR_ALTERNATIVE → SUPERSEDED plus a new `DETERMINISTIC_ALTERNATIVE` patch. | Patch row `FOR UPDATE`. 409 `PATCH_DECIDED`. |

Test cleanup only: `SET authoring.allow_purge = 'on'` bypasses both guard triggers in that DB session. Application code never sets it.

## Widget spec review (`routers/fluid.py`)

| Operation | Tables / effect |
|---|---|
| `POST /v1/widgets/specs` | `store_widget_spec` without a session (gallery spec). |
| `POST /v1/widgets/specs/{id}/review` | `SELECT … FOR UPDATE`, then UPDATE `lifecycle` (NOMINATE → PROMOTION_CANDIDATE; PROMOTE → PROMOTED_TO_TEMPLATE with persistence STATIC; REJECT → REJECTED), `reviewed_by`, `reviewed_at`. |
| `POST /v1/widgets/validate`, `/generate`, `/v1/tutor/format-math` | Read-only (no DB writes). |

`visual.asset` has no writer. No cleanup job yet deletes expired EPHEMERAL specs or ended sessions (NYI, doc 20 §6).

## Private multimodal attempts (`attempt_media`, migration 021)

| Operation | Caller and transaction | Tables / behavior | Idempotency, protection and side effects |
|---|---|---|---|
| Create submission | Student `POST /v1/attempt-media/submissions`; one `engine.begin()` transaction. Resolves `problem_ref` by canonical code or UUID. | Inserts `attempt_media.submission`, then returns an ownership-scoped snapshot. | Non-students get 403; unknown problem 404. Submissions and all evidence are student-owned; non-owner lookup is masked as 404. |
| Upload original | Student/admin route actor, expected `transcription_version`, bounded request stream. Bytes are validated and stored before a second, locked version/owner check and metadata transaction. | Inserts `media_asset`; increments transcription version; appends per-submission event and `pipeline.outbox_event`. Maximum 10 active originals; backend accepts PNG/JPEG/PDF and WAV/MP3/MP4/WebM audio or MP4/WebM video, with signature checks, at most 10 PDF/image pages and 120 seconds audio/video. | Object-store write and Postgres transaction are not atomic. On DB failure the route attempts to remove only its unreferenced object. A stale expected version returns 409. |
| Process/transcribe | Student or admin makes the explicit `POST .../process` request. It records a processing state/event in a short transaction, performs file decode and provider work outside the DB transaction, then stores the result in a new transaction. | Inserts versioned `transcription_candidate`, `evidence_region`, `step_candidate` and `step_candidate_evidence` rows; updates status and emits readiness/progress events. Final direction is the official direct OpenAI endpoint and shared project credential loader used by `mathbank-agent`; Gateway is only used if explicitly selected through `MATHBANK_RUNTIME_AI_PROVIDER`. Runtime follows service `MATHBANK_AGENT_MODEL` (`openai/gpt-4o-mini` default; root value when synchronized), with explicit `MATHBANK_RUNTIME_AI_MODEL` override. No model setting or provider choice implies inference success. Timestamped speech uses direct OpenAI `whisper-1`. | Processing does not auto-approve or grade. Provider/decode errors persist FAILED plus a bounded error code; uploads remain for manual review. Expected version checks prevent stale commits. |
| Edit transcript | Student `PUT .../transcription`, `PATCH .../transcription/steps/{step_id}`, or adjacent-step `merge` / `split`, with `expected_version`. | Adds a new candidate version and associated regions/steps/evidence links; old candidates are retained. Status becomes `STUDENT_REVIEWING`. | Pydantic enforces ordered ordinals, typed step/alignment vocabularies, bounds and nonempty steps. Evidence must refer to an asset in this submission and cannot be reassigned/rewritten under an existing region UUID. A stale version returns 409. |
| Approve current transcript | Student `POST .../approve`, in one transaction after owner/version validation. | Writes exactly one `learner.attempt` (`source='multimodal_approved'`, text assembled from the current approved steps, `is_correct=NULL`) and an `attempt_media.approval` linking that attempt to the immutable candidate version; advances `approved_version`; appends event/outbox metadata. | Existing approval for `(submission_id, transcription_version)` is returned rather than duplicated. Empty transcript is rejected. NULL correctness is excluded from mastery queries/calculation and is not an incorrect answer. |
| Analyze approved work | Explicit `POST .../analyse`; only the current transcription must already be approved. Published canonical steps and reviewed dependencies are read before the provider call. | Appends AI `step_assessment` versions and events, then marks READY. The assessment must cover the candidate step inventory, cite linked evidence and align only to published steps for the same problem. | Low-confidence transcription steps require `UNCERTAIN`. AI retries do not overwrite an instructor assessment; assessment rows are versioned. Failure leaves the approved learner attempt intact. Uncertainty/incorrectness here does not update mastery. |
| Instructor override | Admin-role `POST .../override`; one assessment insert for the selected current step. | Appends `source='INSTRUCTOR'`, actor, reason, next action and evidence references to `step_assessment`; event/outbox contain only identifiers and version metadata. | No AI write path can replace an instructor decision. Assessment history is visible to admins; students see current-version assessments, not full history. |
| Read events/snapshot | Student owner or admin; read-only snapshot/sequence query. | Reads submission metadata, current candidate, approved versions, assessments and up to 500 ordered `attempt_media.event` rows after the requested cursor. | General outbox contains only submission UUID, sequence and transcription version; media bytes, transcript text, answers and assessment prose are not placed there. |
| Purge raw media | Owner/admin DELETE; locks submission and refuses while transcription/alignment/critique is running. | Deletes the selected asset and direct derivative object(s), sets `purged_at`, and appends a purge event. Evidence/transcript/approval metadata remains. | Object deletion and SQL update cannot be one atomic transaction. Purging preserves the approved learner attempt and does not convert it to an outcome. There is no REST delete-submission operation. |

For video processing, `ffprobe` first checks whether an audio stream exists. When present, FFmpeg extracts mono 16 kHz audio for the speech transcription stage; when absent, that stage is skipped while video keyframe processing continues. `ffmpeg` selects keyframes using its timestamp filter and `showinfo`; each generated keyframe is paired with the exact `pts_time` reported by FFmpeg as its temporal evidence timestamp. The runtime does not infer timestamps from a nominal frame rate. The deployment operator reports synthetic video fixtures with and without audio, including timestamped keyframes, passing; these tests do not establish provider inference success. This behavior changes no REST contract or database schema.

The object-store adapter defaults to private S3-compatible storage configured with `AWS_ENDPOINT_URL_S3`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` (optional session token and bucket). `MATHBANK_OBJECT_BUCKET` is canonical; `AWS_BUCKET_NAME` is accepted only as an alias when the canonical name is absent. If both are nonempty and differ, sanitized configuration validation fails rather than allowing REST/web bucket divergence. An explicitly present empty canonical process-environment setting is retained rather than replaced by the alias/default and fails bucket validation. When neither name is configured, the bucket defaults to `mathbank-runtime`. Endpoint, region and access/secret key setting names are unchanged. Filesystem storage is an explicit development/offline backend. Neither Neon Auth nor AI Gateway credentials/URLs are storage configuration. Object bytes are never served from public or presigned URLs: REST checks owner or published-bundle access and returns private/no-store content. The documentation refresh made no live storage call. Separately, the deployment operator reported on 2026-10-06 (UTC) that the private `mathbank-runtime` bucket had been created but an earlier smoke check failed with `ObjectStoreError`. Later operator-reported interface tests passed put/read/delete, unauthorized GET 403 and synthetic cleanup after bucket-alias handling was added. No new production calls were made; these exercised checks do not establish broader production end-to-end acceptance.

The deployment operator also reported migrations 021 and 022 applied to the explicitly selected Neon production target and synthetic rollback-only workflow checks passing for approval idempotence, NULL correctness handling, assessment-version invalidation, instructor override protection/retry behavior, ownership 404, low-confidence uncertainty and purge preserving approval. A later report says six media rollback-only Neon tests and one artifact Neon rollback-only workflow passed; the artifact test covered create/generate/publish/access/lexical and semantic search in 24.66 seconds with a supplied fake 1,536-dimensional vector. It used mocked object storage and no AI/provider call or real object bytes. Reported checks also include a focused REST offline suite with 184 passes (including voiced/silent-video normalization), 15 agent tool regression cases, successful web build, 25 focused frontend units, 17 mocked Playwright cases, and five private-event/credential-sync Node tests. Earlier distinct selections reported 132 offline passes and six live tests skipped, and 146 owned offline passes. Synthetic FFmpeg-video/timestamped-speech tests and Ruff were also reported passing. These are scoped operator reports, not an independent live schema comparison or production inference evidence.

On 2026-10-06 (UTC), final operator direction for new agentic runtime stages is to use the official direct OpenAI endpoint and the same shared project credential loader as `mathbank-agent`; Gateway inference is avoided unless explicitly selected. `MATHBANK_RUNTIME_AI_PROVIDER` defaults to `openai`, and `sync-neon-env` persists the selected provider into service environments while allowing a root-level override. Gateway configuration/credentials remain unchanged. The Gateway vision request failed with HTTP 403 over a billing-credit blocker; a subsequent direct OpenAI runtime request failed with HTTP 429 `insufficient_quota`. No successful inference or model tokens are reported; the user chose available tests rather than adding credits. Runtime credentials and explicit `OPENAI_API_BASE` / `OPENAI_BASE_URL` use the shared project OpenAI loader/client path. Runtime follows the service `MATHBANK_AGENT_MODEL` (`openai/gpt-4o-mini` default); root model settings apply when synchronized. An explicit `MATHBANK_RUNTIME_AI_MODEL` override is available and takes precedence; current source also accepts runtime-specific root/REST settings, so the effective deployed override is not independently verified here. Artifact-agent embeddings use the shared direct OpenAI client with `text-embedding-3-small` at 1,536 dimensions by default; profile/default configuration is not proof an embedding request succeeded. Speech continues to use direct OpenAI `whisper-1`.

## Declarative artifacts (`artifact_runtime`, migration 022)

| Operation | Caller and tables | Behavior and conflict/side-effect rules |
|---|---|---|
| Validate plan | `POST /v1/artifacts/validate`; read-only deterministic validation. | Checks supported subject/elements, IDs, geometry/domain constraints, equations/LaTeX allow-list, overlays/frames and output safety. It does not call a model or persist a result. |
| Request | `POST /v1/artifacts/requests`; student/staff actor, one SQL transaction. | Validates the plan and optional problem UUID before inserting `artifact_request` with owner, source and JSON spec. Owner-scoped GET masks another student's request as 404; staff can inspect it. |
| Generate | Admin-key `POST .../requests/{id}/generate`; one SQL transaction with deterministic CPU rendering and private object writes. | Creates bundle, generated asset metadata, per-asset metadata, overlays, annotations, frame manifest, lineage, validation result and search tags; updates request to GENERATED. Parent bundle must share the subject and determines next version. Repeated generation returns the existing request bundle (and can explicitly publish it). No generative model is called. |
| Validate saved bundle | `POST .../bundles/{id}/validate`; private bundle access rules apply. | Recomputes the deterministic source output, compares stored asset bytes and metadata, and reruns SVG/LaTeX checks. Staff validation appends `validation_result`; learner validation is read-only. |
| Publish | Admin-key `POST .../bundles/{id}/publish`; locks bundle, validates source and stored bytes, then updates bundle to `PUBLISHED` / `APPROVED`. | Invalid bundle is not published. Non-admin readers only see PUBLISHED bundles; admin can read drafts. |
| Read/render assets and frames | Authenticated GETs for bundle, asset list/content, frame manifest and individual frame SVG. | Asset bytes are fetched from private storage and verified against SQL SHA-256 and size; frames are deterministically rendered from validated source and checked against the stored manifest. Responses are private/no-store and use restrictive content headers. |
| Index | Admin-key `POST .../bundles/{id}/index`. | Requires exact source-text SHA-256 and configured provider/model/dimensions. Accepts a supplied nonzero vector or makes a provider call only when `generate_embedding=true`; upserts the single embedding row per bundle. Model and dimensions must match configured profile and vector length. |
| Search / similar | Authenticated POST lexical search, semantic search or bundle similarity. | Lexical search uses PostgreSQL simple-language FTS and filters. Semantic search requires an explicit vector or `generate_embedding=true`, matching profile and current indexed vectors; unavailable profile/index/provider returns `UNAVAILABLE`, never lexical fallback. Similarity reuses the source bundle's current embedding and excludes that bundle from results. |

Generation/validation/publication SQL is transactional, but it cannot atomically commit object-store writes. On a route exception the artifact API attempts cleanup of only objects written in that command. Embeddings are an explicit, mutable one-row cache keyed by bundle; bundle lineage, request specs, validation history and generated assets are separate records. Migration 022 defines no ANN vector index and no Neo4j artifact projection.

## Read paths and retrieval

| Module | Tables/read behavior |
|---|---|
| `db/queries.py` | Competition/problem/concept/technique lists, problem detail with solutions and tags, concept neighbors through recursive CTE, coverage and weak concept analytics. |
| `db/vector_search.py` | Hybrid semantic/lexical over `search.chunk`, `search.embedding`, active model/profile and core problem metadata; imports OpenAI lazily for query embeddings. |
| `db/hybrid_search.py` | Combines vector/lexical/graph retrieval for `/v1/search/problems`. |
| `db/step_search.py` | Step-level hard-filtered hybrid retrieval over `search.chunk` joined to `pedagogy.solution_step` and approved `pedagogy.learning_item`; `similar_steps_for_step` is exposed by `GET /v1/solution-steps/{step_id:path}/practice` and uses the step's stored embedding, avoiding a query embedding call. General semantic search helpers can still call the embedding provider lazily through `vector_search.embed_query`. |
| `db/textbook_admin.py` | Read-only admin corpus browser for one `book_code`. Covers `ingest.content_package`, `core.problem`/`core.solution`, `taxonomy.*`, `pedagogy.solution_part`/`solution_step`/`solution_step_dependency`/`learning_item`/`diagram` and `search.chunk`/`search.embedding` counts. It also issues read-only Cypher counts to Neo4j. `diagram_path` resolves `pedagogy.diagram.local_path` by `(book_code, source_diagram_id)` and refuses paths outside the repository root. No writes. |
| `pipeline_jobs.py` | Read-only status rollups across `pipeline.*`, `knowledge.*`, `core.*`, and graph projection status. |

## Agent sessions

`mathbank-agent/server.py` creates the `agent_sessions` schema if needed and passes a SQLAlchemy async engine to ADK `DatabaseSessionService` with search path set to that schema. Table DML is framework-owned; MathBank source only performs startup verification by listing sessions and then serves ADK routes.

### Agent session link and transcripts (`mathbank_rest/agent_transcripts.py`)

| Operation | Caller | Tables | Behaviour |
|---|---|---|---|
| Link (write) | `POST /v1/learner/agent-sessions` (student JWT), called by the web `POST /api/agent/session` after ADK session creation | reads `agent_sessions.sessions`; upserts `learner.agent_session_link` | Requires the ADK row `(app_name, user_id = student_id, id)` to exist, else 404. Upsert on `(agent_app_name, agent_session_id)`; on conflict updates `last_seen_at` and merges `context` (`||`) **only if** the existing row has the same `student_id`; otherwise no row is returned → 409 `SESSION_OWNED_BY_ANOTHER_STUDENT`. `created` derived from `xmax = 0`. Single transaction (`engine.begin()`). |
| List (read) | `GET /v1/learner/agent-sessions`, `GET /v1/admin/agent-sessions` | link ⋈ `learner.student_profile` ⟕ `agent_sessions.sessions`; correlated counts over `agent_sessions.events` | Excludes partial streaming events from counts; first user message as preview. Admin variant filters by e-mail substring or student UUID and adds `unlinked_count` (ADK sessions with no link). |
| Transcript (read) | `GET /v1/learner/agent-sessions/{id}/transcript`, `GET /v1/admin/agent-sessions/{id}/transcript` | link, `agent_sessions.sessions`, `agent_sessions.events` | Student: must own the link, else 404. Admin: link optional; ambiguous unlinked id across users → 400. Events ordered by timestamp; tool payloads truncated to 2,000 chars; timestamps emitted with UTC offset. |

Illustrative (documentation only, synthetic placeholders):

```sql
-- WRITE: idempotent link, refused for a different owner
INSERT INTO learner.agent_session_link
       (agent_app_name, agent_user_id, agent_session_id, student_id, surface, context)
VALUES (:app_name, :student_id_text, :session_id, :student_id, :surface, CAST(:context_json AS jsonb))
ON CONFLICT (agent_app_name, agent_session_id) DO UPDATE
   SET last_seen_at = now(), context = learner.agent_session_link.context || EXCLUDED.context
 WHERE learner.agent_session_link.student_id = EXCLUDED.student_id
RETURNING agent_session_link_id, (xmax = 0) AS created;
```

No code path updates or deletes ADK `agent_sessions` rows; learner deletion cascades only the link rows.
