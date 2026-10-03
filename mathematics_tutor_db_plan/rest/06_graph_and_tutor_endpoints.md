# REST 06 — Graph and Tutor Endpoints

## Named graph traversals

Expose bounded semantic operations, not arbitrary Cypher.

Examples:

- `GET /v1/concepts/{id}/prerequisites?depth=3`
- `GET /v1/concepts/{id}/dependents?depth=2`
- `GET /v1/problems/{id}/knowledge-neighborhood`
- `POST /v1/learning-paths`
- `POST /v1/problems/similar`

## Learning path request

```json
{
  "target_concept_ids": ["..."],
  "mastered_concept_ids": ["..."],
  "contest_context": "AIME",
  "max_steps": 12
}
```

Return each step with prerequisite reason and representative problems.

## Tutor retrieval endpoint

`POST /v1/tutor/retrieve`

Inputs can include question text, learner context ID, requested depth, and target corpus. The service performs hybrid retrieval against PostgreSQL/search and optionally graph expansion.

Return structured evidence:

- candidate problems
- concepts
- techniques
- prerequisite gaps
- source IDs
- retrieval scores

The LLM should consume this evidence; it should not invent corpus facts without evidence.
