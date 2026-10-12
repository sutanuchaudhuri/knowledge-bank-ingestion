# Multishot Example 01 — Cyclic Quadrilateral

## Initial text
> Let \(ABCD\) be a cyclic quadrilateral. Draw the configuration and then highlight diagonal \(AC\).

## Context array
```json
[
  {"type":"given","fact":"ABCD is a convex quadrilateral"},
  {"type":"given","fact":"A,B,C,D are concyclic"},
  {"type":"focus","fact":"Base quadrilateral first"}
]
```

## Expected base MathState
```text
Quadrilateral(A,B,C,D) GIVEN
Concyclic(A,B,C,D) GIVEN
```

## Expected base SceneState
```text
point_A point_B point_C point_D
segment_AB segment_BC segment_CD segment_DA
circle_Gamma
```

## Expected base VisualState
```text
quadrilateral edges: primary
circle_Gamma: visible, thin, low emphasis
vertex dots: visible
labels: visible
no diagonals
```

## Additive instruction 1
> Add diagonal \(AC\) and highlight it.

Expected delta:
```text
ADD segment_AC
SHOW segment_AC
HIGHLIGHT segment_AC
```

## Cumulative frame 1 expectation
Everything from base persists plus:
```text
segment_AC visible
segment_AC emphasized
circle still light
all four original sides unchanged
```

## Additive instruction 2
> Mark angle \(BAC\), but do not mark any other angle.

Expected:
```text
ADD angle_BAC
SHOW angle_BAC
HIGHLIGHT angle_BAC
```

## Final expectations
- circle remains secondary,
- AC remains visible,
- only angle BAC is marked,
- no label-angle collision.
