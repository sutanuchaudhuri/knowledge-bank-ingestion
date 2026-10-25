# 06 — AWS Step Functions, Bedrock and AgentCore deployment design

## Confirmed service assumptions (verify region and API at build time)
AWS announced optimized Step Functions integration with AgentCore harness in June 2026; harness described as preview at announcement. Standard SDK integration can invoke AgentCore services; select supported path after region check. `InvokeHarness` is request-response (not task-token callback). Place human-review callback in separate Step Functions task, not inside agent invocation. AWS documentation: https://docs.aws.amazon.com/step-functions/latest/dg/connect-bedrockagentcore.html ; https://aws.amazon.com/about-aws/whats-new/2026/06/aws-step-functions-agentcore/ ; https://aws.amazon.com/about-aws/whats-new/2026/03/aws-step-functions-sdk-integrations/ .

## Workflows
A. Authoring: Standard workflow: load source snapshots → parallel AI strategy/quiz/visual proposals (bounded budgets) → validation → optional simulation → persist proposed patch → human review via callback token handled by secure approval API → hash recheck → publish in MathBank transaction/outbox → deploy/verify AWS version → mark activation. Set timeout/escalation; token never sent to AI/client. If AWS deployment fails mark pending/unavailable, not published-ready.
B. Student: Web request → REST ownership/auth → write intent/outbox → short Step Functions execution: load sanitized current context → evaluate deterministic rules → conditional AgentCore reasoning Task → validate recommendation → call REST transition endpoint with idempotent CAS → result. UI polls/subscribes to its own execution until result; no long AWS Wait for student's idle time. Concurrent submissions handled by state version and idempotency keys.
C. Projection: outbox-driven `socratic_workflow` Neo4j refresh after SQL commit; retry idempotently, expose lag/degraded state.

## Failure matrix
Bedrock timeout or malformed structured response → approved safe fallback. AgentCore/Gateway unavailable → deterministic path or pause with clear status. REST 409 CAS → reload authoritative state, do not double-award. Graph unavailable → PostgreSQL safe policy only if completeness assured, otherwise pause. Human rejection → draft revision; never publish. Student abandons → SQL resume pinned release. Paid quota exceeded → pause or fallback; don't silently switch to unauthorized provider.

## IAM/data/security
Separate authoring, reviewer, deployment and student transition roles. Principle of least privilege; private endpoints when feasible; KMS encrypted S3/logs; no secrets in payload/traces; no raw answers in agent telemetry; per-invocation token/latency budget; allowlisted model IDs, Gateway targets, state machine ARNs, REST actions. Store only minimum student evidence in agent invocation. Use CloudWatch traces and correlation IDs; validate logs for PII/key exposure. Feature flags, quotas, alarms for retry storms and cost.

## Infra deliverables
CDK stack for roles, state machines, queues/outbox adapters, task Lambdas, Gateway/AgentCore configs, metrics/alarms and deployment manifest. CI: ASL validation, IAM policy assertions, simulator tests, contract tests, static no-answer-leak tests and live opt-in smoke; NEVER deploy from a draft published by an LLM alone.
