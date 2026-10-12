-- psql-only safety preamble; no diagnostic query IDs in this file.
\set ON_ERROR_STOP on
\pset pager off
\if :{?competition}
\else
\set competition ''
\endif
\if :{?book}
\else
\set book ''
\endif
\if :{?problem_code}
\else
\set problem_code ''
\endif
\if :{?days}
\else
\set days 30
\endif
\if :{?row_limit}
\else
\set row_limit 50
\endif
\if :{?confidence}
\else
\set confidence 0.8
\endif
\if :{?cohort}
\else
\set cohort 10
\endif
\if :{?consumer}
\else
\set consumer analytics
\endif
\if :{?query_text}
\else
\set query_text 'power of a point'
\endif
BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '30s';
SET LOCAL lock_timeout = '2s';
SET LOCAL idle_in_transaction_session_timeout = '60s';
SET LOCAL timezone = 'UTC';
