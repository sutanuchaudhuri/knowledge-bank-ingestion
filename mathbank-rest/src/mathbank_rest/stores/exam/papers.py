"""Exam store, papers area (requirement 71 WP6). Filled in by the work package; see stores/exam/__init__.py.

``PapersPostgres`` delegates to today's quiz SQL modules at call time (behaviour unchanged); ``PapersDynamoDB`` is the mb-exam
implementation on ``ExamUnitOfWork`` and the typed models. Method names start with a stores.READ_PREFIXES entry exactly when they are reads.
"""
from __future__ import annotations


class PapersPostgres:
    """Postgres backend."""


class PapersDynamoDB:
    """DynamoDB backend over mb-exam."""
