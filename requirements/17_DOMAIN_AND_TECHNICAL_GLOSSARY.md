# MathBank Domain and Technical Glossary

## Purpose and reading guide

This is the working vocabulary for developers, administrators and learners.
It covers mathematical meaning, database representation, pipeline behavior,
retrieval, tutoring and operational metrics. It describes the implemented
repository, not a promise that every paper has completed every stage.

**Implemented** means there is a schema/code path; it does not certify that the
data is populated or correct. **Planned** explicitly marks roadmap concepts.
`REVIEWED` means usable under the approval policy, which can be automatic.
Postgres is the system of record; Neo4j and embeddings are derived projections.
Historical GCP/Firestore designs in earlier requirements are not descriptions
of the current Neon/Postgres + Neo4j runtime.

## 1. Mathematics, contests and corpus content

| Term | Clear meaning / example | Representation and cautions |
|---|---|---|
| Competition / contest | An event family, e.g. AIME or Purple Comet. | `core.competition`; external code, name, organization, country and level. |
| AMC | American Mathematics Competitions; AMC10/AMC12 are distinct levels. | Competition codes and paper registries, not one undifferentiated difficulty label. |
| AIME | American Invitational Mathematics Examination. | Competition/edition/paper/problem records; a code such as `AIME_1983_Q01` identifies a problem. |
| HMMT | Harvard-MIT Mathematics Tournament. | Papers can differ by round, subject and tournament format; preserve source context. |
| SMT | Stanford Math Tournament. | Competition and paper identities; subject/round matter. |
| MPG | Math Prize for Girls. | Registered sources and canonical problems; source figures are retained. |
| Purple Comet | Online team competition with middle/high-school divisions. | Separate division sources; year-specific numbered answer counts. Official answers are not necessarily worked solutions. |
| ARML | American Regions Mathematics League. | Archive books split into round-specific paper artifacts; a released queue is distinct from a implemented queue. |
| Edition | A particular year/season of a competition. | `core.competition_edition`, linked to competition. |
| Paper / test / round | A coherent question set, such as an algebra round. | `core.paper`; external code, paper code/type, duration and question count. One PDF can contain many papers. |
| Archive book | A source document containing several years/rounds. | Downloaded PDF plus extracted round artifacts/provenance; not automatically one canonical paper. |
| Problem / question | A mathematical task presented to a learner. | `core.problem`; statement, paper, number, canonical code, answer and source URL. |
| Problem number / ordinal | Position within a paper. | Integer `problem_number`; do not substitute an unrelated PDF page number. |
| Canonical code | Stable readable problem identity. | Unique `core.problem.canonical_code`; used by REST/UI and scoped ingestion. |
| External code | Identity from an upstream registry. | Competition/paper external codes; can differ from canonical problem codes. |
| UUID | Internal globally unique entity identifier. | Primary/foreign keys; opaque identity, not a display name or rank. |
| Statement | The question text, excluding a solution. | `statement_text` / `statement_latex`; authoritative PDF remains useful for transcription checks. |
| LaTeX | Mathematical markup such as `x^2`. | Statement/solution/formula fields; transcription validity is separate from mathematical truth. |
| Markdown | Lightweight document markup. | Parsed artifacts and `body_markdown`; headings delimit question sections. |
| Official answer | Published answer value/key. | `core.problem.official_answer`; not necessarily an explanation. |
| Answer type | Required response format, e.g. numeric or proof. | `core.problem.answer_type`; contextual ARML proof tasks must not be forced into numeric grading. |
| Answer key | Numbered table of official answers. | Retained HTML/JSON/source artifacts; establishes counts/values, not reasoning. |
| Worked solution | Reasoning showing how to solve a problem. | `core.solution`, revision and verification status; absence is explicitly distinct from missing statement. |
| Solution revision | A version of an explanation. | Unique problem + solution kind + revision; different revisions need not be separate problems. |
| Solution step | Ordered reasoning unit in an explanation. | `core.solution_step`: ordinal, type, explanation, formula. Schema availability does not mean all solutions are decomposed. |
| Figure / diagram | Visual information needed to understand a task. | `core.problem_image` plus local page/region files. Text extraction does not replace a geometric diagram. |
| Page span | Source pages belonging to a numbered question/solution. | Artifact manifests/provenance; continuation/shared pages must be handled explicitly. |
| Source provenance | Where content/evidence came from. | Source URLs, page references, hashes, manifests and assertion-source fields. |
| Official / curated / generated | Different origins of content. | Paper official flag, solution kind/verification status and metadata source; generated content must not be represented as official. |
| Algebra | Manipulating symbolic quantities and equations. | Concept taxonomy and classification tags, not a measured ability by itself. |
| Geometry | Reasoning about shapes, position and measurement. | Concept tags, often with source images. |
| Number theory | Integers, divisibility, congruences, primes, etc. | Concept taxonomy. |
| Combinatorics | Counting and discrete arrangements/structures. | Concept taxonomy; methods such as casework are techniques. |
| Probability | Reasoning about uncertainty and random outcomes. | Concept taxonomy; contest level alone does not specify complexity. |
| Contest level | Informal expected competition context. | `estimated_contest_level` text; not a calibrated percentile or official ranking. |

## 2. Concepts, techniques, skills and taxonomy

| Term | Clear meaning / example | Representation and cautions |
|---|---|---|
| Concept | **What mathematics** a task concerns: modular arithmetic. | `knowledge.concept`: UUID, slug, name, description, level/status. A topic label does not establish learner mastery. |
| Technique / method | **How** to approach a task: casework, substitution, invariant argument. | `knowledge.technique`; problem links in `knowledge.problem_technique`. User spelling “tehnic” refers to technique. |
| Skill | **An observable action** a learner should perform: reduce an integer modulo a specified modulus. | `knowledge.skill`: objective, level, source, confidence and review status. Not interchangeable with a concept. |
| Learning objective | A testable statement of intended performance. | Required nonempty `knowledge.skill.objective`; prefer action verbs and observable outcomes. |
| Classification / classify | Assign concepts/techniques and related labels to a problem. | Ingestion classifier records, exports and canonical knowledge links; local success is not proof of Postgres import. |
| Pedagogical enrichment | Add teaching metadata beyond topic tagging. | `problem_skill`, `problem_pedagogy`, skill/concept links and validated prerequisites; tracked in `enrichment_job`. |
| Taxonomy | Controlled catalog of mathematical categories and their organization. | Concept/technique catalogs, slugs and relationship tables. Not a free-form bag of model-generated names. |
| Slug | Stable machine-readable label. | Unique taxonomy slug; model output must refer to permitted catalog identities. |
| Invalid taxonomy slug | A generated identifier absent from the allowed catalog or malformed. | Validation failure/correction feedback; never silently create an unrelated edge. |
| Primary concept | Main topic associated with a problem. | `problem_concept.role`, commonly `PRIMARY`; additional concepts may also apply. |
| Additional / supporting concept | Relevant secondary mathematical topic. | Separate problem-concept link/role; does not imply equal learning importance. |
| Required technique | Method asserted as needed. | `problem_technique.role`, commonly `REQUIRED`; alternate methods may exist. |
| Skill role | Main vs supporting performance requirement. | `problem_skill.role` is `primary` or `supporting`. |
| Required skill level | Intended performance level for this problem-skill link. | `required_level` 1-5; not the learner's measured current level. |
| Importance | Weight of a skill within a problem. | `problem_skill.importance` 0-1; distinct from confidence and mastery. |
| Confidence | How certain an assertion/generator is. | Numeric 0-1 in canonical pedagogy; some classifier outputs use high/medium/low. Not a probability that a student can solve the task. |
| Assertion | A claim linking entities or assigning metadata. | Knowledge-table rows with source, confidence and review/approval information. |
| Assertion source | Origin of a metadata claim. | `assertion_source` or `source`; model/import/human provenance is retained. |
| REQUIRES | Problem depends on a skill. | Directed Problem -> Skill edge / `problem_skill.relation_type`. |
| PRACTICES | Problem provides practice of a skill. | Problem -> Skill relation; practice opportunity is not proof of acquisition. |
| TESTS | Problem assesses a skill. | Problem -> Skill relation; solving through another method complicates attribution. |
| Prerequisite | Knowledge/performance needed before another. | Validated `PREREQUISITE_OF` relations; ordering semantics differ from similarity. |
| PREREQUISITE_OF | A must precede B. | A -> B in skill/concept relation graphs. No self-edge or cycle in validated prerequisite paths. |
| Skill hierarchy | Decomposition of a broad skill into narrower skills. | Skill `PART_OF` relations; graph view requires actual hierarchy data. |
| PART_OF | A is a component of B. | Child -> parent. It is not an invented synonym for prerequisite. |
| HAS_SUBCONCEPT | A parent contains a child concept. | Concept relation form normalized to reverse `PART_OF` for projection/comparison. |
| BUILDS_ON | A extends/depends pedagogically on B. | A -> B; distinct semantics and orientation from B `PREREQUISITE_OF` A. |
| Skill-concept mapping | Associates an observable skill with its subject matter. | `knowledge.skill_concept`; source/confidence/approval tracked separately. |
| Relationship enrichment | Generate validated relationships between catalog entities. | `relationship_enrichment_job`; a separate stage from per-problem tagging. |
| Anchor | Entity selected as the starting point for relationship generation. | Job key: entity kind + anchor UUID. |
| Candidate relationship | Proposed, not yet accepted edge. | Model evidence evaluated against allowed endpoints, semantic rules and graph validation. |
| Semantic verification | Check that a proposed edge expresses the claimed meaning. | Relationship verifier stage; automatic verification is not expert certification. |
| Cycle | A directed path returns to its starting node. | Rejected in validated prerequisite/hierarchy graphs where acyclic ordering is required. |
| DAG | Directed acyclic graph. | Useful model for prerequisite ordering; not every relationship in the entire graph belongs to one DAG. |
| Cycle correction | Regenerate/repair a rejected proposal against existing graph constraints. | Bounded correction attempts; exhaustion remains a failed generation job. |
| Empty relationship result | No defensible edges found for an anchor. | A successfully evaluated/published zero-edge job can be valid; no evaluated anchor is not equivalent to success. |
| Learning context | Answer-free teaching information for a selected problem. | REST learning-context tool/UI: reviewed skills, prerequisites, tags and difficulty dimensions. |
| Similar skill problem | Another task with matching reviewed required skills. | Teaching lookup; vector similarity alone is insufficient to claim shared skill. |
| Easier problem | A task lower on comparable difficulty dimensions/levels. | Teaching recommendations must use available evidence rather than smaller problem numbers alone. |

