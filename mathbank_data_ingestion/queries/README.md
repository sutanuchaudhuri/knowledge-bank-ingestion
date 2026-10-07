# PostgreSQL operator query library

**210 distinct read-only diagnostic templates**, Q001–Q210, in 11 category
files. No migrations, data mutations, model calls, downloads or database
connections were performed to create/validate this library. The JavaScript
utilities use only Node built-ins; they do not import application clients,
load credentials or contact services.

## Index

Each SQL block has a unique `-- Qnnn Title`, purpose/output explanation,
inputs, risk and `-- END Qnnn` marker. The ranges below are inclusive.
Find an individual ID in its linked category or use the single-query emitter.

| Category | Query IDs | Expected output / interpretation |
| --- | --- | --- |
| [Corpus hierarchy](01_corpus.sql) | Q001–Q020 | Competitions, editions, paper inventories, growth, natural-key anomalies, numbering holes and counts. NULL edition years can represent textbooks. |
| [Question quality](02_problem_quality.sql) | Q021–Q040 | Missing statements/answers/solutions/tags, duplicate hashes/text digests, OCR anomalies, metadata coverage and lexical matches. Heuristics are triage signals, not mathematical judgments. |
| [Provenance and diagrams](03_provenance_diagrams.sql) | Q041–Q060 | Book/chapter/page references, missing required figures, hidden-figure linkage audits, image integrity and source-key reconciliation. No document or image bytes are read. |
| [Solutions and step DAGs](04_solutions_steps.sql) | Q061–Q080 | Verification/revision inventories, blank solution bodies, step ordering, ownership mismatches, dependency review, stale approvals and progressive hint coverage. |
| [Knowledge and taxonomy](05_knowledge_taxonomy.sql) | Q081–Q100 | Concept/technique/skill use, trust provenance, low confidence, canonical bridge integrity, ambiguous topic names and technique derivation backlog. |
| [Pedagogy and learning items](06_pedagogy_learning.sql) | Q101–Q120 | Pedagogy dimensions, enrichment drift, visible exercise quality, approval bookkeeping, source-step anchors and practice-skill coverage. |
| [Imports and reconciliation](07_imports.sql) | Q121–Q140 | Package/staging/file/conflict inventories, stalled imports, status-log consistency, reconciliation arithmetic, review volumes and import latency. Raw staging/conflict/audit payloads are excluded. |
| [Pipeline and outbox](08_pipeline.sql) | Q141–Q160 | Run/work queues, expired leases, retries, PDF stage funnel, graph freshness, consumer backlog/latency, projection requests and enrichment publication debt. Never claims work or contacts a graph. |
| [Search and vector health](09_search_vectors.sql) | Q161–Q180 | Model/dimension checks, representation/chunk coverage and freshness, embedding jobs, index definitions, eligibility drift, lexical retrieval and zero-vector counts. Never generates vectors. |
| [Artifacts and storage](10_artifacts_storage.sql) | Q181–Q195 | Non-learner-owned artifact lineage/validation/asset health, aggregate storage footprint, table maintenance estimates, invalid indexes and extension availability. No object-store requests. |
| [Learner and feedback aggregates](11_learner_feedback_aggregates.sql) | Q196–Q210 | Cohort-suppressed practice, mastery, lifecycle, diagnosis, recovery, feedback and media statistics. No per-learner records or private content. |

### Useful starting points

- **“The question is missing”**: Q003, Q017, Q021, Q033, Q038, Q149.
- **“The diagram is missing or leaks the solution”**: Q046–Q052, Q114.
- **“Where did this problem come from?”**: Q043, Q056, Q058, Q060.
- **“Can this solution support guided steps?”**: Q062, Q067–Q080.
- **“The topic/practice selection is weak”**: Q084, Q088, Q095–Q100,
  Q110–Q117, Q177–Q178, Q205–Q206.
- **“Import says complete but content is absent”**: Q127, Q132–Q137,
  Q143, Q149, Q157.
- **“Search is stale”**: Q162–Q174, Q177–Q180, Q190.
- **“Consumers are not catching up”**: Q152–Q159. Start with Q159 to
  discover the *actual* consumer names before setting `consumer`.
