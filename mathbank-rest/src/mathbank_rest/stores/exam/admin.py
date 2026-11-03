"""Exam store, admin area (requirement 71 WP6). Filled in by the work package; see stores/exam/__init__.py.

``AdminPostgres`` delegates to today's quiz SQL modules at call time (behaviour unchanged); ``AdminDynamoDB`` is the mb-exam
implementation on ``ExamUnitOfWork`` and the typed models. Method names start with a stores.READ_PREFIXES entry exactly when they are reads.
"""
from __future__ import annotations


class AdminPostgres:
    """Postgres backend."""


class AdminDynamoDB:
    """DynamoDB backend over mb-exam."""
