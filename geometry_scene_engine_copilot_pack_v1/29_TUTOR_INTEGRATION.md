# Tutor Integration

## Semi-deterministic orchestration

```text
Tutor goal + learner-safe current step / known facts / targets / graph-theorems
  → Geometry Reasoning Agent
  → Geometry Presentation Agent
  → typed GeometryPlan / GEOMETRY_STATE_DELTA
  → deterministic construction / solving / policy / SVG / overlay / validation
  → agent reviews candidate and validation
      PASS and correct pedagogical focus → accept / persist / display
      FAIL or wrong focus → bounded typed-plan revision
```

Reasoning interprets constructions, consults grounded theorem evidence and proposes
mathematical changes. Presentation decides emphasis, disclosure, framing and sequencing
without changing mathematical truth. One model may implement both logical roles initially.
The configured model is a required production dependency, not a deferred optional addition.

For "Help the student understand A1", resolve exactly `A1 = circumcenter(BCD)`,
preserve ABCD, highlight BCD and A1, optionally show an established circumcircle lightly,
and dim AB/AD. Do not substitute ABC or generic ABCD-only geometry or reveal later points.

If BCD is nearly degenerate, return an explicit failed candidate and diagnostics. The
agent may request a supported compatible minimum-angle constraint, alternate seed or
schematic realization preserving all known relations; require explicit relayout and
revalidate. Never silently weaken constraints, discard the accepted scene or publish an
invalid fallback. Preserve rejected debug evidence privately.

Persist/replay selected typed plans, tool results and accepted frame lineage. Expose
concise operation/validation/retry status, not private chain-of-thought or later solution
content. Production acceptance requires both offline deterministic fixtures and configured
paid-model semantic interpretation tests; see
[requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md).

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

The engine applies supplied structured decisions; it does not choose theorem applicability
or reinterpret an unconstrained natural-language tutor goal.

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
