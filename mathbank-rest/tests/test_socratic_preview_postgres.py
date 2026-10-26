"""Synthetic preview integration on the explicitly authorized target; every test rolls back."""
import json
import os
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from mathbank_rest import socratic_preview as preview
from mathbank_rest import socratic_service as service
from mathbank_rest.activity_scoring import AR_OPTIONS
from mathbank_rest.db.postgres import engine
from mathbank_rest.socratic_auth import StaffActor
from mathbank_rest.socratic_contracts import (
    CreateWorkflow,
    PreviewCommand,
    Program,
    Respond,
    Simulate,
    Transition,
    UpdateWorkflow,
)

pytestmark = pytest.mark.skipif(os.getenv("SOCRATIC_DB_TESTS") != "1",
                                reason="Set SOCRATIC_DB_TESTS=1 for the explicitly authorized REST-configured target")


@pytest.fixture
def db(monkeypatch):
    with engine.connect() as conn:
        transaction = conn.begin()

        class BoundEngine:
            @contextmanager
            def connect(self):
                yield conn

            @contextmanager
            def begin(self):
                with conn.begin_nested():
                    yield conn

        monkeypatch.setattr(service, "engine", BoundEngine())
        yield conn
        transaction.rollback()


@pytest.fixture
def actor():
    return StaffActor(actor_id="synthetic:socratic-test:" + str(uuid4()),
                      username="Synthetic preview acceptance", capabilities=["author"])


def activity(db, activity_type, options, policy, *, status="ACTIVE", source_problem_id=None):
    return str(db.execute(text("""
        INSERT INTO activity.definition (activity_type,prompt,options,correctness_policy,source_type,created_by,
                                         status,source_problem_id)
        VALUES (:type,:prompt,CAST(:options AS jsonb),CAST(:policy AS jsonb),'INSTRUCTOR_CREATED',
                'synthetic:socratic-test',:status,:problem)
        RETURNING activity_id
    """), {"type": activity_type, "prompt": f"Synthetic {activity_type} prompt", "options": json.dumps(options),
           "policy": json.dumps(policy), "status": status, "problem": source_problem_id}).scalar_one())


def ar_activity(db):
    # AR1: both true and R explains A.
    return activity(db, "MCQ", list(AR_OPTIONS), {
        "correct_index": 0, "explanation": "Stars and bars gives C(7,2)=21.",
        "hints": ["Count arrangements of stars and bars.", "There are 7 symbols, 2 of them bars."],
        "assertion_reason": {"assertion_true": True, "reason_true": True, "reason_explains": True}})


def journey(db, actor, *, quiz_ref=None, max_transitions=30, extra_nodes=()):
    workflow = service.create_workflow(CreateWorkflow(title="Synthetic preview", domain="Algebra"), actor, "c-" + str(uuid4()))
    numeric = activity(db, "NUMERIC", [], {"correct_value": 0.75, "explanation": "3/4."})
    program = Program.model_validate({
        "strategy_code": workflow.program.strategy_code, "source": {}, "entry": "start",
        "fallback_key": "review", "max_transitions": max_transitions,
        "nodes": [
            {"key": "start", "label": "Start", "type": "START", "prompt": "Begin."},
            {"key": "quiz", "label": "AR check", "type": "QUIZ", "prompt": "Judge A and R.",
             "activity_ref": quiz_ref or ar_activity(db)},
            {"key": "fix", "label": "Remediate", "type": "REMEDIATION", "prompt": "Compute.", "activity_ref": numeric},
            {"key": "lesson", "label": "Lesson", "type": "LESSON", "prompt": "Generalize."},
            {"key": "review", "label": "Review", "type": "HUMAN_REVIEW", "prompt": "Staff review."},
            {"key": "complete", "label": "Done", "type": "COMPLETE", "prompt": "Reflect."},
            *extra_nodes,
        ],
        "edges": [
            {"from_key": "start", "to_key": "quiz", "outcome": "ALWAYS", "priority": 0},
            {"from_key": "quiz", "to_key": "lesson", "outcome": "SUCCESS", "priority": 0},
            {"from_key": "quiz", "to_key": "fix", "outcome": "RETRY", "priority": 0},
            {"from_key": "quiz", "to_key": "review", "outcome": "RETRY", "priority": 5},
            {"from_key": "fix", "to_key": "quiz", "outcome": "SUCCESS", "priority": 0},
            {"from_key": "lesson", "to_key": "complete", "outcome": "ALWAYS", "priority": 0},
            {"from_key": "review", "to_key": "complete", "outcome": "ALWAYS", "priority": 0},
        ],
    })
    saved = service.update_workflow(workflow.workflow_id, UpdateWorkflow(expected_hash=workflow.content_hash, program=program),
                                    actor, "u-" + str(uuid4()))
    return saved


