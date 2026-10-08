# Geometry Scene System: Deterministic Core and Agentic Orchestration

## Status and authority

This requirement records the complete architecture clarification for the independent
[Geometry Scene Engine](../geometry-scene-engine/) and its
[Copilot implementation pack](../geometry_scene_engine_copilot_pack_v1/README.md).
It supersedes wording that describes the entire natural-language-to-diagram capability
as deterministic. It does not declare proposed integrations or agent tests delivered.

**The low-level geometry tools and rendering pipeline should be deterministic or
reproducible given a structured MathState/SceneState/VisualState and seed. The overall
Geometry Scene capability is semi-deterministic: a reasoning agent interprets
natural-language problems, selects constructions/theorems, creates typed state deltas,
invokes deterministic geometry tools, inspects validation results, and may revise the
plan before accepting the artifact.**

```text
DETERMINISTIC CORE
        +
AGENTIC PLANNER / ORCHESTRATOR
        =
SEMI-DETERMINISTIC GEOMETRY SCENE SYSTEM
```

The configured OpenAI model is a required production dependency for free-form
natural-language interpretation and orchestration, not merely an optional future
addition. Structured library/CLI calls and deterministic regression tests must still
work without a model, tutor, application database, or network access. A restricted
context grammar is useful for these paths; it is not a replacement for agent reasoning.

The separate [Neural Geometry Engine roadmap](38_NEURAL_GEOMETRY_ENGINE.md) reuses this
package as a compiler backend. It adds research-facing construction programs,
layout-variable isolation and provisional visuals without replacing this production
contract or certifying its still-separate configured-model acceptance.

## GSE-ARCH: End-to-end boundary

```text
Natural-language problem / tutor goal
        |
        v
Geometry Reasoning Agent
  reads problem, current solution step, known facts, targets, graph/theorems
  interprets intent and chooses a construction strategy
        |
        v
Geometry Presentation Agent
  chooses pedagogical focus, disclosure, emphasis, overlays and framing
        |
        v
Typed GeometryPlan / StateDelta
        |
        v
DETERMINISTIC GEOMETRY TOOLS
  parser / schema validator
  theorem lookup over a specified knowledge snapshot
  construction planner
  constraint solver
  coordinate solver
  visual-policy engine
  SVG renderer
  cumulative overlay engine
  geometry / visual / leakage validator
        |
        v
Candidate frame + validation + diagnostics
        |
        v
Agent reviews result
  PASS and pedagogically appropriate -> accept / persist / show student
  FAIL or poor focus -> revise typed plan and call tools again
  retry budget exhausted -> explicit failure; do not publish invalid geometry
```

This diagram is a required architectural flow, not a statement that every listed tool
or adapter currently exists. Semantic acceptance and mathematical validation are both
necessary: a valid generic quadrilateral does not answer a tutor question about A1.

### GSE-ROLE: Two logical agent roles

| Role | Responsibilities | Forbidden responsibility |
|---|---|---|
| Geometry Reasoning Agent | Understand the problem and context; consult theorem/knowledge graph; decide constructions and mathematical state changes; identify step-relevant objects; create typed GeometryPlan and StateDelta | Invent ungrounded proof status or directly supply an unconstrained final image |
| Geometry Presentation Agent | Decide emphasis, disclosure, cumulative overlays, framing and pedagogical sequencing; request light circles, dashed extensions, selective angle marks and appropriate current focus | Change mathematical truth, theorem status or coordinates merely to beautify the picture |

One configured model may perform both roles initially, but their contracts and
outputs remain separately inspectable. The presentation role emits only visual
operations; any mathematical change must go through the reasoning contract and
its validation boundary. Neither role may bypass deterministic validation.

Required interpretive capabilities include:

- Resolve "the center of the circumcircle of BCD" to `Circumcenter(A1,B,C,D)`,
  not a circumcenter of ABC or a generic ABCD visual.
- Decide whether a perpendicular-bisector construction is useful, using grounded
  facts and theorem prerequisites.
- Select the objects relevant to the current tutor/solution step.
- Recognize when a full circle is distracting and request lower emphasis or a local arc.
- Reveal A1 when appropriate without revealing later points or unproved relations.

### GSE-CORE: Deterministic responsibilities

The engine must solve coordinates, test collinearity and perpendicularity, enforce
tangency and other supplied constraints, generate stable SVG IDs, apply line styles,
maintain cumulative state, detect label collisions, detect target/unknown proof leakage,
and verify that every overlay resolves to an existing semantic geometry object.

