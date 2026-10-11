# Geometry Scene Model

## Entity types

```text
POINT
SEGMENT
LINE
RAY
CIRCLE
ARC
POLYGON
TRIANGLE
QUADRILATERAL
PERPENDICULAR_BISECTOR
ANGLE_MARK
RIGHT_ANGLE_MARK
EQUAL_LENGTH_MARK
PARALLEL_MARK
TANGENCY_MARK
LABEL
```

## Stable IDs

```text
point_A
point_B
segment_AB
circle_Gamma
angle_ABC
triangle_BCD
perp_bisector_CD
```

Stable IDs enable overlays, click targets, replay, Manim export, and tests.

## Scene version

```json
{
  "scene_id": "scene-001",
  "version": 3,
  "entities": [],
  "constraints": [],
  "construction_history": []
}
```
