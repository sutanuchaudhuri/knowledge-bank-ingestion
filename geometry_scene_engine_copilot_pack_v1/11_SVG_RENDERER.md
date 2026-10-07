# SVG Renderer

Required:
- valid SVG,
- stable semantic IDs,
- semantic grouping,
- responsive viewBox,
- click/hover addressability.

Layers:

```text
g#base
g#construction
g#annotations
g#overlay
g#interaction
```

Examples:

```text
point_A
segment_AB
circle_Gamma
angle_ABC
mark_parallel_AB_CD
label_A
```

Renderer only renders state; it never invents mathematics.
