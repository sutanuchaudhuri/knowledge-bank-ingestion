"""Exam store (requirement 71 WP6): quizzes and mock exams, one flag ``EXAM_STORE=postgres|dynamodb|frozen``.

Composed from area modules so they evolve independently:

* ``papers``  paper lifecycle, questions, responses, events, progress, submit, review, diagnosis, quiz evidence (C2 A1-A11, A18)
* ``pool``    the question pool: match (vectors topic branch + concept branch + per-learner history exclusion), write-back with
              uniqueness sentinel and near-duplicate check, pool serve ops for finalize, pool get/list/status (A12-A17, A21)
* ``admin``   admin paper/pool/response operations, regrade, purge (erasure), consumers' operations (A19-A22, E01-E10)

Each area defines ``<Area>Postgres`` (delegates to today's SQL at call time) and ``<Area>DynamoDB`` (typed models, ``ExamUnitOfWork``,
no scans, no Postgres). Callers use ``stores.get_store("exam")``.
"""
from __future__ import annotations

from mathbank_rest.stores.exam.admin import AdminDynamoDB, AdminPostgres
from mathbank_rest.stores.exam.papers import PapersDynamoDB, PapersPostgres
from mathbank_rest.stores.exam.pool import PoolDynamoDB, PoolPostgres


class PostgresExamStore(PapersPostgres, PoolPostgres, AdminPostgres):
    backend = "postgres"


class DynamoDBExamStore(PapersDynamoDB, PoolDynamoDB, AdminDynamoDB):
    backend = "dynamodb"
