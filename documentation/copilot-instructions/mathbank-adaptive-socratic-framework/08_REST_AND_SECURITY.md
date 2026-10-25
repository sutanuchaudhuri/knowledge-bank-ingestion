# 08 — Proposed REST/OpenAPI contract and access control

Paths are new proposals; check actual router prefixes to avoid collisions. Backend service layer must be shared by Web, CLI, MCP and Step Functions task adapters.

## Admin (`staff`, with separate reviewer and publisher authorization)
GET/POST `/v1/admin/socratic/strategies`; GET/PATCH `/v1/admin/socratic/strategies/{id}/draft`; POST `/{id}/propose`, `/{id}/validate`, `/{id}/simulate`, `/{id}/review`, `/{id}/publish`. GET/POST `/v1/admin/socratic/workflows`; GET `/workflows/{id}`; PATCH `/workflows/{id}/draft` with `expected_hash` and `Idempotency-Key`; POST `/workflows/{id}/{ai-propose|validate|simulate|review|publish|deploy}`; GET `/workflows/{id}/{diff|audit|execution-analytics|projection-status}`. Reviewer fields: `expected_hash`, `mathematical_review_confirmed`, `pedagogical_review_confirmed`, `notes`, authenticated actor from principal (not free-form text). Publishing must refuse unreviewed/stale hashes, invalid assets and missing fallback.

## Student (`bearer owner-scoped`)
POST `/v1/learning/workflows/{release_id}/start`; GET `/v1/learning/executions/{id}`; POST `/v1/learning/executions/{id}/{respond|assist|reveal|transition}`; GET `/v1/learning/executions/{id}/history`. `respond` needs `{current_node_key,activity_version,response,expected_state_version,idempotency_key}`. Response returns sanitized current authorized node, request status, feedback allowed after grading; NEVER server-only activity definition. A second identical idempotency key returns same result; conflicting key+payload is 409. Nonowner returns 404/403 per existing project's anti-enumeration convention.

## Internal AWS endpoints
POST `/v1/internal/socratic/decisions/context` and `/commit` with service authentication, explicit release/run/version/event reference, idempotency; load trusted context server-side. Do not accept caller-supplied student score or arbitrary next node. Separate IAM service identity and minimal scopes. Service should not expose raw secret token or review callback to a Bedrock agent.

## Error and control examples
400 invalid semantic action; 401 unauthenticated; 403 wrong role; 404 missing/nonowned; 409 stale hash/version or transition not eligible; 422 schema/rule failure; 429 quota; 503 dependency unavailable. Every error contains `code`, `message` (safe), `correlation_id`, optional `retryable`; no source solution/hidden answer/provider trace leakage. OpenAPI-generated TS client/types; Pydantic strict extras forbidden. Redact learner identifiers in metrics. Content Security Policy and accessibility/reduced-motion fallback for widgets.
