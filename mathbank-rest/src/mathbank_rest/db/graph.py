"""Neo4j connectivity via the official Bolt driver."""
from __future__ import annotations

from neo4j import GraphDatabase

from mathbank_rest.config import settings

driver = GraphDatabase.driver(
    settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
)


def check_neo4j() -> dict:
    """Run a trivial Cypher query to confirm the Bolt connection is alive."""
    try:
        with driver.session() as session:
            record = session.run("RETURN 'connected' AS status").single()
        return {"ok": True, "status": record["status"] if record else None}
    except Exception as exc:  # noqa: BLE001 - surfaced to the health endpoint, not swallowed
        return {"ok": False, "error": str(exc)}
