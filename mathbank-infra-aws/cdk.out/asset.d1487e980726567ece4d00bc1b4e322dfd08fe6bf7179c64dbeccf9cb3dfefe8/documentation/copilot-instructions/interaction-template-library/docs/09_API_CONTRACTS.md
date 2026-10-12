# 09 — REST / Service Contracts

## Templates

```text
GET  /v1/admin/interaction-templates
POST /v1/admin/interaction-templates

GET  /v1/admin/interaction-templates/{id}
POST /v1/admin/interaction-templates/{id}/versions
POST /v1/admin/interaction-template-versions/{id}/validate
POST /v1/admin/interaction-template-versions/{id}/approve
POST /v1/admin/interaction-template-versions/{id}/publish
```

## Controls / icons / animations

```text
GET /v1/admin/control-templates
GET /v1/admin/icon-tokens
GET /v1/admin/animation-templates
```

Mutations require separate platform-admin permission, not normal course author permission.

## Interaction instances

```text
POST /v1/admin/interaction-instances
GET  /v1/admin/interaction-instances/{id}
PATCH /v1/admin/interaction-instances/{id}
POST /v1/admin/interaction-instances/{id}/validate
POST /v1/admin/interaction-instances/{id}/approve
POST /v1/admin/interaction-instances/{id}/preview
```

## SceneSpecs

```text
POST /v1/admin/scenes
GET  /v1/admin/scenes/{id}
PATCH /v1/admin/scenes/{id}

POST /v1/admin/scenes/{id}/validate
POST /v1/admin/scenes/{id}/approve
POST /v1/admin/scenes/{id}/render-web-preview
POST /v1/admin/scenes/{id}/render-manim-preview
```

## Feedback / evidence

```text
POST /v1/admin/feedback-templates
POST /v1/admin/feedback-policies
POST /v1/admin/evidence-rules

POST /v1/admin/evidence-rules/{id}/test
POST /v1/admin/feedback-policies/{id}/simulate
```

## Runtime

```text
POST /v1/interactions/{instance_id}/start
POST /v1/interactions/{instance_id}/event
POST /v1/interactions/{instance_id}/submit
POST /v1/interactions/{instance_id}/reset
GET  /v1/interactions/{instance_id}/state
```

## Runtime response example

```json
{
  "interaction_state": {...},
  "evaluation": {
    "outcome":"ERROR",
    "error_signature":"ROW_SUM_INVALID"
  },
  "feedback": {
    "feedback_template_id":"...",
    "focus_object_ids":["matrix:row:A"],
    "icon_token":"TRY_AGAIN",
    "animation_key":"ANIM_ERROR_HIGHLIGHT"
  },
  "evidence_updates":[
    {
      "misconception_id":"MC-M05",
      "before":0.20,
      "delta":0.35,
      "after":0.55
    }
  ],
  "next_action":"RETRY"
}
```

## Graph endpoints

```text
POST /v1/admin/interactions/graph/projection-request
GET  /v1/admin/interactions/graph/status
GET  /v1/admin/interactions/graph/preview
GET  /v1/admin/interactions/graph/diff
POST /v1/admin/interactions/graph/rebuild
```

## Validation

Every mutation endpoint must fail closed for:
- published immutable objects
- unresolved canonical IDs
- invalid controls
- unknown semantic actions
- evidence rules referencing unknown signatures
- unapproved diagnostic item
- unapproved intervention
