"""Live, rollback-only tests for requirements/47 (student navigation v2 backend):
cross-kind sequence_position authoring + items[] flattening (MCN2-1/MCN2-2), the
gave_up third outcome on learning_item/activity responses (MCN2-7), and the scoped
item-help assist endpoint (MCN2-6)."""
import os
from uuid import uuid4

import pytest
from sqlalchemy import text

from mathbank_rest import micro_course_assist as assist
from mathbank_rest import micro_course_service as courses


@pytest.fixture
def live_conn():
    if os.environ.get("ROUTE_DB_TESTS") != "1":
        pytest.skip("Opt-in rollback-only micro-course item-sequence integration checks")
    from mathbank_rest.db.postgres import engine

    with engine.connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


def _approved_learning_item(conn) -> str | None:
    return conn.execute(text("""
        SELECT learning_item_id FROM pedagogy.learning_item
        WHERE review_status='APPROVED' AND student_visible
          AND jsonb_typeof(choices)='array' AND correct_answer IS NOT NULL
        LIMIT 1
    """)).scalar_one_or_none()


def _make_mcq_activity(conn, **overrides) -> str:
    defaults = dict(options='["A", "B"]', policy='{"correct_index": 1, "explanation": "B is correct."}')
    defaults.update(overrides)
    return str(conn.execute(
        text("""
        INSERT INTO activity.definition
            (activity_type, prompt, options, correctness_policy, source_type, persistence_mode, created_by)
        VALUES ('MCQ', 'Test prompt?', CAST(:options AS jsonb), CAST(:policy AS jsonb),
                'INSTRUCTOR_CREATED', 'STATIC', 'pytest')
        RETURNING activity_id
    """),
        defaults,
    ).scalar_one())


def _make_draft_state(conn) -> tuple[str, str, str]:
    technique_id = conn.execute(text("SELECT technique_id FROM knowledge.technique LIMIT 1")).scalar_one_or_none()
    if technique_id is None:
        pytest.skip("Canonical technique seed row is required")
    code = f"MC-ITEMSEQ-{uuid4().hex[:10].upper()}"
    courses.create_course(
        conn, code, "Item sequence rollback test", "pytest",
        [{"target_type": "TECHNIQUE", "target_id": str(technique_id), "role": "PRIMARY"}],
    )
    release_id = courses.create_release(conn, code, "pytest")
    state_id = courses.add_state(conn, release_id, "S001", 0, "ORIENTATION", "Start", required=False)
    return code, release_id, state_id


def test_items_array_falls_back_to_grouped_by_kind_when_unsequenced(live_conn):
    """MCN2-2: with no sequence_position authored anywhere, items[] preserves the
    pre-existing grouped-by-kind (asset, interaction, learning_item, activity) order."""
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_mcq_activity(live_conn)
    learning_item = _approved_learning_item(live_conn)
    if learning_item is None:
        pytest.skip("An approved/visible gradable learning_item seed row is required")
    courses.attach_learning_item(live_conn, state_id, learning_item, 0, "ENTRY_CHECK", required=False)
    courses.attach_activity(live_conn, state_id, activity_id, 0, "COMPREHENSION", required=False)

    preview = courses.get_course_preview(live_conn, code, release_id)
    state = preview["states"][0]
    assert all(item["sequence_position"] is None for item in state["items"])
    assert [item["item_kind"] for item in state["items"]] == ["learning_item", "activity"]


def test_items_array_honors_authored_cross_kind_sequence(live_conn):
    """MCN2-1: setting sequence_position reorders items[] across kinds, independent of
    each kind's own `ordinal`."""
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_mcq_activity(live_conn)
    learning_item = _approved_learning_item(live_conn)
    if learning_item is None:
        pytest.skip("An approved/visible gradable learning_item seed row is required")
    courses.attach_learning_item(live_conn, state_id, learning_item, 0, "ENTRY_CHECK", required=False)
    courses.attach_activity(live_conn, state_id, activity_id, 0, "COMPREHENSION", required=False)

    # Reverse the grouped-by-kind fallback order: activity first, learning_item second.
    courses.set_item_sequence_position(live_conn, state_id, "activity", activity_id, 0)
    courses.set_item_sequence_position(live_conn, state_id, "learning_item", learning_item, 1)

    preview = courses.get_course_preview(live_conn, code, release_id)
    state = preview["states"][0]
    assert [item["item_kind"] for item in state["items"]] == ["activity", "learning_item"]
    assert [item["sequence_position"] for item in state["items"]] == [0, 1]


