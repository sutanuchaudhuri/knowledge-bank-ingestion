# Multishot Example 05 — Circumcenter Chain

## Problem text
> Given a convex quadrilateral \(ABCD\), let \(A_1,B_1,C_1,D_1\) be the circumcenters of triangles \(BCD,CDA,DAB,ABC\), respectively.

## Context
```json
[
  {"type":"given","fact":"ABCD is convex"},
  {"type":"definition","fact":"A1 = circumcenter(BCD)"},
  {"type":"definition","fact":"B1 = circumcenter(CDA)"},
  {"type":"definition","fact":"C1 = circumcenter(DAB)"},
  {"type":"definition","fact":"D1 = circumcenter(ABC)"}
]
```

## Base frame
Show only quadrilateral ABCD.

## Step 1
> Focus on the definition of \(A_1\).

Expected cumulative state:
```text
ABCD remains
triangle_BCD highlighted
point_A1 added
optional circumcircle_BCD shown lightly
```

## Step 2
> Now add \(B_1\).

Expected cumulative state:
```text
everything from Step 1 remains
triangle_CDA shown/highlighted as current focus
point_B1 added
triangle_BCD can dim but stays in scene
```

## Step 3
> Add \(C_1\) and \(D_1\).

Expected:
```text
A1,B1,C1,D1 all present
ABCD remains
A1B1C1D1 may now be shown
```

## Step 4
> Focus on the shared side \(CD\) used in definitions of \(A_1\) and \(B_1\).

Expected:
- highlight CD,
- highlight A1 and B1,
- do not invent an A1-B1 relation until supplied by reasoning.

## Regression purpose
Prevents the earlier failure where a generic quadrilateral was shown while the tutor asked about \(A_1\).
