# Theorem and Reasoning Boundary

Correct flow:

```text
Problem State
   ↓
Reasoning / Theorem Agent
   ↓
validated MathStateDelta
   ↓
Geometry Scene Engine
   ↓
SVG
```

The renderer is not a theorem prover.

If reasoning proves a relation, it emits a typed state delta. Only then may the visual state assert it.