- **“Show privacy-conscious learner trends”**: Q196–Q210 only.

## Source of truth and prerequisites

Target a PostgreSQL database already provisioned from the **composite**
[`mathbank-db/sql/001_schema.sql` through `024_feedback_evidence.sql`](../../mathbank-db/sql).
These files are not migrations and do not create absent tables.
The schema requires `pg_trgm` and `vector` (the latter's health checks use
`vector_dims` and `<#>`). Modern supported PostgreSQL releases provide
`sha256(bytea)` used by Q190. Use Q195 to inspect extension versions.
`psql` 10+ is needed for conditional variable defaults. Node is needed only
for `emit.mjs`, `validate.mjs` and `test.mjs`, not category SQL execution.

Important composite changes accounted for:

- Migration 008 adds `approval_method` to eight knowledge tables via dynamic
  `FOREACH/EXECUTE`. **Automatic approval is not human review or correctness.**
- Migration 010 makes `competition_edition.year` nullable, adds ingest and
  pedagogy tables. `core.solution_step` has UUID IDs; `pedagogy.solution_step`
  has text IDs. They are not interchangeable.
- Migration 011 adds canonical step/item/taxonomy chunk references.
  Textual pedagogy IDs live on chunks; representation UUIDs may be surrogates.
  Q167 intentionally checks only canonical PROBLEM/SOLUTION UUID sources.
- Migrations 015/017/019 add exercise approval provenance, step techniques,
  admin-edit timestamps, conflict decisions and DAG reviews.
- Migration 021 makes `learner.attempt.is_correct` nullable. Q196/Q197
  **exclude unassessed answers from accuracy denominators**.
- Migrations 022–024 add structured artifacts and feedback evidence verdicts.

Relevant actual REST SQL contracts were inspected in
[`problem_sources.py`](../../mathbank-rest/src/mathbank_rest/db/problem_sources.py),
[`step_search.py`](../../mathbank-rest/src/mathbank_rest/db/step_search.py),
[`topic_pedagogy.py`](../../mathbank-rest/src/mathbank_rest/db/topic_pedagogy.py),
[`vector_search.py`](../../mathbank-rest/src/mathbank_rest/db/vector_search.py) and
[`pipeline_jobs.py`](../../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py).
Q056 follows the REST `_Q[0-9]+$` source-key convention. Q097 follows
normalized exact taxonomy naming, not semantic similarity. Q176/Q177 preserve
live publication/exercise eligibility; an indexed row alone is not eligible.
These queries report SQL state, not remote graph/object-store state or API authorization.

## Run safely

**Use a least-privilege SELECT-only operator role**, preferably on an approved
replica, with access only to the required schemas. Do not use a superuser.
Supply connection information through your existing approved environment,
service configuration or interactive `psql` setup; this library contains no
credentials and does not prescribe storing secrets.

Each category includes `_session.sql` using `\ir` (resolved relative to the
category file). It opens a **REPEATABLE READ READ ONLY** transaction, sets UTC,
30-second statement timeout, 2-second lock timeout and 60-second idle timeout,
then ends with **ROLLBACK**. `ON_ERROR_STOP` is enabled and the pager is disabled.
Do not run these files inside an existing transaction or remove the preamble.
A category can perform many full scans: usually prefer one query.

From the repository root:

```sh
# Inspect everything available; no DB connection.
node mathbank_data_ingestion/queries/emit.mjs --list

# Offline validation/tests; no dependency installation or DB connection.
node mathbank_data_ingestion/queries/validate.mjs
node --test mathbank_data_ingestion/queries/test.mjs

# Emit an exact lookup for inspection only; no DB connection.
node mathbank_data_ingestion/queries/emit.mjs Q037
```

Only **after approving the target database and access**, examples to run yourself:

```sh
# shell pipefail prevents an emitter failure from being mistaken for success.
set -o pipefail
node mathbank_data_ingestion/queries/emit.mjs Q037 |
  psql -X -v ON_ERROR_STOP=1 -v problem_code='YOUR_CANONICAL_CODE'

# Example external competition selector, not a guarantee this code is present.
node mathbank_data_ingestion/queries/emit.mjs Q001 |
  psql -X -v ON_ERROR_STOP=1 -v competition='AIME' -v row_limit=25

# Execute a category when its aggregate scan cost is acceptable.
psql -X -v ON_ERROR_STOP=1 -v days=7 -v cohort=20 \
  -f mathbank_data_ingestion/queries/11_learner_feedback_aggregates.sql

# Consumer name should come from Q159, not an assumed runtime constant.
node mathbank_data_ingestion/queries/emit.mjs Q152 |
  psql -X -v ON_ERROR_STOP=1 -v consumer='analytics'
```

