# Multishot Example 03 — Tangent and Contact Point

## Initial text
> A tangent from point \(P\) touches circle \(\Gamma\) at \(T\). Let \(O\) be the center.

## Context
```json
[
  {"type":"given","fact":"PT is tangent to Gamma at T"},
  {"type":"given","fact":"O is center of Gamma"}
]
```

## Base SceneState
```text
circle_Gamma
point_O
point_P
point_T
segment_PT
segment_OT
```

## Base VisualState
- circle thin/light,
- PT prominent,
- contact point T explicit,
- OT visible but secondary,
- no right-angle mark yet unless the current MathState already asserts it.

## Additive instruction 1
> Highlight the contact point.

Expected:
```text
HIGHLIGHT point_T
```

## Additive instruction 2
> We now use the tangent-radius theorem, so mark \(OT \perp PT\).

Expected MathState delta:
```text
Perpendicular(OT,PT) PROVEN
```

Expected VisualState:
```text
ADD right_angle_mark_OTP
SHOW right_angle_mark_OTP
```

## Critical test
No right-angle marker in base frame before the theorem relation is known/proven.
