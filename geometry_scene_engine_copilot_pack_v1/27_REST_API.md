# REST API

## Create scene

```text
POST /v1/geometry-scenes
```

Request:

```json
{
  "problem_text": "...",
  "context": [
    {"type":"given","fact":"A,B,C,D are concyclic"}
  ],
  "rendering_mode": "EXACT_OR_CONSTRAINED",
  "seed": 17
}
```

Response:

```json
{
  "scene_id": "...",
  "version": 0,
  "math_state": {},
  "scene_state": {},
  "visual_state": {},
  "frame_asset": {},
  "validation": {}
}
```

## Apply delta

```text
POST /v1/geometry-scenes/{scene_id}/deltas
```

Request:

```json
{
  "expected_version": 2,
  "instruction_text": "Highlight triangle BCD and add circumcenter A1.",
  "math_delta": {},
  "scene_delta": {},
  "visual_delta": {}
}
```

## Read version

```text
GET /v1/geometry-scenes/{scene_id}/versions/{version}
```

## Render version

```text
GET /v1/geometry-scenes/{scene_id}/versions/{version}/render
```

## Validate

```text
POST /v1/geometry-scenes/{scene_id}/versions/{version}/validate
```

## Frame sequence

```text
GET /v1/geometry-scenes/{scene_id}/frames
```

## Standalone requirement

The same service logic must be invokable as a Python/library API and CLI without HTTP.
