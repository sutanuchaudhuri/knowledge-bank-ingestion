"""Bounded, shared retries for idempotent Postgres-to-Neo4j publication."""

import logging
import time

from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired, TransientError
from sqlalchemy.exc import SQLAlchemyError

from mathbank_rest.db.pedagogy_admin import ReviewConflict, fingerprint, publish
from mathbank_rest.db.postgres import engine

logger = logging.getLogger(__name__)


def publish_current(codes: list[str]) -> None:
    if not codes:
        raise ValueError("Publication requires at least one canonical problem code")
    for attempt in range(3):
        try:
            with engine.connect() as conn:
                current = fingerprint(conn)
            publish(current, list(dict.fromkeys(codes)))
            return
        except (ReviewConflict, ServiceUnavailable, SessionExpired, TransientError) as exc:
            logger.warning(
                "stage=publication attempt=%s/3 problems=%s cause=%s: %s",
                attempt + 1,
                len(set(codes)),
                type(exc).__name__,
                exc,
            )
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
        except (Neo4jError, SQLAlchemyError, ValueError, OSError, RuntimeError):
            logger.exception(
                "stage=publication problems=%s failed without immediate transient retry",
                len(set(codes)),
            )
            raise
