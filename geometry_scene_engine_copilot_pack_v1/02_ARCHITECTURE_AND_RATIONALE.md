# Architecture and Rationale

## Why this must be a standalone tool

The visual generator must be independently testable because a tutor can ask a correct question while the picture is wrong.

The tutor, course builder, attempt critic, and Manim exporter are clients of the same geometry engine.

## Core abstraction

\[
\text{Diagram}_k
=
F(
\text{MathState}_k,
\text{SceneState}_{k-1},
\text{VisualPolicy},
\Delta_k
)
\]

### MathState
What is mathematically known, given, assumed, proven, unknown, or targeted.

### SceneState
Which geometric objects currently exist.

### VisualState
What is shown, hidden, highlighted, dimmed, dashed, or emphasized.

## Example

```text
MathState:
A,B,C,D are concyclic             GIVEN
AB ∥ CD                           GIVEN
E is midpoint of AB               PROVEN
A,E,C are collinear               TARGET_TO_PROVE

SceneState:
point_A point_B point_C point_D point_E
segment_AB segment_BC segment_CD segment_DA
circle_Gamma

VisualState:
circle_Gamma visible but light
segment_AB emphasized
point_E highlighted
line_AEC hidden because target is not proved
```

## Why theorem consultation is outside rendering

The renderer must never decide a relation because it “looks plausible.”

A reasoning/construction layer may establish:

```text
PROVEN: Collinear(A,E,C)
```

Only then may the rendering change to one continuous line.

## Cyclic quadrilateral rationale

If `Concyclic(A,B,C,D)` is GIVEN:
- coordinates should satisfy concyclicity,
- the circle can be thin/light,
- quadrilateral edges can be more prominent.

The circle is mathematically real but may be pedagogically secondary.

## Large-circle rationale

If only a small arc matters:
- semantic state still contains a full circle,
- rendering may use `VISIBLE_ARC`,
- this is a visual choice, not a mathematical mutation.

## Straight-vs-broken rationale

If collinearity is a target:
- do not reveal exact straightness early,
- a broken/noncommittal representation is acceptable,
- after proof, promote to a single straight line.

## Two render modes

`EXACT_OR_CONSTRAINED`
- prioritize explicit geometry constraints.

`SCHEMATIC`
- allow controlled distortion for clarity while preserving explicit constraints.

## Clients

- Tutor Agent
- Course Builder
- Student Attempt Critique
- Artifact Library
- Manim Generator
- Admin Preview
- Test Harness