`-X` skips user `psqlrc` side effects. These are **psql scripts**, not raw SQL
strings for JDBC/SQLAlchemy: `:'variable'` is psql's SQL-literal quoting.
Do not substitute values with shell string replacement. To adapt a single
query to an application, replace these with your driver's bound parameters
and keep the read-only transaction/timeouts.

An error stops the script. In a noninteractive invocation connection close
rolls back the transaction; in interactive `\i` use `ROLLBACK;` before
continuing after any error.

### Input recipes and defaults

All referenced variables have defaults in `_session.sql`; overrides are set
before inclusion, either with `-v name=value` or interactive `\set`.
All SQL inputs use quoted literal interpolation, with explicit numeric casts.
None are identifiers or fragments of SQL.

| Variable | Default | Recipe / effect |
| --- | --- | --- |
| `competition` | empty string | Exact `core.competition.external_code`, e.g. `-v competition='AIME'`; empty = all. Q148 uses the PDF tracker's corresponding external code. |
| `book` | empty string | Exact `pedagogy.source_book.book_code` from Q041; empty = all. |
| `problem_code` | empty string | Exact `core.problem.canonical_code` from your corpus; empty deliberately returns no exact-lookup rows. |
| `days` | `30` | Integer recent-time window, e.g. `-v days=7`; UTC relative to transaction start. Use a positive modest value. |
| `row_limit` | `50` | Positive integer result cap, e.g. `-v row_limit=25`. This is **not** a scan-cost cap. |
| `confidence` | `0.8` | Numeric threshold in [0,1] for low-confidence audits, e.g. `-v confidence=0.9`. |
| `cohort` | `10` | Distinct learner/reporter minimum, e.g. `-v cohort=20`; SQL always clamps upward to at least 10. |
| `consumer` | `analytics` | Exact receipt `consumer_name`; inspect Q159 and override if needed. |
| `query_text` | `power of a point` | PostgreSQL lexical query, e.g. `-v query_text='intersecting chords'`; never an embedding/model request. |

For interactive use, `\set competition ''` resets an old selector; defaults
do not overwrite already-defined psql variables. A book filter applies only
where its query's input comment lists `book`. The same applies to every input.
Queries described with `Inputs: none` are independent of selectors.

## Reading results

- **Inventories/aggregates**: one row per stated grouping dimension; `NULL`
  labels usually mean missing metadata, not a separate known category.
  Counts can include historical revisions/states where explicitly described.
- **Integrity/backlog checks**: zero rows means no recorded matches under the
  current scope, not proof of globally correct content or filesystem existence.
  Numbering/year gaps can be legitimate contest/editorial conventions.
- **Exact lookups**: zero rows can mean an absent/incorrect code or no source
  relation. Left-joined NULLs indicate missing linked metadata.
- **Percentiles/accuracy**: SQL excludes NULL observations; inspect associated
  denominators. Intervals are PostgreSQL intervals; `_seconds` outputs are
  numeric seconds. Q196 separates assessed and unassessed counts.
- **Storage**: table statistics are estimates; disk bytes include heap/TOAST
  as appropriate, not object-store usage. Purged media metadata can retain
  historical `size_bytes`; Q208's `recorded_bytes` is not live object storage.
- **Review/verification labels**: recorded approval/publication alone never
  certifies mathematical correctness or topic applicability.
- **Limits**: ordering is stable by IDs where practical; result caps truncate
  anomaly sets. Aggregate inventories without limits intentionally return all
  observed groups. Empty query text produces no useful lexical matches.

## Privacy and operator boundaries

Q196–Q210 never select email, password hashes, display names, student/attempt/
session IDs, submitted answers, transcripts, responses, private evidence,
feedback reasons/notes/topics, actor IDs, object keys or JSON payloads.
Each returned group requires at least **10 distinct learners/reporters**;
increase `cohort` for your organization. Suppressed output is **not zero**:
it is unavailable below threshold.

