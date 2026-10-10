# 10 — Refactor the Three Existing Interaction Libraries

The actual original artifacts are included under `examples/*/original`.
They are regression references.

Do not replace them until templated parity tests pass.

## Inequalities

Original:
`examples/inequalities/original/artifacts/inequality_lab.html`

### AM-GM

Target:
`SLIDER_COMPARE_V1`

Inputs:
- a
- b

Computed:
- AM
- GM
- gap

Possible error/diagnostic signatures:
- DOMAIN_INVALID
- EQUALITY_CONDITION_ERROR

### Weighted AM-GM

Target:
`SLIDER_COMPARE_V1`

Additional:
- lambda probability slider
- weight/exponent binding

Signatures:
- WEIGHTS_NOT_NORMALIZED
- EXPONENT_WEIGHT_MISMATCH

### Cauchy-Schwarz

Target:
`VECTOR_EXPLORER_V1`

Signatures:
- PROPORTIONALITY_EQUALITY_ERROR
- DOT_PRODUCT_SETUP_ERROR

### Jensen

Target:
`FUNCTION_GRAPH_EXPLORER_V1`

Signatures:
- CONVEX_DIRECTION_REVERSED
- CONCAVE_DIRECTION_REVERSED
- DOMAIN_INVALID

### Muirhead

Target:
`MAJORIZATION_EXPLORER_V1`

Signatures:
- NOT_SYMMETRIC
- DEGREE_MISMATCH
- MAJORIZATION_PARTIAL_SUM_ERROR
- NORMALIZATION_MULTIPLICITY_ERROR

---

## Polynomials

Original:
`examples/polynomials/original/artifacts/polynomial_lab.html`

### Vieta

Target:
`POLYNOMIAL_ROOT_COEFFICIENT_EXPLORER_V1`

Signatures:
- VIETA_ALTERNATING_SIGN_ERROR
- LEADING_COEFFICIENT_IGNORED
- PAIRWISE_SUM_PRODUCT_CONFUSION

### Quadratic

Target:
`PARAMETER_EXPLORER_V1`

Signatures:
- DISCRIMINANT_SIGN_ERROR
- REPEATED_ROOT_ERROR

### Cubic transformed roots

Target:
`SYMMETRIC_SUM_EXPLORER_V1`

Signatures:
- TRANSFORMED_ROOT_SUM_ERROR
- TRANSFORMED_ROOT_PAIRWISE_ERROR
- TRANSFORMED_ROOT_PRODUCT_ERROR

### Biquadratic

Target:
`SUBSTITUTION_PIPELINE_V1`

Signatures:
- ODD_POWER_PRESENT
- INVALID_X2_SUBSTITUTION
- BACK_SUBSTITUTION_DOMAIN_ERROR

### Higher polynomial

Target:
`STEP_THROUGH_DERIVATION_V1` / `SYMMETRIC_SUM_EXPLORER_V1`

Signatures:
- POWER_SUM_SYMMETRIC_SUM_CONFUSION
- NEWTON_IDENTITY_SIGN_ERROR

---

## Markov

Original:
`examples/markov/original/artifacts/markov_lab.html`

### AMC two-state model

Target:
`STATE_GRAPH_EXPLORER_V1`

Signatures:
- STATE_TOO_COARSE
- STATE_TOO_FINE
- INVALID_SYMMETRY_MERGE

### Triangle bug

Target:
`RECURRENCE_EXPLORER_V1`

Signatures:
- FIRST_STEP_RECURRENCE_ERROR
- FIXED_POINT_ERROR

### Absorbing frog

Target:
`STATE_GRAPH_EXPLORER_V1` + `STEP_THROUGH_DERIVATION_V1`

Signatures:
- ABSORBING_BOUNDARY_ERROR
- FAILURE_STATE_OMITTED
- HITTING_RECURRENCE_ERROR

### Stationary explorer

Target:
`TRANSITION_MATRIX_EDITOR_V1` + `PARAMETER_EXPLORER_V1`

Signatures:
- ROW_SUM_INVALID
- ROW_COLUMN_CONVENTION
- STATIONARY_EQUATION_ERROR
- CONVERGENCE_CONFUSION
- ELEMENTWISE_MATRIX_POWER

---

## Manim refactor

Existing Python files remain references.

Extract into SceneSpec:
- objects
- semantic IDs
- timeline
- narration
- canonical tags
- misconception/counterexample markers

Do not merely call the old Python file as a black box.

---

## Migration phases

### Phase 1
Create templated instances and prove numerical parity.

### Phase 2
Add semantic events/evaluation.

### Phase 3
Add evidence/feedback/remediation.

### Phase 4
Extract SceneSpecs and Web/Manim parity.

### Phase 5
Switch course state references to new instances.

Keep old artifacts disabled but available for rollback until acceptance tests pass.
