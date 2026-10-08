# Acceptance Criteria

The deterministic Geometry Scene Engine core is accepted only if:

1. It creates a base scene from typed state/DSL or documented restricted context without tutor/model runtime.
2. It accepts sequential typed additive instructions.
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

## Semi-deterministic system acceptance

Core acceptance is necessary but insufficient. The complete capability also requires:

19. The configured production model interprets free-form natural-language geometry and
    generates typed GeometryPlan/StateDelta/tool requests.
20. Reasoning and presentation are separate logical roles, even if one model performs both;
    presentation-only changes cannot mutate mathematical truth.
21. Theorem/graph consultation preserves source/version/prerequisite evidence; numeric
    agreement or lookup alone does not authorize PROVEN.
22. Candidate validation and semantic relevance are reviewed before acceptance. Failed
    candidates trigger bounded revision, preserve prior accepted state and remain private.
23. Advertised recovery strategies preserve known relations, stable IDs and leakage rules;
    schematic mode is not permission to violate constraints.
24. Both offline engine tests and actual configured paid-model interpretation tests cover
    all ten cases; model plans are judged by semantic invariants, not byte identity.
25. Natural-language A1 interpretation uses exactly BCD, preserves ABCD, displays
    triangle_BCD/point_A1, never substitutes ABC/generic ABCD-only or prematurely reveals
    A2/B2/C2/D2/later points.
26. Tests include paraphrases, ambiguity, invalid-plan/validation feedback, exhaustion and
    provider errors; record reproducible execution evidence and per-invariant outcomes.
27. Authenticated REST, tutor orchestration and UI display accepted images with ownership,
    version/CAS/idempotency, persistent states/assets/lineage and protected debug evidence.
28. Paid tests are explicitly selectable; skipped/mocked tests are not passed interpretation
    acceptance, and offline success must not be reported as complete production delivery.

See [requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md) for the complete
requirements, examples and honest implementation progress.