This is data minimization and small-cell suppression, **not differential
privacy or a formal anonymity guarantee**. Do not publish repeated overlapping
cohort extracts, attempt differencing, or use it for individual profiling.
Use controlled operator access, an approved reporting window and your
organization's retention/export policy. Artifact row-level diagnostics
Q181–Q191 include only requests with `owner_student_id IS NULL`, a technical
non-learner-owned condition, **not an authorization/public-access guarantee**.
Treat hidden-diagram metadata and unpublished corpus artifacts as admin-only.
No query verifies object existence, downloads bytes or retrieves private content.

## Per-query index

Each link opens the containing category SQL file; search for the indicated ID.
Short titles below summarize the full purpose/output comments in each block.

### Corpus hierarchy

| ID | Query |
| --- | --- |
| [Q001](01_corpus.sql) | Competition inventory and hierarchy coverage |
| [Q002](01_corpus.sql) | Edition inventory, including undated textbooks |
| [Q003](01_corpus.sql) | Paper roster and declared/actual question counts |
| [Q004](01_corpus.sql) | Empty competitions |
| [Q005](01_corpus.sql) | Editions without papers |
| [Q006](01_corpus.sql) | Empty papers with declared questions |
| [Q007](01_corpus.sql) | Monthly corpus growth |
| [Q008](01_corpus.sql) | Competition levels and countries |
| [Q009](01_corpus.sql) | Unkeyed catalog records |
| [Q010](01_corpus.sql) | Same-named competition records |
| [Q011](01_corpus.sql) | Nullable edition-key collisions |
| [Q012](01_corpus.sql) | Competition year gaps |
| [Q013](01_corpus.sql) | Official/unofficial paper coverage |
| [Q014](01_corpus.sql) | Paper duration/score anomalies |
| [Q015](01_corpus.sql) | Problem status by competition |
| [Q016](01_corpus.sql) | Paper numbering bounds |
| [Q017](01_corpus.sql) | Missing declared question slots |
| [Q018](01_corpus.sql) | Out-of-range problem numbering |
| [Q019](01_corpus.sql) | Recent problem modifications |
| [Q020](01_corpus.sql) | Largest competition-edition workloads |

### Question quality

| ID | Query |
| --- | --- |
| [Q021](02_problem_quality.sql) | Blank active statements |
| [Q022](02_problem_quality.sql) | Short statements for triage |
| [Q023](02_problem_quality.sql) | Statement-size distribution |
| [Q024](02_problem_quality.sql) | Duplicate content hashes |
| [Q025](02_problem_quality.sql) | Repeated normalized statements |
| [Q026](02_problem_quality.sql) | Answer completeness by type |
| [Q027](02_problem_quality.sql) | Active problems without solutions |
| [Q028](02_problem_quality.sql) | Missing reviewed concepts |
| [Q029](02_problem_quality.sql) | Missing usable techniques |
| [Q030](02_problem_quality.sql) | Difficulty/classification coverage |
| [Q031](02_problem_quality.sql) | Missing statement hashes |
| [Q032](02_problem_quality.sql) | OCR replacement-character anomalies |
| [Q033](02_problem_quality.sql) | Placeholder-like statements |
| [Q034](02_problem_quality.sql) | Potentially unbalanced dollar delimiters |
| [Q035](02_problem_quality.sql) | Implausible update timestamps |
| [Q036](02_problem_quality.sql) | Answer-bearing untyped questions |
| [Q037](02_problem_quality.sql) | Exact-problem completeness matrix |
| [Q038](02_problem_quality.sql) | Coverage debt by paper |
| [Q039](02_problem_quality.sql) | Difficulty-label whitespace inconsistencies |
| [Q040](02_problem_quality.sql) | Lexical question discovery |

### Provenance and diagrams

