# Standalone Test Harness

This is the model-free deterministic harness for structured fixtures and deltas.
It is one of **two mandatory suites**. A separate configured-model harness must execute
natural-language input → agent plan/tool calls → engine → semantic/frame assertions.
Do not substitute mocks or byte-identical plan snapshots for paid interpretation acceptance.
See [testing strategy](26_TESTING_STRATEGY.md) and
[requirement 37](../requirements/37_GEOMETRY_SCENE_ENGINE.md).

CLI:

```bash
geometry-scene render case.yaml
```

Outputs per frame:

```text
math_state_000.json
scene_state_000.json
visual_state_000.json
frame_000.svg
validation_000.json
```

Semantic assertions:

```text
entity_exists("point_A1")
relation_status("COLLINEAR", ["A","E","C"]) == TARGET_TO_PROVE
visual_not_asserted("COLLINEAR", ["A","E","C"])
svg_element_exists("circle_Gamma")
style("circle_Gamma").emphasis == BACKGROUND
```

SVG snapshots supplement but do not replace semantic assertions.
