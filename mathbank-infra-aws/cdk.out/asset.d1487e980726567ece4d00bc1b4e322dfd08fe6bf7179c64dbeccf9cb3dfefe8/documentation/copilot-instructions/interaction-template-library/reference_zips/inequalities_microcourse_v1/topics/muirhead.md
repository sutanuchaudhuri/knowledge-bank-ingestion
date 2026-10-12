# Muirhead's Inequality

Prerequisites: AM-GM/Weighted AM-GM, symmetric polynomials, homogeneous expressions,
exponent tuples, permutations, majorization.

Use normalized symmetric-mean notation:
[a1,...,an] = (1/n!) times the sum over every permutation of
x_(sigma1)^a1 ... x_(sigman)^an.

Majorization:
sort alpha and beta decreasingly.
alpha majorizes beta if every partial sum through k<n is at least as large,
and total sums are equal.

Muirhead:
if alpha majorizes beta, then [alpha] >= [beta] for positive variables.

Example:
(3,0,0) majorizes (2,1,0) majorizes (1,1,1).

Recognition checklist:
1. symmetric?
2. homogeneous?
3. same total degree?
4. expressible as normalized symmetric sums?
5. exponent tuples comparable by majorization?

Misconceptions:
- MIS-MUIR-01: using Muirhead on cyclic but non-symmetric expressions.
- MIS-MUIR-02: total degrees differ.
- MIS-MUIR-03: exponent tuples not sorted before comparison.
- MIS-MUIR-04: raw symmetric-sum coefficient/multiplicity mismatch.
- MIS-MUIR-05: treating Muirhead as a black box instead of translating to AM-GM when needed.

YouTube anchor: starts 02:31:16; end must be filled after metadata/transcript import.
https://www.youtube.com/watch?v=CPlSjinOpFo

Wikipedia:
https://en.wikipedia.org/wiki/Muirhead%27s_inequality
https://en.wikipedia.org/wiki/Majorization
