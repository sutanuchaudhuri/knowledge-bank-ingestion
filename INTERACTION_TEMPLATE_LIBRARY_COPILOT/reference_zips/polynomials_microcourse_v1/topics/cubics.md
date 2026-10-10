# Cubic Polynomials

## Canonical mapping
No separate cubic canonical node currently exists in the corpus.
Map this course module to:
- `ALG_POLY`
- `ALG_VIETA`
- `VIETA_SYMSUM`
- `VIETA_CONSTRUCT`
as appropriate.

Do not create `ALG_CUBIC` implicitly.

## Prerequisites
Quadratics; factoring; factor theorem; Vieta; symmetric sums.

For x^3+Ax^2+Bx+C with roots a,b,c:
a+b+c=-A
ab+bc+ca=B
abc=-C.

## High-value competition technique
When a problem gives transformed roots such as
a+b, b+c, c+a,
compute their elementary symmetric sums rather than solving for a,b,c.

Example structure:
new root sum = 2(a+b+c).
new root product = (a+b)(b+c)(c+a),
which can be rewritten using elementary symmetric sums.

## Misconceptions
- CUBIC-M01: sign of abc is wrong.
- CUBIC-M02: assumes every cubic factors nicely over integers.
- CUBIC-M03: ignores known root/factor theorem before using formulas.
- CUBIC-M04: expands transformed-root products without using symmetric identities.

## Corpus bridge
- AIME_1996_Q05 — explicit cubic-to-cubic transformed roots.
