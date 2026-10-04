"""Opt-in review tests; all SQL fixtures and audit events roll back."""

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest.db import pedagogy_admin as db
from mathbank_rest.db.postgres import engine

pytestmark = pytest.mark.skipif(
    os.environ.get("MATHBANK_LIVE_PEDAGOGY_TEST") != "1",
    reason="Explicit shared-database authorization is required.",
)


@pytest.fixture
def review_connection(monkeypatch):
    with engine.connect() as conn:
        transaction = conn.begin()

        class FixtureEngine:
            @contextmanager
            def begin(self):
                with conn.begin_nested():
                    yield conn

            @contextmanager
            def connect(self):
                yield conn

        monkeypatch.setattr(db, "engine", FixtureEngine())
        try:
            yield conn
        finally:
            transaction.rollback()


def new_skill(conn, status="PENDING"):
    row = conn.execute(
        text("""
        INSERT INTO knowledge.skill(slug,name,objective,source,confidence,review_status)
        VALUES (:slug,'Review fixture','Count fixture outcomes','rollback-test',0.8,:status)
        RETURNING to_jsonb(skill)
    """),
        {"slug": f"admin-review-fixture-{uuid4()}", "status": status},
    ).scalar_one()
    return row


def item(row):
    return {
        "kind": "skill",
        "key": {"skill_id": row["skill_id"]},
        "expected_revision": db.revision(row),
    }


def read_skill(conn, skill_id):
    return conn.execute(
        text("SELECT to_jsonb(t) FROM knowledge.skill t WHERE skill_id=:id"), {"id": skill_id}
    ).scalar_one()


def test_live_incomplete_starter_is_explicit_and_does_not_block_other_metadata(review_connection):
    conn = review_connection
    starter = db.starter_items(conn)
    link = next(row for row in starter if row["kind"] == "skill_concept")
    conn.execute(
        text(
            "DELETE FROM knowledge.skill_concept WHERE skill_id=:skill_id AND concept_id=:concept_id"
        ),
        link["key"],
    )
    with pytest.raises(db.MissingMetadata, match="incomplete"):
        db.starter_items(conn)
    assert conn.execute(text("SELECT count(*) FROM knowledge.skill")).scalar_one() >= 6


def test_live_review_audits_snapshots_and_rejects_stale_revision(review_connection):
    conn = review_connection
    before = new_skill(conn)
    key = {"skill_id": before["skill_id"]}
    db.decide("skill", key, db.revision(before), "REVIEWED", "Temporary review fixture.")
    after = read_skill(conn, before["skill_id"])
    assert after["review_status"] == "REVIEWED"
    audit = db.history("skill", key)["events"]
    assert len(audit) == 1
    assert audit[0]["before_snapshot"] == before
    assert audit[0]["after_snapshot"] == after
    assert audit[0]["reviewer"] == db.REVIEWER
    with pytest.raises(db.ReviewConflict, match="changed"):
        db.decide("skill", key, db.revision(before), "REJECTED", "Stale review must fail.")
    assert read_skill(conn, before["skill_id"])["review_status"] == "REVIEWED"
    assert len(db.history("skill", key)["events"]) == 1


def test_live_bulk_failure_rolls_back_decisions_and_audits(review_connection):
    conn = review_connection
    a, b = new_skill(conn), new_skill(conn)
    bad_item = {**item(b), "expected_revision": "f" * 64}
    with pytest.raises(db.ReviewConflict, match="changed"):
        db.bulk_decide([item(a), bad_item], "REVIEWED", "Atomic bulk review fixture.")
    for row in (a, b):
        assert read_skill(conn, row["skill_id"])["review_status"] == "PENDING"
        assert not db.history("skill", {"skill_id": row["skill_id"]})["events"]


def test_live_bulk_cycle_validation_rolls_back_every_edge(review_connection):
    conn = review_connection
    a, b = new_skill(conn, "REVIEWED"), new_skill(conn, "REVIEWED")
    rows = []
    for start, end in ((a, b), (b, a)):
        row = conn.execute(
            text("""
            INSERT INTO knowledge.skill_relation
                (from_skill_id,to_skill_id,relation_type,source,confidence,review_status)
            VALUES (:a,:b,'PREREQUISITE_OF','rollback-test',0.8,'PENDING')
            RETURNING to_jsonb(skill_relation)
        """),
            {"a": start["skill_id"], "b": end["skill_id"]},
        ).scalar_one()
        rows.append(row)
    items = [
        {
            "kind": "skill_relation",
            "key": {key: row[key] for key in db.KINDS["skill_relation"]},
            "expected_revision": db.revision(row),
        }
        for row in rows
    ]
    with pytest.raises(ValueError, match="cycle"):
        db.bulk_decide(items, "REVIEWED", "Cycle must roll back the whole bulk batch.")
    for entry in items:
        assert not db.history(entry["kind"], entry["key"])["events"]
    assert (
        conn.execute(
            text("""
        SELECT count(*) FROM knowledge.skill_relation WHERE source='rollback-test'
          AND review_status='REVIEWED'
    """)
        ).scalar_one()
        == 0
    )


def test_live_mapping_requires_reviewed_skills(review_connection):
    conn = review_connection
    skill = new_skill(conn)
    problem_id = conn.execute(text("SELECT problem_id FROM core.problem LIMIT 1")).scalar_one()
    row = conn.execute(
        text("""
        INSERT INTO knowledge.problem_skill
            (problem_id,skill_id,relation_type,role,importance,source,confidence,review_status)
        VALUES (:problem,:skill,'REQUIRES','primary',0.8,'rollback-test',0.8,'PENDING')
        RETURNING to_jsonb(problem_skill)
    """),
        {"problem": problem_id, "skill": skill["skill_id"]},
    ).scalar_one()
    key = {field: row[field] for field in db.KINDS["problem_skill"]}
    with pytest.raises(db.ReviewConflict, match="referenced skills"):
        db.decide("problem_skill", key, db.revision(row), "REVIEWED", "Review dependency fixture.")
    assert not db.history("problem_skill", key)["events"]


def test_live_stale_publish_never_reaches_graph(review_connection, monkeypatch):
    class Projector:
        def ensure_constraints(self, *args, **kwargs):
            raise AssertionError("Stale publication reached the graph")

    original = db.operator_module
    monkeypatch.setattr(
        db, "operator_module", lambda name: Projector() if name == "projector" else original(name)
    )
    with pytest.raises(db.ReviewConflict, match="changed"):
        db.publish("f" * 64)
