"""Notify store (requirement 71 WP3), one flag ``NOTIFY_STORE=postgres|dynamodb|frozen[:backend]``.

``PostgresNotifyStore`` delegates to the SQL in ``mathbank_rest.notifications`` (``notification.event``);
``DynamoDBNotifyStore`` is the ``mb-notify`` implementation (NOTIFICATION, DEDUPE, INBOX_COUNTER). Loaded lazily so the
DynamoDB store never imports the Postgres one.
"""
from __future__ import annotations

from typing import Any

__all__ = ["DynamoDBNotifyStore", "PostgresNotifyStore"]


def __getattr__(name: str) -> Any:
    if name == "PostgresNotifyStore":
        from mathbank_rest.stores.notify.postgres import PostgresNotifyStore

        return PostgresNotifyStore
    if name == "DynamoDBNotifyStore":
        from mathbank_rest.stores.notify.dynamodb import DynamoDBNotifyStore

        return DynamoDBNotifyStore
    raise AttributeError(name)
