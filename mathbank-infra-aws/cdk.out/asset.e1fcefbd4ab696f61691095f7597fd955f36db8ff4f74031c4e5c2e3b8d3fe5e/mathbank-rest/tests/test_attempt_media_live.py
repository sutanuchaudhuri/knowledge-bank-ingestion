"""Opt-in Neon transactions; synthetic learner fixtures always roll back, no model calls."""

import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import attempt_media as runtime
from mathbank_rest.attempt_media_models import Assessment, Region, Transcript
from mathbank_rest.db.postgres import engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_ATTEMPT_MEDIA_LIVE") != "1", reason="explicit Neon opt-in"
)


@pytest.fixture
def fixture():
    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            student = conn.execute(
                text(
                    "INSERT INTO learner.student_profile(email,password_hash,display_name) "
                    "VALUES (:email,'synthetic-not-login-capable','Runtime test') RETURNING student_id"
                ),
                {"email": f"runtime-test-{uuid4()}@example.invalid"},
            ).scalar_one()
            problem = conn.execute(text("SELECT problem_id FROM core.problem LIMIT 1")).scalar_one()
            sid = conn.execute(
                text(
                    "INSERT INTO attempt_media.submission(student_id,problem_id) VALUES (:s,:p) RETURNING submission_id"
                ),
                {"s": student, "p": problem},
            ).scalar_one()
            asset = conn.execute(
                text(
                    "INSERT INTO attempt_media.media_asset(submission_id,asset_type,object_key,mime_type,sha256,"
                    "size_bytes,page_count) VALUES (:id,'IMAGE','synthetic-test-only','image/png',:hash,1,1) "
                    "RETURNING media_asset_id"
                ),
                {"id": sid, "hash": "0" * 64},
            ).scalar_one()
            actor = {"role": "STUDENT", "student_id": str(student)}
            evidence = Region(
                media_asset_id=asset,
                page_number=1,
                x_norm=0.1,
                y_norm=0.2,
                width_norm=0.3,
                height_norm=0.1,
            )
            transcript = Transcript(
                expected_version=1,
                regions=[evidence],
                steps=[
                    {
                        "ordinal": 1,
                        "plain_text": "1+1=3",
                        "latex_text": "1+1=3",
                        "step_type": "ALGEBRA",
                        "confidence": 0.9,
                        "evidence_ids": [evidence.region_id],
                    }
                ],
            )
            yield conn, sid, actor, transcript
        finally:
            transaction.rollback()


def test_approval_is_explicit_idempotent_and_does_not_grade_pending_work(fixture):
    conn, sid, actor, transcript = fixture
    assert (
        conn.execute(
            text("SELECT count(*) FROM attempt_media.approval WHERE submission_id=:id"), {"id": sid}
        ).scalar_one()
        == 0
    )
    saved = runtime.save_transcript(conn, sid, actor, transcript, machine={"raw": "1+1=3"})
    assert saved["transcription_version"] == 2
    approved = runtime.approve(conn, sid, actor, 2)
    again = runtime.approve(conn, sid, actor, 2)
    assert again["learner_attempt_id"] == approved["learner_attempt_id"]
    assert (
        conn.execute(
            text("SELECT is_correct FROM learner.attempt WHERE attempt_id=:id"),
            {"id": approved["learner_attempt_id"]},
        ).scalar()
        is None
    )
    assert runtime.snapshot(conn, sid, actor)["steps"][0]["latex_text"] == "1+1=3"


