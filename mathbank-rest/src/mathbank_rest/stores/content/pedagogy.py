"""Content store, pedagogy area (requirement 71 WP4). Filled in by the work package; see stores/content/__init__.py."""
from __future__ import annotations


class PedagogyPostgres:
    """Postgres backend: delegates to the existing SQL modules (behaviour unchanged)."""


class PedagogyDynamoDB:
    """DynamoDB backend over mb-content (typed models, stores.typed)."""
