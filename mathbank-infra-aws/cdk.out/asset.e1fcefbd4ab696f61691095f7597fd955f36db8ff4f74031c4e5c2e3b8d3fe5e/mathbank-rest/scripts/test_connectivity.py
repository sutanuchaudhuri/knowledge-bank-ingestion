"""Standalone connectivity check — prints Postgres + Neo4j status without starting uvicorn.

Run via `make test-connectivity` (mathbank-rest/Makefile).
"""
from __future__ import annotations

import sys

from mathbank_rest.db.graph import check_neo4j
from mathbank_rest.db.postgres import check_postgres


def main() -> int:
    pg = check_postgres()
    neo = check_neo4j()

    print("Postgres:", pg)
    print("Neo4j:   ", neo)

    return 0 if (pg["ok"] and neo["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())
