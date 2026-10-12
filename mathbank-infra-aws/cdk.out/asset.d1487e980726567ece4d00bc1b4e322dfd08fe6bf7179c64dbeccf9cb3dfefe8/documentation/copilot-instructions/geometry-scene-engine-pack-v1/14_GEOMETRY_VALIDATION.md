# Geometry Validation

## Mathematical validator

Checks:
- collinearity,
- concyclicity,
- equal lengths,
- parallel/perpendicular,
- midpoint,
- tangent,
- circumcenter,
- convexity,
- incidence.

## Visual validator

Checks:
- label collisions,
- clipped labels,
- short segments,
- angle-mark collisions,
- excessive circle prominence,
- invisible contact points,
- confusing line styles,
- invalid overlay references.

## Leakage validator

Fail if rendering asserts a `TARGET_TO_PROVE` or `UNKNOWN` relation.

Examples:
- target collinearity shown straight,
- target perpendicularity shown with right-angle mark,
- target equal lengths shown with ticks,
- target cyclicity shown with circle before established.