| ID | Query |
| --- | --- |
| [Q041](03_provenance_diagrams.sql) | Source-book inventory |
| [Q042](03_provenance_diagrams.sql) | Chapter-section mapping coverage |
| [Q043](03_provenance_diagrams.sql) | Exact problem provenance |
| [Q044](03_provenance_diagrams.sql) | Missing source channels |
| [Q045](03_provenance_diagrams.sql) | Source page-range anomalies |
| [Q046](03_provenance_diagrams.sql) | Missing required question diagrams |
| [Q047](03_provenance_diagrams.sql) | Missing required solution diagrams |
| [Q048](03_provenance_diagrams.sql) | Diagram validation coverage |
| [Q049](03_provenance_diagrams.sql) | Duplicate diagram-byte hashes |
| [Q050](03_provenance_diagrams.sql) | Missing diagram integrity/image links |
| [Q051](03_provenance_diagrams.sql) | Cross-problem diagram/image mismatches |
| [Q052](03_provenance_diagrams.sql) | Hidden diagrams linked to canonical images |
| [Q053](03_provenance_diagrams.sql) | Image coverage by source |
| [Q054](03_provenance_diagrams.sql) | Image ordinal holes |
| [Q055](03_provenance_diagrams.sql) | Unsafe source-URL shapes |
| [Q056](03_provenance_diagrams.sql) | REST-convention PDF source matching |
| [Q057](03_provenance_diagrams.sql) | PDF trackers without canonical papers |
| [Q058](03_provenance_diagrams.sql) | Solution-source ownership mismatch |
| [Q059](03_provenance_diagrams.sql) | Repeated printed numbering |
| [Q060](03_provenance_diagrams.sql) | Section problem-count reconciliation |

### Solutions and step DAGs

| ID | Query |
| --- | --- |
| [Q061](04_solutions_steps.sql) | Solution kinds/verification inventory |
| [Q062](04_solutions_steps.sql) | Latest revisions for an exact question |
| [Q063](04_solutions_steps.sql) | Empty solution bodies |
| [Q064](04_solutions_steps.sql) | Solution revision gaps |
| [Q065](04_solutions_steps.sql) | Core step ordinal integrity |
| [Q066](04_solutions_steps.sql) | Blank core steps |
| [Q067](04_solutions_steps.sql) | Solution-part step-count drift |
| [Q068](04_solutions_steps.sql) | Pedagogy step/part ownership mismatch |
| [Q069](04_solutions_steps.sql) | Global step order holes |
| [Q070](04_solutions_steps.sql) | Per-part index collisions/holes |
| [Q071](04_solutions_steps.sql) | Published-step checkpoint coverage |
| [Q072](04_solutions_steps.sql) | Step roles/types inventory |
| [Q073](04_solutions_steps.sql) | Cross-problem dependencies |
| [Q074](04_solutions_steps.sql) | NEXT edges conflicting with order |
| [Q075](04_solutions_steps.sql) | Opposing reviewed dependency pairs |
| [Q076](04_solutions_steps.sql) | Dependency approval provenance |
| [Q077](04_solutions_steps.sql) | Solution DAG review backlog |
| [Q078](04_solutions_steps.sql) | Admin edits newer than DAG approval |
| [Q079](04_solutions_steps.sql) | Missing progressive hint levels |
| [Q080](04_solutions_steps.sql) | Hint safety/version inventory |

### Knowledge and taxonomy

| ID | Query |
| --- | --- |
| [Q081](05_knowledge_taxonomy.sql) | Concept usage/lifecycle |
| [Q082](05_knowledge_taxonomy.sql) | Disconnected techniques |
| [Q083](05_knowledge_taxonomy.sql) | Concept assertion trust distribution |
| [Q084](05_knowledge_taxonomy.sql) | Low-confidence reviewed techniques |
| [Q085](05_knowledge_taxonomy.sql) | Multiple reviewed primary concepts |
| [Q086](05_knowledge_taxonomy.sql) | Reviewed links to inactive concepts |
| [Q087](05_knowledge_taxonomy.sql) | Skill trust/level inventory |
| [Q088](05_knowledge_taxonomy.sql) | Skills without concept grounding |
| [Q089](05_knowledge_taxonomy.sql) | Problem skill roles/levels |
| [Q090](05_knowledge_taxonomy.sql) | Missing reviewed primary skills |
| [Q091](05_knowledge_taxonomy.sql) | Bidirectional skill prerequisites |
| [Q092](05_knowledge_taxonomy.sql) | Self-linked concept relationships |
| [Q093](05_knowledge_taxonomy.sql) | Concept relation confidence bounds |
| [Q094](05_knowledge_taxonomy.sql) | Taxonomy bridge coverage |
| [Q095](05_knowledge_taxonomy.sql) | Broken taxonomy parents |
| [Q096](05_knowledge_taxonomy.sql) | Wrong canonical bridge types |
| [Q097](05_knowledge_taxonomy.sql) | Ambiguous normalized taxonomy names |
| [Q098](05_knowledge_taxonomy.sql) | Taxonomy edge quality |
| [Q099](05_knowledge_taxonomy.sql) | Step technique derivation coverage |
| [Q100](05_knowledge_taxonomy.sql) | Wrong-type technique assertion targets |

