# Topic-first tutoring, practice selection and correction evidence

## Authority and scope

This merges the learner's expanded tutor requirements (2026-10-07 UTC) and
[pack practice selection](../math_tutor_new_requirements_copilot_pack_v2_expanded/15_PRACTICE_SELECTION.md).
The pack and pasted attachment are inputs, not runtime dependencies. This document
must remain usable after the pack is removed. Architecture references are
[here](reference/README.md); implementation coverage below is not a live AI-quality certificate.

## Required teaching architecture

User → intent router → pedagogy orchestrator → persisted topic plan →
canonical evidence → theory / artifacts / activities → learner response →
diagnosis → plan adaptation. RAG supports teaching; it does not replace it.

Intents: LEARN_TOPIC, SOLVE_PROBLEM, CONTINUE_ATTEMPT, FIND_PRACTICE, QUIZ_ME,
EXPLAIN_STEP, REVIEW_TOPIC, FIND_SIMILAR, EXPLORE_CORPUS. Bare mathematical
topics default to LEARN_TOPIC; “give me a … problem” means FIND_PRACTICE;
“what went wrong in … solution” means EXPLAIN_STEP. Unknown/ambiguous topics
require clarification, never a vaguely related fallback. Explicit “I know the
theory; just give me a hard problem” may skip instruction, without claiming mastery.

LEARN_TOPIC creates session-owned TopicLearningPlan state before presentation:
version, canonical node, current unit/stage, completed checkpoints, quiz outcomes,
misconceptions, remaining units and exposure. Restoring a conversation restores
the plan; switching topics is explicit. No first-turn contest problem by default.
Recognition comes before isolated practice. Wrong responses stay at the checkpoint;
passing a small quiz does not write measured mastery. Review restarts instruction.

For Power of a Point, teach intuition, prerequisite recognition (circle/chord/
secant/tangent), intersecting-chord product, visual derivation, recognition quiz,
tangent–secant form, relation-choice micro-quiz, guided example, intermediate
application, combined techniques, transfer and recap. A generated circle diagram
must satisfy its displayed incidences. Frames highlight PA/PB then PC/PD before
the product equality; they are illustrative, not original source figures or proof.
Use geometry/overlay/pedagogy capabilities, validated deterministic rendering and
explicit sign-in/render failure. Never claim an artifact was generated if it was not.

## Evidence and taxonomy

Concepts, subconcepts, skills and techniques are separate existing canonical
entities. Example proposed vocabulary: circle power; chord–chord, secant–secant,
tangent–secant and radical-axis cases; recognising the configuration, choosing/
writing a product, solving it, combining similarity, comparing equal powers.
Do not introduce a second competing taxonomy or migrate names without review.

Annotation must examine statement + canonical solution + solution steps.
Classify concept, technique and skill separately, then structurally validate
the proposal. Power-of-a-Point evidence may be SECANT_SECANT_PRODUCT,
CHORD_CHORD_PRODUCT, TANGENT_SECANT_PRODUCT, POWER_EQUALITY or
RADICAL_AXIS_POWER_COMPARISON. A name/keyword alone is insufficient; absence
of detected structure is an audit flag, not a proof that the technique is impossible.
“Power of a prime” is not “Power of a Point.”

Explicit-topic membership is a hard gate: canonical concept/skill/technique,
published step evidence, review state, configured confidence threshold, negative
decisions and complete source-dependent diagrams. Vector similarity only ranks
within that set; it never supplies membership. Missing coverage must be reported.
Problem-level technique listings, corpus filters and topic candidates must agree
on evidence and preserve human/rejected decisions across reimports.

## Practice fit and progression

Use versioned retrieval/pedagogy profiles, not permanent opaque weights.
Factors: skill_match, prerequisite_fit, difficulty_fit, technique_match,
misconception_relevance, structural_diversity, semantic_similarity,
previous_exposure. Unknown values remain unknown, never silently perfect.
Canonical fit outranks semantic similarity. Disclose bounded candidate coverage
and machine provenance. Learner identity comes only from trusted runtime state.

Progression: Theory → Recognition → Isolated skill → Guided application →
Mixed application → Transfer → Original problem. Prefer:
1. same representation;
2. same skill, different configuration;
3. same skill with a distractor;
4. combination with another known skill;
5. transfer with a hidden cue.
Use only supported, available material; do not falsely claim all categories exist.

For remediation prefer verified source textbook material, then approved derived
learning items, then newly generated candidates only after validation/review/
publication. Difficulty gaps may justify generation but never bypass publication.
Exclude original P0 and its leaking transformations. Do not show solution seeds,
expected intermediate results or final-proof text in early checkpoints. Generated
practice lifecycle remains separate from deterministic instructional quizzes.

## Feedback, audits and retriever evaluation

