"""Opt-in, rollback-only verification on the explicitly selected configured database."""

import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from mathbank_rest.db import topic_pedagogy as db
from mathbank_rest.db.postgres import engine


@pytest.mark.skipif(os.getenv("TEST_TOPIC_FEEDBACK_DB") != "1",
                    reason="Requires an explicitly selected migrated database; rollback-only synthetic test.")
def test_real_feedback_snapshot_duplicate_review_labels_and_negative_gate(monkeypatch):
    student = uuid4()
    with engine.connect() as conn:
        transaction = conn.begin()

        class ScopedEngine:
            @contextmanager
            def connect(self):
                yield conn

            @contextmanager
            def begin(self):
                with conn.begin_nested():
                    yield conn

        try:
            monkeypatch.setattr(db, "engine", ScopedEngine())
            conn.execute(text("""
                INSERT INTO learner.student_profile(student_id,email,password_hash,status)
                VALUES (:student,:email,'DISABLED_SYNTHETIC_TEST','DISABLED')
            """), {"student": student, "email": f"synthetic-{student}@example.invalid"})
            baseline = db.topic_candidates("Power of point")["candidates"]
            assert len(baseline) >= 2, "Needs two qualifying published-step examples."
            code = baseline[0]["canonical_code"]
            reason = "Synthetic rollback-only relevance test, not a real learner allegation."
            report = db.submit_feedback(student, code, "Power of point", reason)
            assert report["status"] == "PENDING"
            assert report["audit"]["requested_node_id"] == "TECH.GEO.POWER_OF_A_POINT"
            assert report["audit"]["published_step_count"] > 0
            duplicate = db.submit_feedback(student, code, "Power of point", reason)
            assert duplicate["feedback_id"] == report["feedback_id"]
            assert duplicate["audit"] == report["audit"]
            assert code in [c["canonical_code"] for c in db.topic_candidates("Power of point")["candidates"]]

            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text("""
                    UPDATE learner.pedagogy_feedback SET retrieval_verdict='IRRELEVANT'
                    WHERE feedback_id=:id
                """), {"id": report["feedback_id"]})
            resolved = db.resolve_feedback(report["feedback_id"], "RESOLVED",
                "Synthetic review decision used only inside a rolled-back transaction.", "IRRELEVANT", "RETRIEVAL")
            assert resolved["retrieval_verdict"] == "IRRELEVANT"
            assert code not in [c["canonical_code"] for c in db.topic_candidates("Power of point")["candidates"]]
            assert db.resolve_feedback(report["feedback_id"], "RESOLVED", "A duplicate review is not permitted.") is None
            duplicate = db.submit_feedback(student, code, "Power of point", reason)
            assert duplicate["status"] == "RESOLVED" and duplicate["audit"] == report["audit"]

            positive_code = baseline[1]["canonical_code"]
            positive = db.submit_feedback(student, positive_code, "Power of point",
                "Synthetic positive-evidence test, not a real learner allegation.")
            db.resolve_feedback(positive["feedback_id"], "RESOLVED",
                "Synthetic source-relevance label, discarded on rollback.", "RELEVANT", "UNCLASSIFIED")
            examples = db.reviewed_retrieval_examples(500)["examples"]
            own_examples = [row for row in examples if row["review_reference"] in {
                report["feedback_id"], positive["feedback_id"]}]
            assert {row["retrieval_verdict"] for row in own_examples} == {"IRRELEVANT", "RELEVANT"}
            assert positive_code in [c["canonical_code"] for c in db.topic_candidates("Power of point")["candidates"]]
        finally:
            transaction.rollback()
            remaining = conn.execute(text(
                "SELECT count(*) FROM learner.student_profile WHERE student_id=:student"
            ), {"student": student}).scalar_one()
            assert remaining == 0, "Synthetic identity/report cleanup must be exact."
