# PostgreSQL `auth` schema

**Role:** Observed empty namespace. No relations observed; no project migration owner discovered.

**Access family:** No checked-in MathBank access found. Do not infer an authentication implementation from its name.

**Evidence:** live catalog metadata at 2026-10-07T13:40:57.292324+00:00; source `375f3743357cef814c50e3c8752f7f4ce2d6ebe5`.
Metadata is observational, not proof of data correctness, endpoint authorization, or publication readiness.
Exact columns/constraints/indexes below are the observed selected-target catalog. No private row values are included.

[Schema index](README.md) | [DML/access boundaries](../POSTGRES_DML.md) | [REST contracts](../REST_API.md)

## Relations

No tables, views, sequences or foreign relations were observed in this namespace.

## Functions and routines

Extension routines are owned by their installed extension, not project migration code.
Volatility: i=immutable, s=stable, v=volatile. No routine was invoked by this inspection.

| Signature | Returns | Language / volatility | Security definer | Owner / source |
|---|---|---|---|---|
| `init(-)` | `void` | c / v | False | extension `pg_session_jwt` |
| `jwt(-)` | `jsonb` | c / s | False | extension `pg_session_jwt` |
| `jwt_session_init(jwt text)` | `void` | c / v | False | extension `pg_session_jwt` |
| `organization(-)` | `jsonb` | c / s | False | extension `pg_session_jwt` |
| `organization_id(-)` | `uuid` | c / s | False | extension `pg_session_jwt` |
| `session(-)` | `jsonb` | c / s | False | extension `pg_session_jwt` |
| `uid(-)` | `uuid` | c / s | False | extension `pg_session_jwt` |
| `user_id(-)` | `text` | c / s | False | extension `pg_session_jwt` |