## 3. Approval, review and multidimensional difficulty

| Term | Clear meaning | Representation and cautions |
|---|---|---|
| Automatic approval / auto approval | Validated metadata becomes immediately usable without an admin queue barrier. | `review_status=REVIEWED`, `approval_method=automatic`; applies through migration 008 triggers. |
| Human approval | An administrator deliberately accepts or edits an assertion. | `approval_method=human`; protected against automated overwrites. |
| REVIEWED | Usable approved metadata under the current policy. | Can mean automatic **or** human approval; always inspect approval method. |
| PENDING review | An assertion awaiting the relevant approval policy. | Different from a pending pipeline job; current automatic-writer policy usually promotes eligible new metadata. |
| REJECTED | Explicitly disallowed metadata. | Preserved against automatic replacement; does not mean its underlying problem is deleted. |
| Reclassification | Correct an existing topic/method assignment. | Admin edits canonical mappings with human provenance and subsequent projection. |
| Review event | Record of a deliberate review decision/change. | `knowledge.pedagogy_review_event`; before/after evidence. |
| Automatic approval audit | Trace automatic metadata acceptance. | `knowledge.metadata_approval_event`; snapshots and approval timestamp. |
| Protected human correction | An automated pass must not undo an admin decision. | Database trigger policy, not merely a prompt instruction. |
| Difficulty band | Legacy free-text overall difficulty label. | `core.problem.difficulty_band`; currently converted heuristically for mastery weighting. |
| Multidimensional difficulty | Several independent sources of problem difficulty. | `knowledge.problem_pedagogy`; not one universal rank. |
| Conceptual depth | Depth/interdependence of mathematical ideas. | Nullable integer 1-5. |
| Technical load | Execution complexity of methods/calculations. | Nullable integer 1-5. |
| Algebraic load | Amount/complexity of symbolic manipulation. | Nullable integer 1-5. |
| Insight required | Degree of non-obvious observation needed. | Nullable integer 1-5; not equivalent to length. |
| Number of steps | Estimated reasoning-step count. | Nullable nonnegative integer, not a 1-5 score. |
| Prerequisite depth | Estimated depth of prerequisite chain. | Nullable nonnegative integer; not measured learner readiness. |
| Not recorded / unknown | No trustworthy value available. | Null/missing evidence displayed explicitly, never interpreted as zero difficulty or completed work. |
| Verification status | Assurance assigned to solution content. | `core.solution.verification_status`; independent of classification approval. |
| Model review verdict | Second classifier review decision. | `APPROVED`, `CORRECTED`, `NEEDS_HUMAN_REVIEW` in ingestion review output; not interchangeable with all canonical review statuses. |

## 4. Learners, strengths, weaknesses and evidence

| Term | Clear meaning | Representation and cautions |
|---|---|---|
| Student / learner | An authenticated person tracking practice. | `learner.student`; private identity/profile, not public corpus content. |
| Anonymous learner | Someone using tutoring without a tracked student profile. | Agent/session/UI context; do not invent historical mastery. |
| Attempt | Recorded answer/outcome on a problem. | Append-only `learner.attempt`: student/problem, correctness, answer, hint count, time and timestamp/source. |
| Correctness | Whether an attempt was judged correct. | Boolean `is_correct`; no partial-credit state in current scoring. |
| Hint count | Number of hints used for that attempt. | Nonnegative count; affects the score assigned to a correct answer. |
| Time spent | Reported duration of an attempt. | `time_spent_seconds`; not currently part of the mastery-score formula. |
| Mastery score | Weighted estimate of demonstrated performance on linked topics/methods. | `mastery_score` 0-1 in concept/technique caches; exact calculation below. |
| Concept mastery | Estimated performance attributed to a tagged concept. | `learner.concept_mastery`; all linked concepts currently receive attempt evidence, without role/confidence weighting. |
| Technique mastery | Estimated performance attributed to a tagged method. | `learner.technique_mastery`; cannot prove that method was actually used. |
| Skill mastery | Evidence of an observable performance objective. | **Planned richer evidence**, not the current concept/technique score relabelled as skill mastery. |
| Strength score | UI interpretation of higher mastery. | No separate canonical strength-score table/formula; inspect the underlying mastery, attempts and topic/method. |
| Weakness score | UI interpretation of lower mastery. | Current improvement plan ranks lowest mastery; no independent calibrated weakness probability. If showing `1-mastery`, label it as a derived display, not stored evidence. |
| Critical / developing / solid | Current feedback tiers. | `<0.4`, `0.4 <= score <0.7`, `>=0.7`, respectively. No implemented minimum-attempt gate. |
| Attempts count | Evidence volume attached to a mastery row. | `attempts_count`; one correct attempt can produce a high score without strong statistical confidence. |
| Correct count | Raw number of correct attempts. | `correct_count`; unlike mastery, does not apply hint/time/difficulty weights. |
| Recency weight | Prefer recent evidence over old evidence. | `exp(-age_days/45)`; see important half-life clarification below. |
| Difficulty weight | More difficult attempts get greater relative weight. | `1 + 0.5 * normalized_difficulty`; based on legacy bands, not rich pedagogy dimensions. |
| Hint penalty | Reduce evidence from heavily assisted correct answers. | `max(0.4, 1/(1+0.25*hint_count))`. |
| Mastery cache | Rebuildable summary of attempts. | Concept/technique mastery tables; attempts remain the evidence source. |
| Improvement plan | Weakest non-solid areas plus practice tasks. | REST aggregation of existing concept/technique mastery and corpus lookups. |
| Focus area | One selected concept/technique needing work. | Improvement-plan response includes kind, slug, score, tier, counts and recommended problems. |
| Cohort weakness | Aggregate performance over a group. | Average concept mastery, student count and total attempts; not a per-person diagnosis. |
| Diagnostic question | A task intended to identify a gap. | Teaching workflow/prompt; correct/incorrect alone rarely isolates the causal gap. |
| Learner evidence | Observations supporting an ability estimate. | Current attempts and their metadata; richer skill-level reasoning/error evidence is roadmap work. |
| Misconception | A repeatable incorrect mental model. | **Planned richer pedagogy**; do not infer a definitive misconception from a single wrong answer. |
| Prerequisite readiness | Whether needed foundational skills are demonstrated. | Requires learner evidence; existence of a prerequisite edge alone is insufficient. |
| Cold start | No observations for this learner/topic. | Missing mastery row is unknown, not proven weakness. Pure scoring of an empty list returns 0 as a computational convention. |
| Retention / forgetting | Performance over time. | Current recency weighting is a heuristic, not a validated psychological forgetting model. |

