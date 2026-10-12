# Multishot Example 09 — Midpoint and Auxiliary Segment

## Initial text
> \(M\) is the midpoint of \(AB\). Draw segment \(CM\) as an auxiliary construction.

## Context
```json
[
  {"type":"given","fact":"M is midpoint of AB"},
  {"type":"given","fact":"C is not on AB"}
]
```

## Base frame
- A,M,B collinear,
- M between A and B,
- equal ticks on AM and MB,
- C visible.

## Additive instruction
> Draw auxiliary segment \(CM\).

Expected cumulative state:
- CM added in auxiliary style,
- midpoint marks remain,
- CM may be highlighted as current focus,
- no unrelated angle marks introduced.
