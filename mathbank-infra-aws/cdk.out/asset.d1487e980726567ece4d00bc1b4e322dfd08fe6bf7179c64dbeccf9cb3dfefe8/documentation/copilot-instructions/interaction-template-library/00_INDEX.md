# MathBank Interaction + Animation Template Library — Copilot Implementation Pack

## Purpose

Refactor the three current reference implementations — inequalities, polynomials, and
Markov chains — into a reusable platform for:

- interaction templates
- versioned controls
- semantic icon tokens
- animation templates
- declarative SceneSpecs
- shared Web/Manim semantics
- deterministic evaluation
- object-specific UI feedback
- misconception evidence accumulation
- fixed diagnostics
- fixed remediation
- learner event capture
- graph projection and graph-driven instructional relationships
- admin UI/CLI
- validation and parity tests

## Existing reference implementations included

- `examples/inequalities/original/`
- `examples/polynomials/original/`
- `examples/markov/original/`

The original ZIPs are also preserved in `reference_zips/`.

## Read order

1. `docs/01_ARCHITECTURE.md`
2. `docs/02_POSTGRES_SCHEMA.md`
3. `docs/03_TEMPLATE_CATALOG.md`
4. `docs/04_INTERACTION_RUNTIME.md`
5. `docs/05_ANIMATION_SCENESPEC.md`
6. `docs/06_FEEDBACK_MISCONCEPTIONS.md`
7. `docs/07_ADMIN_UI_CLI.md`
8. `docs/08_GRAPH_INTERACTIONS.md`
9. `docs/09_API_CONTRACTS.md`
10. `docs/10_REFACTOR_THREE_EXAMPLES.md`
11. `docs/11_EXAMPLE_FLOWS.md`
12. `docs/12_VALIDATION_TESTS.md`
13. `docs/13_COPILOT_MASTER_PROMPT.md`

## Target architecture

```text
CourseState
   |
   +--> InteractionInstance
           |
           +--> InteractionTemplateVersion
           +--> Controls
           +--> Semantic Graph Bindings
           +--> FeedbackPolicy
           +--> EvidenceRules
           +--> SceneSpec
           +--> Fixed Interventions
```

At runtime:

```text
Learner Action
  -> Semantic Event
  -> Deterministic Evaluation
  -> Error Signature
  -> Evidence Update
  -> Feedback / Probe / Intervention
  -> Retry / Continue
```

## Non-negotiable

A wrong answer is not automatically a misconception.

The shared Neo4j graph contains canonical instructional structure.
Learner-specific evidence remains private in PostgreSQL.

The LLM is a constrained conversational layer, not the interaction engine.
