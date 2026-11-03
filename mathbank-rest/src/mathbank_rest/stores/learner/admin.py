"""Learner store, admin area (requirement 71 WP5). Filled in by the work package; see stores/learner/__init__.py.

``AdminPostgres`` delegates to the existing SQL modules (behaviour unchanged); ``AdminDynamoDB`` is the mb-learner implementation built on
``LearnerUnitOfWork`` and the typed models. Method names start with a stores.READ_PREFIXES entry exactly when they are reads.
"""
from __future__ import annotations


class AdminPostgres:
    """Postgres backend: calls today's functions at call time (monkeypatched tests keep working)."""


class AdminDynamoDB:
    """DynamoDB backend over mb-learner."""
