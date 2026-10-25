# 05 — Educational workflow intermediate representation (IR) and compiler

## Workflow node catalog
START, DISCOVERY, QUIZ, INTERACTION, HINT, FEEDBACK, AI_DECISION, DETERMINISTIC_GATE, PREREQUISITE_PROBE, REMEDIATION, BRANCH, RETURN, TRANSFER, REFLECT, COMPLETE, HUMAN_REVIEW. Every node has immutable key, schema-checked typed config, approved asset refs, student-visible disclosure level, accessible fallback, timing/budget policy. Edges have typed guards, priority and approved fallback.

## Compilation and validation
Parse JSON schema → resolve immutable strategy/course/route/activity refs → reject unknown controls/assets → ensure exactly one start, reachable completion, valid candidate destinations, bound loops/return stacks, no skipping required assessment/review, preserved current-step disclosure, exact release hash → compile to versioned Step Functions infrastructure contract and MathBank runtime representation. Author can change educational IR only; no direct arbitrary ASL, Lambda ARN, IAM statements, tool name, or model prompt injection.

## Decision precedence
1. Server evaluates explicit deterministic admin guards against authoritative assessment and learner records.
2. If exactly one mandatory eligible edge, take it without LLM.
3. If multiple policy-eligible choices, send minimal snapshot and enumerated node IDs to Bedrock agent.
4. Parse strict output, verify selected ID belongs to eligible set, evidence references exist and no prerequisite/disclosure violation; otherwise use approved fallback.
5. Record decision and CAS advance. NEVER let model output new node/quiz/skill/misconception or change graph live.

## Return-stack contract
Nested remediation pushes `{origin_node, required_claim, strategy_version, depth, retry_budget}`; activity completes → check required evidence → pop and return to prior node, or approved escalation. Bounded depth, maximum retries, no indefinite loop. User may ask for hint/reveal but independent-success flag is not asserted.

## State transition pseudocode
```
context = rest.load_authoritative_context(execution_id, actor)
candidates = policy.eligible_edges(release, context)
if mandatory(candidates): selected = deterministic(candidates)
else: selected = validate(agent.recommend(minimal_snapshot(context), candidates)) or policy.fallback
rest.commit_transition(execution_id, expected_state_version, selected, evidence_refs, idempotency_key)
```

## Compilation artifact manifest
`workflow_release_id`, `release_hash`, `compiler_version`, `IR_schema_version`, `references` and their hashes, `ASL_template_hash`, `state_machine_version_arn`, `model_policy_version`, validation report, reviewer attestations, rollback flag. Signing deployment and publication are two distinct operations.
