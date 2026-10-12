# 01 — Architecture

## Core rule

The current HTML and Manim implementations are reference examples, not the platform model.

The platform must separate:

```text
MATHEMATICAL CONTENT
INTERACTION MECHANICS
ANIMATION MECHANICS
FEEDBACK
MISCONCEPTION DIAGNOSIS
GRAPH SEMANTICS
```

## Course-author responsibilities

The author chooses:

- learning objective
- canonical Concept/Technique/Skill bindings
- parameter ranges/defaults
- mathematical formulas
- answer/evaluation criteria
- likely misconceptions
- approved diagnostic items
- approved feedback
- approved remediation
- animation content objects
- course-state transitions

## Platform responsibilities

The platform controls:

- slider/button/matrix/drag/timeline behavior
- semantic icon vocabulary
- interaction event schema
- deterministic evaluation pipeline
- partial-correctness behavior
- evidence accumulation
- feedback ladder
- accessibility
- reduced motion
- SceneSpec execution
- Web renderer
- Manim adapter
- graph projection
- validation
- versioning

## Reuse existing MathBank objects

Do not duplicate:

- `knowledge.concept`
- `knowledge.technique`
- `knowledge.skill`
- `knowledge.misconception`
- `pedagogy.learning_item`
- `pedagogy.intervention_script`
- `activity.definition`
- `visual.asset`
- `visual.widget_spec`
- `pedagogy.micro_course*`
- `pipeline.*`
- existing Neo4j canonical nodes

## Versioning

Every published interaction pins:

```text
interaction_template_version
feedback_policy_version
scene_spec_version
icon/control catalog compatibility
```

Published course releases must never float to `latest`.

## No hidden pedagogy in JavaScript

Bad:

```javascript
if (sum(row) != 1) {
  flashRed();
}
```

Required semantic behavior:

```text
semantic_action = SET_TRANSITION_ROW
evaluation = ERROR
error_signature = ROW_SUM_INVALID
evidence rule -> MC-M05
feedback -> FB-MARKOV-ROW-SUM-01
```

The renderer may flash/highlight visually, but the meaning exists in canonical data.

## Error ≠ misconception

Required process:

```text
error observation
-> evidence
-> repetition/probe
-> confidence
-> confirmed misconception
-> remediation
```

## Shared semantic animation language

Target:

```text
SceneSpec
   ├── WebAnimationRenderer
   └── ManimRenderer
```

Routine course animations should not require separate hand-written logic for the two renderers.

## Accessibility is template-level

Each published template must define:

- keyboard behavior
- focus behavior
- accessible labels
- non-color feedback
- touch targets
- reduced-motion fallback
- screen-reader descriptions
