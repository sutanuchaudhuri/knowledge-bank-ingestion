"""Jobs store (requirement 71 WP3), one flag ``JOBS_STORE=postgres|dynamodb|frozen[:backend]``.

``PostgresJobsStore`` is the REST-side view of today's Studio queue (an HTTP client of mathbank-manim-studio, which owns
the Postgres tables); ``DynamoDBJobsStore`` is the ``mb-jobs`` + SQS implementation used by REST and by the Studio
workers. They are loaded lazily so that using the DynamoDB store never imports the Postgres one.
"""
from __future__ import annotations

from typing import Any

__all__ = ["DynamoDBJobsStore", "JobClaim", "LeaseLost", "PostgresJobsStore"]


def __getattr__(name: str) -> Any:
    if name == "PostgresJobsStore":
        from mathbank_rest.stores.jobs.postgres import PostgresJobsStore

        return PostgresJobsStore
    if name == "DynamoDBJobsStore":
        from mathbank_rest.stores.jobs.dynamodb import DynamoDBJobsStore

        return DynamoDBJobsStore
    if name in ("JobClaim", "LeaseLost"):
        from mathbank_rest.stores.jobs import protocol

        return getattr(protocol, name)
    raise AttributeError(name)
