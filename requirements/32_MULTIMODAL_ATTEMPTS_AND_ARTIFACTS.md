# Multimodal attempts and instructional artifacts

Implementation source packs:
[multimodal entry point](../math_tutor_multimodal_attempt_runtime_v1/START_HERE_COPILOT.md)
and [artifact entry point](../math_tutor_artifact_agents_pack_v1/START_HERE_COPILOT.md).
All numbered documents in both packs are requirements, not evidence of completion.

## Repository audit and REUSE / EXTEND / NEW / DEFER map

This map was established before implementation against the existing REST routers,
learner queries, SQL migrations 001–020, live session runtime, widgets, Next.js
navigation, and shared UI components.

| Component | Decision | Existing surface / required work |
|---|---|---|
| Learner history | EXTEND | `learner.attempt`; approval links to history without assigning false correctness to unassessed work |
| Solution-step DAG, skills, concepts | REUSE | Existing pedagogy/step-runtime APIs and knowledge tables; alternate reasoning is allowed |
| Authentication | REUSE | Student JWT ownership and admin-key instructor boundary |
| Widget rendering / LaTeX | EXTEND | Shared widgets, MathText, themed shell and composer |
| Presentation / live runtime | EXTEND | PostgreSQL event authority, Socket.IO transport; private media must not enter classroom broadcasts |
| Object storage | NEW | No general private-media/artifact store found; authenticated Neon S3-compatible private object storage, not PostgreSQL blobs; explicit filesystem test/dev backend only |
| Media/evidence/version domain | NEW | `attempt_media` additive schema, typed coordinates/times and immutable approved versions |
| Transcription / alignment / critique | NEW | Separate typed provider stages; machine output stays candidate until explicit approval |
| Student review / instructor overrides | NEW | Original-evidence master-detail, row editing and approval; audited instructor revisions |
| Artifact metadata / subject agents | NEW | `artifact_runtime` schema, structured SVG/LaTeX, stable IDs, overlays, validation before publication |
| Vector retrieval | EXTEND | Existing pgvector dimension/model convention; explicit indexing, no implicit paid calls |
| Student evidence in Neo4j | DEFER | No private media/transcript projection; use existing concept/skill graph instead |
| Raster previews / Manim rendering | DEFER | Optional export extension, not required to publish validated SVG/LaTeX; no arbitrary renderer execution |

## Invariants

- Preserve incorrect mathematics during transcription. Raw evidence and machine
  transcription remain distinct from student edits and reasoning assessments.
- Every candidate/approved step references spatial or exact temporal evidence.
- Explicit student approval bridges into learner history; edits invalidate all
  downstream results, and stale provider writes are rejected.
- Original evidence is primary; derived SVG is labelled and optional.
- Private media access is authenticated and owner-scoped; instructor overrides
  preserve prior AI decisions and version history.
- Artifact outputs are structured, subject-aware and validated before reuse.
  Overlay targets must exist; asset bytes live outside PostgreSQL.
- Never run paid models/embeddings as a hidden side effect of audit, migration,
  browser rendering or documentation generation.

## Progress

| Surface | Implemented and verified | Remaining acceptance |
|---|---|---|
| Schema and ownership | Additive migrations 021/022 applied and reapplied idempotently to selected production Neon; six media and one artifact rollback-only SQL workflow tests passed | No private Neo4j projection |
| Evidence processing | Bounded image/PDF normalization, timestamped speech and original-video frame timestamps derived from FFmpeg `pts_time`; synthetic FFmpeg-video and mocked timestamped-speech tests | Real-provider OCR/audio/critique quality blocked by billing/quota |
| Review and history | Student edit/merge/split, explicit approval, stale-result rejection, instructor history; pending NULL correctness excluded from mastery | Derived attempt SVG is optional and deferred |
| UI | Wide themed student/instructor workspaces and artifact library; original evidence and overlays, seek controls, explicit actions and errors | Real-provider media end-to-end acceptance blocked; progress UI uses REST replay/polling |
| Private events | Owner-authorized per-socket replay and durable transactional events/outbox | Dedicated background orchestration/timeout recovery is not yet certified |
| Artifacts | Subject-aware structured SVG/LaTeX, validation, reuse/search, server-rendered frames and explicit profile-driven embedding/indexing; one 24.66-second Neon rollback-only workflow covered create/generate/publish/access/lexical+semantic search with a supplied fake 1536-dimensional vector | Workflow used mocked storage and no AI or real object bytes; no successful paid artifact embedding request |
| Agent orchestration | Existing OpenAI/ADK tutor registry includes two owner-scoped attempt-media readers and three artifact search/read/request tools; offline tool regression passed; student cannot approve through tools | No live paid agentic turn verified against new runtime |
| Storage | Authenticated Neon S3 put/read/delete and unauthenticated GET denied with HTTP 403; synthetic object cleaned up | Cross-store purge is not a distributed atomic transaction |
| Tests | Focused REST offline regression (184 passed, including voiced/silent video), six media rollback-only Neon tests, 15 agent tool regression cases, successful web build, 25 focused frontend units, 17 mocked Playwright cases and artifact rollback workflow | Live OpenAPI availability and bounded rollback/mocked checks do not establish model quality or full pack acceptance |

