# REST 02 — Resource Model and Identifiers

## Canonical resources

- `/competitions`
- `/editions`
- `/papers`
- `/problems`
- `/solutions`
- `/concepts`
- `/techniques`
- `/taxonomy/nodes`
- `/assertions`
- `/sources`
- `/runs`
- `/review-tasks`

## Identifier rules

API paths use immutable canonical IDs. Human codes such as `AMC10-2025-A-Q17` are alternate lookup keys.

Examples:

- `GET /v1/problems/{problem_id}`
- `GET /v1/problems/by-code/AMC10-2025-A-Q17`

Never allow a mutable slug to be the only durable foreign key.

## Resource representation

A problem response may include compact accepted concept/technique lists, but large solutions, provenance, embeddings, and graph neighborhoods should be separate expandable resources.

## Field selection

Support optional `include=` or sparse fieldsets later if payload size warrants it. Avoid building GraphQL-like arbitrary nesting into v1 REST.
