# PostgreSQL, Object Storage, and Reuse

## PostgreSQL entities

Suggested logical tables:

```text
visual.geometry_scene
visual.geometry_scene_version
visual.geometry_math_state
visual.geometry_scene_state
visual.geometry_visual_state
visual.geometry_delta
visual.geometry_validation
visual.geometry_frame
visual.geometry_lineage
```

## Object storage

Store:
```text
SVG frames
serialized scene bundles
thumbnails
optional animation/Manim manifests
```

PostgreSQL stores:
```text
asset_id
object_uri
hash
scene_id
version
status
metadata
```

## pgvector

For future reuse, index descriptions such as:
```text
"cyclic quadrilateral with light circumcircle"
"tangent circle contact-point explanation"
"circumcenter chain for derived quadrilateral"
"target collinearity shown noncommittally"
```

Embeddings support discovery/reuse.

They do not validate geometry.

## Lineage

If an artifact is derived from:
```text
problem_id
solution_step_id
tutor_step_id
```
preserve those references.
