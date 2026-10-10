# 41. Interaction, animation, feedback and misconception-evidence template library

## Comprehensive interaction/animation runtime contract

> **Normative precedence.** This platform is shared by micro-course states, tutoring-route
> steps, video-segment interventions and future instructional surfaces. The same template
> instance must not acquire different correctness, event or misconception behavior based
> on which host renders it.

### 41.A Host-neutral runtime

Allowed hosts:

```text
CourseState
RouteStep
VideoSegment
InterventionStep
```

Graph:

```text
CourseState   -[:USES_INTERACTION]-> InteractionInstance
RouteStep     -[:USES_INTERACTION]-> InteractionInstance
VideoSegment  -[:CAN_LAUNCH]-> InteractionInstance
```

### 41.B Framework-free core package

Create:

```text
@mathbank/interaction-core
  public schemas
  deterministic state reducers
  evaluator specifications
  geometry math
  semantic-event builders
  error-signature vocabulary
  accessibility metadata
```

Consumed by:
- web;
- React Native;
- server validator/evaluator;
- admin preview tests.

Client computation improves responsiveness but server evaluation is authoritative for
persisted correctness/evidence.

### 41.C Public vs server-only configuration

Split instance materialization into:

```text
public_config
server_evaluation_config
```

Public:
- objects;
- ranges;
- labels;
- initial values;
- safe formulas necessary to render;
- accessibility metadata.

Server-only:
- hidden answers;
- scoring predicates;
- diagnostic thresholds;
- misconception-evidence rules if disclosure would reveal scoring;
- answer-bearing remediation conditions.

### 41.D Control → semantic action

Every control maps to a semantic action/object.

```json
{
  "control_key":"ROW_A_COL_B",
  "control_template":"PROBABILITY_MATRIX_CELL",
  "semantic_action":"SET_TRANSITION_PROBABILITY",
  "semantic_object_id":"transition:A:B"
}
```

Never diagnose from raw `click`/`change` alone.

### 41.E Meaningful event granularity

Persist settled semantic events:
- slider commit/debounce;
- matrix cell commit;
- matrix row submit;
- graph node/edge selection;
- drag/drop completion;
- video seek completion;
- derivation-step confirmation.

Do not persist every animation frame/pointer pixel.

### 41.F Immediate evidence engine

Current-interaction feedback must be synchronous:

```text
semantic event
→ deterministic evaluation
→ interaction_event insert
→ evidence update
→ feedback-policy decision
→ response
→ outbox event
```

Background jobs reconcile/roll up; they do not delay visible feedback.

### 41.G Learner evidence boundary

Shared graph may say:

```text
InteractionInstance -[:CAN_REVEAL]-> Misconception
EvidenceRule -[:EVIDENCE_FOR]-> Misconception
```

It may not say:

```text
Student -[:HAS_MISCONCEPTION]-> Misconception
```

Learner evidence/latest-state stays in PostgreSQL.

### 41.H SceneSpec as visual semantic source

One SceneSpec targets:

```text
Web renderer
React Native renderer
Manim renderer
Admin preview
Remediation replay
Video-generation pipeline
```

Specialized renderers are permitted only if they:
- declare capability;
- preserve semantic object IDs/events;
- support accessibility/reduced-motion equivalent;
- keep evaluation out of renderer code.

### 41.I Interaction authoring screen wireframe