### Exact current scoring, not a marketing label

Implemented in [mastery.py](../mathbank-rest/src/mathbank_rest/mastery.py).
For each attempt `i`, let:

```text
age_i = max(0, (now - attempted_at_i) in days)
r_i = exp(-age_i / 45)
d_i = 1 + 0.5 * normalized_difficulty(difficulty_band_i)
c_i = 0                                      if incorrect
c_i = max(0.4, 1/(1 + 0.25 * hint_count_i))    if correct
mastery = clamp(sum(c_i * r_i * d_i) / sum(r_i * d_i), 0, 1)
```

Difficulty keyword mapping is entry=.15, easy=.2, early=.25,
medium/mid=.5, late=.75, hard/difficult=.85, challenge=.95; missing/unrecognized
labels use .5. It is a heuristic, not a published contest calibration.
The implementation constant is named `HALF_LIFE_DAYS`, but the actual formula
uses an **e-folding time** of 45 days: weight at 45 days is approximately .368,
and the mathematical half-life is `45*ln(2)`, approximately 31.2 days.

Example: two same-age, same-difficulty attempts, one unaided correct and one
incorrect, give .5 (developing). With one hint on the correct attempt they give
.4. One unaided correct attempt alone gives 1, but **does not establish mastery
with high confidence**. Scores are recomputed after recording attempts; they
are not continuously time-updated by a clock. Uniformly aging all observations
does not change their normalized weighted average.

Current scoring does not use partial credit, time spent, solution-method proof,
problem-link role/confidence weights or the new difficulty dimensions.
The current attribution query does not explicitly restrict all mapped concept/
technique links to reviewed-only evidence. Do not describe it as a fully
validated skill diagnosis. These are limitations, not instructions to rewrite
scoring while maintaining this glossary.

## 5. Ingestion and orchestration

| Term | Clear meaning | Representation and cautions |
|---|---|---|
| Discovery | Find legitimate contest/source links. | Archive scripts and paper registry; source existence is not content extraction. |
| Download | Fetch a source artifact. | `pipeline.pdf_source.download_status`, timestamps and saved files. HTTP 200 does not certify PDF validity. |
| PDF validation | Verify an actual PDF header/content. | Shared signature validation accepts whitespace before `%PDF-` within the bounded header region; rejects HTML responses. |
| Parse / extract | Convert a document into structured question/solution content. | Docling outputs, question JSON, Markdown and page images; exact counts/provenance checked. |
| Docling | Document-conversion/parser framework. | CPU parsing with formula enrichment in archive workflows; mathematical OCR can still be imperfect. |
| OCR | Recognize text from rendered/scanned pages. | Parser output; equations and layout require verification against originals. |
| Formula enrichment | Additional mathematical transcription processing. | Docling configuration; not proof that every symbol is correct. |
| Native extraction / fallback | Alternate extraction from PDF-native text/layout. | Explicitly distinguish parser paths; a fallback must not masquerade as successful primary parsing. |
| Multimodal classification | Classify using text plus actual images. | Supported classification calls attach PNG source pages, not merely filenames. |
| Ingest / canonical import | Save parsed content to the system of record. | Postgres `core.*`; separate from local artifacts and classifier state. |
| Export | Convert local classification results into importable records. | CSV exports; an export file is not proof of canonical load. |
| SQLite staging | Local ingestion/classification database. | Ingestion `data/mathbank.db`; not the current agent session database. |
| Batch | Bounded group of work items. | Paper runner scope/batch-size options; not necessarily parallel execution. |
| Parallel batch / concurrency | Several tasks executing simultaneously. | Worker/partition configuration and locks; must avoid duplicate paid work and conflicting graph saves. |
| Run | One durable orchestration execution. | `pipeline.run`: UUID, scope, expected/completed/failed counts and times. |
| Scope / snapshot | Exact identities selected for a run. | `requested_scope`; may not include later-added sources. Full archive completion needs a full archive snapshot. |
| Work item | One trackable unit inside a run. | `pipeline.work_item`: identity, status, attempts, leases, metrics and errors. |
| Lease | Time-bounded claim on work. | Owner/expiry fields; expiration is not proof the old process has stopped. |
| Advisory lock | Database-level coordination guard. | Used to prevent conflicting paper/enrichment work; not a user login lock. |
| Idempotency | Repeating work does not duplicate canonical entities. | Stable keys, hashes, upserts and completed-stage checks. Does not mean model calls are cost-free. |
| Resume | Continue the stored scope after interruption. | Saved run UUID and completed-stage checks; not a fresh unbounded ingestion. |
| Retry | Reattempt failed work under policy. | Attempt counts, cooldown and publication outboxes. Generation and graph retries are distinct. |
| Cooldown | Earliest time before retry is due. | Worker recovery policy; not a guaranteed completion deadline. |
| Backoff | Increase delay after transient failures. | Bounded retry policy; persistent errors remain visible. |
| Timeout | Upper bound for waiting on a stage/request. | Parser/provider/service limits; not necessarily a cancellation confirmation. |
| Heartbeat | Evidence a worker recently reported activity. | Run/job times; a process PID alone is weaker evidence. |
| Outbox | Persisted work waiting for external publication. | Completed enrichment jobs with no `published_at`; save can succeed while Neo4j publication fails. |
| Input hash / fingerprint | Identity of the inputs/model settings used. | Job/representation hashes; changed input can make prior output stale. |
| Content hash | Fingerprint of canonical or rendered content. | Detect changes/deduplicate/rebuild; not semantic equivalence. |
| Dependency gate | Refuse downstream work until prerequisites are complete. | ARML queue's exact Purple scope/stage/vector checks; implementation alone does not activate the queue. |
| Backfill | Process existing records missing a derived output. | Embedding/enrichment tools; no worker running means there is no automatic completion ETA. |
| Re-embedding | Recreate vectors after text/model changes. | Versioned representations/models and embedding jobs. |
| CPU / GPU | Compute devices used for parsing/inference. | Archive parsing defaults to CPU; changing hardware is not a substitute for count/layout verification. |

## 6. Graphs, vectors and hybrid RAG