### Pedagogy and learning items

| ID | Query |
| --- | --- |
| [Q101](06_pedagogy_learning.sql) | Pedagogy dimensional profile |
| [Q102](06_pedagogy_learning.sql) | Missing pedagogy dimensions |
| [Q103](06_pedagogy_learning.sql) | Enrichment step-count drift |
| [Q104](06_pedagogy_learning.sql) | Taxonomy confidence backlog |
| [Q105](06_pedagogy_learning.sql) | Unresolved enrichment technique IDs |
| [Q106](06_pedagogy_learning.sql) | Learning-item publication/review inventory |
| [Q107](06_pedagogy_learning.sql) | Visible items missing question/answer content |
| [Q108](06_pedagogy_learning.sql) | Approved but hidden items |
| [Q109](06_pedagogy_learning.sql) | Dangling learning-item parents |
| [Q110](06_pedagogy_learning.sql) | Visible exercises without step anchors |
| [Q111](06_pedagogy_learning.sql) | Cross-problem step anchors |
| [Q112](06_pedagogy_learning.sql) | Duplicate anchor ordinals |
| [Q113](06_pedagogy_learning.sql) | Wrong-type exercise taxonomy targets |
| [Q114](06_pedagogy_learning.sql) | Source-dependent items without diagram strategy |
| [Q115](06_pedagogy_learning.sql) | Malformed multiple-choice shape |
| [Q116](06_pedagogy_learning.sql) | Visible exercise skill coverage |
| [Q117](06_pedagogy_learning.sql) | Published step skills without exercises |
| [Q118](06_pedagogy_learning.sql) | Duplicate visible exercise questions |
| [Q119](06_pedagogy_learning.sql) | Missing approval timestamp/method |
| [Q120](06_pedagogy_learning.sql) | Declared versus core step totals |

### Imports and reconciliation

| ID | Query |
| --- | --- |
| [Q121](07_imports.sql) | Package registry state inventory |
| [Q122](07_imports.sql) | Stalled active package operations |
| [Q123](07_imports.sql) | Multiple manifests per package/version |
| [Q124](07_imports.sql) | File size/row-count footprint |
| [Q125](07_imports.sql) | Invalid file metadata/hash shape |
| [Q126](07_imports.sql) | Staging validation progress |
| [Q127](07_imports.sql) | Imported rows without target keys |
| [Q128](07_imports.sql) | Rejected rows without validation errors |
| [Q129](07_imports.sql) | Repeated staging entity identities |
| [Q130](07_imports.sql) | Open conflict severity/type backlog |
| [Q131](07_imports.sql) | Incomplete resolved-conflict decisions |
| [Q132](07_imports.sql) | Reconciliation discrepancies |
| [Q133](07_imports.sql) | Reconciliation disposition arithmetic |
| [Q134](07_imports.sql) | Completed packages with open errors |
| [Q135](07_imports.sql) | Status transition counts |
| [Q136](07_imports.sql) | Registry/latest-event state mismatch |
| [Q137](07_imports.sql) | Declared versus staged file row counts |
| [Q138](07_imports.sql) | Admin review volumes |
| [Q139](07_imports.sql) | Taxonomy import scope drift |
| [Q140](07_imports.sql) | Package import throughput |

### Pipeline and outbox

