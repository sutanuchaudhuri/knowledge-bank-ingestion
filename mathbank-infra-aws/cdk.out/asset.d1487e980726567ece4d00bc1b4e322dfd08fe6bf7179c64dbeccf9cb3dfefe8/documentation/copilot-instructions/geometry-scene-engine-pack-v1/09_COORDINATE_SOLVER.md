# Coordinate Solver

Use symbolic construction where practical and deterministic/seeded numeric constraints otherwise.

Objective:

\[
L =
w_1L_{\text{constraint}}
+w_2L_{\text{degeneracy}}
+w_3L_{\text{label}}
+w_4L_{\text{viewport}}
+w_5L_{\text{clarity}}
\]

Penalize:
- violated relations,
- coincident points,
- tiny important segments,
- near-degenerate angles,
- unnecessary crossings,
- off-screen labels.

Same state + same seed should yield reproducible or acceptably stable results.