| Term | Clear meaning | Representation and cautions |
|---|---|---|
| Graph | Entities connected by typed relationships. | Neo4j nodes/edges projected from reviewed Postgres assertions. |
| Node | One graph entity: Problem, Concept, Technique, Skill, etc. | Identity/properties, not just a label drawn by the UI. |
| Edge / relationship | Directed typed link between nodes. | Endpoints, type, role, confidence, provenance and approval metadata matter. |
| Corpus graph | Content/topic/method associations. | Projected problem-concept/technique and corpus relationships. |
| Pedagogical graph | Skills, requirements, prerequisite paths and difficulty evidence. | Separate generation and publication from corpus graph. |
| Taxonomy graph | Relationships among concepts/skills. | Dedicated relationship enrichment; empty hierarchy is not fixed by relabelling prerequisite edges. |
| Graph projection / publication | Copy approved canonical data into Neo4j. | Projection tracking and `published_at`; not another source of truth. |
| Graph watermark | Time/version boundary observed during projection. | `pipeline.graph_projection.source_watermark`; not proof all newer writes are visible. |
| Routing / disconnected-session error | Neo4j connectivity/session failure. | Publication/retrieval error; may be transient. Metadata may already be saved successfully. |
| Graph inventory agreement | Verify expected and observed nodes/edges. | Compare identities, direction and provenance, not merely equal total counts. |
| Vector / embedding | Numeric representation of text meaning. | `search.embedding`; vectors are not factual assertions or learner scores. |
| Embedding model | Algorithm/version defining vector space. | `search.embedding_model`; current OpenAI `text-embedding-3-small`, 1536 dimensions. |
| Dimensions | Number of coordinates in each vector. | 1536 for the active model; wrong dimensions/model spaces are incompatible. |
| Representation | Versioned text rendered for indexing. | `search.representation`; statement/solution entity, kind, profile, hash and status. |
| ACTIVE / SUPERSEDED representation | Current vs replaced indexed text version. | Search must exclude superseded and current-text-mismatched representations. |
| Chunk | Retrieval-sized segment of a representation. | `search.chunk`: ordinal, text/hash, token/character counts and canonical IDs. |
| Document | Ambiguous counting unit. | Specify PDF source, canonical problem, solution, representation or chunk; never interchange their totals. |
| Token | Model text-processing unit. | Tokenizer counts; not equivalent to a word or character. |
| pgvector | Postgres extension for vector storage/search. | Vector columns, cosine queries and model-specific ANN indexes. |
| Cosine distance / similarity | Measure relative vector direction. | Lower distance / higher similarity ranks related text; not a correctness or mastery probability. |
| HNSW | Approximate-nearest-neighbor graph index. | Accelerates vector search; “graph index” here is not the Neo4j pedagogical graph. |
| ANN | Approximate nearest-neighbor retrieval. | Speed/recall trade-off; distinct from exhaustive exact search. |
| Semantic retrieval | Find meaning-related text by embeddings. | Query vector against current problem/solution chunks. |
| Lexical retrieval / FTS | Match words/text tokens. | Postgres `tsvector`, `tsquery`, `ts_rank`; lexical rank applied before candidate limit. |
| Trigram | Three-character substring similarity/indexing. | `pg_trgm`/GIN support; not an embedding model. |
| Graph retrieval | Select candidates using reviewed entity/relationship evidence. | Neo4j tag/skill matches and shared-tag expansion, hydrated from canonical Postgres. |
| RAG | Retrieval-augmented generation: supply corpus evidence to a model. | Agent tools -> REST retrieval -> grounded answer; retrieval does not guarantee generation correctness. |
| Hybrid RAG | Combine complementary retrieval sources. | Current graph + vector + lexical problem search; agent does not query every database directly. |
| GraphRAG | Broad term for graph-informed retrieval/generation. | Here it means typed reviewed evidence, not an implemented global community-summary algorithm. |
| RRF / reciprocal rank fusion | Combine ranked lists without equating raw scores. | Problem-level sum of `1/(60 + source_rank)` for contributing sources. |
| Candidate | Possible hit before final ranking/filter/hydration. | Bounded retrieval pools; not automatically shown to the learner. |
| Rank | Position in an ordered result list. | Per-source ranks retained; graph rank and semantic rank are not numeric scores on one scale. |
| Evidence | Basis for including/explaining a hit. | `graph_evidence` and source/rank metadata; not hidden model reasoning. |
| Canonical hydration | Fetch full authoritative records for candidate IDs. | Postgres lookup plus rechecked competition/year filters. |
| Deduplication | Avoid repeated problem entries from several chunks/sources. | Problem-level fusion, then selected chunk/context; multiple chunks can belong to one question. |
| Filter | Restrict eligible results by explicit criteria. | Competition/year and source switches; filters applied before ranking where possible and rechecked. |
| Grounding | Tie claims to retrieved evidence. | Tutor must not invent problem identities, official solutions or mastery evidence. |
| Answer leakage | Reveal a solution when only teaching context was requested. | Similarity guidance uses answer-free learning context; solutions require appropriate tutoring stage. |
| Degraded retrieval | Return available sources while clearly reporting one unavailable source. | Neo4j outages produce warnings and unavailable graph status; vector/provider errors are not disguised as successful empty search. |
| Relevance score | Retrieval ranking signal. | RRF/lexical/vector signals, **not** a probability of student success or truth. |

## 7. Services, agent behavior, UI and configuration

| Term | Clear meaning | Representation and cautions |
|---|---|---|
| Postgres / PostgreSQL | Relational canonical database. | `core`, `knowledge`, `search`, `pipeline`, `learner`, `audit` and agent-session schemas. |
| Neon | Hosted Postgres provider. | Remote SSL connection; quota/connectivity affects persistence, not just model calls. |
| Neo4j / AuraDB | Graph database / hosted Neo4j service. | Derived graph accessed with Bolt/Neo4j driver; local server and Aura credentials differ. |
| SQL schema | Logical namespace in Postgres. | Separates domain/operational/session tables, not necessarily separate servers. |
| REST / API | HTTP interface to corpus and teaching operations. | FastAPI `mathbank-rest`, normally port 8000; `/v1` endpoints and `/docs`. |
| Swagger / OpenAPI | Interactive API explorer / machine-readable contract. | `/docs` and `/openapi.json`; availability does not prove model authentication. |
| ADK | Google Agent Development Kit orchestration framework. | `mathbank-agent`; framework choice does not require a Google model. |
| LiteLLM | Adapter routing model requests to providers. | Agent `LiteLlm`, e.g. `openai/gpt-4o-mini`; provider prefix is significant. |
| OpenAI SDK | Client used for embeddings/chat/completion operations. | REST/ingestion/embedding clients; project key loader is explicit. |
| Chat model vs embedding model | Generate language vs generate vectors. | Agent model and `text-embedding-3-small` perform different jobs; successful embeddings do not certify chat model access. |
| Tool / function call | Agent requests a defined application operation. | REST-backed tools with structured parameters/results. |
| Agentic workflow | Model selects tools/actions over several steps. | ADK turn/session; not unrestricted autonomous database modification. |
| Agentic thinking / progress | User-visible evidence of workflow steps. | Tool starts/results, retrieval provenance, stage/status updates; not exposure of private chain-of-thought or fabricated introspection. |
| Stream / SSE | Incremental events rather than one final response. | Agent/web event handling; tool lifecycle and answer text are different event types. |
| Session | Persisted conversation context. | ADK `DatabaseSessionService` on Postgres `agent_sessions`; not SQLite ingestion state. |
| Turn | One user interaction plus agent processing. | Session events/messages/tool activity; can include several model/tool calls. |
| Session isolation | Keep one learner's conversation separate from others. | Application/user/session identifiers and authenticated ownership; storage on one server does not permit public cross-user access. |
| Progressive hint | Reveal help incrementally without immediately giving the answer. | Teaching tool/UI; hint count is separate recorded attempt metadata. |
| Scaffold / subproblem | Break a difficult task into smaller tasks. | REST decomposition and answer-checking tools; generated scaffold is not an official solution. |
| Next.js / React | Web application/server-rendering framework / UI library. | `mathbank-web`, usually port 5173; API proxies keep credentials server-side. |
| Bootstrap | UI styling/layout component system. | Responsive full-width layouts, cards/tables/forms/badges; appearance does not establish pipeline completeness. |
| SSR / hydration | Server-render HTML / React attach client behavior. | Initial server/client output must agree; unstable timestamps/invalid nesting can cause mismatch. |
| Proxy / BFF | Web-server forwarding layer to backend services. | Next API routes attach backend keys server-side; browser must not receive model/admin secrets. |
| Student authentication / JWT | Identify learners through signed tokens. | Learner endpoints; signing secret and token expiry are independent of OpenAI auth. |
| Admin session | Access to privileged web console. | Signed web session plus guarded admin proxy; not the same as a backend API key. |
| Admin API key | Shared backend administrative credential. | Header `X-Admin-Api-Key`; distinct from OpenAI API key and student JWT. |
| `.env` | Local configuration file excluded from Git. | Root file distributes service settings; OpenAI loader treats root key as authoritative without shell interpolation. |
| Shell environment | Inherited process variables, possibly set by a shell profile. | **Ignored for OpenAI credentials/routing**; other DB/worker configuration retains documented existing precedence. |
| `.zshrc` | Zsh user profile shared by many projects. | MathBank does not read/edit/source it; changing it is not needed for this project's key selection. |
| Environment sync | Distribute root configuration to service files. | `make sync-env` / `make sync-openai-key`; key-only sync preserves unrelated settings, writes owner-only files. |
| Provider configuration | Endpoint, organization/project and provider identity. | OpenAI file settings; inherited routing values cleared when absent from files. An alternate URL must be deliberately configured. |
| Authentication vs authorization | Valid identity vs permission to use a resource. | A valid OpenAI key can lack model permissions or billing quota. |
| HTTP 401 / 403 / 404 / 429 | Auth failure / forbidden / missing resource / rate or quota limit. | `make check-openai` and optional paid LiteLLM check report safe status details, not provider bodies containing partial keys. |
| Rate limit vs quota | Short-term request/token cap vs allocated/billing resource cap. | Both may surface as 429; do not assume a key is invalid. |
| Secret hygiene | Prevent credential exposure. | No keys in code, CLI arguments, browser bundles, logs or Git; share files only over secure channels. |
| PID / pidfile | Process identity / saved identity used for lifecycle management. | Verify executable/port ownership; never kill unrelated processes by name or port indiscriminately. |
| Health / readiness | Process endpoint responds / service is ready for specified use. | Startup HTTP readiness is narrower than a verified DB/model end-to-end interaction. |
| Local vs remote | Databases on this machine vs hosted services. | `make up-app` needs no local DB daemons when Neon/Aura configured; explicit environment routing matters. |

