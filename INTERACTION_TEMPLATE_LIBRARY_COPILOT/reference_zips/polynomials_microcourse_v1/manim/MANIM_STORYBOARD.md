# Polynomial Manim Storyboard

All Manim material is original authored content.
Planned timestamps must be reconciled after rendering before enabling pause-and-question.

## Scene 1 — Vieta (0:00–2:10)
0:00–0:25 Factor polynomial into a_n Π(x-r_i).
0:25–0:55 Expand quadratic and visually match coefficients.
0:55–1:25 Expand cubic only far enough to identify e1,e2,e3.
1:25–1:50 General alternating-sign pattern.
1:50–2:10 Competition rule: if the target is symmetric, do not solve roots individually.

Tags: ALG_VIETA, VIETA_SUM, VIETA_PRODUCT, VIETA_SYMSUM.

## Scene 2 — Quadratic structure (0:00–2:20)
0:00–0:35 Complete-square picture / root symmetry around -b/(2a).
0:35–1:05 Discriminant controls root type.
1:05–1:35 Vieta as root shortcut.
1:35–2:20 Nested P(P(x)) strategy: solve outer P(y)=0, then P(x)=each outer root.

Tags: ALG_QUAD, ALG_VIETA.
Problem bridge: AIME_2020_I_Q14.

## Scene 3 — Cubic transformed roots (0:00–2:30)
0:00–0:40 Cubic coefficient-root map.
0:40–1:20 Replace roots a,b,c by a+b,b+c,c+a.
1:20–2:05 Compute new e1,e2,e3 using old symmetric sums.
2:05–2:30 Build transformed cubic without solving a,b,c.

Problem bridge: AIME_1996_Q05.

## Scene 4 — Biquadratic / quartic (0:00–2:20)
0:00–0:30 Distinguish general quartic from biquadratic.
0:30–1:10 Substitute y=x².
1:10–1:45 Solve y quadratic and map y->x, checking real/complex domain.
1:45–2:20 Quadratic composition creates a quartic but should be attacked structurally.

Problem bridge: AIME_2020_I_Q14.

## Scene 5 — Higher-degree strategy (0:00–3:00)
0:00–0:40 Why full expansion is often the wrong object.
0:40–1:20 Elementary symmetric sums from Vieta.
1:20–2:00 Power sums from Newton identities.
2:00–2:30 Polynomial translation x -> y+h.
2:30–3:00 Choose technique by requested invariant.

Problem bridges:
- AIME_1986_Q11
- HMMT_2003_FEB_ALG_Q07
- AIME_2019_I_Q10
