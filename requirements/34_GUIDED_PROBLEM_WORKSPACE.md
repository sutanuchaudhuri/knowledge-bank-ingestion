# 34 — Guided problem-solving workspace

## Scope and evidence

This captures the student's supplied redesign brief and screenshot for
`/learn?problem=PRASOLOV_PGV1_CH06_P031`, together with the learning-context
failure at `/learn?problem=AIME_1985_Q01`. The supplied snapshots remain
unchanged. This is a concrete implementation record, not a claim that the
entire adaptive-tutoring architecture is finished.

Source revision `1582f808a731e571e79b588d4c73e717eefc7956`, including relevant
worktree changes. Implementation sources:
[workspace](../mathbank-web/app/learn/LearningWorkspace.jsx),
[orientation checks](../mathbank-rest/src/mathbank_rest/guided_orientation.py),
[visual definitions](../mathbank-rest/src/mathbank_rest/guided_visuals.py),
[pedagogy routes](../mathbank-rest/src/mathbank_rest/routers/pedagogy.py),
[graph reads](../mathbank-rest/src/mathbank_rest/pedagogy.py),
[work upload](../mathbank-web/app/_components/WrittenWorkUpload.jsx) and
[construction preview](../mathbank-web/app/_components/ConstructionPreview.jsx).
The existing source/diagram, composer and private transcription workflows
remain authoritative for those capabilities.

## Requirements and delivery status

| ID | Requirement from the brief | Implementation status |
|---|---|---|
| GP-1 | Replace the opening diagnosis questionnaire with **Tutor + My work**, encouraging an observation or small step. | Delivered; no mandatory self-diagnosis. |
| GP-2 | A calm, wide workspace with one page header, tinted formatted question, existing source figures, short actions and collapsed provenance. | Delivered using the shared Bootstrap/theme system. |
| GP-3 | Show Understand → Plan → Work → Check → Reflect, allow independent work and stage navigation. | Delivered as a temporary self-directed journey with jump, skip and self-reported completion. Completion is not mastery. |
| GP-4 | Proactively decode Q31: defining triangles, shared original side and circumcenter equal radii before asking for proof. | Delivered as three authored, statement-gated radio checks. Wrong responses do not advance or disclose the answer; explicit nudges and correct-answer explanations are separate. |
| GP-5 | Give AIME 1985 Q1 a safe starting interaction. | Delivered as initial-condition and recurrence-substitution checks, without the product or full solution. |
| GP-6 | Separate work into small mathematical steps, with feedback attached to the step, not a generic global hint. | Delivered: editable/selectable steps (maximum 20), per-step provisional coaching, stale-draft warning. Full correctness assessment remains in the approved private-attempt workflow. |
| GP-7 | Type math, explain aloud, upload handwriting, or paste an image. | Delivered through shared MathComposer and explicit problem-bound JPEG/PNG/PDF upload/paste, maximum 20 MB. Private upload requires sign-in. No automatic transcription or analysis. |
| GP-8 | Student reviews and edits transcription before assessment; keep original evidence linked. | Reuses the existing private submission workflow. The upload navigates there; temporary typed drafts are not automatically converted into approved evidence. |
| GP-9 | Optional progressive construction visuals before a full solution. | Delivered for authored Q31: prompt-specific triangle/center/circle/radii frames; all first-level centers and the second iteration become available after orientation. Computed illustrative coordinates, not a recovered source figure. No similarity proof or derived scale factor. |
| GP-10 | Contextual hints: orientation question, tiny nudge, visual help and return-to-work prompt, not a mechanical global hint request. | Delivered for authored orientation and Q31 visuals; step coaching returns idea/nudge/next-action panels. A fully adaptive observation/structure/method hint path remains planned. |
| GP-11 | Keep raw skills, confidence, provenance and difficulty dimensions out of the normal student rail. | Delivered. Existing admin/graph inspection remains available outside the solving workspace. Important service/evidence warnings stay visible. |
| GP-12 | Use difficulty, construction roles, prerequisites and solution length to adapt micro-goals. | Partial: existing coaching uses teaching context; opening authored checks are deterministic. General metadata-driven micro-goal planning is not implemented here. |
| GP-13 | Render structured pedagogy actions rather than inventing client-only mathematical prompts. | Partial: server returns `ASK_MICRO_CHECK` / `REQUEST_STUDENT_STEP` and a validated visual-intent contract with exact derived definitions. General model-generated `SHOW_VISUAL_HINT`/artifact actions and a unified durable session are planned. |
| GP-14 | Persist current goal/problem/step state, tutor plan, artifacts, work, prompt, hint level, recovery and progress as a PedagogySession. | Planned for this workspace. Current `pedagogy_session` is a stateless orientation envelope; browser drafts/stages/check progression are temporary. Existing ADK topic lessons and approved private submissions persist separately. |
| GP-15 | Integrate solution-DAG advancement, inferred sticking points, mathematical step classification and precise correctness feedback. | Planned for this workspace; existing step-solving/private-attempt capabilities are linked, not silently substituted for correctness verification. |
| GP-16 | Unify learner terminology and modes: Tutor, Practice, My Work, Progress; Problems, Topics, Artifacts, Knowledge Map; independent/guided/review. | Existing shell is preserved. Whole-site navigation and formal mode consolidation remain planned; review must stay explicit to prevent solution leakage. |
| GP-17 | Keep related/lower-level practice available without clutter or mandatory detours. | Delivered as a collapsed, lazy same-skill practice panel, plus explicit tutor/step-solving links. |
| GP-18 | Learning-data failure must retain the question when available, show the error and allow recovery; never fabricate teaching evidence. | Delivered: graph-independent workspace bootstrap; parallel background context with a 15-second browser deadline; 12-second bootstrap deadline; 20-second GET proxy deadline; driver-managed graph read retries and no deeper traversal when approved ancestry is empty. Coaching is disabled until context recovers; retry retains drafts/check progression. A persistent outage remains an explicit error. |
| GP-19 | An instructional construction must show the current mathematical object or relation, not a plausible generic topic picture. | Delivered for Q31: typed visual intent, source-verified ordered definitions, frame required-object checks, canonical-code matching, two-level circumcenter computation and equal-radii verification. Missing/mismatched/degenerate definitions suppress the visual with an explicit error. |
| GP-20 | Preserve element provenance and keep all center labels readable through progressive construction. | Delivered: original/derived point titles, exact triangle definitions in a collapsed panel, current-focus highlighting, viewport fitting including circles, and an independently magnified second-level panel with a no-scale-inference warning. |