## 8. Admin metrics, completion and evaluation

| Term | Clear meaning | Representation and cautions |
|---|---|---|
| Nine-layer paper completion | All applicable processing layers are evidenced. | Download, parse, ingest, classify, vectors, corpus graph, pedagogy, pedagogy graph, taxonomy relationships. |
| PENDING work | Has not yet completed/started as recorded. | Stage-specific state; not the same as review approval pending. |
| IN_PROGRESS / RUNNING | Work is recorded as active. | Check heartbeat and ownership; a stale status can survive a process crash. |
| COMPLETED | Evidence meets the specified stage/run contract. | Paper-run completion can cover fewer layers than full nine-layer completion. |
| FAILED | A stage could not satisfy its contract. | Error/stage/log reference; distinguish generation failure from publication failure. |
| STALLED | Activity evidence is older than policy allows. | Admin interpretation of heartbeat; not a claim that content is corrupt. |
| UNKNOWN | Cannot observe enough evidence, e.g. graph unavailable. | Warning with observed-at time, not a green success or an invented zero. |
| NOT_TRACKED | Historical/source stage has no reliable tracker. | Do not infer completed timestamps from filesystem or another unrelated event. |
| Observed at | Time metrics/status were queried. | Snapshot timestamp; not the time work finished. |
| Started / completed / published at | Different lifecycle events. | Stage/run timestamps and graph publication timestamp; missing historical times remain unrecorded. |
| Expected vs actual count | Target inventory vs verified inventory. | Scope/questions/chunks/edges must name their units and identities. |
| Vector coverage | Current required entities/chunks have active-model embeddings. | At least one vector per problem is a weaker proxy than complete current statement/solution chunk coverage. |
| Classification coverage | Expected imported canonical mappings exist. | Completed SQLite classifier count alone is insufficient. |
| Graph coverage | Expected approved entities/edges are visible. | Counts plus identity/direction/provenance checks; filtered view node count is not total database size. |
| Pedagogy coverage | Skill mappings and difficulty metadata available. | Separate from concepts/techniques and separate from publication. |
| Throughput / rate | Completed units per elapsed time. | State unit/window, e.g. papers/hour vs questions/hour; mixed stages have different costs. |
| ETA | Estimated finish time using observed backlog/rate. | Conditional forecast, not guarantee; unavailable workers, retries and changing denominators invalidate simple extrapolation. |
| SLA | Agreed measurable service-level commitment. | No contractual completion SLA inferred from one observed run; define scope, thresholds and observation method first. |
| SLO | Target reliability/latency for a service. | Requirement/evaluation target, not achieved merely by documenting it. |
| Latency | Time for a request/stage to finish. | Distinguish retrieval, generation, graph query and entire pipeline latency. |
| Precision@k | Fraction of first k retrieved hits judged relevant. | Requires labelled relevance evaluation; successful HTTP/search does not prove target precision. |
| Recall@k | Fraction of known relevant items found in first k. | Needs a ground-truth relevant set; not corpus coverage. |
| MRR | Mean reciprocal rank of first relevant result. | Ranking quality across labelled queries. |
| NDCG | Ranking measure giving graded relevance and earlier hits more value. | Evaluation design, not the RRF runtime score. |
| Grounded-answer quality | Whether generated claims are supported by evidence. | Requires answer evaluation, not vector similarity alone. |
| Hallucination | Unsupported invented claim/content. | Tutor constraints and tests reduce risk; retrieval cannot eliminate it by itself. |
| Acceptance criterion | Explicit measurable definition of “done.” | Requirements/tests; do not verify a convenient proxy instead. |
| Unit / integration / live test | Isolated logic / component interactions / actual services. | Tests have different costs and proof boundaries; paid/live calls are explicit. |
| Regression | Unintended behavior change. | Focused tests for shell-key precedence, classification, retrieval and scoring. |

## 8b. Textbook packages, solution steps and learning items (v2)