| ID | Query |
| --- | --- |
| [Q141](08_pipeline.sql) | Run state/throughput |
| [Q142](08_pipeline.sql) | Stale run heartbeats |
| [Q143](08_pipeline.sql) | Work-item states versus run counters |
| [Q144](08_pipeline.sql) | Expired owned work leases |
| [Q145](08_pipeline.sql) | Repeated work-item retries |
| [Q146](08_pipeline.sql) | Pipeline duration anomalies |
| [Q147](08_pipeline.sql) | Completed work without hashes |
| [Q148](08_pipeline.sql) | PDF stage funnel |
| [Q149](08_pipeline.sql) | Parsed/ingested question drift |
| [Q150](08_pipeline.sql) | Graph projection freshness/volume |
| [Q151](08_pipeline.sql) | Graph projection duration distribution |
| [Q152](08_pipeline.sql) | Consumer-specific outbox backlog |
| [Q153](08_pipeline.sql) | Consumer processing latency |
| [Q154](08_pipeline.sql) | Consumption preceding event creation |
| [Q155](08_pipeline.sql) | Projection request backlog |
| [Q156](08_pipeline.sql) | DONE requests without completion times |
| [Q157](08_pipeline.sql) | Enrichment publication lag |
| [Q158](08_pipeline.sql) | Relationship enrichment throughput |
| [Q159](08_pipeline.sql) | Registered consumer activity |
| [Q160](08_pipeline.sql) | Run completion-budget inconsistencies |

### Search and vector health

| ID | Query |
| --- | --- |
| [Q161](09_search_vectors.sql) | Model registry/embedding coverage |
| [Q162](09_search_vectors.sql) | Embedding dimension mismatch |
| [Q163](09_search_vectors.sql) | Multiple active model revisions |
| [Q164](09_search_vectors.sql) | Representation kind/status inventory |
| [Q165](09_search_vectors.sql) | Multiple active source representations |
| [Q166](09_search_vectors.sql) | Stale problem representations |
| [Q167](09_search_vectors.sql) | Orphan problem/solution representations |
| [Q168](09_search_vectors.sql) | Active representations without chunks |
| [Q169](09_search_vectors.sql) | Chunk text metadata drift |
| [Q170](09_search_vectors.sql) | Chunk ordinal gaps |
| [Q171](09_search_vectors.sql) | Cross-representation parent chunks |
| [Q172](09_search_vectors.sql) | Missing active-model embeddings |
| [Q173](09_search_vectors.sql) | Active embeddings on superseded sources |
| [Q174](09_search_vectors.sql) | Embedding job retry/stall queue |
| [Q175](09_search_vectors.sql) | Search index definitions/sizes |
| [Q176](09_search_vectors.sql) | Lexical published-step search |
| [Q177](09_search_vectors.sql) | Indexed items failing live eligibility |
| [Q178](09_search_vectors.sql) | Step chunk taxonomy-filter drift |
| [Q179](09_search_vectors.sql) | Search profile version inventory |
| [Q180](09_search_vectors.sql) | Zero-norm embeddings |

### Artifacts and storage

| ID | Query |
| --- | --- |
| [Q181](10_artifacts_storage.sql) | Non-learner-owned artifact publishing coverage |
| [Q182](10_artifacts_storage.sql) | Published bundles without assets |
| [Q183](10_artifacts_storage.sql) | Published artifact validation gaps |
| [Q184](10_artifacts_storage.sql) | Artifact asset storage budget |
| [Q185](10_artifacts_storage.sql) | Assets without searchable metadata |
| [Q186](10_artifacts_storage.sql) | Missing/mismatched artifact lineage |
| [Q187](10_artifacts_storage.sql) | Overlay assets in another bundle |
| [Q188](10_artifacts_storage.sql) | Invalid frame overlay references |
| [Q189](10_artifacts_storage.sql) | Dangling annotation step links |
| [Q190](10_artifacts_storage.sql) | Artifact embedding freshness |
| [Q191](10_artifacts_storage.sql) | Artifact tags without taxonomy matches |
| [Q192](10_artifacts_storage.sql) | Schema/table disk footprint |
| [Q193](10_artifacts_storage.sql) | Vacuum/analyze/dead-tuple health |
| [Q194](10_artifacts_storage.sql) | Invalid/unready indexes |
| [Q195](10_artifacts_storage.sql) | Required extension availability |

