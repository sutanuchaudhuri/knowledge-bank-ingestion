# Multishot Example 02 — Collinearity Is the Target

## Initial text
> Points \(A\) and \(C\) are fixed. Point \(E\) is constructed from two auxiliary lines. Prove that \(A,E,C\) are collinear.

## Context
```json
[
  {"type":"given","fact":"A and C are distinct"},
  {"type":"known","fact":"E is an intersection of two auxiliary lines"},
  {"type":"target","fact":"A,E,C are collinear"}
]
```

## Base MathState
```text
Collinear(A,E,C) TARGET_TO_PROVE
```

## Base visual requirements
FORBID:
```text
A,E,C exactly on one straight line
straight-line marker
line_AEC entity
```

Show A,C,E in a noncommittal configuration.

## Additive instruction 1
> Add the two auxiliary lines defining \(E\).

Cumulative result:
- A,C,E remain,
- auxiliary lines appear light/dashed,
- E highlighted.

## Additive instruction 2
> The proof has now established \(A,E,C\) are collinear.

Expected MathState delta:
```text
Collinear(A,E,C):
TARGET_TO_PROVE → PROVEN
```

Expected SceneState delta:
```text
ADD line_AEC
```

Expected VisualState delta:
```text
SHOW line_AEC
HIDE candidate noncommittal/broken representation
```

## Test assertions
Before proof:
```text
visual_not_asserted(collinear(A,E,C)) == true
```

After proof:
```text
visual_asserted(collinear(A,E,C)) == true
```
