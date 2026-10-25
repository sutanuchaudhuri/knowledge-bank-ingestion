# 07 — Agentic actors, MCP tools and bounded orchestration

## Logical agent roles
1. Authoring Planner: proposes domain strategy/educational nodes/branches using canonical context.
2. Assessment Designer: proposes mixed quiz items, AR1–AR5, rubric and plausible misconception distractors as draft only.
3. Mathematical Critic: checks candidate against source, symbolic/tool checks and counterexamples; may abstain, cannot certify.
4. Disclosure Auditor: examines text/options/hints/diagram state/alt text/API payload for premature answer leakage.
5. Student Simulator: runs authorized student API for strong/novice/guessing/alternative-solution paths; evaluates coverage only.
6. Next-Step Agent: selects from provided eligible approved destinations with evidence citations and reason code; cannot generate new route or mutate mastery.
7. Tutor Conversational Agent: interprets student questions within current node and approved hint limits; never accesses future solution as public tool result.

## Proposed read-only MCP tools (backed by MathBank REST)
`get_problem_canonical_context(problem_code,scope)`; `get_strategy_versions(domain,techniques)`; `get_published_route(release_id,scope)`; `list_reviewed_activities(node_id)`; `get_approved_math_claims(release_id)`; `get_workflow_release(release_id)`; `get_student_context(execution_id)` (student-owned/minimized); `list_eligible_transitions(execution_id,state_version)`; `get_current_disclosure(execution_id)`.

## Proposed authoring MCP tools (staff-only, draft-only)
`propose_strategy_patch(draft_id,expected_hash,patch)`; `propose_discovery_steps`; `propose_assessments`; `propose_feedback_policy`; `validate_workflow_draft`; `simulate_workflow_draft`; `get_review_findings`; `get_projection_status`. Proposals should create revisions with provenance, never apply to published release automatically. Mutations require REST role authorization and optimistic concurrency; tool visibility is not authorization.

## Student tools (scoped)
`submit_current_activity(execution_id,response,idempotency_key)`; `request_current_hint(execution_id,level)`; `request_current_reveal(execution_id)`; `request_next_step(execution_id,state_version)`; `get_owned_execution_status`. No arbitrary student_id argument accepted; identity from invocation bearer/token binding.

## Forbidden tools
No `approve_mathematics`, `self_publish`, `award_mastery`, `execute_sql`, `run_cypher_write`, `unrestricted_stepfunctions_start`, `reveal_future_answers`, `change_review_status`, or direct credentials. Publication is a distinct authenticated human operation outside model-exposed tools. Existing `mathbank-mcp-competitions` remains independently usable; implement `mathbank-mcp-socratic` or scoped AgentCore Gateway targets without duplicating corpus retrieval.

## Next-step strict output
```
{ "selected_node_key":"BIJECTION_REMEDIATION", "reason_code":"JUSTIFICATION_GAP", "evidence_event_ids":["..."], "alternatives":["..."], "uncertainty":"LOW|MEDIUM|HIGH", "explanation_for_audit":"..." }
```
Server cross-checks exact eligible set and event provenance, must not trust confidence alone. Prompt includes domain/strategy policy and current-safe math context, no raw private transcript when evidence summary suffices. Version prompts, models, tools and evaluation datasets.
