# Multishot Example 07 — Parallel Lines and Extension

## Initial text
> Segment \(AB\) is parallel to segment \(CD\). Extend \(AB\) beyond \(B\) to point \(E\).

## Context
```json
[
  {"type":"given","fact":"AB parallel CD"},
  {"type":"construction","fact":"E lies on extension of AB beyond B"}
]
```

## Base frame
- AB and CD solid,
- parallel marks shown only if policy allows and fact is known.

## Additive instruction 1
> Add extension to E.

Expected:
```text
segment_AB remains solid
extension_BE dashed/dotted
point_E visible
```

## Additive instruction 2
> Highlight the extended line direction.

Expected:
- AB remains primary,
- BE highlighted but retains extension style,
- extension not visually indistinguishable from original segment.
