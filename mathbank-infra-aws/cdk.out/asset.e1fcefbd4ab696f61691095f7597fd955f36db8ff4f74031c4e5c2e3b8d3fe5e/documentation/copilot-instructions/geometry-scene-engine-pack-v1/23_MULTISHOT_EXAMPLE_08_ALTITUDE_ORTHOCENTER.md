# Multishot Example 08 — Altitude and Orthocenter

## Initial text
> In triangle \(ABC\), draw altitude from \(A\) to \(BC\). Later draw a second altitude.

## Context
```json
[
  {"type":"given","fact":"ABC is a triangle"}
]
```

## Base frame
Triangle ABC only.

## Step 1
> Construct altitude from A.

Expected:
```text
point_Ha on line BC
segment_AHa
Perpendicular(AHa,BC) via construction semantics
right-angle mark at Ha
```

## Step 2
> Construct altitude from B.

Add:
```text
point_Hb on AC
segment_BHb
right-angle mark at Hb
```

## Step 3
> Highlight intersection of the two altitudes.

Add point H at their intersection.

Do not label H “orthocenter” unless the current context explicitly introduces that semantic identity.
