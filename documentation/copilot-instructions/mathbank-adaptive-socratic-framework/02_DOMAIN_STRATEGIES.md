# 02 — Domain-specific Socratic strategy system

## Hierarchy
Universal contract (attempt before strategic reveal; legitimate explicit reveal allowed; current-step disclosure; verified explanation; transfer) → domain playbook → subdomain technique strategy → bound release-specific discoveries. One problem may compose multiple versions (`PRIMARY`, `SUPPORT`, `REMEDIATION`, `TRANSFER`) with nested return stack; require reviewer-mapped claims and prerequisite gates.

## Seed catalog and characteristic inquiry
| Domain | Technique seeds | Discovery pattern |
|---|---|---|
| Arithmetic | place value, ratios, estimation | concrete representation → estimate → operations → plausibility |
| Algebra | Vieta, inequality, functional equations, recurrence | recognize structure → test transformations → equivalence → exclude extraneous cases |
| Combinatorics | stars and bars, PIE, graph invariants, double counting, pigeonhole, bijections | enumerate small cases → encode objects → counting invariant → generalize |
| Probability | conditioning, Bayes, independence, expectation, Markov | experiment/sample space → condition → quantify → sanity check |
| Number theory | modular arithmetic, divisibility, valuations, Diophantine | examples/residues → conjecture → necessary vs sufficient → proof/counterexample |
| Complex numbers | argument/modulus, roots of unity, complex geometry | move algebra ↔ plane → symmetry/rotation → exact derivation |
| Planar geometry | loci, construction, power of point, inversion | observe → conjecture locus → construct → necessity/converse → degenerate cases |
| Solid geometry | slices, projection, 3D distance, volume | manipulate 3D → cross-section → metric invariant → compute/verify |

## Strategy version data contract
`strategy_code`, `domain_code`, `parent_strategy_version_id?`, `semantic_bindings[]` (canonical IDs), `phases[]` with `objective`, `discovery_prompt_policy`, `allowed_assessment_kinds`, `allowed_interaction_templates`, `hint_policy`, `misconception_probes`, `success_evidence`, `fallback`, `transfer`, `source_refs`, `review_hash`.

## Composition constraints
A nested strategy has a max depth/time/event budget and return-to-claim binding; no endless remediation loops. Alternative routes join only on approved equivalence/claim validation; name or embedding similarity never suffices. No hard rule of fixed number of quizzes; require diverse reasoning evidence by stage.

## Reference fixtures
- Constructions 8.1: chord/center → perpendicular bisectors → constrained loci → intersection → verification; strategic figures initially hidden.
- Loci 7.3: two genuinely interactive lines; test both necessity and sufficiency.
- Stars & Bars: objects/boxes → separators → bijection → positive counts → bounded-variable PIE bridge.
- PIE: universe → overlapping forbidden sets → duplicate counts → alternating inclusion/exclusion.
- Conditional probability: explicit sample space/condition → updated denominator → independence probe → transfer.
- Complex roots of unity: plane symmetry → rotation → cancellation → algebraic identity.
Each fixture must include source provenance, valid alternative answer, hint H1–H5, misconception probe, no-leak test and transfer problem.