## Server/UI contract

`GET /v1/tutor/workspace/{code}` reads the canonical statement and safe figures,
and returns authored orientation plus optional visual intent. It does not wait
for Neo4j, invoke enrichment/publication or call a provider. It uses the existing
parameterized statement read; unknown code 404, storage failures 503.
The UI requests this independently of full context, allowing writing and
authored micro-checks to proceed even when the graph is slow. Context arriving
later must not reset an advanced orientation or edited draft.

`GET /v1/tutor/learning-context/{code}` retains its existing teaching-context
contract and adds `pedagogy_session`. Loading context can still invoke existing
automatic enrichment/publication if metadata is missing; it is **not universally
read-only**. No new provider call was added for authored orientation.

`POST /v1/tutor/micro-check` accepts `{problem_code,index,response}`. It reads
the canonical statement and safe diagrams, never official answers or solution
bodies. Extras are forbidden; problem code/response are 1–200 characters and
index is a strict integer from 0 through 20. Unknown problems return 404,
unsupported checks/choices return 422, storage failures return 503.
The returned session has only the current question/choices, counts, journey,
temporary status and provenance. Answer keys are private; correct choices
return the authored explanation, wrong choices remain at the same index.
`response="hint"` returns a nudge without advancing.

This endpoint is public, stateless and not a graded assessment. A supplied
index is not durable progression evidence. It writes no learner/mastery data.
Generic problems receive a write-a-starting-idea prompt, not a fabricated
problem-specific plan. Next.js proxies these calls through `/api/tutor/*`.

### Current-object visual contract

Server `visual_intent` contains `artifact_goal=TEACH_CURRENT_OBJECT`, subject,
canonical problem code, `current_step`, `must_show`, `max_level`, progressive
frame mode, forbidden proof/scale-factor claims, and a versioned semantic setup.
The Q31 parser verifies the convex base, ordered first-level centers and
defining triangles, and second iteration in the actual canonical statement.
It rejects incomplete/reordered/unsupported text rather than guessing.

