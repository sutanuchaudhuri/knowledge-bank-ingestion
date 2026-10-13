# Geometry Construction Planner

The planner converts constraints into a construction order.

Responsibilities:
- identify primary/derived objects,
- choose valid construction order,
- avoid degeneracy,
- select helper objects,
- preserve target-to-prove uncertainty.

Example:

```text
Input:
ABCD convex and cyclic.
E = AC ∩ BD.

Plan:
1 create circle Gamma
2 choose four cyclic points in convex order
3 create quadrilateral edges
4 create diagonals AC and BD
5 create intersection E
```

The planner may consult theorem/definition services but cannot promote a target to proven without an explicit reasoning delta.
