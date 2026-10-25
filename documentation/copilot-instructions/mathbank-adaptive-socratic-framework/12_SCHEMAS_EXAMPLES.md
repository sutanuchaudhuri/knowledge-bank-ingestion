# 12 — Worked contracts, workflow examples and tool payloads

## Sample educational workflow IR (illustrative, never raw AWS ASL)
```json
{
  "schema_version":"socratic.workflow.v1",
  "code":"COMB_STARS_BARS_BASIC",
  "strategy_version_ref":"STR_COMB_STARS_BARS@1",
  "route_release_ref":"<actual-reviewed-route-release-uuid>",
  "entry":"start",
  "nodes":[
    {"key":"start","type":"START"},
    {"key":"represent","type":"DISCOVERY","config":{"activity_ref":"APPROVED_REPRESENTATION_Q1","reveal_policy":"AFTER_ATTEMPT_OR_EXPLICIT_REVEAL"}},
    {"key":"justify","type":"QUIZ","config":{"assessment_refs":["APPROVED_BIJECTION_AR1","APPROVED_FREE_FORM_01"]}},
    {"key":"select","type":"AI_DECISION","config":{"candidate_keys":["generalize","probe","recap"],"fallback_key":"probe","max_calls":1}},
    {"key":"recap","type":"REMEDIATION","config":{"approved_activity_ref":"BIJECTION_MINI_LESSON","return_key":"justify","max_visits":2}},
    {"key":"probe","type":"PREREQUISITE_PROBE","config":{"activity_ref":"APPROVED_PROBE_01","return_key":"justify","max_visits":2}},
    {"key":"generalize","type":"TRANSFER","config":{"activity_ref":"APPROVED_TRANSFER_01"}},
    {"key":"done","type":"COMPLETE"}
  ],
  "edges":[["start","represent"],["represent","justify"],["justify","select"],["select","generalize"],["select","probe"],["select","recap"],["recap","justify"],["probe","justify"],["generalize","done"]]
}
```
Above is a conceptual compact illustration: production edge objects require typed guard, priority and eligibility; compiler rejects cycles lacking bounded loop/return policy.

## Student submission
```json
{"current_node_key":"justify","activity_version":"1","response":{"assertion_true":true,"reason_true":false,"reason_explains":false},"expected_state_version":4,"idempotency_key":"request-uuid"}
```

## Private selection request and response
```json
{"workflow_release_id":"uuid","execution_id":"opaque-scoped-id","state_version":5,"current_node_key":"select","approved_candidates":[{"key":"generalize","required_evidence":["E_GENERALIZED"]},{"key":"probe","required_evidence":[]},{"key":"recap","required_evidence":[]}],"evidence":[{"event_id":"e1","code":"CONCLUSION_VALID"},{"event_id":"e2","code":"JUSTIFICATION_GAP"}],"fallback_key":"probe"}
```
```json
{"selected_node_key":"recap","reason_code":"JUSTIFICATION_GAP","evidence_event_ids":["e2"],"alternatives":["probe"],"uncertainty":"LOW","explanation_for_audit":"Approved bijection recap targets observed gap."}
```
Validator independently checks eligible set, evidence IDs and content release before accepting. The agent response itself has no write authority.

## Conceptual AWS Standard review machine
```
LoadDraft -> Validate -> Simulate -> WaitForReviewerCallback -> CheckHashAndAttestations -> PublishViaREST -> DeployPinnedVersion -> Verify -> Success
                       rejection/timeout -> MarkNeedsRevision
```
## Conceptual short student state machine
```
GetTrustedContext -> DeterministicGate -> [if unresolved] InvokeAgentCore -> ValidateCandidate -> CommitViaREST -> ReturnSafeNode
                                             error -> ApprovedFallback ----^
```
Human review callback resides in distinct Task state; optimized AgentCore harness invocation is request-response and should not be given review token.
