# Multishot Example 04 — Similar Triangles

## Initial text
> In a geometry problem, triangles \(ABC\) and \(ADE\) will later be shown similar. Initially only the base diagram is known.

## Context
```json
[
  {"type":"given","fact":"A,B,C,D,E are points"},
  {"type":"target","fact":"triangle ABC is similar to triangle ADE"}
]
```

## Base rule
Do not add similarity marks.
Do not visually force correspondence beyond explicit constraints.

## Additive instruction 1
> Highlight the two triangles as the current objects of interest.

Expected:
```text
SHOW triangle_ABC
SHOW triangle_ADE
HIGHLIGHT triangle_ABC
HIGHLIGHT triangle_ADE
```

No similarity symbol or angle marks.

## Additive instruction 2
> We have established \(\angle ABC=\angle ADE\).

Math delta:
```text
EqualAngle(ABC,ADE) PROVEN
```

Visual delta:
```text
ADD matching angle marks on those angles only
```

## Additive instruction 3
> We have also established \(\angle ACB=\angle AED\).

Add second angle-pair marks.

## Additive instruction 4
> Therefore the triangles are similar.

Change target to proven.

Now permit:
```text
caption: triangle ABC ~ triangle ADE
vertex-correspondence overlay
```

## Final cumulative frame
Contains:
- both triangles,
- two established angle-pair markers,
- similarity caption,
- no unrelated angle marks.
