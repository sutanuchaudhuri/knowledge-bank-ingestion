# Vieta's Formulas

## Canonical mapping
- `ALG_VIETA`
- sub-techniques: `VIETA_SUM`, `VIETA_PRODUCT`, `VIETA_SYMSUM`, `VIETA_CONSTRUCT`,
  `VIETA_RECIP`, `VIETA_POWER`, `VIETA_JUMP`, `VIETA_DIRECT`.

## Prerequisites
Factorization; coefficient comparison; roots/zeros; symmetric expressions; signs.

For
P(x)=a_n x^n+a_{n-1}x^(n-1)+...+a_0
with roots r_1,...,r_n,

e_k(r_1,...,r_n)=(-1)^k a_(n-k)/a_n.

Quadratic:
r1+r2=-b/a, r1r2=c/a.

Cubic:
r1+r2+r3=-b/a,
r1r2+r1r3+r2r3=c/a,
r1r2r3=-d/a.

## Competition habits
Do not solve for roots when the target is symmetric in the roots.
Translate the desired expression into e1,e2,e3 or power sums first.

## Common misconceptions
- VIETA-M01: alternating signs forgotten.
- VIETA-M02: formulas used without dividing by leading coefficient.
- VIETA-M03: pairwise product sum confused with product of all roots.
- VIETA-M04: solving roots explicitly when a symmetric expression is enough.
- VIETA-M05: transformed-root polynomial built without recomputing new symmetric sums.

## Corpus bridges
- AMC10_2023A_Q11
- AIME_1996_Q05
- HMMT_2003_FEB_ALG_Q07
- CMM_2026_INDIV_Q11
- HMMT_2021_FEB_GUTS_Q30
