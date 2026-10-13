"""SQLAlchemy engine/connection for the shared Postgres instance's `studio` schema
(requirements/60, migration 044). No ORM models — plain `sqlalchemy.text()` statements,
matching mathbank-rest's own convention.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import Engine

from mathbank_manim_studio.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


@contextmanager
def connection() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn
