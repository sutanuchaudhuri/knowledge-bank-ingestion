"""Learner store, outcomes area (requirement 71 WP5). Filled in by the work package; see stores/learner/__init__.py.

``OutcomesPostgres`` delegates to the existing SQL modules (behaviour unchanged); ``OutcomesDynamoDB`` is the mb-learner implementation built on
``LearnerUnitOfWork`` and the typed models. Method names start with a stores.READ_PREFIXES entry exactly when they are reads.
"""
from __future__ import annotations


class OutcomesPostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""


class OutcomesDynamoDB:
    """DynamoDB backend over mb-learner."""
