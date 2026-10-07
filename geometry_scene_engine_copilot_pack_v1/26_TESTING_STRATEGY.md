# Explicit Testing Strategy

## Objective

Test the Geometry Scene Engine independently from the tutor and application.

The testing strategy must cover:

1. parsing,
2. MathState creation,
3. SceneState construction,
4. coordinate constraints,
5. VisualState policy,
6. SVG structure,
7. cumulative overlays,
8. theorem-leakage prevention,
9. validation,
10. deterministic replay.

## The ten mandatory scenarios

1. Cyclic quadrilateral
2. Collinearity target not yet proved
3. Tangent/contact point
4. Similar triangles progressively established
5. Circumcenter chain
6. Large circle rendered as local arc
7. Parallel line with extension
8. Altitude/orthocenter construction
9. Midpoint with auxiliary line
10. Broken-to-straight transition

## Test levels

### Level 1 — Parser unit tests
Input raw text and context array.

Assert:
```text
correct object extraction
correct relation statuses
correct targets
```

### Level 2 — Scene-state tests
Assert:
```text
required entities exist
forbidden entities do not exist
stable semantic IDs persist
```

### Level 3 — Coordinate tests
Assert numerical relations within tolerance:
```text
concyclic
parallel
perpendicular
midpoint
equal length
incidence
```

### Level 4 — Leakage tests
Examples:
```text
TARGET_TO_PROVE collinearity must not be rendered straight
TARGET_TO_PROVE perpendicularity must not show a right-angle mark
TARGET_TO_PROVE equal lengths must not show equal ticks
TARGET_TO_PROVE similarity must not show correspondence markers
```

### Level 5 — Visual-policy tests
Assert:
```text
circle low emphasis
extension dashed
primary segment stronger
contact point visible
current focus highlighted
only permitted angle marks shown
```

### Level 6 — Overlay accumulation tests
For every frame \(k\):
```text
persistent scene entities from frame_(k-1)
remain in frame_k
```
unless an explicit HIDE/REPLACE visual operation exists.

Scene identity must persist.

### Level 7 — SVG structural tests
Assert:
```text
point_A exists
segment_AB exists
circle_Gamma exists when semantically present
no duplicate IDs
overlay references resolve
```

### Level 8 — Snapshot tests
Use SVG snapshots for gross visual regression.

Do not rely only on snapshots.

### Level 9 — Reproducibility
Given same:
```text
MathState
SceneState seed
VisualPolicy
```
expect the same semantic scene and stable coordinates/layout within defined tolerance.

### Level 10 — End-to-end multishot
Input:
```text
problem text
context[]
delta_1
delta_2
...
```

Output:
```text
all cumulative state JSON
all SVG frames
all validation reports
```

## Required output directory

```text
case_05_circumcenter_chain/
  input.json

  math_state_000.json
  scene_state_000.json
  visual_state_000.json
  frame_000.svg
  validation_000.json

  delta_001.json
  math_state_001.json
  scene_state_001.json
  visual_state_001.json
  frame_001.svg
  validation_001.json

  ...
```

## Example test fixture contract

```json
{
  "case_id": "COLLINEAR_TARGET",
  "problem_text": "...",
  "context": [],
  "seed": 17,
  "steps": [
    {
      "instruction": "...",
      "expected_math": [],
      "expected_scene": [],
      "expected_visual": [],
      "forbidden_visual_claims": []
    }
  ]
}
```

## Hard failure conditions

A test must fail if:

- a target relation is visually leaked,
- an explicit given relation is violated,
- cumulative state is lost,
- an extension is rendered as an ordinary primary segment,
- a low-priority circle dominates the figure,
- a required contact point disappears,
- angle markers overlap or assert unproved information,
- an overlay targets a nonexistent SVG ID,
- a later frame silently changes semantic identities,
- a renderer output cannot be reconstructed from saved state.

## Circumcenter regression

This is mandatory.

Given:
```text
A1 = circumcenter(BCD)
```

and tutor focus:
```text
UNDERSTAND_DEFINITION_OF_A1
```

the frame must include:
```text
triangle_BCD
point_A1
ABCD
```

A generic `ABCD`-only diagram is a test failure.
