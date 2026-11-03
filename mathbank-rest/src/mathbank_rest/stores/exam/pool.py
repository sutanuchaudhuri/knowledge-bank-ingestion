"""Exam store, pool area (requirement 71 WP6). Filled in by the work package; see stores/exam/__init__.py.

``PoolPostgres`` delegates to today's quiz SQL modules at call time (behaviour unchanged); ``PoolDynamoDB`` is the mb-exam
implementation on ``ExamUnitOfWork``, the typed models and the S3 Vectors adapter. Method names start with a stores.READ_PREFIXES entry
exactly when they are reads.
"""
from __future__ import annotations


class PoolPostgres:
    """Postgres backend."""


class PoolDynamoDB:
    """DynamoDB backend over mb-exam."""
