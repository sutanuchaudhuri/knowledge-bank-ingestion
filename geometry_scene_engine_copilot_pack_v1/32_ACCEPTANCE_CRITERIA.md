# Acceptance Criteria

The Geometry Scene Engine is accepted only if:

1. It creates a base scene from text + context without tutor runtime.
2. It accepts sequential additive instructions.
3. Every later frame is cumulative.
4. MathState, SceneState, and VisualState are separately inspectable.
5. Stable semantic IDs persist across frames.
6. GIVEN/PROVEN/TARGET_TO_PROVE/UNKNOWN are supported.
7. Target-to-prove relations are not visually leaked.
8. Cyclic configurations can render a light circle.
9. Very large circles can render only a relevant visible arc.
10. Extensions can be dashed/dotted.
11. Contact/tangent points can be emphasized.
12. Angle marks are selectively shown.
13. Broken/noncommittal geometry can transition to proven straight geometry.
14. Circumcenter chains render all currently relevant derived points.
15. Geometry and visual validators run per frame.
16. SVG elements are addressable by semantic IDs.
17. The engine can replay a saved scene exactly enough for debugging.
18. All ten multishot examples pass.