def cmd(state, **extra):
    return {"expected_version": state["state_version"], "idempotency_key": str(uuid4()), **extra}


def answer(actor, state, response):
    return preview.respond(state["preview_id"], Respond(**cmd(
        state, current_node_key=state["current_node"]["key"], activity_id=state["activity"]["activity_id"],
        activity_revision=state["activity"]["revision"], response=response)), actor)


def go(actor, state, outcome="ALWAYS"):
    return preview.transition(state["preview_id"], Transition(**cmd(state, outcome=outcome)), actor)


def test_full_synthetic_journey_scores_routes_and_records_assistance(db, actor):
    workflow = journey(db, actor)
    learner_counts = db.execute(text(
        "SELECT (SELECT count(*) FROM activity.response),(SELECT count(*) FROM learner.attempt),"
        "(SELECT count(*) FROM learner.micro_course_state_event)")).one()
    state = preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor)
    assert state["synthetic"] and state["current_node"]["key"] == "start" and state["history"] == []
    state = go(actor, state)
    activity_dto = state["activity"]
    assert activity_dto["kind"] == "ASSERTION_REASON" and [o["key"] for o in activity_dto["options"]] == [
        "AR1", "AR2", "AR3", "AR4", "AR5"]
    serialized = json.dumps(state)
    for private in ('"correct_index"', '"assertion_reason"', '"explanation"', '"hints"', '"policy"',
                    "Stars and bars gives", "Count arrangements"):
        assert private not in serialized
    state = answer(actor, state, {"selected_keys": ["AR2"]})
    assert state["current_node"]["key"] == "fix" and state["history"][-1]["rule_id"] == "quiz:RETRY:0"
    assert state["history"][-1]["outcome"] == "RETRY" and "Not yet" in state["feedback"]
    evidence = db.execute(text("""
        SELECT evidence FROM orchestration.socratic_preview_event WHERE preview_id=:id AND action='RESPOND'
    """), {"id": state["preview_id"]}).scalar_one()
    assert evidence["entailment_correct"] is False and evidence["assertion_truth_correct"] is True
    with pytest.raises(HTTPException) as invalid:
        answer(actor, state, {"text": "seven"})
    assert invalid.value.status_code == 422
    state = answer(actor, state, {"text": "3/4"})
    assert state["current_node"]["key"] == "quiz" and state["history"][-1]["outcome"] == "SUCCESS"
    state = preview.assist(state["preview_id"], PreviewCommand(**cmd(state)), actor)
    assert state["help"] == {"level": 1, "text": "Count arrangements of stars and bars.", "assisted": True}
    state = answer(actor, state, {"selected_keys": ["AR1"]})
    assert state["current_node"]["key"] == "lesson" and state["history"][-1]["assisted"] is True
    assert "help" not in state or state["help"] is None
    state = go(actor, state)
    assert state["status"] == "COMPLETE" and state["current_node"]["key"] == "complete"
    assert state["transitions_used"] == 5
    assert preview.get_preview(state["preview_id"], actor) == state
    assert db.execute(text(
        "SELECT (SELECT count(*) FROM activity.response),(SELECT count(*) FROM learner.attempt),"
        "(SELECT count(*) FROM learner.micro_course_state_event)")).one() == learner_counts
    with pytest.raises(HTTPException) as ended:
        go(actor, state)
    assert ended.value.status_code == 409