It must also validate plan/schema/reference consistency before construction.
Theorem lookup returns identified statements and prerequisites from a specified
source/version; theorem selection and applicability reasoning belong to the agent.
Lookup alone is not a proof and must not promote a relation to PROVEN.

Preserve three separate state types:

- **MathState:** givens, construction assumptions, established facts, unknowns, targets
  and disproven relations, each with explicit status and provenance.
- **SceneState:** instantiated constructions, constraints, coordinates, seed,
  stable semantic IDs, version history and solver diagnostics.
- **VisualState:** visibility, emphasis, styles, framing, focus, captions and overlays.

Rendering does not reason. Solving does not create semantic claims. Visual policy does
not mutate MathState. Every accepted frame is cumulative from the preceding accepted
version; existing points remain fixed unless an explicit relayout is requested.

Reproducibility is scoped to the same structured inputs, previous state, seed, policy,
engine/dependency versions and theorem snapshot. Model plans need not be byte-identical;
save the selected structured plan so its deterministic execution can be replayed.

## GSE-PLAN: Typed planning and truth provenance

The GeometryPlan contract must separate mathematical operations and presentation
operations and identify:

- Problem/current tutor goal, current solution step and learner-safe context.
- Known facts, targets, construction definitions, explicit relation statuses and provenance.
- Base scene/version, seed, rendering mode and any permitted relayout.
- Selected construction/theorem references, prerequisite evidence and semantic object refs.
- Required entities, forbidden disclosures, visual focus, overlays and caption anchors.
- The deterministic operations to invoke and the resulting validation requirements.

The concrete Python/REST representation must be versioned and documented. These
requirements do not introduce a second incompatible StateDelta schema: validate
agent-produced requests against the engine's actual contract and translate conceptual
pack examples at the adapter boundary.

A typed `GEOMETRY_STATE_DELTA` action must retain scene identity, expected version,
current math step and source lineage. A mathematically valid frame cannot change learner
mastery, complete a solution step or imply that the learner has supplied a proof.
Numerical agreement is a consistency check, not evidence authorizing PROVEN status.

Agent-generated theorem/claim justifications require a separate semantic evidence check;
a well-formed schema alone cannot establish mathematical truth. Preserve source/step/theorem
references and reject unsupported promotion of targets or unknowns. Do not retrieve or
disclose later solution content simply to improve a diagram.

## GSE-LOOP: Candidate, review, revision and acceptance

1. Assemble bounded, learner-safe context and read the current accepted scene version.
2. Reason about geometry and theorem applicability; produce a typed mathematical plan.
3. Choose presentation separately; validate schema, references, evidence and disclosure.
4. Invoke deterministic construction, solving, policy, rendering and validation.
5. Return the candidate and diagnostics to the agent, including explicit failure reasons.
6. On PASS, verify relevance to the current goal; accept only if both checks pass.
7. On FAIL or wrong focus, revise the typed request within a configured attempt/call/time
   budget. Do not alter the preceding accepted frame.
8. Persist an accepted immutable version and asset; keep rejected candidates in protected
   debug evidence, not in the student-visible accepted frame sequence.
9. On exhaustion, return a structured failure and keep the last valid frame visible with
   an explicit warning. Never present a fallback image as a successful requested artifact.

Retries must be observable and bounded; use existing configured provider credentials.
Record actual calls, latency and token usage where available. Covered paid access does
not imply unlimited retries, new infrastructure authorization, or a fabricated cost estimate.

### Degenerate circumcenter recovery

```text
Agent request:
  Add circumcenter A1 of triangle BCD.

Tool response:
  FAILED
  Reason: triangle BCD nearly degenerate in this coordinate realization.
  Suggested remedies, only when supported by the deterministic tool:
    re-solve base scene with a minimum-angle constraint
    try an alternate explicit seed
    request schematic mode with all established relations preserved

Agent decision:
  Revise realization strategy, retain known facts and stable semantic IDs,
  request explicit relayout where necessary, invoke tools and validate again.
```

These remedies are not silent engine fallbacks or implemented promises. A minimum-angle
constraint must be compatible with the givens. A seed retry does not fix inconsistent
givens. If no valid realization exists, surface the conflict. SCHEMATIC mode may change
framing or unconstrained choices but must not weaken explicit known relations or leakage
rules, and may never label an invalid drawing as mathematically validated.

### Presentation decision versus deterministic application

The agent may decide: "The full circumcircle distracts from A1; show it lightly and
highlight BCD." Once expressed as typed operations, the engine applies that choice
reproducibly without reinterpreting the prose:

