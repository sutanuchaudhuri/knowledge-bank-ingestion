# State Delta Schema

Supported operations:

```text
ADD_OBJECT
ADD_RELATION
PROVE_RELATION
DISPROVE_RELATION
CHANGE_STATUS
ADD_CONSTRUCTION
SHOW
HIDE
HIGHLIGHT
DIM
FOCUS
ANNOTATE
RELABEL
```

Example:

```json
{
  "step": 3,
  "math_delta": {
    "add_relations": [
      {
        "type": "COLLINEAR",
        "args": ["A","E","C"],
        "status": "PROVEN"
      }
    ]
  },
  "scene_delta": {
    "add_entities": [
      {"id": "line_AEC", "type": "LINE", "semantic_refs": ["A","E","C"]}
    ]
  },
  "visual_delta": {
    "show": ["line_AEC"],
    "highlight": ["point_E"],
    "hide": ["candidate_polyline_AEC"]
  }
}
```

Cumulative rule:

`State(k+1) = State(k) + Delta(k+1)`
