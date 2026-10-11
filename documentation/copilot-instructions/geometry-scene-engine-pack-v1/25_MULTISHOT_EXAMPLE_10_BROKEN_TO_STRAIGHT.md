# Multishot Example 10 — Broken Representation Becomes Straight

## Initial text
> A geometry argument will eventually prove that two constructed segments form one straight line through \(P\).

## Context
```json
[
  {"type":"target","fact":"segment XP and PY form a straight line"},
  {"type":"known","fact":"XP exists"},
  {"type":"known","fact":"PY exists"}
]
```

## Base frame
Show a noncommittal configuration such as:
```text
X —— P
       \
        Y
```

Do not draw a 180° mark.
Do not force exact collinearity.

## Step 1
> Establish angle \(XPY=180^\circ\).

Math delta:
```text
AngleMeasure(XPY,180) PROVEN
Collinear(X,P,Y) PROVEN
```

## Cumulative visual update
- transition to a straight line,
- preserve stable point identities,
- show the now-proven relation,
- optional caption: “The two segments form a straight line.”

## Regression purpose
Ensures scene evolution reflects new mathematical state without discarding prior objects.
