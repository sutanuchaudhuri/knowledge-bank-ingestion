# Standalone Test Harness

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
