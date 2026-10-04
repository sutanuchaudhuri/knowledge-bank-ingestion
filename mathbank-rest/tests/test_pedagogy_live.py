"""Opt-in Neon/Aura integration; fixture mutations always roll back."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from mathbank_rest import pedagogy
from mathbank_rest.db.graph import driver
from mathbank_rest.db.postgres import engine

pytestmark = pytest.mark.skipif(
    os.environ.get("MATHBANK_LIVE_PEDAGOGY_TEST") != "1",
    reason="Set MATHBANK_LIVE_PEDAGOGY_TEST=1 explicitly for shared-database tests.",
)
SOURCE = "assistant-draft:counting-foundations-v1"


def inventory():
    with driver.session() as session:
        return [
            row.data()
            for row in session.run("""
            MATCH (a)-[r]->(b) WHERE r.projection_kind = 'pedagogy'
            RETURN a.canonical_id AS start, b.canonical_id AS end,
                   type(r) AS type, properties(r) AS properties
            ORDER BY start, end, type, r.role
        """)
        ]


def test_live_pending_review_gate_in_rolled_back_fixture(monkeypatch):
    with engine.connect() as conn:
        count = conn.execute(
            text("""
            SELECT count(*) FROM knowledge.skill
            WHERE source = :source
        """),
            {"source": SOURCE},
        ).scalar_one()
        assert count == 6
    before = inventory()
    with driver.session() as session:
        tx = session.begin_transaction()
        try:
            tx.run(
                "MATCH(s:Skill {source:$source}) SET s.review_status='PENDING'", source=SOURCE
            ).consume()
            tx.run(
                "MATCH(p:Problem) WHERE p.pedagogy_source IS NOT NULL "
                "SET p.pedagogy_review_status='PENDING'"
            ).consume()
            monkeypatch.setattr(
                pedagogy,
                "graph_rows",
                lambda query, **params: [row.data() for row in tx.run(query, parameters=params)],
            )
            context = pedagogy.learning_context("AMC10_2005B_Q18")
            assert context["metadata_status"] == "unenriched"
            assert not context["skills"] and not context["prerequisites"]
            assert context["difficulty"]["conceptual_depth"] is None
            assert not pedagogy.easier_practice("AMC10_2007B_Q20")["results"]
        finally:
            tx.rollback()
    assert inventory() == before
    assert len(before) >= 18


def test_real_reviewed_queries_inside_rolled_back_fixture(monkeypatch):
    before = inventory()
    with driver.session() as session:
        reviewed_before = session.run(
            "MATCH(s:Skill {source:$source,review_status:'REVIEWED'}) RETURN count(s) AS n",
            source=SOURCE,
        ).single()["n"]
        tx = session.begin_transaction()
        try:
            tx.run(
                "MATCH (s:Skill {source:$source}) SET s.review_status='REVIEWED'", source=SOURCE
            ).consume()
            tx.run("""
                MATCH ()-[r]->() WHERE r.projection_kind='pedagogy'
                SET r.review_status='REVIEWED'
            """).consume()

            def graph_rows(query, **params):
                return [row.data() for row in tx.run(query, parameters=params)]

            monkeypatch.setattr(pedagogy, "graph_rows", graph_rows)
            context = pedagogy.learning_context("AMC10_2007B_Q20")
            assert context["metadata_status"] == "reviewed"
            assert len(context["skills"]) == 2
            assert context["prerequisites"]
            assert all(item["evidence"] for item in context["prerequisites"])
            path = pedagogy.prerequisite_path("counting-restricted-selection")
            assert len(path["prerequisites"]) == 3
            assert not path["truncated"]
            practice = pedagogy.easier_practice("AMC10_2007B_Q20")
            assert practice["results"][0]["canonical_code"] == "AMC10_2005B_Q18"
            evidence = practice["results"][0]["evidence"][0]
            assert evidence["candidate_level"] == 2 and evidence["original_level"] == 3
        finally:
            tx.rollback()
    assert inventory() == before
    with driver.session() as session:
        assert (
            session.run(
                """
            MATCH (s:Skill {source:$source,review_status:'REVIEWED'})
            RETURN count(*) AS n
        """,
                source=SOURCE,
            ).single()["n"]
            == reviewed_before
        )


def test_live_sql_constraints_roll_back_whole_batch():
    slug = f"integration-rollback-{uuid4()}"
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text("""
            INSERT INTO knowledge.skill(slug,name,objective,source,confidence,review_status)
            VALUES (:slug,'Temporary fixture','Rollback check','integration-test',0.5,'PENDING')
        """),
            {"slug": slug},
        )
        conn.execute(text("UPDATE knowledge.skill SET level=0 WHERE slug=:slug"), {"slug": slug})
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM knowledge.skill WHERE slug=:slug"), {"slug": slug}
            ).scalar_one()
            == 0
        )


def test_live_projection_failure_preserves_previous_graph():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "live_projection", root / "mathbank-graph/etl/project_from_postgres.py"
    )
    projection = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(projection)
    before = inventory()

    class FailingTransaction:
        def __init__(self, tx):
            self.tx = tx

        def run(self, query, **params):
            if "MERGE (s:Skill" in query:
                raise RuntimeError("Deliberate projection rollback test")
            return self.tx.run(query, **params)

    class FailingSession:
        def __enter__(self):
            self.session = driver.session()
            return self

        def __exit__(self, *args):
            self.session.close()

        def execute_write(self, operation):
            return self.session.execute_write(lambda tx: operation(FailingTransaction(tx)))

    class FailingDriver:
        def session(self):
            return FailingSession()

    with (
        engine.connect() as conn,
        conn.connection.cursor() as cursor,
        pytest.raises(RuntimeError, match="Deliberate projection rollback"),
    ):
        projection.project_pedagogy(FailingDriver(), cursor)
    assert inventory() == before