“Not related” must create a reviewable correction event, not just an apology.
Capture authenticated learner, problem, requested topic/node, challenged mapping,
query and bounded retrieval evidence, feedback type/text/time and audit version.
Conversation identity/scores are only included when trusted evidence exists.
Do not invent missing telemetry.

An audit specialist distinguishes metadata mismatch from retrieval failure and
insufficient evidence; examines actual solution-step support and structural flags;
creates a PENDING correction candidate/human queue. Repeated reports increase
review priority but do not establish truth. A learner allegation never directly
changes taxonomy, vectors, graph or mastery.

Admin inspects source/solution evidence and applies revision-checked canonical
decisions; explicitly publishes graph correction, refreshes relevant vector
metadata when needed and invalidates retrieval caches. PostgreSQL/graph/vector
operations are non-atomic; expose failures and verify each surface. Resolve the
report only with an evidence note. Repeated identical reports remain idempotent.

Reviewed negatives belong in a retriever evaluation set with query, positive
codes, hard-negative codes, reason and review provenance. Unreviewed complaints
are not training labels. Future reranker/classifier training needs explicit
approval. Regression: Power of Point must exclude PRASOLOV_PGV1_CH06_P076
unless its canonical reviewed decision changes.

## Provenance and learner-safe activity

Separate source identity from original document availability. If book/chapter/
problem are known but exact PDF/page cannot be opened, say “Source book identified;
original page/location provenance incomplete,” not “no original source registered.”
Show known source title/locator and canonical ID; no guessed page highlights.
Activities show intent, teaching stage, actual evidence counts, rendering status
and report state. Never expose private chain-of-thought, tokens or solution payloads.

## Acceptance and delivery record

Verify with deterministic unit tests, real ADK scripted delegation, restored
session state, wrong-answer/nonadvance and duplicate checkpoint tests, reviewed
negative retrieval tests, leakage guards, source provenance rendering and
desktop/mobile checks. Test exact thresholds/output shapes. Paid-model quality
requires a separately labelled live evaluation; offline checks do not establish it.

### Verified implementation (2026-10-07 UTC)

| Area | Delivered | Boundary / remaining work |
|---|---|---|
| Intent and pedagogy specialist | Real ADK pedagogy AgentTool; bare exact topics teach first; explicit practice, review/quiz, checkpoint/resume routes. Unmatched explicit practice requests stop for topic clarification, never fall through to vector recommendations. Root/formatter presentation binds to server evidence. | Surface routing is conservative, not a universal NLU classifier. Complex solve/explore requests retain existing model tools. |
| TopicLearningPlan | Existing PostgreSQL-backed ADK session JSON, revisioned current checkpoint, quiz results/misconceptions/exposure. Wrong A-D answers do not advance; review does not clear exposure. | No new duplicate plan SQL schema or mastery writes. Lesson plans for switched-away topics are not a multi-course archive. |
| Power of a Point | Seven authored stages/checkpoints, circle/chord/secant/tangent recognition, products, isolated/guided arithmetic, mixed skills and transfer/recap. Exact chord incidence and product equality. | Introductory coverage, not full theorem proof/certification. Only this topic currently has an authored validated sequence; other topics disclose the gap. |
| Visual instruction | Four-frame private geometry preview: circle/intersection, first chord, second chord, compare products. Shared validated reset-to-base renderer; accessible frame controls. | No public artifact publication/indexing. Sign-in/render failures explicit. Automated publication of reusable topic courses and tangent/secant/radical-axis visual libraries remains future work. |
| Explicit practice | Published-step membership first; pending/rejected and reviewed-negative exclusion; versioned profile/minimum confidence 0.8; bounded 100-row retrieval and ten complete-source checks before showing one. | General corpus listings share canonical step support but not practice-specific negative/exposure policy. Complete statements/required diagrams are checked at final display, not asserted by ranking alone. |
| Multi-factor ranking | Skill/prerequisite/difficulty/technique/gap/diversity/exposure factors, visible unknown signals; real authenticated attempts/gaps used where available. | Semantic signal remains null: no query embeddings. Difficulty is source-order band; diversity is taxonomy/form/skill proxy. No measured skill mastery inference or mathematical non-paraphrase guarantee. |
| Annotation validation | Shared structural audit over statement/actual steps. Future textbook Power proposals lacking signatures create import warnings and are withheld from new canonical bridge writes; staged originals/human/rejected decisions preserved. | Heuristics are not proof. Broader techniques, full automated enrichment/publication validation and retrospective corpus reannotation remain review work. No bulk annotation or graph mutation ran. |
| Feedback and specialist audit | Authenticated pending report, same-row server snapshot; actual bounded ADK audit specialist; complaint -> report -> audit -> lesson replan. Admin evidence/relevance/error controls. | Pending claims never retag/train. Missing retrieval score/conversation evidence is not invented. Old conversations/reports are not backfilled. |
| Retriever evaluation | Admin-only resolved positive/negative examples with reason/review provenance; resolved IRRELEVANT labels gate the canonical node's practice set. | No training job, automatic source-change invalidation of reviewed labels, or end-to-end graph/vector/cache correction automation. |
| Remediation | Existing approved imported source-derived learning items and origin/visibility gates, plus hidden solution-seed copying guard. | A heuristic leakage check is not a mathematical validator. New generated-item lifecycle, full source-preference orchestration, equivalent-structure detection and transfer diversity remain partial in pack 15. |
| Provenance | Known book/chapter/problem distinguished from missing PDF/location; no guessed source URL/page/highlight. | A known book does not establish cached original pages or complete diagram recovery. |

