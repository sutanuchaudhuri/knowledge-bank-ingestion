# 12 — Validation and Tests

## Template validation

Reject if:
- invalid JSON schemas
- unknown control
- icon outside allowed set
- undeclared semantic action
- undeclared diagnostic signature
- animation without reduced-motion fallback
- missing accessibility semantics
- arbitrary executable code in config

## Instance validation

Reject if:
- template version not published
- config fails schema
- unresolved canonical graph ID
- missing success criteria
- unapproved feedback policy
- misconception mapping references unsupported error signature
- required diagnostic not approved
- required intervention not approved
- scene not approved
- hidden answer payload would be projected

## Scene validation

Reject if:
- duplicate object IDs
- timeline references unknown object
- unsupported action
- invalid timeline ordering
- unresolved canonical tags
- missing reduced-motion behavior
- Web/Manim adapter does not support required object/action

## Feedback validation

Reject if:
- first ordinary error instantly confirms misconception without policy exception
- evidence weight invalid
- probe required but absent
- remediation required but absent
- early feedback leaks answer
- icon conflicts with feedback semantic type

## Graph validation

Reject/flag:
- canonical target missing
- draft instance connected to published CourseState
- evidence rule points to absent misconception
- learner evidence node appears in shared graph
- raw answer body projected
- stale template version edge
- unapproved SceneSpec projected

## Golden tests

### Jensen
wrong direction -> evidence -> probe -> chord remediation -> retry.

### Vieta
partial E1/E2/E3 -> preserve correct pieces -> focus error -> remediation.

### Markov
row total 1.2 -> exact row + graph edges -> evidence -> probe -> remediation -> retry.

## Cross-renderer parity

For each SceneSpec:
- same semantic objects
- same canonical tags
- same semantic events
- same narration bindings

No requirement for pixel-perfect rendering.

## Regression against bundled originals

For the three original HTML artifacts compare:
- initial values
- parameter ranges
- formulas
- computed outputs

Templated runtime must match mathematical behavior before replacing originals.

## Graph tests

- template graph projection idempotent
- instance semantic edges resolve to existing canonical IDs
- learner evidence absent
- answer-bearing data absent
- graph rebuild prunes only `projection_kind='interaction_template'`
- graph diff catches a missing `CAN_REVEAL` edge
- video alignment edge projects
- course-state interaction edge projects