def test_replay_conflict_stale_version_and_owner_isolation(db, actor):
    workflow = journey(db, actor)
    state = preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor)
    body = Transition(**cmd(state, outcome="ALWAYS"))
    moved = preview.transition(state["preview_id"], body, actor)
    assert preview.transition(state["preview_id"], body, actor) == moved
    assert db.execute(text("SELECT count(*) FROM orchestration.socratic_preview_event WHERE preview_id=:id"),
                      {"id": state["preview_id"]}).scalar_one() == 2
    changed = body.model_copy(update={"outcome": "SUCCESS"})
    for attempt, code in ((changed, "SOCRATIC_IDEMPOTENCY_CONFLICT"),
                          (Transition(**cmd(state, outcome="ALWAYS")), "SOCRATIC_PREVIEW_STALE")):
        with pytest.raises(HTTPException) as conflict:
            preview.transition(state["preview_id"], attempt, actor)
        assert conflict.value.status_code == 409 and conflict.value.detail["code"] == code
    other = actor.model_copy(update={"actor_id": "synthetic:socratic-test:other"})
    with pytest.raises(HTTPException) as hidden:
        preview.get_preview(state["preview_id"], other)
    assert hidden.value.status_code == 404
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(text("UPDATE orchestration.socratic_preview_event SET reason='edited' WHERE preview_id=:id"),
                   {"id": state["preview_id"]})


def test_preview_pins_draft_hash_and_activity_snapshot(db, actor):
    quiz = ar_activity(db)
    workflow = journey(db, actor, quiz_ref=quiz)
    with pytest.raises(HTTPException) as stale:
        preview.start_preview(workflow.workflow_id, Simulate(expected_hash="0" * 64), actor)
    assert stale.value.status_code == 409
    state = go(actor, preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor))
    pinned = state["activity"]["revision"]
    db.execute(text("""
        UPDATE activity.definition SET correctness_policy=jsonb_set(correctness_policy,'{correct_index}','4')
        WHERE activity_id=:id
    """), {"id": quiz})
    result = answer(actor, state, {"selected_keys": ["AR1"]})
    assert result["history"][-1]["outcome"] == "SUCCESS"  # scored against the pinned snapshot
    with pytest.raises(HTTPException) as unsupported:
        preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor)
    assert unsupported.value.status_code == 422  # changed key now disagrees with AR judgments
    db.execute(text("""
        UPDATE activity.definition SET correctness_policy=jsonb_set(correctness_policy,'{explanation}','"Edited."')
        WHERE activity_id=:id
    """), {"id": quiz})
    db.execute(text("""
        UPDATE activity.definition SET correctness_policy=jsonb_set(correctness_policy,'{correct_index}','0')
        WHERE activity_id=:id
    """), {"id": quiz})
    fresh = go(actor, preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor))
    assert fresh["activity"]["revision"] != pinned
    program = workflow.program.model_copy(deep=True)
    program.nodes[0].prompt = "Edited start."
    service.update_workflow(workflow.workflow_id, UpdateWorkflow(expected_hash=workflow.content_hash, program=program),
                            actor, "edit-" + str(uuid4()))
    with pytest.raises(HTTPException) as changed:
        go(actor, fresh)
    assert changed.value.detail["code"] == "SOCRATIC_PREVIEW_DRAFT_CHANGED"
    with pytest.raises(HTTPException) as screen:
        preview.respond(state["preview_id"], Respond(**cmd(
            result, current_node_key="quiz", activity_id=quiz, activity_revision=pinned,
            response={"selected_keys": ["AR1"]})), actor)
    assert screen.value.status_code == 409


