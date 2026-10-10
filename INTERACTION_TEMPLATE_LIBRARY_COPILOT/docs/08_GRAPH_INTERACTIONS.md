# 08 — Complete Neo4j Graph Interaction Changes

PostgreSQL remains canonical.
Neo4j remains rebuildable.

This template platform is part of the instructional graph, not a UI-only subsystem.

## Existing graph nodes to reuse

- Concept
- Technique
- Skill
- Misconception
- LearningItem
- MicroCourse
- MicroCourseRelease
- CourseState
- TeachingAsset
- VideoAsset
- VideoSegment
- Intervention
- Problem
- SolutionStep

Never create alternate Concept/Technique/Skill identities.

## New projected labels

```text
InteractionTemplate
InteractionTemplateVersion
InteractionInstance
ControlTemplate
IconToken
AnimationTemplate
SceneSpec
FeedbackTemplate
FeedbackPolicy
EvidenceRule
```

Recommended projection property:

```text
projection_kind = 'interaction_template'
projection_version = 'v1'
postgres_id = <canonical PostgreSQL UUID>
```

## Template structure

```text
InteractionTemplate
  -[:HAS_VERSION]->
InteractionTemplateVersion

InteractionInstance
  -[:USES_TEMPLATE_VERSION]->
InteractionTemplateVersion

CourseState
  -[:USES_INTERACTION]->
InteractionInstance
```

## Canonical instructional edges

```text
InteractionInstance -[:TEACHES]-> Concept
InteractionInstance -[:TEACHES]-> Technique

InteractionInstance -[:PRACTICES]-> Technique

InteractionInstance -[:REQUIRES]-> Concept
InteractionInstance -[:REQUIRES]-> Skill

InteractionInstance -[:ASSESSES]-> Skill

InteractionInstance -[:CAN_REVEAL]-> Misconception
InteractionInstance -[:REMEDIATES]-> Misconception
```

## Feedback / diagnosis graph

```text
InteractionInstance
  -[:USES_FEEDBACK_POLICY]->
FeedbackPolicy

FeedbackPolicy
  -[:MAY_USE]->
FeedbackTemplate

EvidenceRule
  -[:APPLIES_TO]->
InteractionTemplateVersion

EvidenceRule
  -[:EVIDENCE_FOR]->
Misconception

EvidenceRule
  -[:USES_DIAGNOSTIC]->
LearningItem

EvidenceRule
  -[:USES_FEEDBACK]->
FeedbackTemplate

Misconception
  -[:DIAGNOSED_BY]->
LearningItem

Misconception
  -[:REMEDIATED_BY]->
Intervention
```

## Animation / visualization graph

```text
InteractionInstance
  -[:USES_SCENE]->
SceneSpec

SceneSpec
  -[:USES_ANIMATION]->
AnimationTemplate

SceneSpec
  -[:EXPLAINS]->
Concept

SceneSpec
  -[:EXPLAINS]->
Technique

SceneSpec
  -[:REQUIRES]->
Skill

SceneSpec
  -[:ADDRESSES]->
Misconception

SceneSpec
  -[:ILLUSTRATES]->
LearningItem
```

## Control / icon metadata graph

Primarily for admin validation:

```text
InteractionTemplateVersion
  -[:ALLOWS_CONTROL]->
ControlTemplate

InteractionTemplateVersion
  -[:ALLOWS_ICON]->
IconToken

FeedbackTemplate
  -[:USES_ICON]->
IconToken

FeedbackTemplate
  -[:USES_ANIMATION]->
AnimationTemplate
```

## Video integration

The interaction graph must meet the micro-course/video graph:

```text
CourseState -[:USES_VIDEO]-> VideoAsset
VideoAsset -[:HAS_SEGMENT]-> VideoSegment

VideoSegment -[:EXPLAINS]-> Concept
VideoSegment -[:EXPLAINS]-> Technique
VideoSegment -[:ADDRESSES]-> Misconception

VideoSegment -[:CAN_LAUNCH]-> InteractionInstance
VideoSegment -[:CAN_LAUNCH]-> LearningItem
VideoSegment -[:CAN_LAUNCH]-> Intervention

InteractionInstance -[:ALIGNED_WITH]-> VideoSegment
SceneSpec -[:ALIGNED_WITH]-> VideoSegment
```

This supports:

```text
pause video
-> resolve approved transcript segment
-> identify canonical content
-> offer approved interaction
-> complete interaction
-> return to exact timestamp
```

## Web + Manim semantic alignment

```text
InteractionInstance -[:VISUALIZES]-> SceneSpec
TeachingAsset -[:RENDERS_SCENE]-> SceneSpec
VideoSegment -[:RENDERS_SCENE]-> SceneSpec
```

A browser interaction and a Manim video can therefore be different renderings of the
same semantic SceneSpec.

## Example — Markov

```text
CourseState MARKOV_MATRIX_EDIT
  -[:USES_INTERACTION]->
InteractionInstance MARKOV-MATRIX-01

MARKOV-MATRIX-01
  -[:TEACHES]-> PROB_MARKOV_MATRIX
  -[:REQUIRES]-> ALG_MATRIX
  -[:CAN_REVEAL]-> MC-M05
  -[:CAN_REVEAL]-> MC-M02

EvidenceRule ROW_SUM_INVALID
  -[:APPLIES_TO]-> TRANSITION_MATRIX_EDITOR_V1
  -[:EVIDENCE_FOR]-> MC-M05
  -[:USES_DIAGNOSTIC]-> LI-MARKOV-ROW-SUM-PROBE-01
  -[:USES_FEEDBACK]-> FB-MARKOV-ROW-SUM-NEUTRAL

MC-M05
  -[:REMEDIATED_BY]->
INT-MARKOV-ROW-SUM-01
```

