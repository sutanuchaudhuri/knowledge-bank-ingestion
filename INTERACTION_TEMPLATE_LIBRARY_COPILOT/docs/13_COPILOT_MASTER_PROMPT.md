# 13 — Master Copilot Instructions

You are extending the existing MathBank repository.

## Mission

Build a reusable interaction, animation, feedback, misconception and graph platform by
refactoring the bundled inequality, polynomial and Markov prototypes.

Implement every item in this pack.

## Mandatory components

1. interaction template registry
2. immutable template versions
3. control templates
4. semantic icon registry
5. interaction instances
6. animation templates
7. SceneSpec
8. Web SceneSpec renderer
9. Manim SceneSpec adapter
10. semantic event schema
11. deterministic evaluation
12. partial correctness
13. feedback templates
14. feedback policies
15. misconception evidence rules
16. learner misconception evidence
17. diagnostic probes
18. fixed remediation
19. accessibility / reduced motion
20. admin UI
21. CLI
22. REST/service layer
23. complete Neo4j projection
24. graph rebuild/verify/diff
25. refactor of all three existing artifacts
26. regression and graph parity tests

## Before editing

Inspect:
- current latest migration
- visual schema
- pedagogy schema
- learner schema
- micro-course schema
- graph projectors
- pipeline projection/outbox schema
- existing canonical Concept/Technique/Skill/Misconception IDs

Do not modify old migrations.

## Graph is mandatory

Implement all nodes and edges in `08_GRAPH_INTERACTIONS.md`.

At minimum:

```text
CourseState -> USES_INTERACTION -> InteractionInstance

InteractionInstance -> TEACHES -> Concept/Technique
InteractionInstance -> PRACTICES -> Technique
InteractionInstance -> REQUIRES -> Concept/Skill
InteractionInstance -> ASSESSES -> Skill
InteractionInstance -> CAN_REVEAL -> Misconception
InteractionInstance -> REMEDIATES -> Misconception

EvidenceRule -> APPLIES_TO -> InteractionTemplateVersion
EvidenceRule -> EVIDENCE_FOR -> Misconception
EvidenceRule -> USES_DIAGNOSTIC -> LearningItem
EvidenceRule -> USES_FEEDBACK -> FeedbackTemplate

InteractionInstance -> USES_SCENE -> SceneSpec
SceneSpec -> USES_ANIMATION -> AnimationTemplate
SceneSpec -> EXPLAINS -> Concept/Technique
SceneSpec -> ADDRESSES -> Misconception

VideoSegment -> CAN_LAUNCH -> InteractionInstance
VideoSegment -> ALIGNED_WITH -> InteractionInstance
SceneSpec -> ALIGNED_WITH -> VideoSegment
```

Never put learner evidence in shared Neo4j.

## Refactor requirement

Do not wrap original HTML in iframes.
Do not leave one-off JavaScript as the final architecture.
Do not call old Manim files as opaque final renderers.

Extract:
- interaction configs
- semantic events
- evaluation signatures
- graph bindings
- feedback policies
- evidence rules
- SceneSpecs

## Runtime LLM boundary

LLM may:
- rephrase approved feedback
- explain approved context
- classify open text among enumerated candidates

LLM may not:
- create controls
- choose arbitrary icons
- generate animation actions
- invent misconceptions
- alter evidence
- skip probes
- create remediation
- alter graph
- alter correctness

## Evidence requirement

One wrong answer normally creates only evidence.

Implement:
- confidence updates
- probes
- confirmed threshold
- remediation
- resolution
- recurrence

## Object-specific feedback

Feedback must identify the exact:
- matrix row
- state/transition
- equation term
- graph point/vector
- substitution step
- parameter condition

when available.

## Accessibility

All template versions need:
- keyboard support
- focus semantics
- screen-reader labels
- non-color feedback
- reduced motion
- touch accessibility

## Graph operations

Implement:

```bash
interactions graph rebuild --all-published
interactions graph verify <scope>
interactions graph diff <scope>
```

Do not delete unrelated graph content.

## Implementation order

1. schema migration
2. initial catalogs/seeds
3. validators
4. service layer
5. runtime engine
6. event/evaluation system
7. evidence engine
8. feedback engine
9. SceneSpec engine
10. Web renderer
11. Manim adapter
12. admin APIs
13. admin UI
14. CLI
15. graph projector
16. outbox/projection integration
17. graph verifier
18. refactor inequality examples
19. refactor polynomial examples
20. refactor Markov examples
21. tests
22. docs/OpenAPI

## Definition of done

Not complete until:
- all three old artifacts have templated replacements
- mathematical parity passes
- semantic event tests pass
- misconception evidence works
- feedback is object-specific
- Web/Manim semantic parity passes
- graph relationships project
- graph rebuild is idempotent
- learner evidence is absent from shared graph
- accessibility checks pass
- no existing MathBank regression
