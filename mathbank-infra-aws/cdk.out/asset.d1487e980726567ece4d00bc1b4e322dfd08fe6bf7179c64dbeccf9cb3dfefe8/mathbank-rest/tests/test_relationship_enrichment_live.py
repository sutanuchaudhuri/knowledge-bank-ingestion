"""Opt-in live fixtures always roll back metadata, jobs, and audit records."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest.db import pedagogy_admin as admin
from mathbank_rest.db.postgres import engine
from mathbank_rest.relationship_enrichment import Proposal, store_proposal

pytestmark = pytest.mark.skipif(
    os.getenv("MATHBANK_LIVE_PEDAGOGY_TEST") != "1", reason="Live Postgres opt-in"
)


@pytest.mark.parametrize(
    "kind,relation",
    [
        ("skill", "PART_OF"),
        ("skill", "BUILDS_ON"),
        ("concept", "PREREQUISITE_OF"),
    ],
)
def test_automatic_relations_protected_rejections_and_cycle_rollback(kind, relation):
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            suffix = uuid4().hex
            start, end = f"relation-start-{suffix}", f"relation-end-{suffix}"
            ids = []
            for slug in [start, end]:
                if kind == "skill":
                    query = """
                        INSERT INTO knowledge.skill(slug,name,objective,source,confidence)
                        VALUES(:slug,'Fixture action','Compute an exact fixture quantity','fixture',0.9)
                        RETURNING skill_id
                    """
                else:
                    query = "INSERT INTO knowledge.concept(slug,name,description) VALUES(:slug,'Fixture concept','Fixture definition') RETURNING concept_id"
                ids.append(conn.execute(text(query), {"slug": slug}).scalar_one())
            conn.execute(
                text("""
                INSERT INTO knowledge.relationship_enrichment_job(entity_kind,anchor_id,input_hash,status)
                VALUES(:kind,:id,'fixture','IN_PROGRESS')
            """),
                {"kind": kind, "id": ids[0]},
            )

            def proposed(a, b):
                return Proposal.model_validate(
                    {
                        "relationships": [
                            {
                                "from_slug": a,
                                "to_slug": b,
                                "relation_type": relation,
                                "confidence": 0.9,
                                "rationale": "Fixture definitions support this directed relationship for testing.",
                            }
                        ],
                        "explanation": "Fixture proposal tests atomic automatic approval.",
                    }
                )

            assert store_proposal(conn, kind, ids[0], proposed(start, end)) == 1
            table = f"{kind}_relation"
            key = {
                f"from_{kind}_id": str(ids[0]),
                f"to_{kind}_id": str(ids[1]),
                "relation_type": relation,
            }
            where = f"from_{kind}_id=:start AND to_{kind}_id=:end AND relation_type=:type"
            params = {"start": ids[0], "end": ids[1], "type": relation}
            row = conn.execute(
                text(f"SELECT to_jsonb(r) FROM knowledge.{table} r WHERE {where}"), params
            ).scalar_one()
            assert row["review_status"] == "REVIEWED" and row["approval_method"] == "automatic"
            assert conn.execute(
                text(
                    "SELECT status,published_at,edges_inserted FROM knowledge.relationship_enrichment_job WHERE entity_kind=:kind AND anchor_id=:id"
                ),
                {"kind": kind, "id": ids[0]},
            ).one() == ("COMPLETED", None, 1)
            with pytest.raises(ValueError, match="cycle"), conn.begin_nested():
                store_proposal(conn, kind, ids[0], proposed(end, start))
            assert (
                conn.execute(
                    text(
                        f"SELECT count(*) FROM knowledge.{table} WHERE from_{kind}_id=:start AND to_{kind}_id=:end"
                    ),
                    {"start": ids[1], "end": ids[0]},
                ).scalar_one()
                == 0
            )
            after = admin.change_decision(
                conn,
                table,
                key,
                admin.revision(row),
                "REJECTED",
                "Reject fixture relationship for protection test",
            )
            assert after["approval_method"] == "human"
            conn.execute(text("SET LOCAL mathbank.human_review='off'"))
            assert store_proposal(conn, kind, ids[0], proposed(start, end)) == 0
            assert conn.execute(
                text(f"SELECT review_status,approval_method FROM knowledge.{table} WHERE {where}"),
                params,
            ).one() == ("REJECTED", "human")
        finally:
            tx.rollback()
