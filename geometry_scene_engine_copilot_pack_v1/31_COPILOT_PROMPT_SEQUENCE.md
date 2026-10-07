# Copilot Prompt Sequence

## Prompt 1 — Repository audit

Read the entire pack.

Inspect:
- geometry renderer,
- SVG/widget system,
- artifact store,
- object storage,
- graph service,
- taxonomy,
- tutor action schema,
- Manim/YAML engine,
- tests.

Return REUSE/EXTEND/NEW/DEFER.
No code.

## Prompt 2 — Core schemas

Implement:
```text
MathState
SceneState
VisualState
StateDelta
RelationStatus
RenderingMode
```

Add round-trip serialization tests.

## Prompt 3 — DSL parser

Implement JSON/YAML input support.

Start with examples 1, 2, and 9.

## Prompt 4 — Construction planner

Support:
```text
triangle
quadrilateral
cyclic
midpoint
tangent
circumcenter
extension
altitude
intersection
auxiliary line
```

## Prompt 5 — Coordinate solver

Implement deterministic constrained realization.

Add numerical relation assertions.

## Prompt 6 — Visual policy

Implement:
- vertex dots,
- label collision rules,
- light circles,
- dashed extensions,
- auxiliary styling,
- contact-point emphasis,
- angle-mark suppression,
- target-to-prove protection.

## Prompt 7 — SVG renderer

Implement:
```text
base
construction
annotations
overlay
interaction
```
layers and stable semantic IDs.

## Prompt 8 — Overlay stack

Implement cumulative immutable versions.

Existing points should not jump position across frames.

## Prompt 9 — Leakage validator

Must explicitly detect:
- target collinearity rendered straight,
- target perpendicularity with 90° marker,
- target equal lengths with equal ticks,
- target similarity with correspondence markers,
- target cyclicity with a definitive circle.

## Prompt 10 — Ten multishot fixtures

Encode all 10 cases.

For every step generate:
```text
MathState JSON
SceneState JSON
VisualState JSON
SVG
Validation JSON
```

## Prompt 11 — CLI

Implement:
```text
geometry-scene render fixture.yaml
geometry-scene apply scene.json delta.json
geometry-scene validate output_dir
```

## Prompt 12 — REST

Implement create/apply/read/render/validate/frame endpoints.

## Prompt 13 — Tutor adapter

Implement typed `GEOMETRY_STATE_DELTA` action.

## Prompt 14 — Persistence

Integrate PostgreSQL metadata + object storage artifacts.

## Prompt 15 — Regression suite

Run all ten cases in CI.

The circumcenter-chain test is mandatory.
