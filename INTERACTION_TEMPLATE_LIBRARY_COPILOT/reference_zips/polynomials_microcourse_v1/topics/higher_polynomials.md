# Higher-Degree Polynomials

## Canonical mapping
- `ALG_POLY`
- `ALG_VIETA`
- `VIETA_SYMSUM`
- `VIETA_POWER`
- `VIETA_CONSTRUCT`
- `VIETA_RECIP` where relevant.

## Prerequisites
Vieta; factor/remainder theorem; binomial theorem; complex roots; symmetric sums.

## Core techniques
1. Coefficient extraction without full expansion.
2. Elementary symmetric sums.
3. Newton identities / power-sum recurrences.
4. Translation x -> y+h.
5. Reciprocal or transformed roots.
6. Factor theorem and known-root stripping.
7. Functional identities that force many roots or factors.

## Newton identities
For monic polynomial with elementary symmetric sums e_k and power sums p_k:
p1=e1
p2=e1 p1-2e2
p3=e1 p2-e2 p1+3e3
and so on.

## Competition examples
- AIME_1986_Q11: translate a degree-17 alternating polynomial from x to y=x+1.
- AIME_2016_I_Q11: polynomial functional equation.
- AIME_2019_I_Q10: degree-2019 root multiplicities and symmetric coefficient extraction.
- HMMT_2003_FEB_ALG_Q07: power sums / Newton-style manipulation.
- CMM_2026_INDIV_Q11: elementary symmetric sums.

## Misconceptions
- HPOLY-M01: assuming degree-n means n distinct real roots.
- HPOLY-M02: expanding huge products when only one coefficient is needed.
- HPOLY-M03: confusing elementary symmetric sums with power sums.
- HPOLY-M04: applying a recurrence before identifying its characteristic/root data.
- HPOLY-M05: treating a transformed-root polynomial as if coefficients transform termwise.