```json
{
  "expected_version": 1,
  "activate_relations": ["def_A1"],
  "ensure_entities": ["triangle_BCD", "point_A1"],
  "visual": {
    "highlight": ["triangle_BCD", "point_A1"],
    "dim": ["segment_AB", "segment_DA"]
  }
}
```

This engine-shaped example presupposes a previously defined/deferred `def_A1` and
matching existing base IDs; it is not a request to invent those facts.
If an established circle is present, its visual emphasis can separately be BACKGROUND.
Do not construct a new circle solely because the presentation request names it.

### Mandatory A1 lifecycle

Tutor goal: **"Help the student understand A1."**

- Reasoning reads the problem/current step/known facts/targets/grounded theorems and
  resolves exactly `A1 = circumcenter(BCD)`.
- Presentation keeps ABCD, reveals A1, highlights BCD, may show its established
  circumcircle lightly, and dims AB and AD.
- The deterministic engine applies the cumulative delta, solves or verifies coordinates,
  renders SVG, and validates constraints, leakage, references and visual quality.
- PASS plus correct focus permits display; FAIL causes bounded plan revision.
- The frame must contain the original ABCD, `triangle_BCD` and `point_A1`.
  A generic ABCD-only diagram fails even if its numeric geometry is valid.
- Do not substitute triangle ABC or introduce A2/B2/C2/D2. Do not reveal B1/C1/D1
  before their specified reveal stage. Already established but deferred definitions can
  remain in MathState without appearing in the current SceneState/VisualState.

## GSE-TEST: Two mandatory test suites

### Suite A: deterministic engine tests, no LLM

Execute all ten multishot fixtures from structured states and deltas:

1. Cyclic quadrilateral: base sides/light circle, then AC, then angle BAC only.
2. Collinearity target: noncommittal A/E/C before proof; defining auxiliaries; explicit
   proven transition and relayout.
3. Tangent/contact point: PT/OT/contact T; no right-angle marker before explicit justification.
4. Similar triangles: progressive angle pairs; no correspondence marker before similarity.
5. Circumcenter chain: progressive A1/B1/C1/D1; mandatory A1/BCD/base preservation regression.
6. Large circle: full semantic circle, local visual arc and focused chord.
7. Parallel plus extension: primary AB/CD; dashed extension even when highlighted.
8. Altitudes/intersection: construction markers; do not name H an orthocenter without justification.
9. Midpoint plus auxiliary CM: collinearity/ticks persist through later focus.
10. Broken-to-straight: unproved noncollinearity display, externally justified straight transition,
    explicit relayout and preserved IDs.

For every frame save all three state JSON files, applied delta, SVG, numerical/visual/leakage
validation and replay data. Assert statuses, required/forbidden entities, numeric tolerances,
stable identities, cumulative overlays, resolved refs, label/marker safety and styles.
Every case produces an inspectable image sequence; snapshots supplement semantic assertions.
Byte-identical replay is appropriate within a pinned deterministic runtime; document any
cross-platform numerical tolerance rather than applying a byte-identity rule to model output.

### Suite B: agent interpretation tests, configured paid model

```text
Natural-language problem + tutor goal + current accepted scene/context
  -> configured model / geometry agent roles
  -> typed GeometryPlan / StateDelta / tool calls
  -> deterministic engine
  -> semantic invariants + validated cumulative frame sequence
```

This suite must invoke the actual configured model; mocks test plumbing but do not count
as interpretation acceptance. Include natural-language versions of all ten scenarios,
paraphrases, ambiguous/unsupported inputs and validation-feedback/retry scenarios.

Do not demand identical wording, exact plan ordering or byte-identical plans. Enforce
semantic invariants, permitted proof status, theorem/construction refs, correct tool calls,
preserved base state and pedagogical disclosure. For the A1 case:

```text
must identify: triangle BCD
must request: circumcenter A1 over exactly B,C,D
must preserve: ABCD base scene
must not request: circumcenter of ABC
must not introduce: A2/B2/C2/D2 or later visible points
must not assert: any unproved target or unrelated A1/B1 relation
must display on acceptance: triangle_BCD and point_A1, not generic ABCD only
```

Also test that presentation-only choices cannot mutate truth; invalid candidates trigger
revision without accepted-state mutation; unsupported remedies are rejected; repeated
failures stop at the configured budget; network/provider failures are explicit.
Record model/prompt/tool-schema versions, seeds, theorem snapshots, calls, normalized plans,
tool results, retries, validation, accepted images and per-invariant results. Report pass
counts and repeat-run variation, not just a selected successful sample. Define non-safety
quality thresholds before production acceptance; leakage, violated givens and wrong-object
acceptance are hard failures, never averaged away.

