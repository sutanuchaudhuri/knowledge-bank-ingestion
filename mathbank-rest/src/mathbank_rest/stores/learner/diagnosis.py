"""Learner store, diagnosis area (requirement 71 WP5). Filled in by the work package; see stores/learner/__init__.py.

``DiagnosisPostgres`` delegates to the existing SQL modules (behaviour unchanged); ``DiagnosisDynamoDB`` is the mb-learner implementation built on
``LearnerUnitOfWork`` and the typed models. Method names start with a stores.READ_PREFIXES entry exactly when they are reads.
"""
from __future__ import annotations


class DiagnosisPostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""


class DiagnosisDynamoDB:
    """DynamoDB backend over mb-learner."""