Implementation is persistent in the worktree, with no commit requested.
Source-derived architecture documentation and independently observed deployment
evidence are distinct; schema availability does not prove every pack acceptance
criterion. Optional rendered previews/Manim, arbitrary artifact renderer
execution, and private evidence graph publication remain deferred.

### Source-document coverage

The two [multimodal index](../math_tutor_multimodal_attempt_runtime_v1/00_INDEX.md)
and [artifact index](../math_tutor_artifact_agents_pack_v1/00_INDEX.md) enumerate
all source files. Their README/START_HERE, master instructions, prompt sequence
and WHAT_NOT_TO_DO documents are execution constraints, not additional runtime
features. Coverage below intentionally distinguishes implementation from
acceptance; unverified requirements are not marked complete.

| Multimodal document(s) | Coverage / remaining work |
|---|---|
| 01 UX; 15 student/instructor UI | Review/edit/approve workspace, original-media master/detail, overlays and seeking; desktop/mobile mocked browser tests pass |
| 02 architecture; 03 domain; 13 PostgreSQL | Private additive domain, immutable versions, evidence links, approval/history bridge and append-only overrides |
| 04 image/PDF; 05 region grounding | Original page numbering, normalized rectangles, faithful transcription stage; provider-quality acceptance blocked |
| 06 review/approval | Explicit student-only approval, edit/merge/split, optimistic concurrency; production SQL invariants verified |
| 07 audio/video | Bounded ffprobe/ffmpeg normalization and exact timestamps; speech/model quality acceptance blocked |
| 08 segmentation/alignment | Separate grouping/alignment stages; exact step inventory and published same-problem canonical references |
| 09 critique/next action | Flow-aware evidence-citing critique, alternate-method support and uncertainty guards; real model behavior unverified |
| 10 visual SVG | Original spatial/temporal evidence remains primary; optional reconstructed attempt SVG deferred, not substituted for source |
| 11 agent topology | Separate media/transcription/segmentation/alignment/critique capabilities plus existing ADK tutor; no monolithic solve/transcribe prompt |
| 12 REST/socket | Authenticated REST commands/replay and private socket event transport; web review uses polling, not classroom broadcast |
| 14 graph/vector | Reuse existing canonical pedagogy/graph context; no private-media projection or new student-evidence embeddings |
| 16 retention/security | Owner mediation, retention labels and explicit raw-media purge retaining structured approval; scheduled policy sweeps not implemented |
| 17 failure/fallback | Provider errors preserve originals/manual review; stale results rejected; interrupted-job automatic recovery not certified |
| 18 examples; 20 acceptance | Synthetic image/PDF/evidence, timestamps, ownership, approval, stale versions, retention and override tests; real-provider golden flows blocked |
| 19 phases | Core domain/API/UI deployed; optional visual reconstruction, automatic workers and live-provider quality gates remain open |

| Artifact document(s) | Coverage / remaining work |
|---|---|
| 01 architecture; 03 domain; 06 metadata; 20 schema | Additive metadata/domain schema, private object references, publication and lineage |
| 02 artifact types | Validated structured SVG/LaTeX, overlays, manifests, frames and annotations; optional raster/animation exports deferred |
| 04 topology; 07 pipeline | Ten real ADK agents with planner/subject/refinement AgentTool delegation; authenticated private preview/validation, no automatic publication or hidden model calls |
| 05 storage/pgvector | Private Neon S3 verified; model/dimension/hash-coupled indexing verified with fake vectors against production SQL |
| 08 geometry | Stable labelled vertices, lighter circles, extension/contact styling and subject validators |
| 09 algebra; 14 LaTeX | Stable equation layout, safe LaTeX assets and frame metadata |
| 10 combinatorics; 11 number theory | Explicit cases/modulus and subject-specific validation |
| 12 overlays/frames; 13 annotation | Valid-target references, ordered server-rendered frames and linked step/caption/explanation metadata |
| 15 SVG; 16 validation | Structured safe rendering, SVG allowlists, valid stable IDs; no arbitrary renderer execution |
| 17 retrieval/reuse | Lexical search, explicit semantic/index operations and exact embedding profiles; paid embedding quality blocked |
| 18 Manim | Optional export extension deferred; no arbitrary local or remote renderer execution |
| 19 REST; 21 student/tutor UI | Authenticated API/proxies and artifact library with safe private frames; tutor read/request tools registered |
| 22 examples; 24 acceptance | Geometry/algebra/combinatorics/number-theory fixtures, overlays, frames, security, storage and SQL tests |
| 23 phases | Deterministic generation/publication/reuse implemented; paid embedding verification and optional exports remain open |