def test_reveal_caps_success_and_hint_reveal_limits(db, actor):
    workflow = journey(db, actor)
    state = go(actor, preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor))
    for _ in range(2):
        state = preview.assist(state["preview_id"], PreviewCommand(**cmd(state)), actor)
    assert state["help"]["level"] == 2
    with pytest.raises(HTTPException) as exhausted:
        preview.assist(state["preview_id"], PreviewCommand(**cmd(state)), actor)
    assert exhausted.value.detail["code"] == "SOCRATIC_NO_MORE_HINTS"
    state = preview.reveal(state["preview_id"], PreviewCommand(**cmd(state)), actor)
    assert state["feedback"].startswith("Assisted reveal:")
    with pytest.raises(HTTPException) as again:
        preview.reveal(state["preview_id"], PreviewCommand(**cmd(state)), actor)
    assert again.value.detail["code"] == "SOCRATIC_ALREADY_REVEALED"
    state = answer(actor, state, {"selected_keys": ["AR1"]})
    # No UNCERTAIN/ALWAYS rule from quiz: the uncapped SUCCESS edge must not be used.
    assert state["history"][-1]["outcome"] == "UNCERTAIN" and state["current_node"]["key"] == "review"
    assert state["history"][-1]["decision_source"] == "DETERMINISTIC_EVALUATION:FALLBACK"


def test_free_form_abstains_and_budget_exhaustion_routes_to_fallback(db, actor):
    written = activity(db, "SHORT_RESPONSE", [], {})
    workflow = journey(db, actor, quiz_ref=written, max_transitions=1)
    state = go(actor, preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor))
    assert state["activity"]["kind"] == "FREE_FORM_REASONING" and "options" not in state["activity"]
    state = answer(actor, state, {"text": "Use a bijection with stars and bars."})
    assert state["history"][-1]["decision_source"] == "DETERMINISTIC_EVALUATION:BUDGET_EXHAUSTED"
    assert state["status"] == "COMPLETE" and state["current_node"]["key"] == "review"
    assert "not auto-scored" in state["feedback"]


@pytest.mark.parametrize("binding", ["poll", "inactive", "cross_source", "not_uuid"])
def test_unsupported_bindings_fail_visibly_and_appear_in_validation(db, actor, binding):
    problem = db.execute(text("SELECT problem_id::text FROM core.problem LIMIT 1")).scalar_one()
    ref = {
        "poll": lambda: activity(db, "LIVE_POLL", [{"label": "A"}], {"correct_option": "A"}),
        "inactive": lambda: activity(db, "MCQ", ["a", "b"], {"correct_index": 0}, status="INACTIVE"),
        "cross_source": lambda: activity(db, "MCQ", ["a", "b"], {"correct_index": 0}, source_problem_id=problem),
        "not_uuid": lambda: "quiz-42",
    }[binding]()
    workflow = journey(db, actor, quiz_ref=ref)
    with pytest.raises(HTTPException) as refused:
        preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash), actor)
    assert refused.value.status_code == 422 and refused.value.detail["code"] == "SOCRATIC_ACTIVITY_UNSUPPORTED"
    report = service.validate_workflow(workflow.workflow_id, workflow.content_hash, actor)
    assert any(finding.startswith("Node quiz:") for finding in report.findings)


def test_requested_resource_start_must_be_reachable_activity(db, actor):
    workflow = journey(db, actor, extra_nodes=(
        {"key": "orphan", "label": "Orphan", "type": "TOPIC", "prompt": "Unreachable."},))
    started = preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash,
                                                                   start_node_key="quiz"), actor)
    assert started["current_node"]["key"] == "quiz" and started["activity"]["kind"] == "ASSERTION_REASON"
    for key in ("orphan", "review", "complete"):
        with pytest.raises(HTTPException) as refused:
            preview.start_preview(workflow.workflow_id, Simulate(expected_hash=workflow.content_hash,
                                                                 start_node_key=key), actor)
        assert refused.value.status_code == 422
