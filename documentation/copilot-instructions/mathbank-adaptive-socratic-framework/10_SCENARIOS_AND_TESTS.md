# 10 — End-to-end scenarios and acceptance test matrix

Every fixture has: source problem/solution and permission; expected route/version; approved graph/quiz/visual refs; student starting context; candidate edges; correct and incorrect responses; authorized resulting node; hidden-data checks; idempotency; trace; human reviewer signature.

## Scenarios
S01 Construct 8.1: progressive chord/center constraints; strategic perpendicular bisector not shown pre-attempt; wrong conjecture H1 then H2; explicit reveal marks assistance; alternative correct construction only through approved claim equivalence.
S02 Loci 7.3: drag both lines; verify invariant and necessity/sufficiency; degenerate/counterexample branch; return to original.
S03 Stars & Bars: concrete object distribution → bijection MCQ → free form formula; correct total/invalid bijection triggers justification mini-lesson; positive vs nonnegative transfer.
S04 PIE: small overlapping sets; detect overcount; false sign pattern on 3-set case; structured AR explanation; appropriate remediation.
S05 Graph theory: identify degree-sum invariant via tiny graphs; wrong parity conjecture → counterexample; proof/transfer.
S06 Conditional probability: denominator after conditioning; independence confusion triggers sample-space visualization; approved return.
S07 Complex roots of unity: plane rotation → cancellation → algebraic formula; branch to geometry strategy and back.
S08 Solid geometry: interactive cross-section vs static accessible alternate; valid solution despite different orientation.
S09 Number theory: residue conjecture true in examples but false generally; counterexample before proof.
S10 Assertion–Reason: five distinct AR1–AR5 mathematically validated fixtures; separate A/R/explanation judgments retained and feedback correct.
S11 Free form: correct alternative wording/symbolic equivalence accepted when verified; ambiguous unsupported response prompts clarification, not random wrong mark.
S12 Independent learner: shortcuts and hints allowed; independent success separate from helped success; transfer required.
S13 Student interrupts/resumes days later pinned to release; new published version does not silently replace.
S14 Simultaneous duplicate submissions; CAS + idempotent award one decision/event.
S15 Bedrock output invalid/timeout; safe approved fallback with audit. Candidate ID not in allowlist rejected.
S16 Draft publish with missing human mathematical review blocked even if AI and structural critics pass.
S17 Split/merge/reorder draft; preserve history and rewrite dependencies; published version unaffected.
S18 Shared graph rebuilding while unavailable; projector only owns `socratic_workflow`, never deletes canonical/private data.
S19 MCP nonowner attempts private learner lookup denied; student tool cannot request future hint or raw solution.
S20 Accessibility: keyboard geometry alternative, AR quiz screen reader, reduced motion, no visual-only correctness.
S21 Failure after Step Functions invocation but before acknowledgment: retry reconciles execution/outbox idempotently, no duplicate transition.
S22 Cost cap / region unsupported AgentCore harness: alternate verified SDK integration or pause; no unauthorized model fallback.

## Test levels
Unit: schema validations; graph reachability; rule precedence; AR evaluator; H1–H5 leak detection; numerical/symbolic/geometry checker. Contract: REST/OpenAPI/MCP schemas and scope. DB: FK immutability, CAS, idempotency, outbox and projection rollback. Integration: Step Functions Local/mocks or test account, Bedrock stub vs opted-in paid runs. E2E: real preview parity and 22 scenarios, with no unnecessary model calls. Security: dynamic property scanning of all pre-answer payloads, injection/secret tests and project-owned graph deletion boundary. Quality: baseline vs revised lesson outcomes, human SME approval; no unsupported claims of improved learning from simulations alone.

## Required CI gates
No migration without catalog audit; no publication with draft asset; no agent output can authorize itself; no correct key before submit; no private learner edges in Neo4j; no unbounded cycles; no undocumented MCP write; no mark COMPLETE without actual run evidence. Paid integration tests opt-in, cost-cap tagged.