Desktop:

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ Interaction: MARKOV-MATRIX-01      Template: TRANSITION_MATRIX_EDITOR v1    │
├────────────────────┬───────────────────────────────────┬─────────────────────┤
│ CONFIGURATION      │ LIVE PREVIEW                      │ SEMANTICS / RULES   │
│ Template version   │                                   │ TEACHES             │
│ Controls           │   State graph      Matrix         │ • PROB_MARKOV...    │
│ Initial state      │   A ─────→ B       [ .3 .4 .5 ]  │ REQUIRES            │
│ Layout             │                                   │ • ALG_MATRIX        │
│ Accessibility      │   [Submit row]                    │ CAN_REVEAL          │
│                    │                                   │ • MC-M05            │
│ SceneSpec          │   Feedback preview:               │ Evidence rules      │
│ Feedback policy    │   row total = 1.2                 │ Diagnostic item     │
│                    │                                   │ Intervention        │
├────────────────────┴───────────────────────────────────┴─────────────────────┤
│ Event inspector: SET_TRANSITION_ROW → ROW_SUM_INVALID → +0.35 → TRY_AGAIN  │
│ [Validate] [Web preview] [Reduced motion] [Manim preview] [Submit review]  │
└──────────────────────────────────────────────────────────────────────────────┘
```

Phone/tablet admin preview may stack panes, but platform-authoring itself can remain a
desktop-first protected workflow.

### 41.J Object-specific feedback contract

Evaluation may return:

```text
focus_object_ids
related_object_ids
accepted_components
focus_components
icon_token
feedback_template_id
animation_key / scene_spec_id
diagnostic_learning_item_id
intervention_id
next_action
```

Examples:
- Markov: exact invalid row + outgoing arrows;
- Vieta: retain correct `e1/e3`, focus wrong `e2`;
- Jensen: highlight curve/chord and inequality direction.

### 41.K Return envelope

Subflow launch includes:

```json
{
  "host_type":"MICRO_COURSE_STATE|ROUTE_STEP|VIDEO_SEGMENT|INTERVENTION",
  "host_id":"uuid",
  "enrollment_or_attempt_id":"uuid",
  "origin_state_id":"uuid|null",
  "origin_route_step_id":"uuid|null",
  "origin_video_time_ms":132000
}
```

Interaction completion returns to that envelope; it cannot select an arbitrary next state.

### 41.L Golden acceptance expansion

In addition to Jensen/Vieta/Markov flows, test:
- web/mobile semantic parity;
- route-step host;
- video-segment host;
- secure public/server config split;
- immediate evidence update;
- reduced-motion behavior;
- graph host edges;
- zero learner-specific Neo4j facts.


## Decision and rollout

Requested 2026-10-09 UTC from the attached Copilot implementation pack
(`INTERACTION_TEMPLATE_LIBRARY_COPILOT/`: `00_INDEX.md`, 13 `docs/*.md` files,
5 `schemas/*.schema.json` JSON Schema contracts, `NEXT_MIGRATION_SKELETON.sql`,
and three existing reference prototypes — Inequalities, Polynomials, Markov
Chains — each a one-off HTML/JS lab plus hand-written Manim scripts, SVG
diagrams and fixed quiz banks). This is requirements input, not evidence of an
implemented schema; no migration has been applied yet. It refactors those
three prototypes into a reusable, deterministic platform of interaction
templates, versioned controls, semantic icon tokens, animation templates,
declarative SceneSpecs, deterministic evaluation, misconception evidence
accumulation, fixed diagnostics/remediation, learner event capture, and graph
projection. It depends on and extends
[40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md): `CourseState` is
`pedagogy.micro_course_state`, and this pack's `knowledge.misconception` /
`pedagogy.intervention_script` / `pedagogy.learning_item` references assume
that schema already exists. Non-negotiable: a wrong answer is not
automatically a misconception; the LLM is a constrained conversational layer
rephrasing/explaining/classifying among predeclared candidates, never the
interaction engine itself; learner-specific evidence stays in PostgreSQL and
is never projected to the shared Neo4j graph.

## Complete requirement inventory

| ID | Requirement | Acceptance |
|---|---|---|
| ITL-1 | Interaction template registry | `visual.interaction_template` (`template_key` UNIQUE, `interaction_family`, `status`) is a root catalog of reusable template *families*; `visual.interaction_template_version` (`UNIQUE(interaction_template_id, version)`, `input_schema`/`state_schema`/`event_schema`/`output_schema` jsonb, `default_layout`, `allowed_controls`, `allowed_icons`, `diagnostic_capabilities`, `animation_slots`, `accessibility_policy`, `content_hash`, DRAFT→...→PUBLISHED) is the immutable versioned contract actually bound by courses — published versions are never edited in place. |
| ITL-2 | Reusable control and icon catalogs | `visual.control_template` (`control_key` UNIQUE, `control_type` from a documented vocabulary of 14 e.g. `REAL_SLIDER`, `PROBABILITY_MATRIX_CELL`, `VECTOR_HANDLE`, `TIMELINE`; `config_schema`/`accessibility_schema`). `visual.icon_token` (`token_key` UNIQUE, `icon_class` CHECK IN SEMANTIC/CONTEXTUAL/DECORATIVE, `accessible_label` NOT NULL, FK → `visual.asset`). Course authors pick only from these approved registries; they cannot upload arbitrary icons or ad hoc controls. Color must never be the only feedback signal. |
| ITL-3 | Interaction instances with FK-backed semantic bindings | `visual.interaction_instance` (`canonical_code` UNIQUE, FK → a specific `interaction_template_version`, `instance_config`/`initial_state`/`success_criteria` jsonb, `learning_objective` NOT NULL, `feedback_policy_id`, `scene_spec_id`, `review_status`). `interaction_instance_concept/technique/skill/misconception` are FK-backed binding tables with a shared role vocabulary (`TEACHES, REQUIRES, PRACTICES, ASSESSES, CAN_REVEAL, REMEDIATES`), never free text. |
| ITL-4 | Animation templates and declarative SceneSpec | `visual.animation_template` (`animation_key` UNIQUE, `input_schema`, `semantic_output_events`, `reduced_motion_behavior` NOT NULL — every animation requires a reduced-motion fallback, e.g. `MOVE_TOKEN` → "instant state change + focus highlight + text announcement"). `visual.scene_spec` (`UNIQUE(canonical_code, version)`, `scene_schema_version`, `scene_json`, DRAFT→APPROVED) is a single declarative timeline of typed `objects` (18 types: `STATE_NODE`, `MATRIX`, `VECTOR`, `FUNCTION_GRAPH`, `POLYNOMIAL`, ... ) and timed `timeline` entries (`at_ms`, `action` from a 23-action vocabulary e.g. `DRAW_TRANSITION`, `EQUATION_MORPH`, `MATRIX_MULTIPLY_STEP`, `ERROR_HIGHLIGHT`), each optionally bound to a narration segment and canonical concept/technique/skill/misconception tags. Exact JSON Schema in `schemas/scene_spec.schema.json` (required: `scene_key`, `scene_version`, `objects[].{id,type}`, `timeline[].{at_ms,action}`). |
| ITL-5 | Dual renderers with semantic (not pixel) parity | One SceneSpec is rendered by both a Web renderer and a Manim adapter. Parity requires identical object IDs, canonical tags, semantic event sequence, and narration bindings — not pixel-identical frames. Hand-written Manim scripts may never remain the final, opaque renderer; they must decompose into SceneSpec timelines. |
| ITL-6 | Deterministic evaluation and semantic events | Every learner action emits a `learner.interaction_event` (append-only: `student_id`, `interaction_instance_id`, `event_type`, `semantic_action`, `control_key`, `object_id`, `before_state`/`after_state` jsonb, `evaluation_outcome`, `error_signature`). Evaluation is template-defined and deterministic — it never calls an LLM to decide correctness. Exact JSON Schema in `schemas/semantic_event.schema.json` (required: `event_type`, `semantic_action`, `interaction_instance_id`, `action_payload`). |
| ITL-7 | Partial correctness and object-specific feedback | A result may be `CORRECT`/`PARTIAL`/an error signature, never collapsed to binary right/wrong when partial credit applies (e.g. Vieta: correct `e1`/`e2`, wrong `e3` → feedback names the exact wrong term, not "incorrect"). Feedback must identify the exact matrix row, state/transition, equation term, graph point/vector, substitution step, or parameter condition at fault. |
| ITL-8 | Feedback templates and policies | `pedagogy.feedback_template` (`UNIQUE(feedback_key, version)`, `feedback_type` from CORRECT/PARTIAL/TRY_AGAIN/PROCEDURAL_ERROR/CONCEPTUAL_ERROR/MISCONCEPTION_PROBE/MISCONCEPTION_CONFIRMED/PREREQUISITE_GAP/TRANSFER_SUCCESS/OUT_OF_SCOPE, `approved_content`, optional icon/animation FK, `allowed_agent_rephrase`). `pedagogy.feedback_policy` (`UNIQUE(policy_key, version)`, `policy_json` encoding a staged ladder: attempt 1 → neutral clue, attempt 2 → focused clue, attempt 3 → diagnostic probe, confidence ≥ threshold → intervention, remediation complete → retry original). Exact JSON Schemas in `schemas/feedback_policy.schema.json`. |
| ITL-9 | Misconception evidence engine | `pedagogy.misconception_evidence_rule` (FK → `knowledge.misconception` and a specific `interaction_template_version`; `semantic_action`, `error_signature`, `predicate_json`, `evidence_weight numeric(5,4) CHECK BETWEEN -1 AND 1`, `requires_probe`, optional diagnostic `learning_item_id`/`feedback_template_id`/`intervention_id`). `learner.misconception_evidence` (append-only: `student_id`, `interaction_event_id`, `misconception_id`, `evidence_type`, `evidence_weight`, `confidence_before`/`confidence_after`). One wrong answer normally only adds weighted evidence; a misconception is "confirmed" (triggering the fixed `pedagogy.intervention_script`) only once accumulated confidence crosses an authored threshold, after a diagnostic probe — never on the first error. A genuine prerequisite gap (e.g. matrix-multiplication failure inside a Markov task) must be tagged `PREREQUISITE_GAP`, never mislabeled as the unrelated misconception. Exact JSON Schema in `schemas/evidence_rule.schema.json`. |
| ITL-10 | Accessibility is mandatory, not optional | Every template version must support keyboard operation, focus semantics, screen-reader labels, non-color-only feedback, a reduced-motion path, and touch access. Template/scene validation rejects a version missing these. |
| ITL-11 | Runtime LLM boundary | The agent may: rephrase approved feedback, explain approved content, classify open text among predeclared candidate signatures. It may never: invent a misconception, alter an evidence weight, create remediation, create a control/icon, change a correctness determination, mutate the graph, skip a required diagnostic, choose an unapproved intervention, or generate an animation action. |
| ITL-12 | Runtime service contract | `POST /v1/interactions/{instance_id}/{start,event,submit,reset}`, `GET /v1/interactions/{instance_id}/state`. Exact event response shape: `{interaction_state, evaluation:{outcome,error_signature}, feedback:{feedback_template_id,focus_object_ids,icon_token,animation_key}, evidence_updates:[{misconception_id,before,delta,after}], next_action}`. |
| ITL-13 | Admin UI and CLI parity | Admin routes: `/admin/{interaction-templates,interaction-instances,animation-scenes,feedback-policies,misconception-rules}`. CLI: `interactions {templates list/show/validate/publish, controls list, icons list, animations list, instances create/validate/preview, scenes create/validate/render-web/render-manim, feedback validate, evidence test-rule, graph request/status/verify/diff/rebuild --all-published}`. UI, CLI and REST must share one service layer — no divergent logic paths. |
| ITL-14 | Neo4j projection (additive, scoped) | New labels `InteractionTemplate, InteractionTemplateVersion, InteractionInstance, ControlTemplate, IconToken, AnimationTemplate, SceneSpec, FeedbackTemplate, FeedbackPolicy, EvidenceRule` (`projection_kind='interaction_template'`); reuses existing `Concept, Technique, Skill, Misconception, LearningItem, MicroCourse*, CourseState, VideoAsset, VideoSegment, Intervention` labels, never duplicating them. Required edges include `CourseState-[:USES_INTERACTION]->InteractionInstance`, `InteractionInstance-[:{TEACHES,PRACTICES,REQUIRES,ASSESSES,CAN_REVEAL,REMEDIATES}]->{Concept,Technique,Skill,Misconception}`, `EvidenceRule-[:APPLIES_TO]->InteractionTemplateVersion`, `-[:EVIDENCE_FOR]->Misconception`, `-[:USES_DIAGNOSTIC]->LearningItem`, `-[:USES_FEEDBACK]->FeedbackTemplate`, `InteractionInstance-[:USES_SCENE]->SceneSpec-[:USES_ANIMATION]->AnimationTemplate`, `SceneSpec-[:{EXPLAINS,ADDRESSES}]->{Concept,Technique,Misconception}`, `VideoSegment-[:CAN_LAUNCH]->{InteractionInstance,LearningItem,Intervention}`, `InteractionInstance-[:ALIGNED_WITH]->VideoSegment`. Never projected: learner interaction events, learner misconception confidence, learner answers/course state, hidden correct-answer payloads, raw answer-bearing feedback bodies, full transcript text, private storage paths, raw LLM output, personal learner profiles/mastery — explicitly, `Student-[:HAS_MISCONCEPTION]->MC-M05` must never exist in the shared graph. |
| ITL-15 | Idempotent, non-destructive projector | `mathbank-graph/etl/project_interaction_templates.py`: query published template versions → approved course-bound instances → approved SceneSpecs → approved feedback/evidence structures → create a `pipeline.graph_projection` row → MERGE projector-owned nodes → MERGE edges to existing canonical nodes (fail on a missing required canonical target) → prune only `projection_kind='interaction_template'`-owned stale nodes/edges → complete the row → verify parity (nonzero exit on mismatch). Never deletes canonical knowledge nodes or another projection_kind's content. |
| ITL-16 | Graph verify/diff | Verify compares Postgres-expected vs. Neo4j-actual across template versions, instances, semantic mappings, feedback policies, evidence rules, SceneSpecs, animation references, video-alignment edges, and course-state interaction links; exact diff shape `{scope, missing_nodes[], missing_edges[], stale_edges[]}`. |
| ITL-17 | Validation gates | Template: reject invalid JSON Schemas, an unknown control, an icon outside the allowed set, an undeclared semantic action/diagnostic signature, an animation without a reduced-motion fallback, missing accessibility semantics, or arbitrary executable code in config. Instance: reject an unpublished template version, a config schema failure, an unresolved canonical graph ID, missing success criteria, an unapproved feedback policy, an error signature with no evidence-rule mapping, a required-but-unapproved diagnostic/intervention/scene, or a hidden answer payload that would be projected. Scene: reject duplicate object IDs, a timeline referencing an unknown object, an unsupported action, invalid timeline ordering, unresolved canonical tags, missing reduced-motion behavior, or an action/object unsupported by one of the two renderers. Feedback: reject an ordinary first error instantly confirming a misconception, an invalid evidence weight, a missing required probe/remediation, early answer leakage, or an icon conflicting with its feedback type. |
| ITL-18 | Golden regression tests | Jensen (wrong direction → evidence → probe → chord remediation → retry), Vieta (partial E1/E2/E3 correctness → preserve correct pieces → focus the wrong term → remediation), Markov (row total 1.2 → exact row + graph edges identified → evidence → probe → remediation → retry) must each pass end to end, plus: graph projection is idempotent; learner evidence is absent from the shared graph; answer-bearing data is absent from the shared graph; rebuild prunes only `projection_kind='interaction_template'`; a missing `CAN_REVEAL` edge is caught by diff; video-alignment and course-state-interaction edges project correctly. |
| ITL-19 | Refactor of the three existing prototypes | Inequalities (AM-GM/Weighted AM-GM/Cauchy-Schwarz/Jensen/Muirhead), Polynomials (Vieta/quadratic/cubic/biquadratic/higher-degree), and Markov Chains (two-state/recurrence/hitting/transition-matrix/stationary) each become template-driven `interaction_instance` rows with real `error_signature` sets (e.g. Markov's `ROW_SUM_INVALID`, `NEGATIVE_PROBABILITY`; Vieta's `VIETA_ALTERNATING_SIGN_ERROR`; Jensen's `CONVEX_DIRECTION_REVERSED`), replacing the one-off HTML/JS labs and opaque Manim scripts. Must not wrap the original HTML in an iframe, and must not leave one-off JavaScript as the final architecture. Mathematical behavior (initial values, parameter ranges, formulas, computed outputs) must match the originals before they are retired. |
| ITL-20 | Hard prohibitions | Never: project learner evidence/answers/mastery to shared Neo4j; let a course author upload an arbitrary icon or write free-text past the approved control/icon registries; treat one ordinary wrong answer as a confirmed misconception; skip a required diagnostic probe; let the runtime invent a control, animation action, misconception, or remediation; synchronize Neo4j inside the Postgres publication transaction; run a destructive `DETACH DELETE` beyond this pack's own `projection_kind`. |

## Mandated implementation order

The source master prompt (`docs/13_COPILOT_MASTER_PROMPT.md`) fixes an exact
22-step build order, which this project must follow rather than reordering
for convenience: (1) schema migration, (2) initial catalogs/seeds, (3)
validators, (4) service layer, (5) runtime engine, (6) event/evaluation
system, (7) evidence engine, (8) feedback engine, (9) SceneSpec engine, (10)
Web renderer, (11) Manim adapter, (12) admin APIs, (13) admin UI, (14) CLI,
(15) graph projector, (16) outbox/projection integration, (17) graph
verifier, (18-20) refactor the inequality/polynomial/Markov examples, (21)
tests, (22) docs/OpenAPI. Before any of this, the implementer must inspect
the current highest migration number, the live `visual`/`pedagogy`/`learner`
schemas, [40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md)'s schema
(assumed pre-existing), existing graph projectors, and the
`pipeline.projection_request`/outbox schema — and must never edit an old
migration file.

## Open design items to resolve before migration authoring

- This pack's schema hard-depends on `knowledge.misconception`,
  `pedagogy.micro_course_state`, `pedagogy.intervention_script`, and
  `pedagogy.learning_item` from doc 40 — doc 40's migration must be applied
  first, in migration-number order, even though only this pack was named for
  "implementation" in the original request.
  `interaction_instance_concept/technique/skill/misconception`'s exact columns
  are given as "add FK-backed tables" rather than literal DDL in the source
  and must be fixed at migration-authoring time (uuid PK, FK, `role` text
  CHECK, `PRIMARY KEY(instance_id, target_id, role)`, matching the pattern
  already used by doc 40's state-binding tables).
- `control_type`/`feedback_type`/role vocabularies are documented prose, not
  shown as literal CHECK constraints in the source DDL excerpts — must be
  made explicit CHECK constraints at migration time for parity with the rest
  of this codebase's convention (e.g. `pedagogy.solution_step_requirement`).
- The 20 seeded interaction templates, 14 control templates (11 seeded, 3
  gap-flagged: `DROPDOWN_CANONICAL`, `MATRIX_ROW_EDITOR`, `PLAYBACK_CONTROL`),
  23 icon tokens, and 29 animation templates referenced by
  `reference_zips/*/admin_import/microcourse_seed.json` and the pack's own
  `seeds/*.json` files are catalog **content**, not schema; they load via
  step (2) of the mandated order above, after the migration.

## Implementation status

Migrations 032 and 033 and the initial seed/runtime/projector implementation
were reported complete in the previous session. Migration 034 now adds the
ordered micro-course-state-to-interaction binding and guards the bound approved
instance configuration against edits when a referenced course release is
published. The micro-course admin UI lists only approved instances whose exact
template versions are PUBLISHED; the learner API applies the same filter. The
web reader renders the reference families declaratively (accessible Markov
state graph and recurrence, Vieta roots/coefficient sums, Jensen x²
curve/chord comparison) without evaluating stored expressions.

Five of the twenty seed-loaded template versions — `STATE_GRAPH_EXPLORER_V1`,
`TRANSITION_MATRIX_EDITOR_V1`, `RECURRENCE_EXPLORER_V1`,
`POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1`, `FUNCTION_GRAPH_EXPLORER_V1` — now
have real, non-placeholder input/state/event/output JSON Schemas and an
accessibility policy, and are `PUBLISHED` (`scripts/seed_reference_courses.py`
in `mathbank-rest`). Five approved `interaction_instance` rows bind to them and
back the three published reference courses in
[40_MICRO_COURSE_PLATFORM.md](40_MICRO_COURSE_PLATFORM.md). The remaining
fifteen seed templates stay `DRAFT` placeholders until a course needs them.

This web rendering is a visual exploration layer, not the ITL-12 persisted
interaction-event runtime: learner submissions, misconception evidence and
mastery updates are not exposed by this course renderer. The broader
requirements for all template evaluators, interaction-event REST, control
library completeness, Web/Manim SceneSpec renderers and the remaining golden
acceptance flows remain open.

## Cross-document implementation sequence

All six documents must be implemented as one dependency-ordered program:

```text
Phase 0  Inventory current DB migrations, services, projectors, routes, UI and tests.
Phase 1  Resolve canonical schema/contract gaps and secure student payload v2.
Phase 2  Complete interaction catalogs + deterministic runtime + evidence engine.
Phase 3  Complete SceneSpec Web/Manim/mobile renderers and accessibility behavior.
Phase 4  Complete micro-course media/transcript/Q&A/intervention authoring.
Phase 5  Add micro-course ↔ tutoring-route bindings and nested route runtime.
Phase 6  Complete student web/tablet/phone layouts and shared API client.
Phase 7  Complete admin catalog/workspace/media/widgets/routes/publish/graph screens.
Phase 8  Complete structural Neo4j projectors + verify/diff for all projection kinds.
Phase 9  Complete search/embedding publication for approved course/route content.
Phase 10 Wire audit, AI usage, outbox consumers, analytics rollups and retention.
Phase 11 Build mobile client/offline replay/push features.
Phase 12 Run comprehensive cross-system golden fixtures and security/privacy checks.
```

### Global hard prohibitions

Never:
- create a parallel Concept/Technique/Skill taxonomy;
- mutate published content in place;
- expose hidden answers/evaluation policy in learner JSON;
- treat one wrong answer as a confirmed misconception;
- project learner-specific misconception/mastery data into shared Neo4j;
- run destructive shared-graph rebuilds;
- let runtime LLMs invent course states/routes/interactions/remediations;
- duplicate service logic separately in UI/CLI/mobile;
- claim graph/search parity from a queued job;
- use a separate fake preview renderer;
- lose exact return state/time when launching a subflow.