| Current prompt | Every frame must include |
|---|---|
| Define A₁ | ABCD, highlighted BCD, computed A₁ |
| Shared side | BCD, CDA, A₁, B₁, highlighted CD |
| Equal radii | BCD, A₁, A₁C and A₁D |
| Write a starting idea after orientation | A₁B₁C₁D₁ and all first-level centers; later frames apply the same definition to create A₂ and then A₂B₂C₂D₂ |

The renderer revalidates all eight ordered definitions and computes centers
from a deterministic nondegenerate example. It checks equal distance to all
three defining vertices, rejects collinearity/nonfinite results, and checks
required elements and level bounds before rendering. Every frame is aligned,
including the initial frame; there is no bare-quadrilateral fallback.
Changing the prompt resets the frame to its aligned starting state.
Second-level construction depicts the requested setup, not a similarity
argument. The magnified panel has independent zoom, explicitly unsuitable
for reading the similarity coefficient.

This is an authored semantic parser and deterministic geometry renderer,
**not an arbitrary-statement parser or a paid image-generation model**.
Unsupported problems remain explicitly unavailable rather than receiving
a generic diagram. Wider artifact-agent integration remains future work.

Separate current-object implementation verification (2026-10-07 UTC):
the live workspace proxy returned HTTP 200 in **0.29 seconds**, with all eight
definitions and `DEFINE_A1`. The initial visual showed highlighted BCD and A₁
with no second-level object. Real micro-check responses changed the visual
focus and unlocked the first-level quadrilateral and second iteration.
Desktop/mobile checks found no horizontal overflow. This measures the initial
API, not a guarantee about total page/network time.

The alignment/loading update passed **38 REST tests, 18 focused JavaScript
unit tests and 19 browser tests**, including a genuinely stalled context with
a 15-second deadline, late-context progression preservation, failed visual
intent suppression and mathematical equal-radii checks for all eight centers.
Ruff, editor diagnostics, production build and reference-link/whitespace
validation passed. Running OpenAPI matched the source snapshot (188/94).
No paid provider call or learner-data mutation was used for these checks.

Step coaching retains the existing explicit `/coach` action: at most three
hints per written step, require changed work before further help, limit a
submitted step to 4,000 characters. Switching step tabs does not reset counts.
Generated coaching is visibly marked **not verified correctness**.

Upload creates a private submission bound to the active canonical code,
uploads the original and opens editable transcription. Errors remain visible;
an asset-upload failure after submission creation offers a resume link.
Changing problems/unmounting cancels outstanding upload UI requests. Approved
evidence, transcription and assessment semantics remain those in
[requirement 32](32_MULTIMODAL_ATTEMPTS_AND_ARTIFACTS.md).

## Acceptance and remaining architecture

### Compact presentation and source math

The workspace prioritizes the question, current checkpoint, student composer
and optional construction. Change-problem controls, source metadata, working
preferences, routine enrichment/prerequisite warnings and workspace persistence
notes are collapsed. Actual loading/coaching/upload failures remain visible with
recovery actions; hiding routine diagnostics never enables unavailable hints.
Tutor controls no longer stick over the lower-level-practice panel.

KaTeX CSS and `rehype-katex` must resolve the same renderer version. The AIME
source already contained correct subscripts; incompatible 0.19 CSS with 0.16
markup caused the bad presentation. They now resolve to 0.16.47. Browser tests
measure subscripts at 70% of the base font, below the baseline, at 1440/390 px.
MathML remains accessible but visually clipped; copied accessibility text can
contain both representations without implying duplicate visible formulas.

`problemPresentation.mjs` runs on the tutor GET proxy and independently before
workspace rendering. It preserves `statement_text`, prepares a display-only
representation, joins only recognized PDF word breaks, repairs prose ligatures,
and supplies authored Q31 indexed-point/given-coefficient formatting. Code,
Asymptote, links and already-delimited math are protected. KaTeX checks each
delimited expression and reports parse failures in diagnostics. These are
deterministic presentation checks, not AI certification or mathematical
non-paraphrase validation. Loading a question makes no paid formatter request.

### Solution-grounded teaching, not question-only planning

