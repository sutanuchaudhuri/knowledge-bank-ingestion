# Multishot Example 06 — Large Circle, Local Arc

## Initial text
> A very large circle passes through points \(A,B,C\), but only a small local portion near \(A,B,C\) matters.

## Context
```json
[
  {"type":"given","fact":"A,B,C lie on circle Gamma"},
  {"type":"visual_preference","fact":"local configuration is pedagogically primary"}
]
```

## Semantic state
Full `circle_Gamma` exists.

## Visual state
```text
circle_Gamma.render_mode = VISIBLE_ARC
circle_Gamma.emphasis = BACKGROUND
```

## Additive instruction
> Highlight chord \(AB\).

Expected cumulative frame:
- local arc remains,
- chord AB added/emphasized,
- no need to zoom to full circle,
- metadata still identifies a full semantic circle.

## Validation
Renderer must not replace the semantic circle with an arbitrary curve.
