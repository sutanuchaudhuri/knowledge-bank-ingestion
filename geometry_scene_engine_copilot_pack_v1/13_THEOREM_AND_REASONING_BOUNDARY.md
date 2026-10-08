# Theorem and Reasoning Boundary

Correct flow:

```text
Problem State
   ↓
Geometry Reasoning Agent (interpret / choose construction / consult theorems)
   ↓
Geometry Presentation Agent (focus / disclosure / styles, never truth)
   ↓
typed GeometryPlan / StateDelta + grounded evidence
   ↓
Deterministic Geometry Scene Engine
   ↓
candidate SVG + validation + diagnostics
   ↓
agent review → accept or bounded revision
```

The renderer is not a theorem prover.

If reasoning proves a relation, it emits a typed state delta. Only then may the visual state assert it.

Theorem lookup is deterministic against a specified graph/knowledge snapshot and returns
statement IDs, prerequisites and provenance. Selecting and applying a theorem is agent
reasoning. Lookup, schema validity and numeric agreement alone do not establish PROVEN.
Reject unsupported promotions through the semantic evidence boundary.

Both logical roles may initially use one configured model. The production model-backed
interpretation layer is required; it is not implemented by the restricted deterministic
parser. Rendering never consults a model or invents a theorem.
See [requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md).
