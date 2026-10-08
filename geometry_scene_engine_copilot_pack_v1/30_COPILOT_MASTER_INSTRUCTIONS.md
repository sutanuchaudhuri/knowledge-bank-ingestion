# Copilot Master Instructions

## Mission

Implement an independent deterministic geometry core and a required model-backed
agentic planner/orchestrator. Together they are the semi-deterministic Geometry Scene System.

The low-level tools and rendering pipeline must be deterministic or reproducible given
structured MathState/SceneState/VisualState and seed. The overall capability uses an agent
to interpret natural-language intent, select constructions/theorems, create typed plans/deltas,
inspect validation and revise before acceptance.

Follow [requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md) completely.
Do not describe the full natural-language-to-artifact system as deterministic or defer
the configured production model layer as an optional future feature.

## Mandatory first action

Inspect the repository and return a detailed:

```text
REUSE
EXTEND
NEW
DEFER
```

mapping.

Do not code before that.

## Architecture invariants

### Invariant 1 — Separate states
`MathState`, `SceneState`, and `VisualState` must be separate types.

### Invariant 2 — Relation status
Every relevant mathematical relation has an explicit status.

### Invariant 3 — No proof leakage
`TARGET_TO_PROVE` and `UNKNOWN` relations must not be visually asserted.

### Invariant 4 — Cumulative versions
Every scene update creates a new version from the preceding version.

### Invariant 5 — Stable semantic IDs
Existing semantic entity IDs persist across frames.

### Invariant 6 — Renderer does not reason
Renderer cannot prove relations.

### Invariant 7 — Solver does not invent semantics
Coordinate solver satisfies supplied constraints; it cannot create new mathematical claims.

### Invariant 8 — Visual policy does not mutate truth
Styling never changes MathState.

### Invariant 9 — Validate every frame
Every generated frame has a validation record.

### Invariant 10 — Standalone use
The engine works without tutor runtime or database.

### Invariant 11 — Two logical agent roles
Geometry Reasoning selects grounded mathematical constructions/state changes.
Geometry Presentation selects focus/disclosure/styles without changing truth.
One model may perform both initially, with separately inspectable typed outputs.

### Invariant 12 — Review and bounded revision
Return candidate validation/diagnostics to the agent. Publish only validated,
goal-relevant accepted frames. Preserve rejected evidence and the prior accepted
version; retries/remedies must be supported, compatible and bounded.
Schematic mode must not weaken explicit constraints or proof-leakage protection.

### Invariant 13 — Two mandatory test suites
Run model-free deterministic fixtures and configured paid-model natural-language
interpretation tests. Judge model output by semantic invariants, not byte identity.
Mocks or skipped paid tests do not establish production interpretation acceptance.

### Invariant 14 — Evidence is not numeric agreement
Theorem lookup returns versioned statements/prerequisites. Selection and applicability
belong to reasoning with grounded evidence. Schema validity, lookup or coordinates alone
cannot promote a target to PROVEN.

## Suggested module structure

```text
geometry_scene/
  schemas/
    math_state.py
    scene_state.py
    visual_state.py
    delta.py
    enums.py

  parser/
    natural_language_parser.py
    dsl_parser.py

  planner/
    construction_planner.py

  solver/
    coordinate_solver.py
    constraint_library.py

  visual_policy/
    geometry_policy.py
    status_policy.py

  renderer/
    svg_renderer.py
    overlay_renderer.py

  validation/
    math_validator.py
    visual_validator.py
    leakage_validator.py

  service/
    geometry_scene_service.py

  api/
  cli/
  persistence/
  tests/
```

## Multishot examples are executable specifications

Convert every example file into:
- a fixture input,
- sequential deltas,
- expected MathState,
- expected SceneState,
- expected VisualState,
- forbidden visual assertions,
- SVG structural assertions,
- validation assertions.

Do not merely copy them into documentation.

## Required regression

The circumcenter-chain scenario must prevent the known failure:
```text
Tutor asks about A1
but UI shows only generic ABCD
```

This must become a permanent regression test.

## No “simplified MVP” that removes core semantics

A first implementation may support fewer relation types, but it must not omit:
- relation statuses,
- cumulative scene versions,
- stable IDs,
- leakage validation,
- independent test harness.

These are foundational, not optional polish.

## Logging/debugging

For every failed frame, make it possible to inspect:

```text
input problem text
context array
previous MathState
previous SceneState
previous VisualState
applied delta
solver diagnostics
render policy
validation failures
generated SVG
```

## Determinism

Use explicit seeds for tests.

Avoid random scene changes between runs unless a test specifically exercises alternative valid layouts.