def test_set_item_sequence_position_rejects_unknown_kind_and_unattached_item(live_conn):
    code, release_id, state_id = _make_draft_state(live_conn)
    with pytest.raises(ValueError):
        courses.set_item_sequence_position(live_conn, state_id, "bogus_kind", "x", 0)
    with pytest.raises(courses.MicroCourseNotFound):
        courses.set_item_sequence_position(live_conn, state_id, "activity", str(uuid4()), 0)


def test_set_item_sequence_position_blocked_on_published_release(live_conn):
    """The existing publish-immutability guard applies here too: a published release's
    items cannot be resequenced any more than they can be otherwise edited."""
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_mcq_activity(live_conn)
    courses.attach_activity(live_conn, state_id, activity_id, 0, "COMPREHENSION", required=False)
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    with pytest.raises(courses.MicroCourseConflict):
        courses.set_item_sequence_position(live_conn, state_id, "activity", activity_id, 0)


def _enroll(conn, code, student_id):
    return courses.start_enrollment(conn, code, str(student_id))["enrollment_id"]


def test_gave_up_is_recorded_as_a_distinct_third_outcome_on_learning_item(live_conn):
    """MCN2-7: a gave-up attempt is neither correct nor incorrect in the ordinary sense —
    it is flagged distinctly and reveals the answer immediately."""
    student_id = live_conn.execute(text("SELECT student_id FROM learner.student_profile LIMIT 1")).scalar_one_or_none()
    learning_item = _approved_learning_item(live_conn)
    if student_id is None or learning_item is None:
        pytest.skip("A student and an approved/visible gradable learning_item seed row are required")
    code, release_id, state_id = _make_draft_state(live_conn)
    courses.attach_learning_item(live_conn, state_id, learning_item, 0, "ENTRY_CHECK", required=False)
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    enrollment_id = _enroll(live_conn, code, student_id)

    result = courses.submit_learning_item_response(
        live_conn, enrollment_id, str(student_id), learning_item, None, gave_up=True
    )
    assert result["gave_up"] is True
    assert result["is_correct"] is False
    assert result["correct_answer"]

    event = live_conn.execute(text("""
        SELECT payload FROM learner.micro_course_state_event
        WHERE enrollment_id=:id AND event_type='QUIZ_RESPONSE'
    """), {"id": enrollment_id}).mappings().one()
    assert event["payload"]["gave_up"] is True
    assert event["payload"]["is_correct"] is False


def test_submit_learning_item_response_requires_choice_unless_gave_up(live_conn):
    student_id = live_conn.execute(text("SELECT student_id FROM learner.student_profile LIMIT 1")).scalar_one_or_none()
    learning_item = _approved_learning_item(live_conn)
    if student_id is None or learning_item is None:
        pytest.skip("A student and an approved/visible gradable learning_item seed row are required")
    code, release_id, state_id = _make_draft_state(live_conn)
    courses.attach_learning_item(live_conn, state_id, learning_item, 0, "ENTRY_CHECK", required=False)
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    enrollment_id = _enroll(live_conn, code, student_id)
    with pytest.raises(ValueError):
        courses.submit_learning_item_response(live_conn, enrollment_id, str(student_id), learning_item, None)


def test_gave_up_is_recorded_as_a_distinct_third_outcome_on_activity(live_conn):
    student_id = live_conn.execute(text("SELECT student_id FROM learner.student_profile LIMIT 1")).scalar_one_or_none()
    if student_id is None:
        pytest.skip("A student seed row is required")
    code, release_id, state_id = _make_draft_state(live_conn)
    activity_id = _make_mcq_activity(live_conn)
    courses.attach_activity(live_conn, state_id, activity_id, 0, "COMPREHENSION", required=False)
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    enrollment_id = _enroll(live_conn, code, student_id)

    result = courses.submit_activity_response(live_conn, enrollment_id, str(student_id), activity_id, gave_up=True)
    assert result["gave_up"] is True
    assert result["is_correct"] is False
    assert result["correct_choice_index"] == 1
    assert result["explanation"] == "B is correct."


