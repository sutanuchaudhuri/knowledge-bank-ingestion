"""Explicit live DB checks; fixtures and audit rows always roll back."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest.db import pedagogy_admin as admin
from mathbank_rest.db.postgres import engine

pytestmark = pytest.mark.skipif(
    os.getenv("MATHBANK_LIVE_PEDAGOGY_TEST") != "1", reason="Live Postgres opt-in"
)


def test_corpus_worker_selects_publication_jobs_without_ambiguous_status():
    from scripts.enrich_corpus import select_work

    with engine.connect() as conn:
        unpublished, remaining = select_work(conn, 1)
    assert len(remaining) <= 1
    assert all(isinstance(code, str) for code in unpublished + remaining)


def test_worker_prioritizes_due_retries_and_excludes_cooldown_and_exhaustion():
    from scripts.enrich_corpus import select_work

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            problem_id, code = conn.execute(
                text("""
                SELECT p.problem_id,p.canonical_code FROM core.problem p
                WHERE NOT EXISTS(SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id=p.problem_id)
                ORDER BY p.canonical_code DESC LIMIT 1
            """)
            ).one()
            conn.execute(
                text("""
                INSERT INTO knowledge.enrichment_job(problem_id,status,attempts,updated_at)
                VALUES(:id,'FAILED',1,'2000-01-01')
                ON CONFLICT(problem_id) DO UPDATE
                SET status='FAILED',attempts=1,updated_at='2000-01-01'
            """),
                {"id": problem_id},
            )
            assert select_work(conn, 1)[1] == [code]
            assert code not in select_work(conn, 10000, [code])[1]
            conn.execute(
                text("UPDATE knowledge.enrichment_job SET attempts=3 WHERE problem_id=:id"),
                {"id": problem_id},
            )
            assert code not in select_work(conn, 10000)[1]
            conn.execute(
                text(
                    "UPDATE knowledge.enrichment_job SET attempts=1,updated_at=now() WHERE problem_id=:id"
                ),
                {"id": problem_id},
            )
            assert code not in select_work(conn, 10000)[1]
        finally:
            transaction.rollback()


def test_cross_corpus_cycle_rolls_back_then_corrected_import_completes_atomically(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from mathbank_rest import enrichment

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            problem_id, code = conn.execute(
                text("""
                SELECT p.problem_id,p.canonical_code FROM core.problem p
                WHERE NOT EXISTS(SELECT 1 FROM knowledge.problem_skill s WHERE s.problem_id=p.problem_id)
                ORDER BY p.canonical_code DESC LIMIT 1
            """)
            ).one()
            suffix = uuid4().hex
            start, end = f"fixture-start-{suffix}", f"fixture-end-{suffix}"
            for slug in [start, end]:
                conn.execute(
                    text("""
                    INSERT INTO knowledge.skill(slug,name,objective,source,confidence)
                    VALUES(:slug,'Fixture skill','Compute a fixture sum','fixture',0.8)
                """),
                    {"slug": slug},
                )
            conn.execute(
                text("""
                INSERT INTO knowledge.skill_relation(from_skill_id,to_skill_id,relation_type,source,confidence)
                SELECT a.skill_id,b.skill_id,'PREREQUISITE_OF','fixture',0.8
                FROM knowledge.skill a,knowledge.skill b WHERE a.slug=:end AND b.slug=:start
            """),
                {"start": start, "end": end},
            )
            conn.execute(
                text("""
                INSERT INTO knowledge.enrichment_job(problem_id,status)
                VALUES(:id,'IN_PROGRESS') ON CONFLICT(problem_id)
                DO UPDATE SET status='IN_PROGRESS',published_at=NULL
            """),
                {"id": problem_id},
            )
            data = {
                "skills": [
                    {
                        "slug": start,
                        "name": "Fixture starting skill",
                        "objective": "Compute a fixture sum",
                        "level": 1,
                        "role": "prerequisite",
                        "prerequisite_for": [end],
                    },
                    {
                        "slug": end,
                        "name": "Fixture ending skill",
                        "objective": "Compute an exact fixture product",
                        "level": 2,
                        "role": "primary",
                        "prerequisite_for": [],
                    },
                ],
                "concept_slugs": [],
                "technique_slugs": [],
                "difficulty": {
                    "conceptual_depth": 1,
                    "technical_load": 1,
                    "algebraic_load": 1,
                    "insight_required": 1,
                    "number_of_steps": 1,
                    "prerequisite_depth": 1,
                    "estimated_contest_level": "Fixture",
                },
                "confidence": 0.8,
            }

            @contextmanager
            def begin():
                with conn.begin_nested():
                    yield conn

            monkeypatch.setattr(enrichment, "engine", SimpleNamespace(begin=begin))
            result = enrichment.TeachingMetadata.model_validate(data)
            manifest = enrichment.build_manifest(code, result, set(), set())
            with pytest.raises(ValueError, match=f"{start}|{end}"):
                enrichment.persist_metadata(problem_id, result, manifest, False)
            assert (
                conn.execute(
                    text("SELECT count(*) FROM knowledge.problem_skill WHERE problem_id=:id"),
                    {"id": problem_id},
                ).scalar_one()
                == 0
            )
            assert (
                conn.execute(
                    text("SELECT status FROM knowledge.enrichment_job WHERE problem_id=:id"),
                    {"id": problem_id},
                ).scalar_one()
                == "IN_PROGRESS"
            )
            data["skills"][0]["prerequisite_for"] = []
            result = enrichment.TeachingMetadata.model_validate(data)
            enrichment.persist_metadata(
                problem_id, result, enrichment.build_manifest(code, result, set(), set()), False
            )
            assert conn.execute(
                text(
                    "SELECT status,published_at FROM knowledge.enrichment_job WHERE problem_id=:id"
                ),
                {"id": problem_id},
            ).one() == ("COMPLETED", None)
            assert (
                conn.execute(
                    text("SELECT count(*) FROM knowledge.problem_skill WHERE problem_id=:id"),
                    {"id": problem_id},
                ).scalar_one()
                == 1
            )
            assert (
                conn.execute(
                    text("""
                SELECT count(*) FROM knowledge.skill_relation r
                JOIN knowledge.skill a ON r.from_skill_id=a.skill_id
                JOIN knowledge.skill b ON r.to_skill_id=b.skill_id
                WHERE a.slug=:end AND b.slug=:start
            """),
                    {"start": start, "end": end},
                ).scalar_one()
                == 1
            )
        finally:
            transaction.rollback()


def test_future_pending_is_auto_approved_and_human_rejection_is_protected():
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            row = conn.execute(
                text("""
                INSERT INTO knowledge.skill(slug,name,objective,source,confidence)
                VALUES(:slug,'Fixture skill','Compute a fixture sum','fixture',0.8)
                RETURNING skill_id,review_status,approval_method
            """),
                {"slug": f"auto-fixture-{uuid4()}"},
            ).first()
            assert row[1:] == ("REVIEWED", "automatic")
            conn.execute(text("SET LOCAL mathbank.human_review='on'"))
            conn.execute(
                text(
                    "UPDATE knowledge.skill SET review_status='REJECTED',"
                    "objective='Admin corrected objective' WHERE skill_id=:id"
                ),
                {"id": row[0]},
            )
            conn.execute(text("SET LOCAL mathbank.human_review='off'"))
            conn.execute(text("SET LOCAL mathbank.automatic_writer='on'"))
            conn.execute(
                text(
                    "UPDATE knowledge.skill SET review_status='PENDING',"
                    "objective='Machine overwrite' WHERE skill_id=:id"
                ),
                {"id": row[0]},
            )
            current = conn.execute(
                text(
                    "SELECT review_status,approval_method,objective "
                    "FROM knowledge.skill WHERE skill_id=:id"
                ),
                {"id": row[0]},
            ).first()
            assert current == ("REJECTED", "human", "Admin corrected objective")
            count = conn.execute(
                text(
                    "SELECT count(*) FROM knowledge.metadata_approval_event "
                    "WHERE after_snapshot->>'skill_id'=:id"
                ),
                {"id": str(row[0])},
            ).scalar_one()
            assert count == 1
        finally:
            transaction.rollback()


def test_human_correction_and_reapproval_snapshot_are_accurate():
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            row = conn.execute(
                text("""
                INSERT INTO knowledge.skill(slug,name,objective,source,confidence)
                VALUES(:slug,'Fixture skill','Compute a fixture sum','fixture',0.8)
                RETURNING to_jsonb(skill)
            """),
                {"slug": f"auto-human-fixture-{uuid4()}"},
            ).scalar_one()
            after = admin.change_decision(
                conn,
                "skill",
                {"skill_id": row["skill_id"]},
                admin.revision(row),
                "REVIEWED",
                "Verified fixture objective",
            )
            assert after["approval_method"] == "human"
            assert after["review_status"] == "REVIEWED"
            event = conn.execute(
                text(
                    "SELECT after_snapshot FROM knowledge.pedagogy_review_event "
                    "WHERE entity_key=CAST(:key AS jsonb)"
                ),
                {"key": '{"skill_id":"' + row["skill_id"] + '"}'},
            ).scalar_one()
            assert event == after
        finally:
            transaction.rollback()