Keep paid tests explicitly selectable and separate from offline CI. Production still
requires the model-backed layer. A skipped paid suite is "not evaluated", not "passed".

## GSE-INTEGRATE: REST, tutor, UI and persistence

- Keep the root subproject independently installable/testable; the deterministic core
  must not import MathBank runtime/database/model providers.
- Expose authenticated create/apply/read/render/validate/frame operations. The agent/model
  interpretation adapter is a distinct boundary, not an implicit model call inside SVG rendering.
- Wire both logical roles into the tutor orchestration plan. Return typed tool errors,
  validation and diagnostics so the agent can revise; do not return success-shaped defaults.
- Preserve ownership, expected-version/CAS, idempotency and immutable accepted versions.
  Reject stale requests rather than overwriting a concurrently accepted frame.
- The web renders only accepted, owner-authorized assets. Show current focus, cumulative
  frames and captions without exposing credentials, later solution content or debug payloads.
- Provide concise operation/review/retry status and evidence references, not private
  chain-of-thought. Staff can inspect structured plans, validations and rejected candidates
  through protected debug/admin surfaces.
- Persist accepted states/deltas/validation/lineage in PostgreSQL metadata and private frame
  assets/bundles in object storage, reusing existing adapters. Isolate candidate debug evidence.
  A local SQLite development adapter is not this production storage integration.
- Cache/reuse only with matching structured state, context/disclosure, engine/policy/schema
  versions and ownership checks. Cache hits never bypass validation or imply a new proof.
  Embeddings/graph retrieval support discovery/theorem context, not geometric validation.

## Initial repository audit: REUSE / EXTEND / NEW / DEFER

| Classification | Decision |
|---|---|
| REUSE | Safe declarative SVG/stable-ID conventions and test patterns; later reuse existing auth, private object-storage/artifact and graph retrieval adapters outside the standalone core |
| EXTEND | Existing preview/step/tutor contracts through explicit adapters; do not use reset-to-base frames for cumulative scenes |
| NEW | Independent typed states/plan/delta contracts, planner, solver, policy, renderer, validation, CLI/harness; geometry-specific agent interpretation/review contracts with two logical roles and configured-model tests |
| DEFER | Manim/animation and vector/taxonomy artifact-discovery coupling; not the production reasoning/presentation model layer |

## Implementation progress and remaining acceptance work

| Surface | Observed status |
|---|---|
| Independent deterministic source package | Initial implementation under `geometry-scene-engine/src/geometry_scene/`; separate MathState/SceneState/VisualState, cumulative deltas and seeded solving |
| Ten executable structured fixtures | Present under `geometry-scene-engine/fixtures/`; multishot tests produce per-frame SVG/state/validation files in temporary test output |
| Offline core/example/standalone API tests | Latest local run: **35 passed**, with one upstream TestClient deprecation warning; includes circumcenter focus, replay/ownership/CAS/idempotency tests |
| Static checking | mypy reported no issues in 15 source files; initial ruff findings fixed/formatted |
| Image review/persistent gallery/CI artifacts | Pending; temporary test SVG generation is not completed persistent/visual acceptance |
| Full failure evidence and all visual/semantic safety cases | Pending broader coverage; current tests are not a theorem prover or complete visual-quality certification |
| Standalone REST and local durability | Injectable router and SQLite adapter exist and are tested in isolation |
| MathBank REST/tutor/web integration | Pending; standalone router is not yet mounted in MathBank REST and geometry tools are not yet registered in tutor/UI |
| GeometryPlan and agentic reasoning/presentation/review loop | Required, not implemented; the existing `tutor.py` typed action is not the configured-model orchestration layer |
| Paid configured-model interpretation acceptance suite | Required, not implemented or run; no geometry interpretation model calls made during this requirement update |
| Production PostgreSQL/private object-store persistence | Pending; no geometry migration/provisioning applied |

Recorded verification:

```bash
geometry-scene-engine/.venv/bin/pytest geometry-scene-engine/tests -q --tb=short
geometry-scene-engine/.venv/bin/mypy geometry-scene-engine/src --ignore-missing-imports
```

Full acceptance requires **both** suites plus production integration, accepted-image
display, persistent/debug/replay evidence and the pack's remaining core safety criteria.
Do not declare the semi-deterministic system complete based only on deterministic fixtures.