def test_item_help_help_intent_never_reveals_answer(monkeypatch, live_conn):
    """MCN2-6: the "help" intent only ever sees grounding without a correct_answer/
    correct_index field, and the (mocked) model call is scoped to that grounding only."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from mathbank_rest import tutor

    student_id = live_conn.execute(text("SELECT student_id FROM learner.student_profile LIMIT 1")).scalar_one_or_none()
    learning_item = _approved_learning_item(live_conn)
    if student_id is None or learning_item is None:
        pytest.skip("A student and an approved/visible gradable learning_item seed row are required")
    code, release_id, state_id = _make_draft_state(live_conn)
    courses.attach_learning_item(live_conn, state_id, learning_item, 0, "ENTRY_CHECK", required=False)
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    enrollment_id = _enroll(live_conn, code, student_id)

    create = MagicMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"message": "Think about what the question is really asking."}'))]
        )
    )
    monkeypatch.setattr(tutor._client.chat.completions, "create", create)
    monkeypatch.setattr(tutor._client, "with_options", lambda **kwargs: tutor._client)

    result = assist.get_item_assist(
        live_conn, enrollment_id, str(student_id), "learning_item", learning_item, "help", "I'm stuck",
    )
    assert result["intent"] == "help"
    assert result["message"]
    sent_grounding = create.call_args.kwargs["messages"][1]["content"]
    assert "correct_answer" not in sent_grounding


def test_item_help_give_up_intent_reveals_and_records(live_conn):
    student_id = live_conn.execute(text("SELECT student_id FROM learner.student_profile LIMIT 1")).scalar_one_or_none()
    learning_item = _approved_learning_item(live_conn)
    if student_id is None or learning_item is None:
        pytest.skip("A student and an approved/visible gradable learning_item seed row are required")
    code, release_id, state_id = _make_draft_state(live_conn)
    courses.attach_learning_item(live_conn, state_id, learning_item, 0, "ENTRY_CHECK", required=False)
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    enrollment_id = _enroll(live_conn, code, student_id)

    result = assist.get_item_assist(
        live_conn, enrollment_id, str(student_id), "learning_item", learning_item, "give_up", None,
    )
    assert result["action"] == "revealed"
    assert result["gave_up"] is True
    assert result["correct_answer"]

    audit_rows = live_conn.execute(text("""
        SELECT count(*) FROM audit.action_log
        WHERE entity_type='MICRO_COURSE_ITEM' AND entity_id=:entity_id
    """), {"entity_id": f"learning_item:{learning_item}"}).scalar_one()
    assert audit_rows >= 1


def test_item_help_give_up_on_asset_is_a_skip_not_a_reveal(live_conn):
    """Non-gating kinds (asset/interaction) have no correct answer; "give up" converges
    with Skip (requirements/47 §3.3)."""
    student_id = live_conn.execute(text("SELECT student_id FROM learner.student_profile LIMIT 1")).scalar_one_or_none()
    asset_id = live_conn.execute(text("SELECT asset_id FROM visual.asset WHERE validation_status='VALID' LIMIT 1")).scalar_one_or_none()
    if student_id is None or asset_id is None:
        pytest.skip("A student and a valid asset seed row are required")
    code, release_id, state_id = _make_draft_state(live_conn)
    courses.attach_asset(live_conn, state_id, str(asset_id), 0, "PRIMARY")
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    enrollment_id = _enroll(live_conn, code, student_id)

    result = assist.get_item_assist(
        live_conn, enrollment_id, str(student_id), "asset", str(asset_id), "give_up", None,
    )
    assert result == {"intent": "give_up", "item_kind": "asset", "action": "skip", "gave_up": True}


def test_item_help_rejects_item_not_in_current_state(live_conn):
    student_id = live_conn.execute(text("SELECT student_id FROM learner.student_profile LIMIT 1")).scalar_one_or_none()
    learning_item = _approved_learning_item(live_conn)
    if student_id is None or learning_item is None:
        pytest.skip("A student and an approved/visible gradable learning_item seed row are required")
    code, release_id, state_id = _make_draft_state(live_conn)
    courses.review_release(live_conn, release_id, "APPROVED", "pytest")
    courses.publish_release(live_conn, release_id, "pytest")
    enrollment_id = _enroll(live_conn, code, student_id)

    with pytest.raises(courses.MicroCourseNotFound):
        assist.get_item_assist(
            live_conn, enrollment_id, str(student_id), "learning_item", learning_item, "give_up", None,
        )