### Verification and running services

- Focused REST offline suite: 184 passed, including both voiced and
  silent-video normalization; focused agent context/step/widget suite: 15 passed.
- Production Neon: six media workflow tests and one artifact workflow test passed,
  with synthetic fixtures unconditionally rolled back. The artifact test used a
  mocked object store and supplied fake vector; it made no provider call and
  wrote no real object bytes.
- Frontend: 25 focused units and 17 mocked Playwright cases passed; production
  Next.js build passed. These runs made no paid requests or real-user mutations.
- Private event/credential sync: five focused Node tests passed.
- REST and tutor services were restarted by their individually verified PIDs;
  running REST exposes 18 attempt-media and 16 artifact paths; this matched the
  source-generated OpenAPI path groups. The existing enrichment watcher was not
  stopped.
- Authenticated storage roundtrip and anonymous HTTP 403 were independently
  observed, with the named synthetic object deleted afterward.

## User-selected deployment

Target: existing Neon **production** branch. Root-file target consistency was
checked without displaying credentials: the Neon and REST PostgreSQL settings
match the explicitly supplied endpoint. Use the branch S3 endpoint, not Neon Auth
URLs. The user selected **official direct OpenAI endpoints as used by
`mathbank-agent`** for new agentic stages: the shared project credential
loader, `OPENAI_API_BASE` / `OPENAI_BASE_URL`, and service
`MATHBANK_AGENT_MODEL` apply (default `openai/gpt-4o-mini`; root model settings
must be synchronized to services where applicable). A deliberate
`MATHBANK_RUNTIME_AI_MODEL` override is available. Speech remains
`whisper-1`; artifact embeddings use the same shared OpenAI client and retain
their explicit model/dimension profile. Neon Gateway remains an explicit
alternative, never an automatic fallback.

`make sync-neon-env` copies AWS S3 settings and gateway credentials to server
environment files with mode 0600, preserving unrelated values. Agent tools do not
receive S3 master credentials. Browser bundles must never receive these values.
`make sync-env` and `make sync-keys` include this synchronization.

## External provider acceptance blocker

The user authorized at most $10 for tiny synthetic paid checks. Gateway inference
returned HTTP 403 with a billing/credit blocker; the explicitly selected direct
OpenAI endpoint returned HTTP 429 `insufficient_quota`. No successful response
reported token usage, so no paid completion or actual spend figure is asserted.
The user chose to finish available validation and record this blocker rather
than keep retrying. After credits/model access are restored, separately verify
faithful handwriting/diagram transcription, timestamped audio, multimodal video
reasoning, flow-aware critique, and embedding/retrieval quality within the
remaining authorized cap.

### Balance-increase recheck

After the user reported increasing the OpenAI balance, one synthetic vision
request was attempted through the configured official OpenAI endpoint using
`gpt-4o-mini`. It still returned HTTP 429, `insufficient_quota`, with code
`credit_balance_exhausted`. No successful model response or usage was returned;
the remaining checks were stopped rather than retried. Root, REST and agent
saved keys match; no explicit organization/project selector is configured.
This verifies the blocker, not account billing details or AI quality.

A reusable opt-in [synthetic quality test](../mathbank-rest/tests/test_ai_quality_live.py)
now checks preservation of wrong mathematics, spatial evidence, segmentation,
incorrect/alternate/unjustified/uncertain reasoning, bounded speech timestamps,
and dimension-correct semantic retrieval. It uses only invented inputs, makes
no database/storage writes, and reserves a conservative ceiling of at most $9
per invocation before paid calls. This reservation is not a billed spend report.
The fixture is typeset, not representative handwriting; a later representative
handwriting/diagram corpus is still required for broad quality certification.

```sh
RUN_AI_QUALITY_LIVE=1 mathbank-rest/.venv/bin/python -m pytest \
  -q -s mathbank-rest/tests/test_ai_quality_live.py
```

Do not rerun until credits are available to the organization/project associated
with the root API key. ChatGPT subscription credit is not API billing credit.

### Subsequent authorized retry

