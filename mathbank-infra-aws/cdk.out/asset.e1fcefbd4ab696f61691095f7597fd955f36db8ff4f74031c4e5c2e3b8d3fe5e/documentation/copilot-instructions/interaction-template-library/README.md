# Interaction Template Library — Complete Copilot Pack

This ZIP is the implementation contract for converting MathBank's current one-off
interactive teaching artifacts into a reusable interaction/animation/feedback platform.

It contains the actual prior reference implementations for:

- Inequalities: AM-GM, Weighted AM-GM, Cauchy-Schwarz, Jensen, Muirhead
- Polynomials: Vieta, Quadratic, Cubic, Biquadratic/Quartic, Higher Polynomial
- Markov chains: state compression, recurrence, absorbing hitting, stationarity

It also contains:

- PostgreSQL schema requirements
- reusable interaction template catalog
- controls + semantic icons
- SceneSpec for Web + Manim
- deterministic semantic events
- feedback ladder
- misconception evidence rules
- prerequisite-gap handling
- admin UI + CLI requirements
- REST contracts
- COMPLETE Neo4j graph interaction changes
- projection targets/outbox/rebuild/verify/diff
- templated examples for all three domains
- end-to-end flows
- JSON schemas
- seed catalogs
- validation/tests
- master Copilot prompt

## Start

Read `00_INDEX.md`.

## Central rule

```text
Course content
+ InteractionTemplateVersion
+ InstanceConfig
+ Graph Bindings
+ FeedbackPolicy
+ EvidenceRules
+ SceneSpec
= Published Interaction
```

## Graph rule

PostgreSQL is canonical.
Neo4j is derived and rebuildable.

The template system participates in the instructional graph, for example:

```text
CourseState -[:USES_INTERACTION]-> InteractionInstance
InteractionInstance -[:TEACHES]-> Concept
InteractionInstance -[:CAN_REVEAL]-> Misconception
EvidenceRule -[:EVIDENCE_FOR]-> Misconception
SceneSpec -[:EXPLAINS]-> Technique
VideoSegment -[:CAN_LAUNCH]-> InteractionInstance
```

Learner-specific interaction events and misconception confidence never go into shared Neo4j.

## Important

The bundled original HTML and Manim files are regression references.
Do not use iframe wrapping or opaque Manim execution as the final architecture.