## Example — Vieta

```text
InteractionInstance VIETA-ROOT-COEFF-01
  -[:TEACHES]-> ALG_VIETA
  -[:PRACTICES]-> VIETA_SYMSUM
  -[:CAN_REVEAL]-> VIETA-M01
  -[:CAN_REVEAL]-> VIETA-M02

SceneSpec VIETA-ROOTS-TO-COEFF
  -[:EXPLAINS]-> ALG_VIETA
  -[:USES_ANIMATION]-> ANIM_ROOTS_TO_COEFFICIENTS
```

## Example — Jensen

```text
InteractionInstance JENSEN-CHORD-01
  -[:TEACHES]-> <existing Jensen canonical node>
  -[:CAN_REVEAL]-> MIS-JENSEN-01
  -[:CAN_REVEAL]-> MIS-JENSEN-02

SceneSpec JENSEN-CONVEX-CHORD
  -[:EXPLAINS]-> <existing Jensen node>
  -[:ADDRESSES]-> MIS-JENSEN-01
  -[:USES_ANIMATION]-> ANIM_CHORD_CONVEXITY
```

## What must never be projected

Never put into shared Neo4j:

- learner interaction events
- learner misconception confidence
- learner answers
- learner course state
- hidden correct answer payloads
- raw feedback bodies when answer-bearing
- full video transcript text
- private storage paths
- raw LLM classifications
- personal learner profiles/mastery

Bad:

```text
Student -[:HAS_MISCONCEPTION]-> MC-M05
```

Do not create this shared edge.

## Projection filters

Project only:

- PUBLISHED template versions
- approved instances attached to published course releases
- approved feedback policies/templates
- approved evidence rules
- approved SceneSpecs
- approved semantic mappings
- approved canonical misconceptions

Draft authoring content can have a separate admin preview, never learner graph.

## Projection request additions

Extend `pipeline.projection_request`.

Targets:

```text
GRAPH_INTERACTION_TEMPLATES
GRAPH_INTERACTION_INSTANCES
GRAPH_SCENE_SPECS
GRAPH_FEEDBACK_RULES
```

Scopes:

```text
INTERACTION_TEMPLATE
INTERACTION_INSTANCE
SCENE_SPEC
MICRO_COURSE_RELEASE
```

## Outbox events

```text
INTERACTION_TEMPLATE_PUBLISHED
INTERACTION_INSTANCE_APPROVED
SCENE_SPEC_PUBLISHED
FEEDBACK_POLICY_PUBLISHED
EVIDENCE_RULE_APPROVED
MICRO_COURSE_INTERACTION_CHANGED
```

Do not write Neo4j inside the PostgreSQL publication transaction.

## Projector

Suggested:

```text
mathbank-graph/etl/project_interaction_templates.py
```

Ownership:

```text
projection_kind='interaction_template'
```

Prune only projector-owned metadata nodes/relationships.

Never delete canonical knowledge nodes.

## Rebuild

```bash
interactions graph rebuild --all-published
```

Algorithm:

1. query published template versions
2. query approved course-bound interaction instances
3. query approved SceneSpecs
4. query approved feedback/evidence structures
5. create graph projection evidence row
6. MERGE projector-owned nodes
7. MERGE edges to existing canonical graph nodes
8. fail on missing required canonical target
9. prune stale projector-owned nodes/edges
10. finish projection row
11. verify parity
12. nonzero exit on mismatch

## Graph verify / diff

Compare PostgreSQL expected:

- template versions
- instances
- instance semantic mappings
- feedback policies
- evidence rules
- SceneSpecs
- animation references
- video alignment edges
- course-state interaction links

against Neo4j actual.

Example diff:

```json
{
  "scope":"MARKOV-MATRIX-01",
  "missing_nodes":[],
  "missing_edges":[
    {
      "from":"InteractionInstance:...",
      "relationship":"CAN_REVEAL",
      "to":"Misconception:MC-M05"
    }
  ],
  "stale_edges":[]
}
```

## Useful graph queries

### Find interactions that can reveal a misconception

```cypher
MATCH (i:InteractionInstance)-[:CAN_REVEAL]->(m:Misconception)
WHERE m.canonical_id=$misconception_id
RETURN i
```

### Find scenes that explain a technique

```cypher
MATCH (s:SceneSpec)-[:EXPLAINS]->(t:Technique)
MATCH (s)-[:USES_ANIMATION]->(a:AnimationTemplate)
WHERE t.canonical_id=$technique_id
RETURN s,a
```

### Find remediation

```cypher
MATCH (m:Misconception)-[:REMEDIATED_BY]->(i:Intervention)
WHERE m.canonical_id=$misconception_id
RETURN i
```

### Find interaction prerequisites

```cypher
MATCH (i:InteractionInstance)-[:REQUIRES]->(s:Skill)
WHERE i.canonical_id=$interaction_id
RETURN s
```

## Runtime graph usage

Graph may support structural selection:

```text
current CourseState
-> allowed InteractionInstance
-> canonical target
-> CAN_REVEAL misconceptions
-> approved remediation structure
```

Display text, answers, event state and learner evidence still come from PostgreSQL.