def test_edit_invalidates_analysis_and_preserves_approved_history(fixture):
    conn, sid, actor, transcript = fixture
    saved = runtime.save_transcript(conn, sid, actor, transcript)
    runtime.approve(conn, sid, actor, 2)
    assessment = Assessment(
        step_id=saved["steps"][0]["step_id"],
        correctness="INCORRECT",
        alignment_type="UNSUPPORTED_LEAP",
        confidence=0.9,
        why="Arithmetic mismatch",
        next_action="Recheck the sum",
        evidence_ids=transcript.steps[0].evidence_ids,
    )
    runtime.save_assessments(conn, sid, actor, 2, [assessment])
    changed = transcript.model_copy(update={"expected_version": 2, "regions": None})
    changed.steps[0].latex_text = "1+1=2"
    runtime.save_transcript(conn, sid, actor, changed)
    view = runtime.snapshot(conn, sid, actor)
    assert view["transcription_version"] == 3 and view["assessments"] == []
    assert (
        conn.execute(
            text("SELECT latex_text FROM attempt_media.approved_step WHERE submission_id=:id"),
            {"id": sid},
        ).scalar_one()
        == "1+1=3"
    )
    with pytest.raises(runtime.MediaError, match="TRANSCRIPTION_VERSION_CONFLICT"):
        runtime.save_assessments(conn, sid, actor, 2, [assessment])


def test_instructor_override_is_append_only_and_survives_ai_retry(fixture):
    conn, sid, actor, transcript = fixture
    saved = runtime.save_transcript(conn, sid, actor, transcript)
    runtime.approve(conn, sid, actor, 2)
    assessment = Assessment(
        step_id=saved["steps"][0]["step_id"],
        correctness="UNJUSTIFIED",
        alignment_type="UNMATCHED_BUT_PLAUSIBLE",
        confidence=0.9,
        why="Needs justification",
        next_action="Explain the move",
        evidence_ids=transcript.steps[0].evidence_ids,
    )
    runtime.save_assessments(conn, sid, actor, 2, [assessment])
    override = assessment.model_copy(
        update={
            "correctness": "CORRECT",
            "alignment_type": "VALID_ALTERNATE_STEP",
            "why": "Instructor verified an alternate method",
        }
    )
    runtime.save_assessments(
        conn, sid, {"role": "ADMIN", "student_id": None}, 2, [override], source="INSTRUCTOR"
    )
    runtime.save_assessments(conn, sid, actor, 2, [assessment])
    view = runtime.snapshot(conn, sid, {"role": "ADMIN", "student_id": None})
    assert view["assessments"][0]["source"] == "INSTRUCTOR"
    assert len(view["assessment_history"]) == 2
    assert view["assessment_history"][0]["correctness"] == "UNJUSTIFIED"


def test_private_evidence_never_leaks_to_another_student(fixture):
    conn, sid, actor, transcript = fixture
    runtime.save_transcript(conn, sid, actor, transcript)
    other = {"role": "STUDENT", "student_id": str(uuid4())}
    for read in (runtime.snapshot, lambda c, i, a: runtime.events(c, i, a, 0)):
        with pytest.raises(runtime.MediaError, match="SUBMISSION_NOT_FOUND"):
            read(conn, sid, other)


def test_low_confidence_cannot_be_graded_as_a_student_mistake(fixture):
    conn, sid, actor, transcript = fixture
    transcript.steps[0].confidence = 0.4
    saved = runtime.save_transcript(conn, sid, actor, transcript)
    runtime.approve(conn, sid, actor, 2)
    assessment = Assessment(
        step_id=saved["steps"][0]["step_id"],
        correctness="INCORRECT",
        alignment_type="UNMATCHED_BUT_PLAUSIBLE",
        confidence=0.8,
        why="OCR uncertain",
        next_action="Review the original",
        evidence_ids=transcript.steps[0].evidence_ids,
    )
    with pytest.raises(runtime.MediaError, match="LOW_CONFIDENCE_REQUIRES_UNCERTAIN"):
        runtime.save_assessments(conn, sid, actor, 2, [assessment])


def test_media_purge_metadata_keeps_approved_content(fixture):
    conn, sid, actor, transcript = fixture
    runtime.save_transcript(conn, sid, actor, transcript)
    runtime.approve(conn, sid, actor, 2)
    conn.execute(
        text("UPDATE attempt_media.media_asset SET purged_at=now() WHERE submission_id=:id"),
        {"id": sid},
    )
    view = runtime.snapshot(conn, sid, actor)
    assert view["steps"][0]["latex_text"] == "1+1=3"
    assert view["assets"][0]["purged_at"] is not None
    assert len(view["approvals"]) == 1