| Term | Meaning | Representation |
|---|---|---|
| Content package | One versioned, hash-identified import bundle (for example a Prasolov `pedagogy_v3/` folder). It is an input, not the production store. | `ingest.content_package` (status REGISTERED → … → POSTGRES_COMPLETE), files in `ingest.package_file`, status history in `ingest.package_status_event`. |
| Staging row / import conflict | A raw CSV row kept for audit, and a recorded, non-fatal source problem (duplicate, orphan, count mismatch). | `ingest.staging_row`, `ingest.import_conflict` (severity INFO/WARNING/ERROR). |
| Reconciliation | The check that source count = staging count = database count for each entity and scope. | `ingest.reconciliation.reconciled`; printed by `make -C mathbank-db textbook-import-status-remote`. |
| Textbook / chapter paper | A book is modeled as a competition with an undated edition. Each chapter is a paper. | `core.competition` `PRASOLOV_PGV1` (level TEXTBOOK), `core.competition_edition.year` NULL, papers `PRASOLOV_PGV1_CH01…CH30`. |
| Solution part | One labeled section of a worked solution (for example "a)"). | `pedagogy.solution_part`; graph `(:Solution)-[:HAS_PART]->(:SolutionPart)`. |
| Solution step | The smallest tutorable reasoning unit. It has a type, a tutor role, a hint level and a checkpoint flag, and it exercises one skill/concept/subconcept. | `pedagogy.solution_step` (text lives only here); graph `:SolutionStep` with metadata only, plus `USES_SKILL`/`USES_CONCEPT`/`USES_SUBCONCEPT`. |
| Step dependency (DAG) | A directed logical relation between steps: `NEXT` is reading order; `DEPENDS_ON` and the others are semantic. The relation must be acyclic and have no self-loops. | `pedagogy.solution_step_dependency`; graph step-to-step edges with confidence, source_type and review_status. |
| Occurrence | Disambiguates a repeated source ID. The second copy of `P-1.1-a` becomes `P-1.1-a#2`. | `occurrence` columns; the `#k` suffix in primary keys. |
| Learning item | A reviewable no-proof transformation of a source problem (MCQ, subproblem, numeric variant, …) used for practice and recovery. | `pedagogy.learning_item` (imported as PENDING_REVIEW; `student_visible` requires APPROVED), `learning_item_step_anchor`; graph `:LearningItem` only after approval. All 11,186 Prasolov items are auto-approved (Phase 10). |
| Diagram visibility | `STUDENT_PROBLEM` figures may be shown with the problem. `SOLUTION_HIDDEN` figures reveal the solution and must never be shown before the solution is. | `pedagogy.diagram.visibility`; only STUDENT_PROBLEM rows link to `core.problem_image`. |
| Taxonomy node bridge | A mapping from package taxonomy IDs (DOMAIN/CONCEPT/SUBCONCEPT/SKILL/TECHNIQUE) to canonical knowledge rows. | `pedagogy.taxonomy_node.concept_id/skill_id/technique_id`; graph `:Concept:Subconcept` label for subconcepts. |
| Projection kind | A tag that marks which projector owns a graph node or edge, so that each projector deletes or replaces only its own data. | `projection_kind` property: `pedagogy` (batch replacement), `solution_steps` (textbook step layer), and others. |
| Step vector / step retrieval | An embedding of a step's metadata and text, used to find similar reasoning steps (same skill) in *other* problems. Filters are hard filters; the vector side and the lexical side are fused with RRF. | `search.representation` kind `SOLUTION_STEP` (profile `pedagogy_step_v2`); `db/step_search.py`; `GET /v1/solution-steps/{id}/practice` never returns step text. |
| Solve attempt (step runtime session) | One student working one problem step by step. At most one open session per student and problem; "start" resumes it. Not the same as a legacy *attempt* (one graded answer). | `learner.solve_attempt` (IN_PROGRESS → SUBMITTED/COMPLETED/ABANDONED). Completion writes one `learner.attempt` row (`source='step_runtime'`) that feeds mastery. |
| Step state | Where the student is on each step: NOT_SEEN → PRESENTED → ATTEMPTED → SUCCESS_INDEPENDENT / SUCCESS_WITH_HELP / FAILED (→ RETRY_PRESENTED) / SKIPPED. | `learner.attempt_step_state`; *independent* success is only possible with help level 0 (DB CHECK). |
| Help level | How much help was used on a step: 0 none, 1 directional prompt, 2 concept reminder, 3 strategic hint, 4 near-explicit step, 5 full reveal. Any help makes success "with help". | `attempt_step_state.help_level_used`; `HINT_REQUESTED` events. Text for levels 1–4 is generated and cached in `pedagogy.step_hint`; level 5 returns the reference step. |
| Learner event | An immutable fact about what happened (step presented, response submitted, hint requested, step evaluated, …). Corrections are new events, never edits. | `learner.event`; the `event_append_only` trigger blocks UPDATE/DELETE. |
| State version | An optimistic-concurrency counter for a session. Every mutation sends the version it saw; a stale one is rejected so two tabs can't overwrite each other. | `tutor.runtime_state.state_version`; HTTP 409 `STATE_VERSION_CONFLICT`. |
| Idempotency key | A client-chosen request ID. Retrying the same request replays the original response; reusing the key for a different request is an error. | `Idempotency-Key` header → `learner.idempotency_record`; HTTP 422 `IDEMPOTENCY_KEY_REUSED`. |
| Step grader (evaluator) | The server-side check of a student's step response against the canonical step. The model returns a verdict, a confidence and a failure mode; the runtime turns that into SUCCESS or FAILED. Students never grade themselves. | `step_tutor.evaluate_step` (`STEP_TUTOR_MODEL`); applied by `record_step_outcome`; stored in `attempt_step_state.last_evaluation` and the `STEP_EVALUATED` event. |
| Verdict | The grader's judgement: CORRECT, PARTIALLY_CORRECT, INCORRECT or OFF_TOPIC. Only CORRECT with confidence ≥ 0.6 counts as success. | `last_evaluation.verdict`; shown to the student with the feedback. |
| Failure mode / failure location | Why a step failed (pack 13 list, e.g. NOT_RECOGNIZED, CALCULATION_ERROR) and where (setup, reasoning, computation, …). Teacher-facing evidence for gap diagnosis. | `last_evaluation.failure_mode` / `failure_location`; never sent to the student. |
| Leak guard | A check that a hint or feedback doesn't give away the step: no 7-word run copied from the canonical step that the student doesn't already have. | `step_tutor.leaks_solution`; leaking feedback is redacted (`feedback_redacted`), leaking hints are retried or replaced by a template. |
| Hint ladder / hint cache | The five ordered help levels a student climbs one at a time (nudge → concept → strategy → near-explicit → reveal). Generated hints are reused for every student. | `pedagogy.step_hint` keyed by (step, level, `prompt_version`); `GET /v1/attempts/{id}/steps/{step_id}/hints` restores the ladder. |
| Step goal | A student-safe description of what the current step should achieve, derived from its `step_type`, so the student knows the target without seeing the answer. | `current_step.goal` in the runtime payload (`step_tutor.STEP_GOALS`). |
| Solution timeline | The solve-page list of all steps with their state. Future steps are opaque (part and index only); completed steps show the reference step next to your response. | `runtime.timeline`; rendered at `/learn/solve/{code}`. |
| Transactional outbox | A change notice written in the same transaction as the state change, so downstream consumers (graph, analytics) never miss or double-apply it. | `pipeline.outbox_event`, `pipeline.outbox_consumption` (consumer worker not built yet — doc 20 NYI-P6). |
| Gap diagnosis | One evidence-based run that asks "which missing skill most likely explains why this step failed?". It is deterministic (rules `rules-v1`), not a model guess, and it never overwrites earlier runs. | `pedagogy.gap_diagnosis` (trigger AUTO / STUDENT_REQUEST / TUTOR); `POST /v1/attempts/{id}/steps/{step_id}/diagnose`; auto-run after a step fails twice or after 3+ hints. |
| Knowledge gap (hypothesis) | One ranked candidate cause inside a diagnosis: the step's own skill, a skill from an earlier step it depends on, a subconcept pattern, or a background concept. It carries a confidence (0.05–0.95, admin-only); students see likely / possible / worth checking. | `pedagogy.knowledge_gap` (`rank`, `failure_location`, `failure_mode`, target concept/subconcept/skill, `confidence`). |
| Hypothesis status | Whether later evidence supported a gap: UNRESOLVED → CONFIRMED (failed again on that skill) → RESOLVED (later solved independently), or UNRESOLVED → REJECTED (solved independently, so it wasn't the gap). Success with help doesn't count. | `knowledge_gap.status`, `status_reason`; event `GAP_HYPOTHESIS_RESOLVED`. |
| Recommended action | What the diagnosis suggests next: RETRY_WITH_HINT (a slip, or a skill already shown), DIAGNOSTIC_PROBE (unsure: try a quick check), RECOVERY_DETOUR (confident gap: short detour, Phase 10). | `gap_diagnosis.recommended_action`; shown as the card badge. |
| Diagnostic probe | A short check that tests one hypothesised skill: an approved learning item first, otherwise an unseen step with the same skill from another problem (step text hidden). Never the problem the student is stuck on, never a cross-reference stub. | `gap_diagnosis.probes`; links on the "What's tripping you up?" card. |
| Evidence fingerprint | A hash of the evidence behind a diagnosis (tries, help, grader verdict, history, predecessor steps), not the step state. Same evidence → the same diagnosis is reused instead of a duplicate. | `gap_diagnosis.evidence_fingerprint`, unique per attempt and step; response field `reused`. |
| Auto-approval (learning items) | An operator step that marks structurally valid imported items APPROVED and student-visible without a human reviewer. It is a product decision for now, not expert certification. | `make -C mathbank-db textbook-approve-learning-items-remote`; `learning_item.approval_method='automatic'`, `approved_at`. `human` is reserved for the future review UI. |
| AI re-rank | An optional model pass that may **reorder** the rules-v1 hypotheses of a diagnosis, never add or drop them. Off by default. | `DIAGNOSIS_LLM_RERANK=1`, model `DIAGNOSIS_RERANK_MODEL` → `STEP_TUTOR_MODEL` → `gpt-4.1-mini`; stored in `gap_diagnosis.ai_rerank`; "AI-ranked" badge. |
| Recovery plan (detour) | A short, staged side-trip that strengthens one gap skill, then returns the student to the exact step they were stuck on. Offered, never forced. | `pedagogy.recovery_plan` (trigger DIAGNOSIS / STUDENT_REQUEST / TUTOR / BRANCH; status ACTIVE, SUSPENDED, COMPLETED, EXHAUSTED, ABORTED, SUPERSEDED); `step_recovery.py` (`recovery-rules-v1`); `POST /v1/attempts/{id}/recovery-plans`. |
| Recovery stage | The ordered phases of a detour: FOUNDATION (theory or worked example) → RECOGNITION → ISOLATED_EXECUTION → GUIDED_APPLICATION → TRANSFER → RETURN_TO_STEP. | `recovery_plan_item.stage`; the stage track in the solve page. |
| Recovery item | One thing to do inside a detour: a learning item (MCQ or subproblem), a theory card, or the final RETURN. Two tries each. | `pedagogy.recovery_plan_item` (kind LEARNING_ITEM / THEORY / RETURN; status PENDING → PRESENTED → PASSED / FAILED / SKIPPED). MCQ graded by choice, subproblem by the step grader, theory by acknowledgement. |
| Adaptation decision | What the planner does after an item: ADVANCE, CONFIRM (right after a miss → one extra item at the same stage), RETRY, ALTERNATE (swap in a different item) or BRANCH (one-level sub-detour on a prerequisite; the parent is SUSPENDED). At most 3 added items. | Response field `decision`; `recovery_plan_item.added_reason`; event `RECOVERY_PLAN_BRANCHED`. |
| Mastery policy (detour) | The rule that ends a detour as successful: 2 first-try successes plus a passed transfer item. Meeting it → COMPLETED and the gap → RESOLVED; running out of items → EXHAUSTED and the gap stays CONFIRMED. It does not write `learner.mastery`. | `recovery_plan.mastery_policy`, `mastery`; student text "first-try goal met (N ✓)". |
| Return to step | Leaving a detour: the origin step goes from DETOURED back to "Try again" (RETRY_PRESENTED) with its tries and hints kept. `/resume` after a finished plan; `/abort` to leave early. | `POST /v1/recovery-plans/{id}/resume` / `abort`; events `RETURNED_TO_ORIGINAL_STEP`, `RECOVERY_PLAN_ABORTED`. |
| Cross-reference stub | Source text that only points elsewhere ("Solution is similar to … heading a)") and can't stand alone. Excluded from recovery, worked examples and probes. | `CROSS_REFERENCE_STUB_RE` in `step_runtime.py` (118 items, 204 steps match). |
| Knowledge-gaps console | The admin page that lists gap hypotheses and detours across students, with totals, top open targets and a teacher view of each plan. Read-only. | `/admin/knowledge-gaps`; `GET /v1/admin/knowledge-gaps`, `GET /v1/admin/recovery-plans[/{id}]`. |
| Topic closeness | Ranking signal for recovery worked examples and practice items: 2 = same subconcept as the stuck problem, 1 = same concept, 0 = neither. Applied after skill match, before variety. Prevents off-topic examples (e.g. an inversion step for a radical-axis problem). | `step_recovery._candidates` / `_worked_example`, joined through `pedagogy.problem_enrichment`. |

## 8c. Agent conversations and regression testing

| Term | Meaning | Representation |
|---|---|---|
| Agent session | One tutor chat thread kept by Google ADK. MathBank does not own its tables. | Framework schema `agent_sessions` (`sessions`, `events`; naive-UTC timestamps); `user_id` = student UUID or `anonymous`. |
| Agent session link | The project-owned record that a given ADK session belongs to a given student, on a surface (home chat / solve workspace). Created only when the ADK row's `user_id` equals the student. | `learner.agent_session_link` (migration 016), unique `(agent_app_name, agent_session_id)`, cascades on learner deletion. |
| Transcript (rebuilt conversation) | The ordered messages of a session rebuilt from stored ADK events. Students see their text and tutor replies; admins also see thinking, tool calls and truncated tool results. | `GET /v1/learner/agent-sessions/{id}/transcript`, `GET /v1/admin/agent-sessions/{id}/transcript`; pages `/learn/conversations`, `/admin/conversations`. |
| Unlinked (anonymous) session | A chat started while signed out. Stored by ADK, never linked or claimable; admins see only a count. | `unlinked_count` in `GET /v1/admin/agent-sessions`. |
| E2E regression suite | Playwright browser tests run against the live local stack. `@llm` specs make paid calls and run only on request. | `mathbank-web/e2e/*.spec.mjs`; `make -C mathbank-web e2e` / `e2e-llm`; [23](23_E2E_REGRESSION_SUITE.md). |
| Coverage matrix | Per-entity comparison of source CSV rows (summed across packages) with Postgres rows, embedded rows (pgvector) and Neo4j nodes/edges. Status is `OK` (every expected store complete), `GAP` (an expected store is short), `UNKNOWN` (graph not reachable) or `PROVENANCE`. | `GET /v1/admin/textbooks/coverage`; Coverage tab of `/admin/textbooks`; [24](24_ADMIN_TEXTBOOK_CORPUS_DASHBOARD.md). |
| Provenance-only file | A raw source CSV kept for audit (hashed and registered) but deliberately not imported, because an enriched file supersedes it (e.g. `csv/transformations.csv`, `problem_concepts.csv`). | `ingest.package_file` row with role RAW; `PROVENANCE` row in the coverage matrix. |
| Textbook corpus dashboard | Read-only admin view of every imported textbook problem with its solution, parts/steps, dependencies, transformations, taxonomy, diagrams (including solution-hidden ones) and per-store status. | `/admin/textbooks`, `/admin/textbooks/problems/{canonical_code}`; `/v1/admin/textbooks/*`. |

## 8d. Fluid widgets, live classroom and student add-ons

| Term | Meaning | Representation |
|---|---|---|
| Presentation plan | A versioned, admin-authored lesson outline: ordered topics with planned seconds and scenes, plus course time limits. Once PUBLISHED it cannot change; edits make a new version with the same `plan_key`. | `authoring.presentation_plan`, `authoring.plan_topic`; `/v1/authoring/presentation-plans/*`; [27](27_FLUID_WIDGET_LAYER.md). |
| Proposed patch | The structured operations that an admin chat message compiles into (e.g. `UPDATE_TOPIC_TIME`), with an impact preview. Nothing changes until an explicit APPLY. | `authoring.proposed_patch`; `…/proposed-patches/{id}/apply`. |
| Live session | One real-time class run of a plan, joined by code. Holds control mode (AI_ACTIVE / INSTRUCTOR_ACTIVE), `state_version` and an event sequence. | `live.session`, `live.participant`; `/v1/live/sessions/*`; [28](28_DISTRIBUTED_LIVE_PLATFORM.md). |
| Session event | An append-only, ordered record of a live change. A reconnecting client replays everything after its last `sequence`. Its audience is SESSION, STUDENT, INSTRUCTOR or GROUP. | `live.session_event` (UPDATE blocked by trigger), mirrored to `pipeline.outbox_event`. |
| Command receipt | The stored outcome of a live command, keyed by `client_command_id`. A retry returns the original result with `duplicate: true`. | `live.command_receipt`. |
| Takeover | An instructor taking control of a session, student or group. While active, AI tutor messages are refused (409 `AI_NOT_IN_CONTROL`) and pending AI recommendations become STALE. | `live.takeover`; commands `TAKEOVER` / `RELEASE` / `LOCK_AGENT`. |
| Recommendation | A proposed live action from the AI tutor, poll branch, time orchestrator or instructor NL command. Low-risk ones auto-apply when the AI is in control; the rest wait for the instructor. | `live.recommendation` (`based_on_version`, PROPOSED/ACCEPTED/REJECTED/STALE). |
| Activity | A quiz/poll item. The definition is reusable; an instance is one opening in a session; a response is one per participant. | `activity.definition`, `activity.instance`, `activity.response`; types MCQ … LIVE_POLL. |
| Poll branch | The next-step suggestion from poll correctness: ≥80 % CONTINUE, ≥50 % REINFORCE, otherwise PREREQUISITE. | `POLL_BRANCH` recommendation. |
| WidgetSpec | Versioned declarative JSON for one of 13 registered visual types. It is validated (no scripts/HTML/handlers, ≤64 KB, ≤300 elements) before it is stored or shown. | `visual.widget_spec`; `/v1/widgets/*`; `mathbank-widgets` `WidgetHost`. |
| Widget persistence | STATIC (reusable template), SESSION (kept with the session) or EPHEMERAL (throw-away). Promotion to a template needs admin review. | `visual.widget_spec.persistence`, review NOMINATE/PROMOTE/REJECT. |
| Socket gateway | The Socket.IO server inside `mathbank-live`. It authenticates, joins rooms, relays commands to REST and fans out events. It holds no business state. | `mathbank-live/lib/gateway.mjs`, `ws://localhost:5174/socket.io`. |
| MathComposer | The student text box with a symbol palette, quick (deterministic) and ✨ (agentic) formatting, and a live KaTeX preview. | `mathbank-widgets/src/MathComposer.jsx`; [29](29_STUDENT_INPUT_ADDONS.md). |
| Agentic formatting | A small model adds LaTeX delimiters without changing the student's words. If its output fails validation, the deterministic result is used. | `POST /v1/tutor/format-math` `mode=agentic`; `math_format.py`. |
| Voice (TTS/STT) | ElevenLabs read-aloud (🔊) and dictation (🎤), proxied by Next.js server routes so the key stays server-side. | `/api/voice/{health,tts,stt}`; `ELEVEN_API_KEY`. |
| Multimodal submission | A student-owned attempt containing private uploads and versioned transcribed work. It is not a live-class event or graph node. | `attempt_media.submission`; `/v1/attempt-media/submissions`; migration 021. |
| Evidence region | A page rectangle or timestamp interval tied to a media asset; each step and assessment references evidence IDs. | `attempt_media.evidence_region`; spatial and temporal coordinates are mutually exclusive. |
| Transcription candidate | Immutable version of machine-transcribed or student-edited steps and their evidence links. New edits create a new version rather than rewriting approved mathematical content. | `attempt_media.transcription_candidate`, `step_candidate`, `step_candidate_evidence`. |
| Approved multimodal attempt | An explicit student approval linking one exact transcription version to a `learner.attempt` row. Approval itself does not assert correctness. | `attempt_media.approval`; the linked attempt has `source='multimodal_approved'` and `is_correct=NULL`. NULL is excluded from mastery. |
| Step assessment / instructor override | Evidence-grounded, versioned alignment and correctness assessment; instructor rows are protected from AI overwrite. This is not a calibrated skill/mastery score. | `attempt_media.step_assessment`; `AI` or `INSTRUCTOR`; `/analyse` or admin `/override`. |
| Private attempt event | Ordered progress/status event, replayable only after ownership checks. The transactional outbox gets identifiers and sequence/version metadata, not private media or transcript content. | `attempt_media.event`; `pipeline.outbox_event`; `mathbank-live` `attempt:watch` emits to that socket only. |
| Declarative artifact plan | Strict structured instructions for a subject-specific diagram, equation card or frame sequence; output generation and validation are deterministic. | `ArtifactPlan`; `/v1/artifacts/validate`; migration 022. |
| Artifact bundle | Versioned, validated package of artifact metadata and private object-store assets; draft bundles are admin-only and students see published bundles. | `artifact_runtime.artifact_bundle`, `artifact_asset`, `artifact_lineage`; `/v1/artifacts/bundles/*`. |
| Artifact publication | Explicit validated change from DRAFT/VALIDATED to PUBLISHED/APPROVED, requiring staff. It does not publish a Neo4j graph projection. | Admin `POST /v1/artifacts/bundles/{id}/publish`; validated bytes remain in private object storage. |
| Explicit artifact embedding | A vector indexed for one bundle using a supplied vector or an explicit provider request; its source-text hash, model and dimensions must match. | `artifact_runtime.artifact_embedding`; semantic retrieval reports UNAVAILABLE rather than falling back to lexical search. |
| Private object store | S3-compatible storage for attempt media and generated artifact bytes. REST serves bytes only through owner/publication checks, never public or presigned URLs. | `AWS_ENDPOINT_URL_S3` and storage credentials; separate from Neon Auth and AI Gateway configuration. |

`attempt_media` and `artifact_runtime` are source-implemented schema/runtime surfaces; their migration application and object-store deployment acceptance are not verified by these documentation references. They are not projected into Neo4j.

## 9. Planned terms that must not be confused with live functionality

- **Course / curriculum / learning path:** versioned ordering of lessons,
  skills and practice. Rich course orchestration is roadmap work; an existing
  prerequisite path is not a complete course.
- **Calibrated skill mastery:** a validated estimate of performance against
  observable skill objectives. Multimodal step assessments are versioned
  evidence, not calibrated mastery; concept/technique caches remain a distinct,
  coarse model.
- **Misconception diagnosis / remediation policy:** validated interpretation
  of reasoning errors plus targeted interventions; not a generic wrong-answer
  response relabelled as diagnosis. The rules-v1 gap diagnosis and staged
  recovery detours (Phases 9–10) are implemented, but they are not validated
  misconception models.
- **Aggregated partial-credit mastery / method attribution:** the current
  multimodal assessment records step-level correctness/alignment, but no
  aggregation into mastery or method attribution is implemented. Existing
  mastery consumes assessed Boolean outcomes.
- **Expert certification:** domain-expert validation of generated metadata.
  Auto approval and a second model verifier do not establish this.
- **Retrieval-quality target achieved:** needs labelled measurement and
  recorded results, not just a working hybrid query.
- **Production OAuth / federated login:** broader identity integration; the
  current signed admin-session/shared-key bridge is not full enterprise IAM.

## 10. Authoritative implementation references

- [Canonical schema](../mathbank-db/sql/001_schema.sql), [vector schema](../mathbank-db/sql/002_vector_schema.sql), [learner schema](../mathbank-db/sql/003_learner_schema.sql).
- [Pedagogy schema](../mathbank-db/sql/006_pedagogy.sql), [automatic approval](../mathbank-db/sql/008_automatic_metadata.sql), [relationship jobs](../mathbank-db/sql/009_relationship_enrichment.sql).
- [Canonical implementation reference](reference/README.md): source-derived PostgreSQL schema through migrations 001–022, DML, graph schema, REST/OpenAPI snapshot, web proxies, multimodal attempts and artifact runtime.
- [Mastery formula](../mathbank-rest/src/mathbank_rest/mastery.py), [learner attribution and queries](../mathbank-rest/src/mathbank_rest/db/learner.py).
- [Hybrid ranking](../mathbank-rest/src/mathbank_rest/db/hybrid_search.py), [vector/lexical retrieval](../mathbank-rest/src/mathbank_rest/db/vector_search.py).
- [Pipeline metrics](../mathbank-rest/src/mathbank_rest/db/pipeline_jobs.py), [nine-layer completion requirements](16_PIPELINE_JOB_CONSOLE_AND_HYBRID_RAG.md).
- [Pedagogical roadmap](13_PEDAGOGICAL_GRAPH_AND_TUTOR_REQUIREMENTS.md), [relationship semantics](15_RELATIONSHIP_ENRICHMENT.md), [recovery behavior](14_AUTOMATIC_ENRICHMENT_RECOVERY.md).
- [Textbook import schema](../mathbank-db/sql/010_textbook_import.sql), [package importer](../mathbank-db/etl/import_textbook_package.py), [step graph projector](../mathbank-graph/etl/project_textbook_steps.py), [import tracker](18_PRASOLOV_IMPORT_AND_V2_RUNTIME_TRACKER.md), [gotchas](19_GOTCHAS_AND_OPERATIONAL_PITFALLS.md).
- [Agent session storage](../mathbank-agent/session_config.py), [file-only OpenAI credential loader](../scripts/project_env.py), [safe credential/model check](../scripts/check-openai.py), [developer setup](../README.md).

When implementation changes, update definitions, units, directions, formulas
and planned/implemented distinctions here rather than leaving incompatible
meanings in the UI, requirements and code.
