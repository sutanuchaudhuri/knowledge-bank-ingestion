# Copilot Prompt Sequence

This sequence implements **deterministic core + agentic planner/orchestrator =
semi-deterministic Geometry Scene System**. The configured production model layer is
required, not deferred optional work. Keep the core independently testable/model-free.
Follow [requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md); record delivered,
pending and tested surfaces separately.

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
GeometryPlan (agent-facing typed contract, not a competing delta format)
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

Wire the action into the model-backed orchestration plan described below; a typed
action class alone is not natural-language reasoning or production tutor integration.

## Prompt 14 — Persistence

Integrate PostgreSQL metadata + object storage artifacts.

## Prompt 15 — Regression suite

Run all ten cases in CI.

The circumcenter-chain test is mandatory.

## Prompt 16 — Geometry Reasoning Agent

Use the configured model to interpret the natural-language problem/current tutor goal,
read learner-safe known facts/targets/current step, consult versioned theorem/graph
evidence, select constructions and generate schema-validated GeometryPlan/StateDelta.
Keep model/database imports outside the deterministic core. Validate theorem prerequisites
and proof-status evidence; do not invent final coordinates or ungrounded PROVEN facts.

## Prompt 17 — Geometry Presentation Agent

Implement a second logical role, initially shareable with the same model. Decide
pedagogical focus, disclosure, overlays, framing, de-emphasis and sequencing. Emit only
visual operations; mathematical changes require the reasoning boundary.
For A1, preserve ABCD and reveal/highlight exactly triangle BCD and circumcenter A1.

## Prompt 18 — Agent review/revision loop

Invoke deterministic tools, inspect candidate frames/validation/diagnostics and verify
goal relevance before acceptance. On failure revise within explicit call/time/attempt
budgets. Support only advertised compatible remedies; preserve known relations, IDs and
the prior accepted frame. Save rejected evidence privately, fail explicitly on exhaustion,
and publish only accepted owner-authorized assets. Never relax givens in schematic mode.

## Prompt 19 — Paid interpretation acceptance and end-to-end display

Run configured-model natural-language tests for all ten cases, paraphrases, ambiguous
inputs and failed-candidate revision. Assert semantic constructions, correct tool calls,
disclosure, statuses and accepted images rather than byte-identical plans. The A1 case
must resolve BCD, never ABC/generic ABCD-only, with no premature later-point reveal.
Record model/prompt/schema versions, calls/retries, plans, validation and per-invariant
results; skipped/mocked tests are not model interpretation acceptance.
Verify authenticated REST, tutor registration, accepted UI images and durable lineage.
Offline fixture success alone does not complete the semi-deterministic system.
