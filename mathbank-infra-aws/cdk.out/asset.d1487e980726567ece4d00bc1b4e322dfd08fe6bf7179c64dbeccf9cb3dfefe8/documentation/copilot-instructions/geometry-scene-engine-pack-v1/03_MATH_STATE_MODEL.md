# Mathematical State Model

## Relation statuses

```text
GIVEN
ASSUMED_FOR_CONSTRUCTION
PROVEN
UNKNOWN
TARGET_TO_PROVE
DISPROVEN
```

## Fact types

```text
Point(A)
Segment(A,B)
Line(A,B)
Ray(A,B)
Circle(Gamma)
Triangle(A,B,C)
Quadrilateral(A,B,C,D)
Collinear(A,B,C)
Concyclic(A,B,C,D)
Parallel(AB,CD)
Perpendicular(AB,BC)
EqualLength(AB,AC)
EqualAngle(ABC,BCD)
Midpoint(M,A,B)
Tangent(AT,Gamma,T)
Secant(AB,Gamma)
Circumcenter(O,A,B,C)
Intersection(E,line_1,line_2)
AngleMeasure(ABC,90)
```

## Schema example

```json
{
  "objects": [
    {"type": "POINT", "id": "A"},
    {"type": "POINT", "id": "B"}
  ],
  "relations": [],
  "targets": [],
  "assumptions": [],
  "provenance": [],
  "step_index": 0
}
```

Visual properties never belong here.