Verification: **133 REST/import tests passed** (four optional/live-runtime tests
skipped); **57 agent tests passed**, including actual scripted ADK delegation,
explicit ranked practice, exposure retention and complaint audit chains;
**97 web unit tests** and **nine focused browser cases** passed (1440/390 px),
plus production build. Real deterministic renderer validated all four authored
frames. A fresh actual PostgreSQL ADK session-service instance restored checkpoint
progress; exact synthetic session/user-state cleanup completed.

The opt-in `TEST_TOPIC_FEEDBACK_DB=1` integration test verified actual feedback
snapshot/duplicate behavior, pending-label database constraints, positive/negative
review evidence and negative practice exclusion inside one rollback-only
transaction; the synthetic identity/reports did not persist. Live reloaded REST
matched the source OpenAPI, returned six qualified alternatives without Q76,
enforced authentication, returned exact known-book provenance, and rendered all
four private frames. REST/agent readiness was verified without paid inference.

Migration 024 was explicitly authorized/applied to the same configured target
as 023. This is separate from source-derived documentation, not a full catalog
audit. Current source OpenAPI is 186 paths / 93 schemas. No paid inference,
training, embeddings, bulk reimport/retagging or graph publication ran in this
implementation. Offline/scripted tests are **not live model-quality evidence**.

Pack 15 is therefore **substantially extended but still partial**, not universally
complete. Broader authored lessons, mathematical diversity validators and the
reviewed generated-practice factory remain in the implementation tracker.

### Interactive lesson navigation and learner work

The tutor sidebar now shows the seven lesson stages with short labels/icons,
completed/skipped/pending status, the selected stage, a completed-only progress
bar and elapsed time recorded when a stage is left. `skip step`, `jump to step N`
and `jump to problem` are deterministic, revision-checked session actions.
Jumping never completes a stage; explicit skips are retained separately from
checkpoint completion. Revisiting a completed stage does not erase its completed
record. The selected stage and status are presented independently.

The authored A-D checkpoints render as radio choices; the numeric segment-product
checkpoint uses a number field. Both are checked by deterministic authored
validators and include a short explanation only after a correct response.
Optional hints are revealed only after an explicit request. In particular, a
wrong answer no longer reveals the hint automatically. No unauthored free-text
response is recorded as completed or mastery.

When the tutor's latest response explicitly identifies a canonical problem, the
composer accepts a JPEG, PNG or PDF of the student's solution and links it to
that same problem in the existing private attempt-media flow. Upload is
authenticated, limited to 20 MB and returns to the editable transcription
workspace. Transcription/AI processing is a separate explicit learner action;
the original upload is never treated as verified math. The uploader is disabled
when no active canonical code is available. Verified practice blocks include an
explicit canonical-code label; if a reply contains multiple problems, the learner
must select which one the work belongs to before uploading. This prevents
ambiguous or mismatched submissions. If upload fails after submission creation,
the learner can reopen that private submission and retry.

Safe geometry remains limited to the validated instructional frames already
available to the authored lesson. Frames illustrate stage progress and do not
expose a full contest solution. There is no generic solver-generated partial
diagram for arbitrary problems yet; a missing validated figure is not replaced
with a guessed construction.

The analysis step in the private work pipeline also checks the approved
transcription against the linked problem before critique. A clear mismatch or
unverified context stops analysis; if every transcribed step is classified as
irrelevant, critique is refused. This guard runs only after the student
explicitly approves the transcription and requests analysis.

These additions reuse ADK session JSON, existing attempt-media REST routes and
the existing authenticated proxy. They add no PostgreSQL/Neo4j schema, REST
endpoint or graph publication. Source OpenAPI remains 186 paths / 93 schemas.
Focused verification: the lesson state/ADK tests and stream-mapper tests pass;
the web production build succeeds. Full mobile/browser upload-flow verification
is still outstanding. The time value is session elapsed wall-clock time between
stage interactions (including idle time), not foreground-only active time.