Before choosing an approach for an explicit problem-discussion request, the
tutor must consult available stored solutions rather than infer a strategy
solely from graph tags. `prepare_problem_guidance` loads canonical context and
figures and invokes `POST /v1/tutor/guidance-plan`. REST reads up to six nonempty
`core.solution` records, retaining kind/revision/verification provenance. Each
private reference is bounded to 12,000 characters; bounded/excerpted coverage is
reported. Markdown is preferred, with nonempty LaTeX as an alternative.

The response contains only a short route rationale, 3–5 high-level stages, one
first checkpoint, a selected reference ID and provenance/counts. Raw solutions,
official-answer fields and private reasoning are not ADK tool responses or
activity payloads. AIME Q1 has an authored plan gated by its exact recurrence,
target product and a supporting stored neighboring-term relation. It chooses
the relation-based route instead of routine term-by-term computation, without
answering the checkpoint or final product. Other supported references use the
existing configured REST model for this explicit action; refusal/invalid JSON,
invented reference IDs and detected final-answer literals fail explicitly.
No references means `status=unavailable`, not fabricated solution grounding.

The exact browser discussion prompt routes deterministically before the root
model. Its validated public reply is pinned, and the safe selected plan is
retained in existing ADK session JSON for subsequent conversation context.
Ambiguous numbered selections still require resolution by the orchestrator.
Existing authenticated Prasolov step-runtime actions remain separate.
`/coach` now also consults stored solution references privately before generating
one hint, allowing alternate valid student methods. Graph/context GETs and
authored micro-checks remain answer-free; page opening does not generate a plan.

Activity shows actual solution-record counts, unverified-source status and
teaching-stage count, not a claim that retrieval proved a solution. Literal
three-or-more-digit final answers are rejected; this is **not a general
proof/spoiler-safety verifier**. All generated guidance remains provisional,
and durable workspace sessions/general solution-DAG integration remain planned.

Separate implementation checks (2026-10-07 UTC): **48 REST tests, 47 agent tests,
41 focused JavaScript tests and 17 browser tests passed**, with production build,
lint and editor diagnostics. A live no-provider AIME planner/ADK check consulted
two UNVERIFIED records, returned four stages and one checkpoint, and excluded
raw solution fields/final answer. Its temporary synthetic agent session was
removed. Running OpenAPI matched the screened source snapshot: **189 paths /
95 schemas**. These checks are not live schema parity or general paid-model
quality certification.

Separate live implementation verification on 2026-10-07 UTC, after the
student-authorized REST reload: AIME Q1 returned two authored checks; Q31
returned three. A read-only timing probe isolated the prior Q31 stall to its
depth-boundary traversal (over 60 seconds), despite an empty approved ancestor
result. Skipping that impossible deeper path produced a **2.6-second** canonical
learning context. Both requested routes rendered at 1440/390 px without
horizontal overflow; the AIME checkpoint advanced through the same-origin
micro-check proxy. This is route/behavior verification, not live schema parity
or a paid AI-quality assessment.

Initial workspace validation: **34 REST tests, 11 JavaScript unit tests and
16 browser tests passed**, including prior corpus/topic/hydration regressions.
Ruff, the production web build, local reference links and whitespace checks
passed. Browser mocks test failure/authorization behavior without paid
inference; the separate live observations above verify deployed route behavior.

- REST tests verify source gating, answer-key exclusion, no wrong-answer
  advancement, explicit nudges, endpoint validation and managed graph reads.
- Browser tests cover desktop/mobile discovery, attached/stale step feedback,
  per-step hint counts, private upload authorization, explicit context failure,
  question-only fallback, draft-preserving retry and no horizontal overflow.
- Existing source provenance, diagrams, practice and problem-linked chat remain
  available; full solution review is never triggered by opening this page.
- Future durable sessions must bind learner ownership and canonical problem,
  revision-check actions, record recovery/elapsed stage time, preserve work
  across navigation and integrate reviewed solution-DAG evidence without
  turning self-reported completion or provisional coaching into mastery.
- Future generalized visuals must reuse validated artifact contracts and
  respect current-object/required-element/spoiler bounds; the current engine
  is not a generative agent.

See [UI contract](30_MODERN_UI_DESIGN_SYSTEM.md),
[topic lessons](33_TOPIC_FIRST_TUTOR_AND_PRACTICE.md) and the
[source-derived architecture reference](reference/README.md).
