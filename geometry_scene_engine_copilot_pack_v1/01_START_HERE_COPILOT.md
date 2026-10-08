# START HERE — Copilot

## Read order

Read [requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md) for the governing
deterministic-core/agentic-planner distinction and implementation status.

Read:
1. `02_ARCHITECTURE_AND_RATIONALE.md`
2. `03_MATH_STATE_MODEL.md`
3. `04_GEOMETRY_SCENE_MODEL.md`
4. `05_VISUAL_STATE_MODEL.md`
5. `06_GEOMETRY_SCENE_DSL.md`
6. `07_STATE_DELTA_SCHEMA.md`
7. `08_CONSTRUCTION_PLANNER.md`
8. `09_COORDINATE_SOLVER.md`
9. `10_VISUAL_POLICY_ENGINE.md`
10. `11_SVG_RENDERER.md`
11. `12_OVERLAY_STACK_AND_FRAMES.md`
12. `13_THEOREM_AND_REASONING_BOUNDARY.md`
13. `14_GEOMETRY_VALIDATION.md`
14. `15_TEST_HARNESS.md`
15. all ten multishot examples
16. `26_TESTING_STRATEGY.md`
17. `30_COPILOT_MASTER_INSTRUCTIONS.md`
18. `31_COPILOT_PROMPT_SEQUENCE.md`

## First implementation task

Inspect the current repository and return:

```text
Component                                  REUSE / EXTEND / NEW / DEFER
-----------------------------------------------------------------------
Existing geometry visual renderer
Existing SVG/widget renderer
Existing artifact storage
Existing object storage adapter
Existing pgvector metadata
Existing geometry taxonomy
Existing solution-step DAG
Existing graph service
Existing tutor action schema
Existing Manim/YAML work
Existing tests
```

Do not code before this mapping.

## Fundamental contract

Separate free-form agent interpretation from deterministic execution. The overall
system is semi-deterministic, while structured library/CLI use must remain model-free.
The conceptual text/context calls below require a reasoning adapter for free-form
input; a restricted DSL parser is not a general natural-language agent.

```text
create_scene(problem_text, context[])
apply_delta(scene_state, instruction)
render(scene_state, visual_state)
validate(math_state, scene_state, visual_state, svg)
```

Two logical agent roles produce a typed GeometryPlan/StateDelta: reasoning chooses
constructions/theorems and grounded mathematical changes; presentation chooses focus,
disclosure and styles without changing truth. The configured model is required for
production interpretation. Run offline engine tests and paid semantic interpretation
tests separately; accepted candidates must pass validation and goal-relevance review.

## Cumulative-state rule

```text
S0 = base scene from givens
S1 = S0 + delta_1
S2 = S1 + delta_2
S3 = S2 + delta_3
...
```

Never regenerate unrelated geometry per tutor turn.

## Example input

```json
{
  "problem_text": "ABCD is cyclic. Prove that E lies on line AC.",
  "context": [
    {"type": "given", "fact": "A,B,C,D are concyclic"},
    {"type": "target", "fact": "A,E,C are collinear"},
    {"type": "known", "fact": "E is intersection of two constructed lines"}
  ],
  "focus": ["ABCD", "E"]
}
```

Expected:
- draw cyclic quadrilateral,
- circle light,
- show E,
- do not draw A-E-C straight yet,
- do not show a collinearity marker,
- preserve the target as unproved.
