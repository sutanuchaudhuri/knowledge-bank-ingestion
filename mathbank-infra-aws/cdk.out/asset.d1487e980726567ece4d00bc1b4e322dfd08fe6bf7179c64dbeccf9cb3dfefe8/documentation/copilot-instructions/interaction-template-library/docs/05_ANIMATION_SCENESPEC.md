# 05 — SceneSpec: Shared Web + Manim Animation Language

## Objective

Routine instructional visuals should be described once and rendered through:

```text
SceneSpec
  ├── Web renderer
  └── Manim renderer
```

## Example

```json
{
  "scene_key": "MARKOV_AMC_2019_STATE_COMPRESSION",
  "scene_version": 1,
  "objects": [
    {
      "id": "state_A",
      "type": "STATE_NODE",
      "label": "(1,1,1)",
      "semantic_tags": ["PROB_MARKOV"]
    },
    {
      "id": "state_B",
      "type": "STATE_NODE",
      "label": "(2,1,0) type",
      "semantic_tags": ["PROB_MARKOV","TECH_STATE_GRAPH"]
    }
  ],
  "timeline": [
    {"at_ms":0,"action":"SHOW","targets":["state_A","state_B"]},
    {"at_ms":1800,"action":"DRAW_TRANSITION","from":"state_A","to":"state_B","label":"3/4"},
    {"at_ms":3200,"action":"DRAW_TRANSITION","from":"state_B","to":"state_A","label":"1/4"},
    {
      "at_ms":4800,
      "action":"HIGHLIGHT",
      "targets":["state_A","state_B"],
      "semantic_event":"STATE_MODEL_COMPLETED"
    }
  ]
}
```

## Initial object types

```text
TEXT
LATEX
NUMBER
STATE_NODE
TRANSITION_EDGE
MATRIX
MATRIX_CELL
VECTOR
POINT
LINE
CURVE
FUNCTION_GRAPH
BAR
REGION
POLYNOMIAL
ROOT_MARKER
EQUATION_BLOCK
IMAGE_ASSET
ICON
```

## Initial actions

```text
SHOW
HIDE
FADE
MOVE
SCALE
HIGHLIGHT
DEHIGHLIGHT
DRAW
DRAW_TRANSITION
MOVE_TOKEN
COLLAPSE_EQUIVALENT_STATES
EXPAND_STATE
MORPH
EQUATION_MORPH
SUBSTITUTE
REVEAL_TERM
COMPARE
GRAPH_TO_MATRIX
MATRIX_TO_GRAPH
MATRIX_MULTIPLY_STEP
TWO_STEP_PATH_EXPANSION
ERROR_HIGHLIGHT
CORRECTIVE_REPLAY
WAIT
```

## Semantic events

Examples:

```text
CONCEPT_INTRODUCED
TECHNIQUE_RECOGNITION_CUE_SHOWN
EQUATION_DERIVED
STATE_MODEL_COMPLETED
MISCONCEPTION_COUNTEREXAMPLE_SHOWN
REMEDIATION_STEP_COMPLETED
```

## Narration

Timeline spans may bind:
- narration segment ID
- canonical concepts
- techniques
- skills
- misconceptions
- Q&A contexts

After Manim rendering:
- reconcile actual timestamps
- persist them
- enable timestamp-grounded questioning only after approval

## Reduced motion

Every animation template needs an alternate semantic presentation.

Example:

```text
MOVE_TOKEN
```

becomes:

```text
instant state change + focus highlight + text announcement
```

without losing instructional meaning.

## Semantic parity

Web and Manim do not have to be pixel-identical.

They must preserve:
- object IDs
- canonical tags
- semantic event sequence
- narration references
- misconception markers