The next explicit user-requested retry received successful `gpt-4o-mini` vision
and segmentation responses. Live execution exposed a missing JSON-mode prompt
instruction (HTTP 400), corrected centrally for all stages, and an unstructured
transcription confusing `PROSE_LINE` region type with reasoning-step type.
Image transcription now requests a strict typed JSON schema with separate enums;
its schema-constrained vision request succeeded. Regression tests cover both
request contracts. A test-fixture version was also corrected from 0 to the
runtime's valid initial version 1.

The subsequent segmentation request again returned HTTP 429
`credit_balance_exhausted`; further paid checks stopped. Partial successful
responses do not establish full fidelity or quality. Speech, flow-aware critique,
alternate reasoning and live embedding quality remain unverified.

### Immediate tutor geometry previews

**Agent topology implemented after the explicit follow-up:** all ten specialists
from artifact pack document 04 are now actual ADK `Agent` instances, composed
using `AgentTool`. Subject Planning routes to Geometry, Algebra, Combinatorics
and Number Theory; each subject can invoke LaTeX, SVG, Overlay/Frame, Annotation
and Validation specialists. The tutor exposes planner/subject delegates and
retains conversational control. This replaces the earlier capability-only gap;
it is **in-process Agent-as-Tool**, not remote A2A transport.

Specialists reuse the existing OpenAI/LiteLLM model. ADK invocation-only student
authorization is restored in isolated child runners through async-context-local
state; tokens are never placed in model input/output or saved event payloads.
Anonymous calls stop before inference. The acyclic network limits each invocation
to 16 delegated calls and 24 specialist model calls, with a 120-second per-delegate
timeout. These are not billing caps; live model quality remains a separate gate.
Real ADK Runner tests with scripted models exercise planner -> geometry -> SVG,
overlays, annotation, validation -> private drawing, and all three other subject
paths (including LaTeX refinement). REST previews are validated for every subject;
no automatic staff publication, storage or semantic indexing occurs.

Multi-agent verification: eight focused specialist tests (including concurrent
student isolation, anonymous denial and call limits) pass within the combined
23-test agent regression selection. Artifact REST/runtime selection: 110 pass.
Browser/proxy/parser selection: 14 units and three mocked Playwright tests pass,
including safe algebra LaTeX previews. No new paid inference was made to validate
this topology; actual OpenAI planning/tool-selection quality remains unverified.

Previously `request_artifact` could only submit work for later staff generation,
and the source-diagram instruction inadvertently discouraged requested
illustrations. The geometry specialist now registers `draw_geometry_diagram`, using private
ephemeral `/v1/artifacts/geometry-preview` and `/geometry-preview/content`.
The shared geometry validation/rule profile produces the SVG; triangle incircles
are computed from supplied named vertices. There is no paid model call, database
write, object-store write or automatic publication in the drawing capability.
Students still cannot publish/index reusable artifacts.

Generated sketches are explicitly distinguished from original source figures.
A generic quadrilateral drawing illustrates its triangle constructions; it does
not assert equal inradii or draw the desired rectangle conclusion as a given.
Problem/source panels and generated-image loading passed mocked desktop/mobile
browser tests; live paid tutor tool-selection remains unverified due quota.

Initial runtime verification (before specialist/preview additions): 184 focused REST offline tests
passed; six media and one artifact rollback-only Neon tests passed; 15
agent-tool tests passed; 25 UI unit tests and 17 mocked E2E cases passed; and
the web production build passed. The artifact test used mocked storage and a
supplied fake vector, with no provider call or real object bytes. A sanitized
constructed client confirmed provider `openai`, official `api.openai.com`
endpoint and `gpt-4o-mini`; this verifies configuration only, not inference.
Live REST route groups reportedly exposed 18 attempt-media and 16 artifact
paths, matching the source snapshot; three anonymous private REST/proxy GETs
returned 401. The OpenAPI snapshot regenerated byte-for-byte from the frozen
application source (3.1.0, 174 paths and 89 schemas). These scoped checks do
not establish full pack acceptance. Provider billing/quota remains the external
blocker for inference and model-quality acceptance.

After deploying the specialist/preview changes, the running REST OpenAPI was
observed at 178 paths / 90 schemas, including 20 artifact paths; anonymous generic
preview POST returned 401. The tutor app remained discoverable, and a real module
import confirmed ten agents plus five root AgentTools. REST and tutor were
restarted only after verifying their individual process identities; the
enrichment watcher remained running. The latest web production build passed.
These are scoped service/source checks, not live database parity or paid quality
certification. Root delegation is visible in chat activity; nested AgentTool
child events are not automatically forwarded to the browser stream.
