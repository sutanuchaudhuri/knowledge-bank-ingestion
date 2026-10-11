# Biquadratic and Quartic Structure

## Canonical mapping
The current corpus has no dedicated `BIQUADRATIC` or `QUARTIC` canonical node.
Map this module to `ALG_POLY` and, where applicable, `ALG_QUAD`/Vieta techniques.
Do not silently create new taxonomy nodes.

## Biquadratic form
A x^4+B x^2+C=0.

Set y=x^2:
A y^2+B y+C=0.

Then map each admissible y back:
- y>0 -> x=±sqrt(y) over reals.
- y=0 -> x=0.
- y<0 -> no real x, but two complex x roots.

## General quartic
A general quartic contains x^3 and x terms and does not reduce to y=x^2.
Competition problems more often exploit factorization, reciprocal symmetry,
composition, or a clever substitution than Ferrari's general formula.

## Composition bridge
If P is quadratic, P(P(x)) is degree four.
AIME_2020_I_Q14 is an excellent structural example:
work from the roots of the outer P rather than expanding the quartic first.

## Misconceptions
- QUARTIC-M01: every quartic called "biquadratic."
- QUARTIC-M02: y=x^2 substitution used when odd powers are present.
- QUARTIC-M03: negative y roots discarded even when complex roots matter.
- QUARTIC-M04: quartic composition expanded before exploiting nested structure.

## Corpus bridge
- AIME_2020_I_Q14 — quartic arising from composition of a quadratic.
