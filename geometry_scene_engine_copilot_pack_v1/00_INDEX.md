# Geometry Scene Engine — Copilot Implementation Pack v1

## Mission

Build a standalone, testable Geometry Scene Engine for the Mathematics Tutor platform.

The overall system is semi-deterministic: model-backed geometry reasoning and
presentation roles interpret natural-language intent, create typed plans/deltas, invoke
a deterministic geometry core, inspect validation and revise before acceptance.
The core consumes structured state and applies cumulative deltas reproducibly.
See [requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md) for the authoritative
architecture and progress tracker.

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
Validation + agent review → accept or bounded revision
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
11. Keep reasoning and presentation as separate logical roles; presentation cannot mutate truth.
12. Run both model-free deterministic tests and configured-model semantic interpretation tests.
    The production model layer is required, not deferred optional work.
13. Publish only validated, goal-relevant accepted frames; preserve failures and bound retries.

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
