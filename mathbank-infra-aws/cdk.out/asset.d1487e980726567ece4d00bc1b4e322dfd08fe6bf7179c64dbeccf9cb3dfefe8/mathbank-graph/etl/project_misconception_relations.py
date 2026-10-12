"""DEPRECATED — superseded by requirements/51 ENR-1/ENR-4, do not run this anymore.

This script's RouteStep.REQUIRES-join-derived edges were a reasonable approximation
before `knowledge.misconception`/`knowledge.misconception_taxonomy_link` existed
(see `scripts/backfill_misconception_catalog.py`), but they had two real problems
confirmed live: (1) every edge this script wrote carries `projection_kind` left
unset on the *relationship*, while attaching to Misconception *nodes* that carry
`projection_kind='tutoring_routes'` — `route_projection.py`'s atomic rebuild does a
node-level `DETACH DELETE` on everything with that kind, which silently wipes these
out-of-band edges on every single re-run, with no warning (confirmed live: a routine
re-projection zeroed `misconception-concepts/-skills/-techniques` from 82,019 edges to
0); (2) it derived a misconception's taxonomy targets from its *RouteStep's* REQUIRES
edges rather than from the misconception's own `taxonomy_node_ids`, which is a looser
approximation now that the canonical, purpose-built `knowledge.misconception_taxonomy_link`
junction table exists.

`route_projection.py`'s `metadata()`/`_project()` now project `RELATES_TO` directly from
`knowledge.misconception_taxonomy_link` as part of the same atomic rebuild that creates
the Misconception nodes themselves, so it can never be wiped by that rebuild again, and
is the current source of truth. This file is kept only for historical reference; it
should not be executed going forward.

------------------------------------------------------------------------------------
Project a derived Misconception -> Concept|Skill|Technique relationship into the
Neo4j graph (requirements/50_NEO4J_KNOWLEDGE_GRAPH_QUALITY_BUGS.md BUG-2/NGQ-2).

`knowledge.misconception` has no concept/skill/technique column in Postgres at all —
Misconception nodes have historically only ever connected to the per-route-checkpoint
"process" layer (RouteStep via CAN_TRIGGER, LearningItem via DIAGNOSED_BY/TESTS_MISCONCEPTION,
TheoryItem via REMEDIATED_BY), never to the taxonomy itself. This script does not require
any new Postgres authoring: it composes two *already-projected* graph relationships —
  (RouteStep)-[:CAN_TRIGGER]->(Misconception)   (which RouteStep a misconception belongs to)
  (RouteStep)-[:REQUIRES]->(Concept|Skill|Technique)   (what that same RouteStep targets)
into one new derived edge:
  (Misconception)-[:RELATES_TO {derived_via:'RouteStep.REQUIRES'}]->(Concept|Skill|Technique)

Confirmed live before writing this script: 99.3% of the 80,168 Misconception nodes have at
least one such derivable target (82,019 total edges across 79,591 distinct misconceptions and
6,746 distinct taxonomy nodes) — the 0.7% remainder belong to a RouteStep with no REQUIRES
edges at all and simply get no RELATES_TO edge, which is correct (there is nothing to derive).
The derived edge's `review_status` is copied verbatim from the source REQUIRES edge it was
composed from (confirmed 100% of those are already 'REVIEWED') rather than asserted outright —
this is a deterministic composition of already-reviewed data, not a new unreviewed claim.

Idempotent (MERGE), batched via Neo4j 5's native `CALL ... IN TRANSACTIONS` (no APOC needed),
and purely additive — never deletes or modifies any pre-existing relationship. Run via:
    GRAPH_ENV_FILE=remote.env .venv/bin/python etl/project_misconception_relations.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from project_from_postgres import _load_env, graph_target  # noqa: E402

BATCH_ROWS = 2000


def project_misconception_relations(driver) -> dict[str, int]:
    with driver.session() as session:
        before = session.run(
            "MATCH (:Misconception)-[r:RELATES_TO]->() RETURN count(r) AS n"
        ).single()["n"]
        session.run(f"""
            MATCH (rs:RouteStep)-[req:REQUIRES]->(target)
            WHERE target:Concept OR target:Skill OR target:Technique
            MATCH (rs)-[:CAN_TRIGGER]->(m:Misconception)
            CALL (m, target, req) {{
                MERGE (m)-[r:RELATES_TO]->(target)
                SET r.projection_kind = 'misconception_relations', r.derived_via = 'RouteStep.REQUIRES',
                    r.review_status = req.review_status
            }} IN TRANSACTIONS OF {BATCH_ROWS} ROWS
        """)
        after = session.run(
            "MATCH (:Misconception)-[r:RELATES_TO]->() RETURN count(r) AS n"
        ).single()["n"]
        distinct_misconceptions = session.run(
            "MATCH (m:Misconception)-[:RELATES_TO]->() RETURN count(DISTINCT m) AS n"
        ).single()["n"]
    return {"edges_before": before, "edges_after": after, "distinct_misconceptions_linked": distinct_misconceptions}


def main() -> None:
    env = _load_env()
    target = graph_target(env)
    try:
        stats = project_misconception_relations(target.driver)
        print(f"RELATES_TO edges before: {stats['edges_before']}")
        print(f"RELATES_TO edges after:  {stats['edges_after']}")
        print(f"Distinct misconceptions linked: {stats['distinct_misconceptions_linked']}")
    finally:
        target.close()


if __name__ == "__main__":
    main()
