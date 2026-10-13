"""Live, rollback-only tests for quiz/activity admin authoring
(requirements/46_MICRO_COURSE_QUIZ_AUTHORING_API_GAPS.md QZA-1..7)."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import micro_course_service as courses
from mathbank_rest import quiz_service as quizzes


@pytest.fixture
def live_conn():
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in rollback-only quiz-authoring integration checks")
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def _make_draft_state(live_conn) -> tuple[str, str, str]:
    """Returns (canonical_code, release_id, state_id) for a fresh DRAFT course+release+state."""
    technique_id = live_conn.execute(text("SELECT technique_id FROM knowledge.technique LIMIT 1")).scalar_one_or_none()
    if technique_id is None:
        pytest.skip("Canonical technique seed rows are required")
    code = f"MC-QZA-TEST-{uuid4().hex[:10].upper()}"
    courses.create_course(
        live_conn, code, "Quiz authoring rollback test", "pytest",
        [{"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"}],
    )
    release_id = courses.create_release(live_conn, code, "pytest")
    state_id = courses.add_state(live_conn, release_id, "S001", 0, "ORIENTATION", "Start")
    return code, release_id, state_id


def _make_activity(live_conn, **overrides) -> str:
    defaults = dict(
        activity_type="MCQ", prompt="2+2=?", options=[{"text": "3"}, {"text": "4"}],
        correctness_policy={"correct_index": 1}, created_by="pytest",
    )
    defaults.update(overrides)
    result = quizzes.create_activity(live_conn, **defaults)
    return result["activity_id"]


def test_create_activity_is_instructor_created_and_static(live_conn):
    activity_id = _make_activity(live_conn)
    row = quizzes.get_activity(live_conn, activity_id)
    assert row["source_type"] == "INSTRUCTOR_CREATED"
    assert row["persistence_mode"] == "STATIC"
    assert row["activity_type"] == "MCQ"


def test_create_activity_rejects_unknown_activity_type(live_conn):
    with pytest.raises(ValueError, match="activity_type"):
        quizzes.create_activity(
            live_conn, activity_type="NOT_A_TYPE", prompt="x", options=[], correctness_policy={},
            created_by="pytest",
        )


def test_list_activities_filters_by_status(live_conn):
    activity_id = _make_activity(live_conn)
    quizzes.deactivate_activity(live_conn, activity_id, "pytest")
    active_only = quizzes.list_activities(live_conn, q="2+2", status="ACTIVE")
    assert all(item["activity_id"] != activity_id for item in active_only["items"])
    all_items = quizzes.list_activities(live_conn, q="2+2", status="ALL")
    assert any(item["activity_id"] == activity_id for item in all_items["items"])


def test_update_activity_changes_prompt(live_conn):
    activity_id = _make_activity(live_conn)
    updated = quizzes.update_activity(live_conn, activity_id, prompt="What is 2+2, truly?", actor="pytest")
    assert updated["prompt"] == "What is 2+2, truly?"


def test_update_activity_rejects_non_instructor_created(live_conn):
    activity_id = live_conn.execute(
        text("""
            INSERT INTO activity.definition (activity_type, prompt, source_type, persistence_mode, created_by)
            VALUES ('MCQ', 'precompiled prompt', 'PRECOMPILED', 'STATIC', 'seed')
            RETURNING activity_id
        """)
    ).scalar_one()
    with pytest.raises(quizzes.ActivityConflict, match="INSTRUCTOR_CREATED"):
        quizzes.update_activity(live_conn, str(activity_id), prompt="hacked", actor="pytest")


def test_update_activity_requires_at_least_one_field(live_conn):
    activity_id = _make_activity(live_conn)
    with pytest.raises(ValueError, match="at least one"):
        quizzes.update_activity(live_conn, activity_id, actor="pytest")


def test_skill_mapping_validates_and_sets(live_conn):
    skill_id = live_conn.execute(text("SELECT skill_id FROM knowledge.skill LIMIT 1")).scalar_one_or_none()
    if skill_id is None:
        pytest.skip("Canonical skill seed rows are required")
    activity_id = _make_activity(live_conn)
    updated = quizzes.set_skill_mapping(live_conn, activity_id, str(skill_id), "pytest")
    assert updated["target_skill_id"] == str(skill_id)

    with pytest.raises(quizzes.ActivityNotFound):
        quizzes.set_skill_mapping(live_conn, activity_id, str(uuid4()), "pytest")


def test_source_mapping_validates_and_sets(live_conn):
    problem_id = live_conn.execute(text("SELECT problem_id FROM core.problem LIMIT 1")).scalar_one_or_none()
    if problem_id is None:
        pytest.skip("Canonical problem seed rows are required")
    activity_id = _make_activity(live_conn)
    updated = quizzes.set_source_mapping(live_conn, activity_id, str(problem_id), "pytest")
    assert updated["source_problem_id"] == str(problem_id)


def test_deactivate_reactivate_round_trip(live_conn):
    activity_id = _make_activity(live_conn)
    deactivated = quizzes.deactivate_activity(live_conn, activity_id, "pytest")
    assert deactivated["status"] == "INACTIVE"
    with pytest.raises(quizzes.ActivityConflict, match="already deactivated"):
        quizzes.deactivate_activity(live_conn, activity_id, "pytest")
    reactivated = quizzes.reactivate_activity(live_conn, activity_id, "pytest")
    assert reactivated["status"] == "ACTIVE"


def test_attach_detach_activity_binding(live_conn):
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_activity(live_conn)

    courses.attach_activity(live_conn, state_id, activity_id, 0, "ENTRY_CHECK")
    release = courses.get_release(live_conn, release_id)
    bound_ids = [a["activity_id"] for a in release["states"][0]["activities"]]
    assert activity_id in bound_ids

    courses.detach_activity(live_conn, state_id, activity_id)
    release_after = courses.get_release(live_conn, release_id)
    bound_ids_after = [a["activity_id"] for a in release_after["states"][0]["activities"]]
    assert activity_id not in bound_ids_after


def test_attach_activity_rejects_deactivated_activity(live_conn):
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_activity(live_conn)
    quizzes.deactivate_activity(live_conn, activity_id, "pytest")
    with pytest.raises(ValueError, match="deactivated"):
        courses.attach_activity(live_conn, state_id, activity_id, 0, "ENTRY_CHECK")


def test_update_activity_binding_changes_purpose(live_conn):
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_activity(live_conn)
    courses.attach_activity(live_conn, state_id, activity_id, 0, "ENTRY_CHECK")
    courses.update_activity_binding(live_conn, state_id, activity_id, purpose="TRANSFER")
    release = courses.get_release(live_conn, release_id)
    activity = next(a for a in release["states"][0]["activities"] if a["activity_id"] == activity_id)
    assert activity["purpose"] == "TRANSFER"


def test_deactivate_blocked_while_bound_to_published_release(live_conn):
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_activity(live_conn)
    courses.attach_activity(live_conn, state_id, activity_id, 0, "ENTRY_CHECK")
    # Force the release to PUBLISHED directly (bypassing the full review/validate/publish
    # workflow, which is exercised elsewhere) to isolate this guard's own behavior.
    live_conn.execute(
        text("UPDATE pedagogy.micro_course_release SET status='PUBLISHED' WHERE release_id=:id"),
        {"id": release_id},
    )
    with pytest.raises(quizzes.ActivityConflict, match="published micro-course"):
        quizzes.deactivate_activity(live_conn, activity_id, "pytest")
