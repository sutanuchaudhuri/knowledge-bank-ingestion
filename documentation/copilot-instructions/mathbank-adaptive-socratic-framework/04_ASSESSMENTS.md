# 04 — Mixed assessment contracts and secure evaluation

## Supported question kinds
SINGLE_CHOICE, MULTI_SELECT, NUMERIC_EXACT, NUMERIC_TOLERANCE, SYMBOLIC, FREE_FORM_REASONING, ASSERTION_REASON, ERROR_IDENTIFY, COUNTEREXAMPLE, ORDERING, MATCHING, PREDICTION, GEOMETRY_INTERACTION, TRANSFER. Each contains `purpose` (ORIENTATION, DISCOVERY, JUSTIFICATION, DIAGNOSTIC, PRACTICE, TRANSFER), `skill_bindings`, rubric, retry/hint/reveal and deterministic or approved rubric-assisted evaluator.

## Assertion–Reason classification
AR1 A true R true and R adequately explains A; AR2 A true R true but R is not explanation; AR3 A true R false; AR4 A false R true; AR5 both false. Store and evaluate independent A truth, R truth and entailment judgment; AR2 requires a mathematically sound distinction between mere association and justification. Differentiate answer accuracy from reasoning validity and independence/hint use. Each variant needs a golden fixture.

## Public/private separation
Before submission: activity ID/version, prompt, safe options, response contract, current visual. Never send `correct_values`, scoring predicates, hidden error signature mappings, answers/solution, answer-bearing alt text, future stages. On server: key, symbolic predicate, rubric, permitted equivalences, feedback variants and threshold policy. After submission: bounded verdict, approved feedback, next permitted action; partial scoring withhold future step results.

## Evaluation routing
- Choice, multiple select, ordering, matching and numeric: deterministic exact/tolerance-aware evaluation.
- Symbolic: normalization and equivalence checking with explicit domain constraints and exceptional cases; abstain if unsupported rather than hallucinate proof.
- Geometry: structured semantic action → geometry engine's deterministic constraints; image model only interpretation/proposal, not mathematical ground truth.
- Open reasoning: Bedrock may classify against approved rubric/candidate signatures and cite response spans, output `SUPPORTED|PARTIAL|UNCERTAIN`; uncertain triggers clarified question or human review. No automatic mastery certification from free text.
- One wrong answer generates tentative evidence, not a diagnosed misconception; use approved probe and accumulation before remediation. Private learner events and evidence in SQL.

## Example policy
At each discovery stage use at least one meaningful attempt, use a varied question mix rather than arbitrary quotas, include at least one justification and one transfer checkpoint per release. `Reveal answer` allowed explicitly; record assisted path separately from independent success; no punitive gamification for hints.
