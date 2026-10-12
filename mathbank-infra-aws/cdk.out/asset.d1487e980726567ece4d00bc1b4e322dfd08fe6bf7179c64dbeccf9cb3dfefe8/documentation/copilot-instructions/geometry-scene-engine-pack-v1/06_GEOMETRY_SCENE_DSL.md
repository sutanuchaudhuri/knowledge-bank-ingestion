# Geometry Scene DSL

## YAML example

```yaml
scene:
  id: cyclic_quad_001
  rendering_mode: exact_or_constrained

objects:
  A: {type: point}
  B: {type: point}
  C: {type: point}
  D: {type: point}

relations:
  - type: cyclic
    args: [A, B, C, D]
    status: given

targets:
  - type: collinear
    args: [A, E, C]
    status: target_to_prove

visual:
  focus: [A, B, C, D]
  policies:
    circle_emphasis: background
```

## Additive instruction

```yaml
delta:
  add_objects:
    M: {type: point}
  add_relations:
    - type: midpoint
      args: [M, A, B]
      status: proven
  visual:
    highlight: [M, segment_AM, segment_MB]
```

Applying a delta creates a new immutable scene version.
