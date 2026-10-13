-- Idempotent bootstrap for the mathbank application role + database.
-- Invoked by `make create-db` with :appuser / :apppass / :appdb psql variables set.

SELECT 'CREATE ROLE ' || quote_ident(:'appuser') || ' LOGIN PASSWORD ' || quote_literal(:'apppass') AS cmd
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'appuser')
\gexec

SELECT 'CREATE DATABASE ' || quote_ident(:'appdb') || ' OWNER ' || quote_ident(:'appuser') AS cmd
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'appdb')
\gexec
