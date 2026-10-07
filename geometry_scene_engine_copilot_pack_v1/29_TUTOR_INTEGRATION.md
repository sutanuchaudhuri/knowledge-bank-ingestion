# Tutor Integration

## Wrong request style

```text
"Draw a diagram for this problem."
```

This is too unconstrained.

## Correct request style

Tutor emits a typed visual action:

```json
{
  "action": "GEOMETRY_STATE_DELTA",
  "scene_id": "scene-123",
  "expected_scene_version": 4,
  "current_math_step": "UNDERSTAND_DEFINITION_OF_A1",
  "math_delta": {},
  "scene_delta": {
    "ensure_entities": ["triangle_BCD", "point_A1"]
  },
  "visual_delta": {
    "highlight": ["triangle_BCD", "point_A1"],
    "dim": ["segment_AB", "segment_DA"]
  },
  "caption": "A1 is the circumcenter of triangle BCD."
}
```

## Tutor responsibility

Tutor decides:
- pedagogical intent,
- current reasoning step,
- which known/proven facts are relevant.

## Geometry engine responsibility

Engine decides:
- valid scene construction,
- coordinate realization,
- rendering policy,
- cumulative overlay,
- validation.

## Example: shared-side explanation

Tutor says:
> Both \(A_1\) and \(B_1\) come from triangles containing \(C,D\).

Requested visual focus:

```text
triangle_BCD
triangle_CDA
segment_CD
point_A1
point_B1
```

Expected visual state:
- CD emphasized,
- A1/B1 highlighted,
- unrelated edges dimmed,
- no new relation between A1/B1 invented.

## Result contract

Tutor receives:
```text
new scene version
frame asset
validation status
caption anchors
semantic element IDs
```
