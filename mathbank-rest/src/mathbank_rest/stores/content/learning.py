"""Content store, learning area (requirement 71 WP4). Filled in by the work package; see stores/content/__init__.py."""
from __future__ import annotations


class LearningPostgres:
    """Postgres backend: delegates to the existing SQL modules (behaviour unchanged)."""


class LearningDynamoDB:
    """DynamoDB backend over mb-content (typed models, stores.typed)."""