### Learner and feedback aggregates

| ID | Query |
| --- | --- |
| [Q196](11_learner_feedback_aggregates.sql) | Daily evaluated/unassessed outcomes |
| [Q197](11_learner_feedback_aggregates.sql) | Competition practice breadth/outcomes |
| [Q198](11_learner_feedback_aggregates.sql) | Solve-session lifecycle funnel |
| [Q199](11_learner_feedback_aggregates.sql) | Independent/assisted step outcomes |
| [Q200](11_learner_feedback_aggregates.sql) | Concept mastery population bands |
| [Q201](11_learner_feedback_aggregates.sql) | Daily activity rollup completeness |
| [Q202](11_learner_feedback_aggregates.sql) | Diagnosis intervention mix |
| [Q203](11_learner_feedback_aggregates.sql) | Gap confirmation by failure location |
| [Q204](11_learner_feedback_aggregates.sql) | Recovery outcomes/branching |
| [Q205](11_learner_feedback_aggregates.sql) | Feedback triage/error distribution |
| [Q206](11_learner_feedback_aggregates.sql) | Pending feedback age bands |
| [Q207](11_learner_feedback_aggregates.sql) | Multimodal submission funnel |
| [Q208](11_learner_feedback_aggregates.sql) | Private media retention/storage budget |
| [Q209](11_learner_feedback_aggregates.sql) | Latest approved-step alignment quality |
| [Q210](11_learner_feedback_aggregates.sql) | Event ingestion by actor/type |

## Offline verification and limitations

`validate.mjs` reads the actual numbered migrations and composes CREATE TABLE
columns with additive ALTERs, explicitly including migration 008's dynamic
`approval_method` additions. It checks sequential unique IDs, documentation,
single SELECT/WITH statements, mutation/unsafe keyword absence, balanced
parentheses, application table references, qualified column references and
unqualified identifiers in simple single-table queries. It also checks category
read-only preambles/ROLLBACKs. `test.mjs` tests ID inventory, guarded emission,
unknown-ID rejection and variable defaults. No dependencies are installed.

**This is structural/schema lint, not a PostgreSQL parser.** No suitable
offline SQL parser was found in the project environment. `psql` exists but
cannot parse/bind arbitrary SQL offline. During creation and offline validation,
no database connection, EXPLAIN, migration, DML, vector generation or network
call was performed. Those offline checks alone did not establish server
parser/type binding; the separate deployment observation below does.
Derived CTE/series scope and multi-join unqualified columns
were manually reviewed, not fully resolved by the lint. The SQL was written
as executable PostgreSQL templates against the inspected final schema, not
pseudocode. Run selected diagnostics on an approved deployed schema to verify
actual results; failures should be investigated, not worked around by applying
migrations from this library.

Verified offline on 2026-10-07: **210 sequential unique templates / 11 categories**;
composite catalog composed from **115 tables**; **352 application-table
references**, **785 qualified-column references** and **113 single-table
unqualified-identifier checks** passed. All **5 Node tests** passed, including
guarded emission of every ID and rejection of invalid selection. Editor
diagnostics reported no errors. These offline checks do not establish execution
or data-dependent correctness.

### Separate deployment observation — 2026-10-07 UTC

Following creation/offline validation, the coordinating agent reported using
the **configured REST PostgreSQL on the explicitly user-selected deployment
target** to `PREPARE` then `DEALLOCATE` all **210 queries** in a **READ ONLY**
transaction, with per-query savepoints and quoted synthetic input defaults.
**210/210 parsed and bound successfully** against that deployment. This
establishes server parsing/type binding and referenced-schema compatibility
for the tested templates, inputs and target at that time; it is not an offline
test and was not rerun while documenting this observation.

**The diagnostic SELECTs were NOT executed. No diagnostic row results were
read or persisted.** No migration or DML was performed by that validation.
Runtime execution, data-dependent semantics/correctness, execution-time
permissions for intended operator roles, query plans, resource costs and
behavior with other inputs/deployments remain unverified. Successful PREPARE
does not prove runtime authorization, useful results or acceptable scan cost.

The query library intentionally targets migrations **001–024**. Migration
025's corpus-authoring additions do not expand this library's scope.
