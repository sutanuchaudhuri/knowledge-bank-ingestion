# 07 — Admin UI and CLI

## Admin routes

```text
/admin/interaction-templates
/admin/interaction-instances
/admin/animation-scenes
/admin/feedback-policies
/admin/misconception-rules
```

## Template Library screen

Show:
- template key
- version
- family
- allowed controls
- allowed icons
- diagnostic capabilities
- accessibility status
- publication status
- instance count
- graph projection status

Actions:
- create draft version
- compare versions
- validate
- approve
- publish
- graph preview
- graph diff
- deprecate

## Interaction Instance editor

From a micro-course state:

```text
Add Interaction
  ↓
Choose template
  ↓
Choose exact published version
  ↓
Configure controls / values
  ↓
Bind existing Concept / Technique / Skill
  ↓
Attach likely Misconceptions
  ↓
Map error signatures to evidence rules
  ↓
Attach feedback policy
  ↓
Attach diagnostic items
  ↓
Attach interventions
  ↓
Attach SceneSpec
  ↓
Preview learner flow
  ↓
Validate
  ↓
Approve / publish with course release
```

## Three-pane authoring layout

```text
+--------------------+-----------------------------+------------------------+
| Structure          | Preview                     | Semantics              |
|                    |                             |                        |
| template/version   | live interaction            | concepts               |
| controls           | event inspector             | techniques             |
| scene timeline     | feedback preview            | skills                 |
| feedback stages    | reduced-motion preview      | misconceptions         |
|                    |                             | graph relationships    |
+--------------------+-----------------------------+------------------------+
```

## Event inspector

Admin can fire test events and see:

```text
semantic_action
evaluation
error_signature
candidate misconceptions
evidence delta
current confidence
feedback selected
diagnostic selected
intervention selected
graph targets
```

This is critical for testing diagnosis before publication.

## Icon picker

Only approved semantic tokens.

Display:
- token
- icon preview
- accessible label
- semantic role
- allowed contexts

Do not let course authors upload arbitrary icons for:
- correct
- wrong
- warning
- misconception
- remediation
- prerequisite

## Scene editor

Provide:
- object palette
- object IDs
- timeline
- animation action selector
- semantic event selector
- narration segment binding
- canonical graph tags
- misconception markers
- Web preview
- Manim render preview

## Feedback-policy editor

Example:

```text
ROW_SUM_INVALID
  attempt 1 -> neutral feedback
  attempt 2 -> focused feedback
  attempt 3 -> diagnostic probe
  confidence >= .80 -> intervention
  remediation complete -> original interaction retry
```

## Graph inspector

For an interaction instance display:

```text
TEACHES
PRACTICES
REQUIRES
ASSESSES
CAN_REVEAL
REMEDIATES
USES_SCENE
USES_FEEDBACK_POLICY
ALIGNED_WITH VIDEO SEGMENT
```

Allow:
- Postgres graph preview
- Neo4j projected view
- diff

## CLI

Suggested:

```bash
interactions templates list
interactions templates show <key> --version 1
interactions templates validate <file>
interactions templates publish <id>

interactions controls list
interactions icons list
interactions animations list

interactions instances create <json>
interactions instances validate <id>
interactions instances preview <id>

interactions scenes create <json>
interactions scenes validate <id>
interactions scenes render-web <id>
interactions scenes render-manim <id>

interactions feedback validate <policy>
interactions evidence test-rule <rule> --event <json>

interactions graph request <scope>
interactions graph status <scope>
interactions graph verify <scope>
interactions graph diff <scope>
interactions graph rebuild --all-published
```

UI, CLI and REST use the same service layer.
