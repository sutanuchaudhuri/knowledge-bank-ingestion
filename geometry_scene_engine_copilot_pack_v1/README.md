# Geometry Scene Engine — Copilot Implementation Pack v1

## Mission

Build a standalone, testable Geometry Scene Engine for the Mathematics Tutor platform.

The overall system interprets a problem statement plus current mathematical context
through model-backed geometry reasoning and presentation roles. They create typed plans
and deltas for an independent deterministic engine, inspect validation, and revise before
acceptance. The engine applies structured instructions cumulatively; it is not itself the
free-form natural-language reasoning layer.

**The low-level geometry tools and rendering pipeline should be deterministic or
reproducible given a structured MathState/SceneState/VisualState and seed. The overall
Geometry Scene capability is semi-deterministic: a reasoning agent interprets
natural-language problems, selects constructions/theorems, creates typed state deltas,
invokes deterministic geometry tools, inspects validation results, and may revise the
plan before accepting the artifact.**

The complete requirement and implementation tracker is
[requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md).

It is not an ordinary image generator.

```text
Natural-language problem / tutor goal
    ↓
Geometry Reasoning Agent + Geometry Presentation Agent
    ↓
Typed GeometryPlan / StateDelta
    ↓
Mathematical State
    ↓
Geometry Scene State
    ↓
Visual State
    ↓
SVG / Overlay Frames
    ↓
Validation + agent review
    ├─ accept → persist/show
    └─ reject → bounded plan revision
```

```text
DETERMINISTIC CORE + AGENTIC PLANNER / ORCHESTRATOR
    = SEMI-DETERMINISTIC GEOMETRY SCENE SYSTEM
```

## Non-negotiable principles

1. Visual truth must not leak unproved mathematical truth.
2. Every frame is cumulative from the previous state.
3. A new step adds or changes state; it does not redraw a new unrelated diagram.
4. Semantic geometry and visual appearance are separate.
5. The coordinate solver must satisfy constraints where possible.
6. Visual policy may simplify or de-emphasize mathematically secondary objects.
7. Geometry reasoning/theorem consultation is separate from rendering.
8. The engine must be callable/testable independently of the tutor.
9. Every rendered element must have stable semantic identity.
10. The tutor requests a state delta or visual focus, not “draw a picture.”
11. Reasoning and presentation are two logical roles, even when one model performs both;
    visual decisions cannot change mathematical truth.
12. Production natural-language interpretation requires the configured model. Offline
    deterministic tests remain model-free; paid interpretation tests check semantic
    invariants, not byte-identical plans.
13. A failed candidate is not published. Preserve diagnostics, revise within explicit
    budgets, and never relax known relations or leakage protection to obtain an image.

## Documents

1. `01_START_HERE_COPILOT.md`
2. `02_ARCHITECTURE_AND_RATIONALE.md`
3. `03_MATH_STATE_MODEL.md`
4. `04_GEOMETRY_SCENE_MODEL.md`
5. `05_VISUAL_STATE_MODEL.md`
6. `06_GEOMETRY_SCENE_DSL.md`
7. `07_STATE_DELTA_SCHEMA.md`
8. `08_CONSTRUCTION_PLANNER.md`
9. `09_COORDINATE_SOLVER.md`
10. `10_VISUAL_POLICY_ENGINE.md`
11. `11_SVG_RENDERER.md`
12. `12_OVERLAY_STACK_AND_FRAMES.md`
13. `13_THEOREM_AND_REASONING_BOUNDARY.md`
14. `14_GEOMETRY_VALIDATION.md`
15. `15_TEST_HARNESS.md`
16–25. Ten multishot examples
26. `26_TESTING_STRATEGY.md`
27. `27_REST_API.md`
28. `28_POSTGRES_OBJECT_STORAGE.md`
29. `29_TUTOR_INTEGRATION.md`
30. `30_COPILOT_MASTER_INSTRUCTIONS.md`
31. `31_COPILOT_PROMPT_SEQUENCE.md`
32. `32_ACCEPTANCE_CRITERIA.md`
33. `33_WHAT_NOT_TO_DO.md`
