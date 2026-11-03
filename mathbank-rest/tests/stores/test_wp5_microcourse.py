"""WP5 micro-course area of the learner store on DynamoDB (requirement 71 WP5; access patterns A26-A32, write paths T21-T26).

moto only: ``content_table`` seeded with the WP4 logical course (release snapshot, answer keys, an interaction instance) next to the
learner table. The DynamoDB backend is exercised directly and through the student routes; the PostgreSQL side of the parity
checks runs the REAL ``micro_course_service`` / ``micro_course_assist`` SQL code against an in-memory SQL stand-in (``PgWorld``) that
interprets the handful of statements those functions issue, so both backends serve the same scenario and their responses are diffed.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import pytest
from fastapi import Header
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))
import test_wp4_learning as wp4
from parity_harness import ParityCase, assert_parity

from mathbank_rest import interaction_runtime as ixrt
from mathbank_rest import micro_course_assist as assist
from mathbank_rest import micro_course_service as courses
from mathbank_rest import security, stores
from mathbank_rest.config import settings
from mathbank_rest.main import app
from mathbank_rest.models import base
from mathbank_rest.models.ddb.learner import LearnerProfile
from mathbank_rest.models.manual import learner_microcourse as mc
from mathbank_rest.routers import micro_courses as mc_router
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore, PostgresContentStore
from mathbank_rest.stores.errors import IdempotencyKeyReused, ValidationFailed
from mathbank_rest.stores.learner import DynamoDBLearnerStore, PostgresLearnerStore
from mathbank_rest.stores.learner.microcourse import MicroCourseDynamoDB, MicroCoursePostgres
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork

CODE = "MC-1"
STORE = MicroCourseDynamoDB()
WHEN = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)
TEMPLATE_VERSION = wp4.uid(200)
MISCONCEPTION = wp4.uid(300)


def seed_profile(sid: str, **over) -> None:
    typed.put_new(LearnerProfile(**{
        "PK": toolkit.student_pk(sid), "SK": "PROFILE", "student_id": sid, "email": f"{sid[:6]}@x.org", "email_lc": f"{sid[:6]}@x.org",
        "first_name": "Ada", "last_name": "Lovelace", "display_name": "Ada L", "password_hash": "h", "search_blob": "ada",
        "status": "ACTIVE", "is_anonymous": False, "token_version": 1, "version": 1, "created_at": WHEN, **over}))


def seed_interaction() -> None:
    wp4.put(wp4.item(f"IINST#{wp4.INTERACTION1}", "META", "IINST", interaction_instance_id=wp4.INTERACTION1,
                     interaction_template_version_id=TEMPLATE_VERSION, template_key="TRANSITION_MATRIX_EDITOR_V1",
                     template_version=1, canonical_code="INT-1", title="Slider", instance_config={"a": 1},
                     initial_state={"x": 0}, learning_objective="explore", success_criteria={"type": "x"},
                     source_content_hash=wp4.SHA, review_status="APPROVED", approved_at=wp4.NOW, concept_ids=[], skill_ids=[],
                     technique_ids=[], misconception_ids=[]))


@pytest.fixture()
def world(content_table):
    """The WP4 logical course in mb-content, the DynamoDB content store, an ACTIVE student in mb-learner."""
    wp4.seed_course()
    wp4.seed_keys()
    seed_interaction()
    student = str(uuid.uuid4())
    seed_profile(student)
    with stores.override_store("content", DynamoDBContentStore()):
        yield student


def enroll(student: str, **kw) -> dict:
    return STORE.start_enrollment(None, CODE, student, **kw)


def eid_of(runtime: dict) -> str:
    return runtime["enrollment_id"]


def partition(student: str) -> list:
    out, token = [], None
    while True:
        page = typed.query("learner", toolkit.student_pk(student), limit=200, next_token=token)
        out += page.items
        token = page.next_token
        if not token:
            return out


def items_of(student: str, kind: type) -> list:
    return [i for i in partition(student) if isinstance(i, kind)]


def correct_choice(runtime: dict) -> int:
    return 1                                    # LI1: choices ["a", "b"], key "b"


# ------------------------------------------------------------------------------------------------ models

def test_models_accept_every_migrated_shape():
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "mathbank-db"))
    try:
        from aws import common
        from aws.dynamo.specs import learner as spec
    except ImportError:
        pytest.skip("mathbank-db is not importable")
    finally:
        sys.path.remove(str(Path(__file__).resolve().parents[3] / "mathbank-db"))
    sid, eid, course, rel, state = (str(uuid.uuid4()) for _ in range(5))
    ev, ix, inst, mid, evid = (str(uuid.uuid4()) for _ in range(5))
    t0 = dt.datetime(2026, 10, 6, 0, 55, 3, 270501, tzinfo=dt.UTC)
    last = {"LI-1": {"kind": "QUIZ_RESPONSE", "event_id": ev, "state_id": state, "created_at": "2026-10-06T00:55:03.270501Z",
                     "payload": {"learning_item_id": "LI-1", "choice_index": 1, "is_correct": True, "gave_up": False}},
            ev: {"kind": "ACTIVITY_RESPONSE", "event_id": ev, "state_id": state, "created_at": "2026-10-06T00:55:03.270501Z",
                 "payload": {"activity_id": ev, "is_correct": False, "value": 4}}}
    rows = [
        (spec._enroll, {"enrollment_id": eid, "student_id": sid, "micro_course_id": course, "release_id": rel, "status": "IN_PROGRESS",
                        "started_at": t0, "completed_at": None, "canonical_code": CODE, "current_state_id": state,
                        "state_version": 3, "runtime_updated_at": t0, "holds_open_sentinel": True, "last_responses": last}),
        (spec._enroll, {"enrollment_id": eid, "student_id": sid, "micro_course_id": course, "release_id": rel, "status": "COMPLETED",
                        "started_at": t0, "completed_at": t0, "canonical_code": CODE, "current_state_id": state,
                        "state_version": 7, "runtime_updated_at": t0, "holds_open_sentinel": False, "last_responses": None}),
        (spec._mcevent, {"event_id": ev, "enrollment_id": eid, "state_id": state, "event_type": "STATE_CHANGED",
                         "payload": {"action": "CONTINUE"}, "created_at": t0, "student_id": sid, "release_id": rel}),
        (spec._mcevent, {"event_id": ev, "enrollment_id": eid, "state_id": state, "event_type": "ENROLLED",
                         "payload": {"canonical_code": CODE}, "created_at": t0, "student_id": sid, "release_id": rel}),
        (spec._ixevent, {"interaction_event_id": ix, "student_id": sid, "enrollment_id": eid, "course_state_id": state,
                         "interaction_instance_id": inst, "event_type": "CHANGE", "semantic_action": "SET_VALUE",
                         "control_key": "slider", "object_id": None, "before_state": {"x": 0}, "action_payload": {"value": 0.5},
                         "after_state": {"x": 0.5}, "evaluation_outcome": None, "error_signature": None, "created_at": t0}),
        (spec._ixevent, {"interaction_event_id": ix, "student_id": sid, "enrollment_id": eid, "course_state_id": state,
                         "interaction_instance_id": inst, "event_type": "SUBMIT", "semantic_action": "SUBMIT_ROW",
                         "control_key": None, "object_id": "r1", "before_state": None, "action_payload": {"row": [1, 0]},
                         "after_state": None, "evaluation_outcome": "ERROR", "error_signature": "ROW_SUM_INVALID", "created_at": t0}),
        (spec._misc_evidence, {"evidence_id": evid, "student_id": sid, "interaction_event_id": ix, "misconception_id": mid,
                               "evidence_type": "OBSERVED_ERROR", "evidence_weight": 0.4, "confidence_before": 0.0,
                               "confidence_after": 0.4, "created_at": t0}),
        (spec._misc_state, {"student_id": sid, "misconception_id": mid, "evidence_id": evid, "confidence_after": 1, "created_at": t0}),
    ]
    seen = set()
    for transform, row in rows:
        for raw in transform(row) or ():
            item = common.clean_item(raw)
            for k in [k for k in item if k.startswith("GSI") and k.endswith(("PK", "SK")) and item[k] in ("", None)]:
                del item[k]
            item = toolkit.decode(item)
            model = base.parse_item("learner", item)
            seen.add(type(model))
            assert model.to_item(strict=False)["PK"] == item["PK"]
    assert {mc.LearnerEnroll, mc.LearnerEnrollOwner, mc.LearnerUniqueOpenEnroll, mc.LearnerMcevent, mc.LearnerIxevent,
            mc.LearnerMiscevid, mc.LearnerMiscstate} <= seen


def test_refinements_replace_the_generated_models_and_enforce_the_constraints():
    for item_type, model in (("ENROLL", mc.LearnerEnroll), ("MCEVENT", mc.LearnerMcevent), ("IXEVENT", mc.LearnerIxevent),
                             ("MISCSTATE", mc.LearnerMiscstate), ("MISCEVID", mc.LearnerMiscevid),
                             ("UNIQUE_OPEN_ENROLL", mc.LearnerUniqueOpenEnroll), ("ENROLL_OWNER", mc.LearnerEnrollOwner)):
        assert base.model_for("learner", item_type) is model
    sid, mid = str(uuid.uuid4()), str(uuid.uuid4())
    good = {"PK": toolkit.student_pk(sid), "SK": mc.miscstate_sk(mid), "type": "MISCSTATE", "student_id": sid,
            "misconception_id": mid, "confidence": 0.5, "confirmed": False}
    assert mc.LearnerMiscstate.from_item(good).confidence == 0.5
    from mathbank_rest.stores.errors import ItemSchemaError

    for bad in ({**good, "confidence": 1.2}, {**good, "confidence": -0.1}, {**good, "confirmed": "no"}):
        with pytest.raises(ItemSchemaError):
            mc.LearnerMiscstate.from_item(bad)
    evid = {"PK": toolkit.student_pk(sid), "SK": f"MISC#{mid}#2026-10-06T00:55:03.270501Z#{uuid.uuid4()}", "type": "MISCEVID",
            "student_id": sid, "evidence_id": str(uuid.uuid4()), "misconception_id": mid, "evidence_type": "OBSERVED_ERROR",
            "evidence_weight": 0.5, "confidence_before": 0.0, "confidence_after": 0.5, "created_at": "2026-10-06T00:55:03.270501Z"}
    assert mc.LearnerMiscevid.from_item(evid).evidence_weight == 0.5
    for bad in ({**evid, "evidence_weight": 1.5}, {**evid, "confidence_after": 2}, {**evid, "evidence_type": "GUESS"}):
        with pytest.raises(ItemSchemaError):
            mc.LearnerMiscevid.from_item(bad)
    eid = str(uuid.uuid4())
    event = {"PK": toolkit.student_pk(sid), "SK": mc.mcevent_sk(eid, "2026-10-06T00:55:03.270501Z", uuid.uuid4()), "type": "MCEVENT",
             "student_id": sid, "enrollment_id": eid, "event_id": str(uuid.uuid4()), "event_type": "ENROLLED", "actor_type": "STUDENT",
             "release_id": str(uuid.uuid4()), "state_id": str(uuid.uuid4()), "created_at": "2026-10-06T00:55:03.270501Z"}
    assert mc.LearnerMcevent.from_item(event).event_type == "ENROLLED"
    with pytest.raises(ItemSchemaError):
        mc.LearnerMcevent.from_item({**event, "event_type": "TELEPORTED"})
    with pytest.raises(ItemSchemaError):
        mc.LearnerMcevent.from_item({**event, "actor_type": "ROBOT"})


# ------------------------------------------------------------------------------------------------ enroll (T21 / A26)

def test_enroll_writes_one_transaction_and_returns_the_runtime(world):
    runtime = enroll(world)
    eid = eid_of(runtime)
    assert runtime["enrollment_status"] == "IN_PROGRESS" and runtime["state_version"] == 1
    assert runtime["current_state"]["state_id"] == wp4.STATE1 and runtime["canonical_code"] == CODE
    assert (runtime["step_count"], runtime["step_number"]) == (2, 1)
    wp4.assert_no_keys(runtime)
    mine = partition(world)
    assert {i.type for i in mine} == {"PROFILE", "ENROLL", "UNIQUE_OPEN_ENROLL", "MCEVENT"}
    enrollment = items_of(world, mc.LearnerEnroll)[0]
    assert enrollment.GSI1PK == f"MC_RELEASE#{wp4.REL1}" and enrollment.GSI1SK.startswith("IN_PROGRESS#")
    assert enrollment.state_version == 1 and enrollment.last_responses == {}
    assert items_of(world, mc.LearnerUniqueOpenEnroll)[0].SK == f"UNIQUE#open_enroll#{wp4.COURSE_ID}"
    event = items_of(world, mc.LearnerMcevent)[0]
    assert event.event_type == "ENROLLED" and event.payload == {"canonical_code": CODE} and event.GSI1PK == f"MC_RELEASE#{wp4.REL1}#EVT"
    assert STORE.get_enrollment_owner(None, eid) == world


def test_enroll_resumes_the_open_enrollment_and_a_race_loser_resumes_the_winner(world, monkeypatch):
    first = enroll(world)
    again = enroll(world)
    assert again["enrollment_id"] == first["enrollment_id"] and len(items_of(world, mc.LearnerEnroll)) == 1
    real_get = typed.get

    def stale_pointer_read(model, pk, sk, **kw):          # the loser reads the sentinel before the winner wrote it
        if model is mc.LearnerUniqueOpenEnroll and not getattr(stale_pointer_read, "used", False):
            stale_pointer_read.used = True
            return None
        return real_get(model, pk, sk, **kw)

    monkeypatch.setattr(typed, "get", stale_pointer_read)
    loser = enroll(world)
    assert stale_pointer_read.used and loser["enrollment_id"] == first["enrollment_id"]
    assert len(items_of(world, mc.LearnerEnroll)) == 1


def test_enroll_idempotency_key_replays_and_a_reused_key_is_422(world):
    first = enroll(world, idempotency_key="k1")
    replay = enroll(world, idempotency_key="k1")
    assert "replayed" not in first and replay["replayed"] is True
    assert set(replay) - {"replayed"} == set(first)
    assert replay["enrollment_id"] == first["enrollment_id"] and len(items_of(world, mc.LearnerMcevent)) == 1
    with pytest.raises(IdempotencyKeyReused):
        STORE.start_enrollment(None, "MC-OTHER", world, idempotency_key="k1")


def test_enroll_refuses_unknown_courses_and_inactive_students(world):
    with pytest.raises(courses.MicroCourseNotFound, match="published micro-course not found"):
        STORE.start_enrollment(None, "MC-NOPE", world)
    other = str(uuid.uuid4())
    seed_profile(other, status="DISABLED")
    with pytest.raises(courses.MicroCourseNotFound, match="active student account not found"):
        STORE.start_enrollment(None, CODE, other)
    assert items_of(other, mc.LearnerEnroll) == []
    with pytest.raises(courses.MicroCourseNotFound, match="active student account not found"):
        STORE.start_enrollment(None, CODE, str(uuid.uuid4()))            # no profile at all


# ------------------------------------------------------------------------------------------------ runtime and key rules (A27)

def test_runtime_shows_no_answer_key_or_explanation_before_answering(world):
    runtime = enroll(world)
    state = runtime["current_state"]
    assert sorted(state) == sorted(["state_id", "state_key", "state_type", "title", "ordinal", "objective", "student_instruction",
                                    "estimated_seconds", "required", "module_id", "module_title", "assets", "interactions",
                                    "activities", "learning_items", "transcript_segments", "qa_contexts", "items",
                                    "answered_learning_item_ids"])
    wp4.assert_no_keys(runtime)
    wp4.assert_no_keys(STORE.get_enrollment_runtime(None, eid_of(runtime), world))
    assert all("explanation" not in i and "answered_correctly" not in i for i in state["learning_items"] + state["activities"])
    assert state["module_title"] == "Mod" and state["answered_learning_item_ids"] == []
    assert runtime["can_continue"] is False and runtime["can_go_back"] is False and runtime["can_finish"] is False


def test_runtime_reveals_an_explanation_only_for_answered_items(world):
    eid = eid_of(enroll(world))
    STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1)
    STORE.submit_activity_response(None, eid, world, wp4.ACT1, choice_index=1)
    state = STORE.get_enrollment_runtime(None, eid, world)["current_state"]
    li = {i["learning_item_id"]: i for i in state["learning_items"]}
    act = {a["activity_id"]: a for a in state["activities"]}
    assert li[wp4.LI1]["answered_correctly"] is True and li[wp4.LI1]["explanation"] == wp4.KEY_SENTINELS[1]
    assert "explanation" not in li[wp4.LI2] and "explanation" not in act[wp4.ACT2]
    assert act[wp4.ACT1]["answered_correctly"] is False and act[wp4.ACT1]["explanation"] == wp4.KEY_SENTINELS[3]
    assert state["answered_learning_item_ids"] == [wp4.LI1]
    assert wp4.KEY_SENTINELS[0] not in json.dumps(state)                 # the correct answer itself never appears


def test_another_students_enrollment_is_404_everywhere(world):
    eid = eid_of(enroll(world))
    other = str(uuid.uuid4())
    seed_profile(other)
    calls = [
        lambda: STORE.get_enrollment_runtime(None, eid, other),
        lambda: STORE.advance_enrollment(None, eid, other, 1, "CONTINUE"),
        lambda: STORE.submit_learning_item_response(None, eid, other, wp4.LI1, 0),
        lambda: STORE.submit_activity_response(None, eid, other, wp4.ACT1, choice_index=0),
        lambda: STORE.record_interaction_event(None, eid, other, wp4.INTERACTION1, event_type="CHANGE", semantic_action="X"),
        lambda: STORE.assist_item(None, eid, other, "learning_item", wp4.LI1, "give_up", None),
        lambda: STORE.abandon_enrollment(None, eid, other),
    ]
    for call in calls:
        with pytest.raises(courses.MicroCourseNotFound, match="micro-course enrollment not found"):
            call()
    assert items_of(other, mc.LearnerMcevent) == [] and items_of(world, mc.LearnerEnroll)[0].status == "IN_PROGRESS"
    assert STORE.list_enrollments(None, other)["items"] == []


# ------------------------------------------------------------------------------------------------ responses (T23)

def test_learning_item_response_records_event_and_pointer_without_touching_the_state_version(world):
    eid = eid_of(enroll(world))
    right = STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1)
    assert right == {"learning_item_id": wp4.LI1, "choice_index": 1, "is_correct": True, "gave_up": False,
                     "explanation": wp4.KEY_SENTINELS[1]}
    wrong = STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 0)
    assert wrong["is_correct"] is False and "correct_answer" not in wrong and "correct_choice_index" not in wrong
    enrollment = items_of(world, mc.LearnerEnroll)[0]
    assert enrollment.state_version == 1 and enrollment.response_seq == 2
    latest = enrollment.last_responses[wp4.LI1]
    assert latest.kind == "QUIZ_RESPONSE" and latest.payload.is_correct is False and latest.payload.choice_index == 0
    events = [e for e in items_of(world, mc.LearnerMcevent) if e.event_type == "QUIZ_RESPONSE"]
    assert len(events) == 2 and {e.payload["is_correct"] for e in events} == {True, False}
    assert all(e.state_id and str(e.state_id) == wp4.STATE1 for e in events)


def test_give_up_reveals_the_key_only_in_the_gave_up_response(world):
    eid = eid_of(enroll(world))
    gave = STORE.submit_learning_item_response(None, eid, world, wp4.LI1, None, gave_up=True)
    assert gave["gave_up"] is True and gave["is_correct"] is False
    assert gave["correct_answer"] == "b" and gave["correct_choice_index"] == 1 and gave["explanation"] == wp4.KEY_SENTINELS[1]
    activity = STORE.submit_activity_response(None, eid, world, wp4.ACT2, gave_up=True)
    assert activity["correct_value"] == 4 and activity["is_correct"] is False and activity["explanation"] == "e"


def test_response_validation_errors_and_scope(world):
    eid = eid_of(enroll(world))
    with pytest.raises(ValueError, match="choice_index is required"):
        STORE.submit_learning_item_response(None, eid, world, wp4.LI1, None)
    with pytest.raises(ValueError, match="outside the available choices"):
        STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 5)
    with pytest.raises(ValueError, match="value is required"):
        STORE.submit_activity_response(None, eid, world, wp4.ACT2)
    with pytest.raises(courses.MicroCourseNotFound, match="approved learning item not found"):
        STORE.submit_learning_item_response(None, eid, world, "LI-nope", 0)
    with pytest.raises(courses.MicroCourseNotFound, match="quiz activity not found"):
        STORE.submit_activity_response(None, eid, world, wp4.uid(999), choice_index=0)
    assert [e.event_type for e in items_of(world, mc.LearnerMcevent)] == ["ENROLLED"]
    numeric = STORE.submit_activity_response(None, eid, world, wp4.ACT2, value=4)
    assert numeric["is_correct"] is True and "correct_value" not in numeric
    last = items_of(world, mc.LearnerEnroll)[0].last_responses[wp4.ACT2]
    assert last.kind == "ACTIVITY_RESPONSE" and last.payload.value == 4


def test_double_submit_with_the_same_key_replays_and_records_once(world):
    eid = eid_of(enroll(world))
    first = STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1, idempotency_key="resp-1")
    replay = STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1, idempotency_key="resp-1")
    assert replay == {**first, "replayed": True} and "replayed" not in first
    assert len([e for e in items_of(world, mc.LearnerMcevent) if e.event_type == "QUIZ_RESPONSE"]) == 1
    assert items_of(world, mc.LearnerEnroll)[0].response_seq == 1
    with pytest.raises(IdempotencyKeyReused):
        STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 0, idempotency_key="resp-1")
    act = STORE.submit_activity_response(None, eid, world, wp4.ACT1, choice_index=0, idempotency_key="act-1")
    assert STORE.submit_activity_response(None, eid, world, wp4.ACT1, choice_index=0, idempotency_key="act-1") == {**act, "replayed": True}


def test_a_concurrent_response_write_is_retried_not_lost(world, monkeypatch):
    eid = eid_of(enroll(world))
    real_build = STORE._build_response
    state = {"raced": False}

    def racing(uow, enrollment_id, grade):
        built = real_build(uow, enrollment_id, grade)
        if not state["raced"]:                              # a second response commits after this one read the item
            state["raced"] = True
            STORE.submit_activity_response(None, eid, world, wp4.ACT1, choice_index=0)
        return built

    monkeypatch.setattr(STORE, "_build_response", racing)
    STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1)
    answered = items_of(world, mc.LearnerEnroll)[0].last_responses
    assert set(answered) == {wp4.LI1, wp4.ACT1}                      # neither pointer was overwritten
    assert len([e for e in items_of(world, mc.LearnerMcevent) if "RESPONSE" in e.event_type]) == 2


# ------------------------------------------------------------------------------------------------ advance (T22)

def finish_assessment(eid: str, student: str) -> None:
    STORE.submit_learning_item_response(None, eid, student, wp4.LI1, 1)         # LI1 is the only required item


def test_advance_checks_the_client_version_then_moves_and_completes(world):
    runtime = enroll(world)
    eid = eid_of(runtime)
    with pytest.raises(courses.MicroCourseConflict, match="lesson changed"):
        STORE.advance_enrollment(None, eid, world, 7, "CONTINUE")
    with pytest.raises(ValueError, match="CONTINUE or BACK"):
        STORE.advance_enrollment(None, eid, world, 1, "SIDEWAYS")
    with pytest.raises(courses.MicroCourseConflict, match="no approved back transition"):
        STORE.advance_enrollment(None, eid, world, 1, "BACK")
    finish_assessment(eid, world)
    moved = STORE.advance_enrollment(None, eid, world, 1, "CONTINUE")
    assert moved["current_state"]["state_id"] == wp4.STATE2 and moved["state_version"] == 2 and moved["step_number"] == 2
    assert moved["can_finish"] is True and moved["can_continue"] is False
    with pytest.raises(courses.MicroCourseConflict, match="lesson changed"):
        STORE.advance_enrollment(None, eid, world, 1, "CONTINUE")           # the client's copy is stale now
    done = STORE.advance_enrollment(None, eid, world, 2, "CONTINUE")
    assert done["enrollment_status"] == "COMPLETED" and done["state_version"] == 3 and done["completed_at"] is not None
    enrollment = items_of(world, mc.LearnerEnroll)[0]
    assert enrollment.status == "COMPLETED" and enrollment.state_version == 3 and enrollment.GSI1SK.startswith("COMPLETED#")
    assert items_of(world, mc.LearnerUniqueOpenEnroll) == []
    assert [e.event_type for e in items_of(world, mc.LearnerMcevent)] == ["ENROLLED", "QUIZ_RESPONSE", "STATE_CHANGED", "COMPLETED"]
    with pytest.raises(courses.MicroCourseConflict, match="not in progress"):
        STORE.advance_enrollment(None, eid, world, 3, "CONTINUE")
    fresh = enroll(world)                                                   # completing frees the course for a new enrollment
    assert fresh["enrollment_id"] != eid and fresh["state_version"] == 1


def test_advance_is_idempotent_and_a_concurrent_advance_is_a_409(world):
    eid = eid_of(enroll(world))
    finish_assessment(eid, world)
    first = STORE.advance_enrollment(None, eid, world, 1, "CONTINUE", idempotency_key="adv")
    assert STORE.advance_enrollment(None, eid, world, 1, "CONTINUE", idempotency_key="adv")["replayed"] is True
    assert items_of(world, mc.LearnerEnroll)[0].state_version == 2 and first["state_version"] == 2
    assert [e.event_type for e in items_of(world, mc.LearnerMcevent)].count("STATE_CHANGED") == 1
    # another tab advanced between this client's read and its commit: the transaction condition (not the code check) rejects it
    stale = STORE._load_open(world, eid)
    STORE.advance_enrollment(None, eid, world, 2, "CONTINUE")
    with mock.patch.object(MicroCourseDynamoDB, "_load_open", return_value=stale), \
            pytest.raises(courses.MicroCourseConflict, match="lesson changed"):
        STORE.advance_enrollment(None, eid, world, 2, "CONTINUE")


def test_a_response_after_completion_or_abandon_is_409(world):
    eid = eid_of(enroll(world))
    STORE.abandon_enrollment(None, eid, world)
    with pytest.raises(courses.MicroCourseConflict, match="not in progress"):
        STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1)
    with pytest.raises(courses.MicroCourseConflict, match="not in progress"):
        STORE.submit_activity_response(None, eid, world, wp4.ACT1, choice_index=0)
    with pytest.raises(courses.MicroCourseConflict, match="not in progress"):
        STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action="X")
    assert STORE.get_enrollment_runtime(None, eid, world)["enrollment_status"] == "ABANDONED"       # still readable


# ------------------------------------------------------------------------------------------------ list and abandon (A28 / T25)

def test_list_enrollments_filters_by_status_and_abandon_frees_the_course(world):
    first = eid_of(enroll(world))
    STORE.record_interaction_event(None, first, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action="SET")
    abandoned = STORE.abandon_enrollment(None, first, world)
    assert abandoned["status"] == "ABANDONED" and abandoned["state_version"] == 2 and abandoned["enrollment_id"] == first
    second = eid_of(enroll(world))
    assert second != first
    listed = STORE.list_enrollments(None, world)
    assert [i["enrollment_id"] for i in listed["items"]] == [second, first] and listed["total"] == 2
    assert [i["status"] for i in listed["items"]] == ["IN_PROGRESS", "ABANDONED"]
    assert listed["items"][0]["canonical_code"] == CODE and listed["items"][0]["current_state_id"] == wp4.STATE1
    only = STORE.list_enrollments(None, world, status="ABANDONED")
    assert [i["enrollment_id"] for i in only["items"]] == [first] and only["total"] == 1
    assert STORE.list_enrollments(None, world, limit=1)["total"] == 2 and len(STORE.list_enrollments(None, world, limit=1)["items"]) == 1
    with pytest.raises(ValueError, match="status must be"):
        STORE.list_enrollments(None, world, status="DONE")
    with pytest.raises(courses.MicroCourseConflict, match="not in progress"):
        STORE.abandon_enrollment(None, first, world)
    assert [e.event_type for e in items_of(world, mc.LearnerMcevent)].count("ABANDONED") == 1


# ------------------------------------------------------------------------------------------------ interaction events (T24 / A31 / A32)

class RuleContent(DynamoDBContentStore):
    """The content store of a future C6 FEEDBACK_CATALOG: serves the approved evidence rule for one error signature."""

    def find_misconception_evidence_rule(self, conn, template_version_id, semantic_action, error_signature):
        if (template_version_id, semantic_action, error_signature) == (TEMPLATE_VERSION, "SUBMIT_ROW", "ROW_SUM_INVALID"):
            return {"misconception_id": MISCONCEPTION, "evidence_weight": 0.5}
        return None


def test_interaction_event_is_recorded_and_the_response_shape_is_unchanged(world):
    eid = eid_of(enroll(world))
    out = STORE.record_interaction_event(
        None, eid, world, wp4.INTERACTION1, event_type="change", semantic_action="set_value", control_key="slider",
        before_state={"x": 0}, action_payload={"value": 0.25}, after_state={"x": 0.25})
    assert set(out) == {"interaction_event_id"}
    event = items_of(world, mc.LearnerIxevent)[0]
    assert str(event.interaction_event_id) == out["interaction_event_id"] and event.event_type == "CHANGE"
    assert event.semantic_action == "SET_VALUE" and event.action_payload == {"value": 0.25} and event.before_state == {"x": 0}
    assert event.evaluation_outcome is None and str(event.course_state_id) == wp4.STATE1
    with pytest.raises(courses.MicroCourseNotFound, match="interaction instance not found"):
        STORE.record_interaction_event(None, eid, world, wp4.uid(998), event_type="CHANGE", semantic_action="X")
    with pytest.raises(ValueError, match="event_type is required"):
        STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="  ", semantic_action="X")
    replay = STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action="X",
                                            idempotency_key="ix")
    assert STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action="X",
                                          idempotency_key="ix") == {**replay, "replayed": True}
    assert len(items_of(world, mc.LearnerIxevent)) == 2


def test_evidence_is_off_by_default_even_for_a_failing_submission(world):
    eid = eid_of(enroll(world))
    with stores.override_store("content", RuleContent()):
        STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="SUBMIT", semantic_action="submit_row",
                                       action_payload={"row": [0.9, 0.9]})
    event = items_of(world, mc.LearnerIxevent)[0]
    assert event.evaluation_outcome is None and items_of(world, mc.LearnerMiscevid) == []


def test_misconception_evidence_accumulates_with_the_unchanged_maths(world, monkeypatch):
    monkeypatch.setattr(settings, "misconception_evidence", "on")
    eid = eid_of(enroll(world))
    submit = lambda row: STORE.record_interaction_event(
        None, eid, world, wp4.INTERACTION1, event_type="SUBMIT", semantic_action="submit_row", action_payload={"row": row})
    with stores.override_store("content", RuleContent()):
        submit([0.5, 0.5])                                               # CORRECT: evaluated, no evidence
        assert items_of(world, mc.LearnerMiscevid) == [] and STORE.list_misconceptions(None, world)["items"] == []
        submit([0.9, 0.9])                                               # ROW_SUM_INVALID -> +0.5
        first = STORE.get_misconception_state(None, world, MISCONCEPTION)
        assert (first["confidence"], first["confirmed"]) == (0.5, False)
        submit([0.9, 0.9])                                               # 0.5 + 0.5 -> 1.0 (clamped at 1, confirmed)
        submit([0.9, 0.9])
    state = STORE.get_misconception_state(None, world, MISCONCEPTION)
    assert state["confidence"] == 1.0 and state["confirmed"] is True and state["misconception_id"] == MISCONCEPTION
    evidence = sorted(items_of(world, mc.LearnerMiscevid), key=lambda e: e.created_at)
    assert [(e.confidence_before, e.confidence_after, e.evidence_weight) for e in evidence] == \
        [(0.0, 0.5, 0.5), (0.5, 1.0, 0.5), (1.0, 1.0, 0.5)]
    assert {e.evidence_type for e in evidence} == {"OBSERVED_ERROR"}
    stored = items_of(world, mc.LearnerMiscstate)[0]
    assert stored.version == 3 and str(stored.last_evidence_id) == str(evidence[-1].evidence_id)
    outcomes = sorted(((e.evaluation_outcome, e.error_signature) for e in items_of(world, mc.LearnerIxevent)), key=str)
    assert outcomes == [("CORRECT", None)] + [("ERROR", "ROW_SUM_INVALID")] * 3
    listed = STORE.list_misconceptions(None, world)
    assert listed["total"] == 1 and listed["items"][0]["confidence"] == 1.0
    assert STORE.get_misconception_state(None, world, wp4.uid(1)) is None


def test_last_ten_interactions_of_an_item_come_back_newest_first(world):
    eid = eid_of(enroll(world))
    for n in range(12):
        STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action=f"A{n}",
                                       control_key="c", action_payload={"n": n})
    recent = STORE.list_item_interactions(None, eid, world, wp4.INTERACTION1)
    assert [r["semantic_action"] for r in recent] == [f"A{n}" for n in range(11, 1, -1)]
    assert recent[0] == {"event_type": "CHANGE", "semantic_action": "A11", "control_key": "c", "action_payload": {"n": 11}}
    assert STORE.list_item_interactions(None, eid, world, wp4.uid(77)) == []


# ------------------------------------------------------------------------------------------------ admin plane (A29 / A30 / T26)

def test_reset_moves_the_learner_and_records_the_admin_actor(world):
    eid = eid_of(enroll(world))
    finish_assessment(eid, world)
    STORE.advance_enrollment(None, eid, world, 1, "CONTINUE")
    assert STORE.get_enrollment_owner(None, wp4.uid(1)) is None
    runtime = STORE.reset_enrollment(None, eid, wp4.STATE1, "service:admin-key")
    assert runtime["current_state"]["state_id"] == wp4.STATE1 and runtime["state_version"] == 3
    reset = next(e for e in items_of(world, mc.LearnerMcevent) if e.event_type == "RESET")
    assert reset.actor_type == "ADMIN" and reset.payload["actor"] == "service:admin-key" and reset.payload["from_state_version"] == 2
    with pytest.raises(ValueError, match="does not belong"):
        STORE.reset_enrollment(None, eid, wp4.uid(555), "service:admin-key")
    with pytest.raises(courses.MicroCourseNotFound):
        STORE.reset_enrollment(None, wp4.uid(556), wp4.STATE1, "service:admin-key")
    assert STORE.get_enrollment_runtime(None, eid, world)["state_version"] == 3


def test_course_activity_aggregates_enrollments_events_and_quiz_accuracy(world):
    other = str(uuid.uuid4())
    seed_profile(other, first_name="Grace", last_name="Hopper")
    e1, e2 = eid_of(enroll(world)), eid_of(STORE.start_enrollment(None, CODE, other))
    finish_assessment(e1, world)
    STORE.advance_enrollment(None, e1, world, 1, "CONTINUE")
    STORE.advance_enrollment(None, e1, world, 2, "CONTINUE")
    STORE.submit_activity_response(None, e2, other, wp4.ACT1, choice_index=0)
    STORE.submit_activity_response(None, e2, other, wp4.ACT1, choice_index=1)
    activity = STORE.list_course_activity(None, CODE)
    assert (activity["total_enrollments"], activity["in_progress"], activity["completed"], activity["completion_rate"]) == (2, 1, 1, 0.5)
    assert activity["release_id"] == wp4.REL1 and activity["version"] == 1
    assert [(s["state_key"], s["reached_count"]) for s in activity["step_funnel"]] == [("s1", 2), ("s2", 1)]
    accuracy = {q["activity_id"]: q for q in activity["quiz_accuracy"]}
    assert (accuracy[wp4.ACT1]["attempts"], accuracy[wp4.ACT1]["correct"], accuracy[wp4.ACT1]["state_key"]) == (2, 1, "s1")
    assert accuracy[wp4.ACT2]["attempts"] == 0
    assert len(activity["recent_activity"]) <= 25 and activity["recent_activity"][0]["event_type"] == "ACTIVITY_RESPONSE"
    assert {e["student_initials"] for e in activity["recent_activity"]} == {"AL", "GH"}
    assert {e["state_title"] for e in activity["recent_activity"]} <= {"First", "Second"}
    with pytest.raises(courses.MicroCourseNotFound):
        STORE.list_course_activity(None, "MC-NOPE")


# ------------------------------------------------------------------------------------------------ item-help

@pytest.fixture()
def echo_help(monkeypatch):
    """The model call replaced by an echo of the grounding it would receive (parity compares the groundings)."""
    monkeypatch.setattr(assist, "_help", lambda kind, grounding, message: {
        "intent": "help", "item_kind": kind, "grounding": grounding, "student_message": message})


def test_help_grounds_each_item_kind_without_any_answer_key(world, echo_help):
    eid = eid_of(enroll(world))
    STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action="SET", control_key="c",
                                   action_payload={"v": 1})
    seen = {}
    for kind, item in (("learning_item", wp4.LI1), ("activity", wp4.ACT1), ("interaction", wp4.INTERACTION1), ("asset", wp4.ASSET_PRIVATE)):
        out = STORE.assist_item(None, eid, world, kind, item, "help", "stuck")
        wp4.assert_no_keys(out)
        seen[kind] = out["grounding"]
        assert out["grounding"]["state_context"]["state_qa_contexts"][0]["context_type"] == "FAQ"
    assert seen["learning_item"]["question_text"] == "Q1?" and seen["learning_item"]["choices"] == ["a", "b"]
    assert seen["activity"]["options"] == [{"label": "x = 1"}, {"label": "x = 2"}]
    assert seen["interaction"]["recent_student_actions"] == [
        {"event_type": "CHANGE", "semantic_action": "SET", "control_key": "c", "action_payload": {"v": 1}}]
    assert seen["asset"]["approved_transcript_segments"] == [{"start_ms": 0, "transcript_text": "hello"}]
    with pytest.raises(courses.MicroCourseNotFound, match="learning item not found in the current lesson state"):
        STORE.assist_item(None, eid, world, "learning_item", "LI-nope", "help", None)
    with pytest.raises(courses.MicroCourseNotFound, match="asset not found"):
        STORE.assist_item(None, eid, world, "asset", wp4.uid(1), "give_up", None)
    assert [e.event_type for e in items_of(world, mc.LearnerMcevent)] == ["ENROLLED"]        # help writes nothing


def test_give_up_through_item_help_reveals_and_records(world, echo_help):
    eid = eid_of(enroll(world))
    out = STORE.assist_item(None, eid, world, "learning_item", wp4.LI1, "give_up", None)
    assert out == {"intent": "give_up", "item_kind": "learning_item", "action": "revealed", "gave_up": True,
                   "correct_answer": "b", "explanation": wp4.KEY_SENTINELS[1]}
    act = STORE.assist_item(None, eid, world, "activity", wp4.ACT2, "give_up", None)
    assert act["correct_value"] == 4 and act["action"] == "revealed"
    assert STORE.assist_item(None, eid, world, "asset", wp4.ASSET_PRIVATE, "give_up", None) == {
        "intent": "give_up", "item_kind": "asset", "action": "skip", "gave_up": True}
    recorded = [e for e in items_of(world, mc.LearnerMcevent) if e.event_type.endswith("RESPONSE")]
    assert {e.payload["gave_up"] for e in recorded} == {True} and len(recorded) == 2


# ------------------------------------------------------------------------------------------------ backend contract

class _NoPostgres:
    def __getattr__(self, name):
        raise AssertionError(f"DynamoDB learner store touched PostgreSQL ({name})")


@contextmanager
def no_postgres(monkeypatch):
    import mathbank_rest.db.postgres as pg

    monkeypatch.setattr(pg, "engine", _NoPostgres())
    monkeypatch.setattr(mc_router, "engine", _NoPostgres())
    yield


def test_dynamodb_methods_never_touch_postgres(world, monkeypatch, echo_help):
    other = str(uuid.uuid4())
    seed_profile(other)
    with no_postgres(monkeypatch):
        runtime = enroll(world)
        eid = eid_of(runtime)
        STORE.get_enrollment_runtime(None, eid, world)
        STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1, idempotency_key="a")
        STORE.submit_activity_response(None, eid, world, wp4.ACT1, choice_index=0)
        STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action="X")
        STORE.assist_item(None, eid, world, "learning_item", wp4.LI2, "help", None)
        STORE.assist_item(None, eid, world, "activity", wp4.ACT2, "give_up", None)
        STORE.list_enrollments(None, world)
        STORE.list_item_interactions(None, eid, world, wp4.INTERACTION1)
        STORE.list_misconceptions(None, world)
        STORE.list_course_activity(None, CODE)
        STORE.get_enrollment_owner(None, eid)
        STORE.advance_enrollment(None, eid, world, 1, "CONTINUE")
        STORE.reset_enrollment(None, eid, wp4.STATE1, "service:admin-key")
        STORE.abandon_enrollment(None, eid, world)
        # the learner has no enrollment of another course in progress: the DynamoDB read model needs no connection either
        assert STORE.list_enrollments(None, other)["items"] == []


def public_methods(cls) -> set[str]:
    return {m for m in vars(cls) if not m.startswith("_") and callable(getattr(cls, m))}


def test_both_backends_expose_the_same_operations_and_reads_are_named_as_reads():
    assert public_methods(MicroCourseDynamoDB) == public_methods(MicroCoursePostgres)
    reads = {"get_enrollment_runtime", "list_enrollments", "list_item_interactions", "list_misconceptions", "get_misconception_state",
             "get_enrollment_owner", "list_course_activity"}
    writes = {"start_enrollment", "advance_enrollment", "submit_learning_item_response", "submit_activity_response",
              "record_interaction_event", "abandon_enrollment", "reset_enrollment", "assist_item"}
    methods = public_methods(MicroCourseDynamoDB)
    assert methods == reads | writes
    assert {m for m in methods if m.startswith(stores.READ_PREFIXES)} == reads
    assert issubclass(DynamoDBLearnerStore, MicroCourseDynamoDB) and issubclass(PostgresLearnerStore, MicroCoursePostgres)


def test_a_frozen_store_serves_reads_and_rejects_writes(world):
    eid = eid_of(enroll(world))
    frozen = stores.FrozenProxy("learner", STORE)
    assert frozen.get_enrollment_runtime(None, eid, world)["enrollment_id"] == eid
    assert frozen.list_enrollments(None, world)["total"] == 1
    from mathbank_rest.stores.errors import StoreFrozen

    for call in (lambda: frozen.start_enrollment(None, CODE, world), lambda: frozen.submit_learning_item_response(None, eid, world, wp4.LI1, 1),
                 lambda: frozen.abandon_enrollment(None, eid, world), lambda: frozen.assist_item(None, eid, world, "asset", "x", "help", None)):
        with pytest.raises(StoreFrozen):
            call()


def test_postgres_backend_delegates_to_the_service_functions_at_call_time(monkeypatch):
    pg, seen = MicroCoursePostgres(), []
    conn = object()
    monkeypatch.setattr(courses, "start_enrollment", lambda c, code, sid: seen.append(("start", c is conn, code, sid)) or {"r": 1})
    monkeypatch.setattr(courses, "get_enrollment_runtime", lambda c, eid, sid: seen.append(("get", eid, sid)) or {})
    monkeypatch.setattr(courses, "advance_enrollment", lambda c, eid, sid, v, a: seen.append(("adv", v, a)) or {})
    monkeypatch.setattr(courses, "submit_learning_item_response",
                        lambda c, eid, sid, li, ci, gave_up=False: seen.append(("li", li, ci, gave_up)) or {})
    monkeypatch.setattr(courses, "submit_activity_response",
                        lambda c, eid, sid, a, choice_index=None, value=None, gave_up=False: seen.append(("act", a, choice_index, value)) or {})
    monkeypatch.setattr(courses, "record_interaction_event", lambda c, eid, sid, inst, **kw: seen.append(("ix", inst, kw["event_type"])) or "ev-1")
    monkeypatch.setattr(courses, "list_enrollments", lambda c, sid, status, limit: seen.append(("list", status, limit)) or {"items": [], "total": 0})
    monkeypatch.setattr(courses, "abandon_enrollment", lambda c, eid, sid: seen.append(("abandon", eid)) or {})
    monkeypatch.setattr(courses, "get_enrollment_owner", lambda c, eid: seen.append(("owner", eid)) or "s")
    monkeypatch.setattr(courses, "get_course_activity", lambda c, code: seen.append(("activity", code)) or {})
    monkeypatch.setattr(courses, "reset_enrollment", lambda c, eid, to, actor: seen.append(("reset", to, actor)) or {})
    monkeypatch.setattr(assist, "get_item_assist", lambda c, eid, sid, kind, item, intent, msg: seen.append(("assist", kind, intent)) or {})
    monkeypatch.setattr(assist, "recent_interactions", lambda c, eid, item: seen.append(("recent", item)) or [])
    monkeypatch.setattr(ixrt, "list_misconception_state", lambda c, sid: seen.append(("misc", sid)) or [{"misconception_id": "m1"}])
    pg.start_enrollment(conn, "MC", "s", idempotency_key="ignored")
    pg.get_enrollment_runtime(conn, "e", "s")
    pg.advance_enrollment(conn, "e", "s", 4, "CONTINUE")
    pg.submit_learning_item_response(conn, "e", "s", "LI", 1, gave_up=True)
    pg.submit_activity_response(conn, "e", "s", "A", value=2.0)
    assert pg.record_interaction_event(conn, "e", "s", "I", event_type="CHANGE", semantic_action="X") == {"interaction_event_id": "ev-1"}
    pg.list_enrollments(conn, "s", "COMPLETED", 5)
    pg.abandon_enrollment(conn, "e", "s")
    pg.get_enrollment_owner(conn, "e")
    pg.list_course_activity(conn, "MC")
    pg.reset_enrollment(conn, "e", "t", "me")
    pg.assist_item(conn, "e", "s", "asset", "x", "help", None)
    pg.list_item_interactions(conn, "e", "s", "I")
    assert pg.list_misconceptions(conn, "s") == {"items": [{"misconception_id": "m1"}], "total": 1}
    assert pg.get_misconception_state(conn, "s", "m1") == {"misconception_id": "m1"} and pg.get_misconception_state(conn, "s", "zz") is None
    assert [s[0] for s in seen[:13]] == ["start", "get", "adv", "li", "act", "ix", "list", "abandon", "owner", "activity", "reset",
                                         "assist", "recent"]
    assert seen[0] == ("start", True, "MC", "s") and seen[3] == ("li", "LI", 1, True)


def test_shared_pure_logic_matches_the_postgres_behaviour():
    item = {"learning_item_id": "LI", "choices": ["a", "b"], "correct_answer": "b", "answer_or_solution_seed": "why"}
    assert courses.grade_learning_item(item, 1, False) == (True, 1)
    assert courses.grade_learning_item(item, 0, False) == (False, 1)
    assert courses.grade_learning_item(item, None, True) == (False, 1)
    with pytest.raises(ValueError):
        courses.grade_learning_item(item, None, False)
    with pytest.raises(courses.MicroCourseConflict):
        courses.grade_learning_item({**item, "correct_answer": ""}, 0, False)
    assert courses.pick_transition([{"from_state_id": "s", "to_state_id": "z", "transition_type": "NEXT", "condition_type": "ALWAYS",
                                     "priority": 2},
                                    {"from_state_id": "s", "to_state_id": "y", "transition_type": "USER_CONTINUE",
                                     "condition_type": "ALWAYS", "priority": 1}], "s", "CONTINUE")["to_state_id"] == "y"
    assert ixrt.next_confidence(0.7, 0.5) == 1.0 and ixrt.next_confidence(0.2, -0.5) == 0.0 and ixrt.is_confirmed(0.8)
    assert ixrt.evaluate_submission("TRANSITION_MATRIX_EDITOR_V1", "SUBMIT", {"row": [0.5, 0.5]})["outcome"] == "CORRECT"
    assert ixrt.evaluate_submission("TRANSITION_MATRIX_EDITOR_V1", "CHANGE", {"row": [0.5, 0.5]}) is None
    assert ixrt.evaluate_submission("OTHER", "SUBMIT", {"row": [0.5]}) is None
    assert ixrt.evaluate_submission("TRANSITION_MATRIX_EDITOR_V1", "SUBMIT", {"row": ["x"]}) is None


# ================================================================================================ route parity with PostgreSQL
#
# The PostgreSQL side runs the real service functions against PgWorld, an in-memory stand-in for the SQL they issue.

STARTED = dt.datetime(2026, 10, 6, 0, 55, 3, 270501, tzinfo=dt.UTC)
PG_KEYS = {wp4.LI1: ("b", wp4.KEY_SENTINELS[1]), wp4.LI2: (wp4.KEY_SENTINELS[0], None)}
PG_POLICIES = {wp4.ACT1: {"correct_index": 0, "explanation": wp4.KEY_SENTINELS[3]},
               wp4.ACT2: {"correct_value": 4, "explanation": "e"}}


class _Result:
    def __init__(self, rows=(), scalar=None):
        self.rows, self.value = list(rows), scalar

    def mappings(self):
        return self

    def __iter__(self):
        return iter(self.rows)

    def one_or_none(self):
        return self.rows[0] if self.rows else None

    one = first = one_or_none

    def all(self):
        return self.rows

    def scalar_one(self):
        return self.value

    scalar_one_or_none = scalar = scalar_one


class PgWorld:
    """In-memory SQL stand-in: statements are matched by (whitespace-normalised) fragments, in order."""

    def __init__(self, student: str):
        self.snap, self.student = wp4.learner_snapshot(), student
        self.enrollments: dict[str, dict] = {}
        self.events: list[dict] = []
        self.interaction_events: list[dict] = []
        self.statements: list[str] = []
        self.next_id = 0
        self.routes = [
            ("FOR UPDATE OF c", self.course), ("SELECT status FROM learner.student_profile", lambda p: _Result(scalar="ACTIVE")),
            ("AND status='IN_PROGRESS' ORDER BY started_at DESC", self.open_enrollment),
            ("ORDER BY ordinal, state_id", lambda p: _Result(scalar=self.snap["states"][0]["state_id"])),
            ("INSERT INTO learner.micro_course_enrollment", self.insert_enrollment),
            ("INSERT INTO tutor.micro_course_runtime", lambda p: self.runtime_created(p)),
            ("INSERT INTO learner.micro_course_state_event", self.insert_event),
            ("AS step_number", self.runtime_row),
            ("a.validation_status='VALID'", lambda p: _Result(self.assets(p["state_id"]))),
            ("FROM pedagogy.micro_course_state_interaction si", lambda p: _Result(self.state(p["state_id"])["interactions"])),
            ("a.correctness_policy->>'explanation'", lambda p: _Result(self.activities(p["state_id"]))),
            ("DISTINCT ON (payload->>'activity_id')", lambda p: _Result(self.latest("ACTIVITY_RESPONSE", "activity_id"))),
            ("li.learning_item_id, li.question_text, li.choices, li.answer_or_solution_seed", lambda p: _Result(self.items(p["state_id"]))),
            ("DISTINCT ON (payload->>'learning_item_id')", lambda p: _Result(self.latest("QUIZ_RESPONSE", "learning_item_id"))),
            ("seg.segment_id", lambda p: _Result([{k: s[k] for k in ("segment_id", "start_ms", "end_ms", "transcript_text", "speaker",
                                                                      "segment_index")}
                                                  for s in self.state(p["state_id"])["transcript_segments"]])),
            ("SELECT context_type, question_pattern, approved_content FROM pedagogy.state_qa_context",
             lambda p: _Result([{k: q[k] for k in ("context_type", "question_pattern", "approved_content")}
                                for q in self.state(p["state_id"])["qa_contexts"]])),
            ("SELECT transition_id, transition_type, condition_type, priority", self.outgoing),
            ("rt.current_state_id, rt.state_version", self.lock_runtime),
            ("SELECT e.status, e.release_id, rt.current_state_id", self.lock_runtime),
            ("SELECT e.status, e.release_id FROM learner", self.lock_runtime),
            ("SELECT transition_id, to_state_id", self.pick_transition),
            ("SELECT count(*) FROM pedagogy.micro_course_transition", lambda p: _Result(scalar=len(self.outgoing_rows(p["state_id"])))),
            ("UPDATE learner.micro_course_enrollment SET status='COMPLETED'", self.complete),
            ("UPDATE tutor.micro_course_runtime SET state_version=state_version+1, updated_at=now() WHERE", self.bump),
            ("UPDATE tutor.micro_course_runtime SET current_state_id", self.move),
            ("SELECT li.learning_item_id, li.choices, li.correct_answer", self.grading_item),
            ("SELECT sa.state_id, a.activity_type, a.options, a.correctness_policy", self.grading_activity),
            ("SELECT e.enrollment_id, e.status, rt.current_state_id", self.interaction_enrollment),
            ("SELECT 1 FROM visual.interaction_instance",
             lambda p: _Result(scalar=1 if p["id"] == wp4.INTERACTION1 else None)),
            ("INSERT INTO learner.interaction_event", self.insert_interaction),
            ("INSERT INTO pipeline.outbox_event", lambda p: _Result()),
            ("INSERT INTO audit.action_log", lambda p: _Result()),
            ("SELECT li.question_text, li.choices, li.correct_answer", self.assist_item_row),
            ("SELECT a.activity_type, a.prompt, a.options, a.correctness_policy", self.assist_activity_row),
            ("SELECT i.learning_objective, i.success_criteria, si.required", self.assist_interaction_row),
            ("SELECT a.title, a.asset_kind, sa.presentation_role", self.assist_asset_row),
            ("SELECT seg.start_ms, seg.transcript_text", self.assist_segments),
            ("FROM learner.interaction_event WHERE enrollment_id", self.recent_interactions),
            ("FROM pedagogy.micro_course_target t", lambda p: _Result([{"target_type": "CONCEPT", "name": "Equation", "description": None}])),
        ]

    # ---- engine / connection protocol
    @contextmanager
    def begin(self):
        yield self

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.statements.append(sql)
        for fragment, handler in self.routes:
            if fragment in sql:
                return handler(params or {})
        raise AssertionError(f"PgWorld: unhandled statement: {sql[:200]}")

    # ---- helpers over the logical course
    def state(self, state_id):
        return next(s for s in self.snap["states"] if s["state_id"] == str(state_id))

    def enrollment(self, params):
        e = self.enrollments.get(str(params.get("enrollment_id")))
        return e if e and e["student_id"] == str(params.get("student_id", self.student)) else None

    def new_id(self) -> str:
        self.next_id += 1
        return str(uuid.UUID(int=0xE000 + self.next_id))

    # ---- enroll
    def course(self, p):
        if p["code"] != CODE:
            return _Result()
        return _Result([{"micro_course_id": wp4.COURSE_ID, "canonical_code": CODE, "release_id": wp4.REL1}])

    def open_enrollment(self, p):
        open_ = [e for e in self.enrollments.values() if e["student_id"] == p["student_id"] and e["status"] == "IN_PROGRESS"]
        return _Result(scalar=open_[-1]["id"] if open_ else None)

    def insert_enrollment(self, p):
        eid = self.new_id()
        self.enrollments[eid] = {"id": eid, "student_id": p["student_id"], "status": "IN_PROGRESS", "completed_at": None,
                                 "current_state_id": None, "state_version": 1}
        return _Result(scalar=eid)

    def runtime_created(self, p):
        self.enrollments[p["enrollment_id"]]["current_state_id"] = p["state_id"]
        return _Result()

    def insert_event(self, p):
        match = re.search(r"'([A-Z_]+)', CAST", " ".join(self._last_sql().split()))
        self.events.append({"enrollment_id": p["enrollment_id"], "state_id": p["state_id"],
                            "event_type": p.get("event_type") or match.group(1), "payload": json.loads(p["payload"])})
        return _Result()

    def _last_sql(self) -> str:
        return self.statements[-1]

    # ---- runtime
    def runtime_row(self, p):
        e = self.enrollment(p)
        if e is None:
            return _Result()
        st, states = self.state(e["current_state_id"]), self.snap["states"]
        module = self.snap["modules"][0] if st["module_id"] == wp4.MODULE1 else None
        return _Result([{
            "enrollment_id": e["id"], "enrollment_status": e["status"], "started_at": STARTED, "completed_at": e["completed_at"],
            "micro_course_id": wp4.COURSE_ID, "release_id": wp4.REL1, "version": 1, "state_version": e["state_version"],
            "canonical_code": CODE, "course_title": self.snap["course"]["title"], "course_description": "Intro", "estimated_minutes": 15,
            "state_id": st["state_id"], "state_key": st["state_key"], "state_ordinal": st["ordinal"], "state_type": st["state_type"],
            "state_title": st["title"], "objective": st["objective"], "student_instruction": st["student_instruction"],
            "estimated_seconds": st["estimated_seconds"], "required": st["required"], "module_id": st["module_id"],
            "module_title": module["title"] if module else None, "step_count": len(states),
            "step_number": sum(1 for s in states if s["ordinal"] <= st["ordinal"])}])

    def assets(self, state_id):
        return [{**{k: v for k, v in a.items() if k not in ("private_object", "content_hash", "video_asset_id")},
                 "uri": "object-store:abc.png"} for a in self.state(state_id)["assets"]]

    def activities(self, state_id):
        return [{**{k: v for k, v in a.items() if k != "estimated_seconds"}, "explanation": PG_POLICIES[a["activity_id"]]["explanation"]}
                for a in self.state(state_id)["activities"]]

    def items(self, state_id):
        return [{**{k: i[k] for k in ("learning_item_id", "question_text", "choices", "purpose", "ordinal", "required",
                                      "sequence_position")}, "explanation": PG_KEYS[i["learning_item_id"]][1]}
                for i in self.state(state_id)["learning_items"]]

    def latest(self, event_type, field):
        latest = {}
        for ev in self.events:
            if ev["event_type"] == event_type and ev["payload"].get(field):
                latest[ev["payload"][field]] = ev["payload"]["is_correct"]
        return [{field: k, "is_correct": v} for k, v in latest.items()]

    def outgoing_rows(self, state_id):
        return [{k: t[k] for k in ("transition_id", "transition_type", "condition_type", "priority")}
                for t in self.snap["transitions"] if t["from_state_id"] == str(state_id)]

    def outgoing(self, p):
        return _Result(self.outgoing_rows(p["state_id"]))

    # ---- locks and mutations
    def lock_runtime(self, p):
        e = self.enrollment(p)
        if e is None:
            return _Result()
        return _Result([{"status": e["status"], "release_id": wp4.REL1, "current_state_id": e["current_state_id"],
                         "state_version": e["state_version"]}])

    def pick_transition(self, p):
        wanted = p["transition_types"]
        rows = [t for t in self.snap["transitions"] if t["from_state_id"] == p["state_id"] and t["condition_type"] == "ALWAYS"
                and t["transition_type"] in wanted]
        return _Result([{"transition_id": t["transition_id"], "to_state_id": t["to_state_id"]} for t in rows[:1]])

    def complete(self, p):
        e = self.enrollments[p["enrollment_id"]]
        e["status"], e["completed_at"] = "COMPLETED", STARTED
        return _Result()

    def bump(self, p):
        self.enrollments[p["enrollment_id"]]["state_version"] += 1
        return _Result()

    def move(self, p):
        e = self.enrollments[p["enrollment_id"]]
        e["current_state_id"], e["state_version"] = p["state_id"], e["state_version"] + 1
        return _Result()

    # ---- grading lookups
    def grading_item(self, p):
        state = self.state(p["state_id"])
        item = next((i for i in state["learning_items"] if i["learning_item_id"] == p["item_id"]), None)
        if item is None:
            return _Result()
        correct, seed = PG_KEYS[item["learning_item_id"]]
        return _Result([{"learning_item_id": item["learning_item_id"], "choices": item["choices"], "correct_answer": correct,
                         "answer_or_solution_seed": seed}])

    def grading_activity(self, p):
        for st in self.snap["states"]:
            for a in st["activities"]:
                if a["activity_id"] == p["activity_id"]:
                    options = ["x = 1", "x = 2"] if a["activity_type"] == "MCQ" else []
                    return _Result([{"state_id": st["state_id"], "activity_type": a["activity_type"], "options": options,
                                     "correctness_policy": PG_POLICIES[a["activity_id"]]}])
        return _Result()

    # ---- interaction events
    def interaction_enrollment(self, p):
        e = self.enrollment(p)
        return _Result([{"enrollment_id": e["id"], "status": e["status"], "current_state_id": e["current_state_id"]}] if e else [])

    def insert_interaction(self, p):
        self.interaction_events.append(p)
        return _Result(scalar=self.new_id())

    def recent_interactions(self, p):
        rows = [e for e in self.interaction_events if e["enrollment_id"] == p["enrollment_id"] and e["instance_id"] == p["item_id"]]
        return _Result([{"event_type": e["event_type"], "semantic_action": e["semantic_action"], "control_key": e["control_key"],
                         "action_payload": json.loads(e["payload"])} for e in reversed(rows)][: p["limit"]])

    # ---- item-help grounding rows
    def _member(self, state_id, key, field, value):
        return next((m for m in self.state(state_id)[key] if m[field] == value), None)

    def assist_item_row(self, p):
        m = self._member(p["state_id"], "learning_items", "learning_item_id", p["item_id"])
        return _Result([{"question_text": m["question_text"], "choices": m["choices"], "correct_answer": PG_KEYS[p["item_id"]][0],
                         "answer_or_solution_seed": PG_KEYS[p["item_id"]][1], "purpose": m["purpose"], "required": m["required"]}] if m else [])

    def assist_activity_row(self, p):
        m = self._member(p["state_id"], "activities", "activity_id", p["item_id"])
        return _Result([{"activity_type": m["activity_type"], "prompt": m["prompt"], "options": wp4.learner_snapshot() and
                         [{"label": o.get("label")} for o in m["options"]] if m["options"] else [],
                         "correctness_policy": PG_POLICIES[p["item_id"]], "purpose": m["purpose"], "required": m["required"]}] if m else [])

    def assist_interaction_row(self, p):
        m = self._member(p["state_id"], "interactions", "interaction_instance_id", p["item_id"])
        return _Result([{"learning_objective": m["learning_objective"], "success_criteria": m["success_criteria"],
                         "required": m["required"]}] if m else [])

    def assist_asset_row(self, p):
        m = self._member(p["state_id"], "assets", "asset_id", p["item_id"])
        return _Result([{"title": m["title"], "asset_kind": m["asset_kind"], "presentation_role": m["presentation_role"]}] if m else [])

    def assist_segments(self, p):
        return _Result([{"start_ms": s["start_ms"], "transcript_text": s["transcript_text"]}
                        for s in self.snap["states"][0]["transcript_segments"]])


def fake_student_header(x_student: str = Header()) -> uuid.UUID:
    return uuid.UUID(x_student)


EID = str(uuid.UUID(int=0xE001))             # both backends mint the same first enrollment id (see ``parity``)


class Parity:
    """One TestClient per backend; the learner and content stores are switched per request."""

    def __init__(self, student: str):
        self.who, http = student, TestClient(app)
        self.clients = {}
        for backend, learner, content in (("postgres", MicroCoursePostgres(), PostgresContentStore()),
                                          ("dynamodb", STORE, DynamoDBContentStore())):
            self.clients[backend] = self._client(http, learner, content)

    def _client(self, http, learner, content):
        outer = self

        class One:
            def request(self, method, path, **kw):
                kw["headers"] = {"X-Student": outer.who, **(kw.get("headers") or {})}
                with stores.override_store("learner", learner), stores.override_store("content", content):
                    return http.request(method, path, **kw)

        return One()

    def both(self, name, method, path, *, json_body=None, expect=None, allowed=()):
        """Run one request on both backends and fail on any difference not listed in ``allowed``."""
        case = ParityCase(name, method, path, json=json_body, expect_status=expect)
        return assert_parity(self.clients, case, allowed=["$.started_at", "$.completed_at", *allowed])


@pytest.fixture()
def parity(world, monkeypatch):
    pg = PgWorld(world)
    monkeypatch.setattr(mc_router, "engine", pg)
    counter = iter(range(0xE001, 0xF000))
    monkeypatch.setattr(toolkit, "uuid7", lambda: str(uuid.UUID(int=next(counter))))     # enrollment id first: 0xE001, like PgWorld
    app.dependency_overrides[security.get_current_student_id] = fake_student_header
    monkeypatch.setattr(assist, "_help", lambda kind, grounding, message: {"intent": "help", "item_kind": kind, "grounding": grounding,
                                                                        "message": message})
    yield Parity(world)
    app.dependency_overrides.pop(security.get_current_student_id, None)


def enroll_both(c: Parity):
    res = c.both("enroll", "POST", f"/v1/micro-courses/{CODE}/enroll", expect=201)
    assert res["dynamodb"][1]["enrollment_id"] == EID == res["postgres"][1]["enrollment_id"]
    return res


def test_student_routes_have_parity_across_backends(parity):
    c = parity
    enroll_both(c)
    c.both("enroll again resumes", "POST", f"/v1/micro-courses/{CODE}/enroll", expect=201)
    first = c.both("runtime", "GET", f"/v1/micro-courses/enrollments/{EID}", expect=200)
    wp4.assert_no_keys(first["dynamodb"][1])
    wp4.assert_no_keys(first["postgres"][1])
    base_path = f"/v1/micro-courses/enrollments/{EID}"
    c.both("incorrect", "POST", f"{base_path}/responses", json_body={"learning_item_id": wp4.LI1, "choice_index": 0}, expect=200)
    c.both("correct", "POST", f"{base_path}/responses", json_body={"learning_item_id": wp4.LI1, "choice_index": 1}, expect=200)
    c.both("give up", "POST", f"{base_path}/responses", json_body={"learning_item_id": wp4.LI2, "gave_up": True}, expect=200)
    c.both("missing choice", "POST", f"{base_path}/responses", json_body={"learning_item_id": wp4.LI1}, expect=422)
    c.both("unknown item", "POST", f"{base_path}/responses", json_body={"learning_item_id": "LI-nope", "choice_index": 0}, expect=404)
    c.both("activity choice", "POST", f"{base_path}/activity-responses", json_body={"activity_id": wp4.ACT1, "choice_index": 1}, expect=200)
    c.both("activity numeric", "POST", f"{base_path}/activity-responses", json_body={"activity_id": wp4.ACT2, "value": 4}, expect=200)
    c.both("activity give up", "POST", f"{base_path}/activity-responses", json_body={"activity_id": wp4.ACT2, "gave_up": True}, expect=200)
    c.both("unknown activity", "POST", f"{base_path}/activity-responses", json_body={"activity_id": wp4.uid(999), "choice_index": 0},
           expect=404)
    answered = c.both("runtime after answers", "GET", base_path, expect=200)
    state = answered["dynamodb"][1]["current_state"]
    assert state["answered_learning_item_ids"] == [wp4.LI1, wp4.LI2] and state["learning_items"][0]["explanation"]
    c.both("interaction event", "POST", f"{base_path}/interaction-events", expect=200, allowed=("$.interaction_event_id",),
           json_body={"interaction_instance_id": wp4.INTERACTION1, "event_type": "change", "semantic_action": "set_value",
                      "control_key": "slider", "action_payload": {"value": 0.25}})
    c.both("interaction unknown instance", "POST", f"{base_path}/interaction-events", expect=404,
           json_body={"interaction_instance_id": wp4.uid(998), "event_type": "x", "semantic_action": "y"})
    for kind, item in (("learning_item", wp4.LI1), ("activity", wp4.ACT1), ("interaction", wp4.INTERACTION1), ("asset", wp4.ASSET_PRIVATE)):
        res = c.both(f"help {kind}", "POST", f"{base_path}/item-help", expect=200,
                     json_body={"item_kind": kind, "item_id": item, "intent": "help", "student_message": "stuck"},
                     allowed=("$.grounding.canonical_targets[*].description", "$.grounding.state_context.canonical_targets[*].description"))
        wp4.assert_no_keys(res["dynamodb"][1])
    c.both("give up learning item", "POST", f"{base_path}/item-help", expect=200,
           json_body={"item_kind": "learning_item", "item_id": wp4.LI1, "intent": "give_up"})
    c.both("give up activity", "POST", f"{base_path}/item-help", expect=200,
           json_body={"item_kind": "activity", "item_id": wp4.ACT2, "intent": "give_up"})
    c.both("give up asset", "POST", f"{base_path}/item-help", expect=200,
           json_body={"item_kind": "asset", "item_id": wp4.ASSET_PRIVATE, "intent": "give_up"})
    c.both("help outside the state", "POST", f"{base_path}/item-help", expect=404,
           json_body={"item_kind": "learning_item", "item_id": "LI-nope", "intent": "help"})
    c.both("advance with a stale version", "POST", f"{base_path}/advance", expect=409,
           json_body={"expected_state_version": 9, "action": "CONTINUE"})
    c.both("advance back has no transition", "POST", f"{base_path}/advance", expect=409,
           json_body={"expected_state_version": 1, "action": "BACK"})
    moved = c.both("advance", "POST", f"{base_path}/advance", expect=200, json_body={"expected_state_version": 1, "action": "CONTINUE"})
    assert moved["dynamodb"][1]["state_version"] == 2 and moved["dynamodb"][1]["can_finish"] is True
    c.both("advance with the old version", "POST", f"{base_path}/advance", expect=409,
           json_body={"expected_state_version": 1, "action": "CONTINUE"})
    done = c.both("complete", "POST", f"{base_path}/advance", expect=200, json_body={"expected_state_version": 2, "action": "CONTINUE"})
    assert done["dynamodb"][1]["enrollment_status"] == "COMPLETED"
    c.both("respond after completion", "POST", f"{base_path}/responses", expect=409,
           json_body={"learning_item_id": wp4.LI1, "choice_index": 1})
    c.both("runtime after completion", "GET", base_path, expect=200)
    c.both("unknown course", "POST", "/v1/micro-courses/MC-NOPE/enroll", expect=404)


def test_another_students_enrollment_is_404_on_both_backends(parity):
    c = parity
    enroll_both(c)
    owner = c.who
    other = str(uuid.uuid4())
    seed_profile(other)
    c.who = other
    base_path = f"/v1/micro-courses/enrollments/{EID}"
    c.both("runtime", "GET", base_path, expect=404)
    c.both("response", "POST", f"{base_path}/responses", expect=404, json_body={"learning_item_id": wp4.LI1, "choice_index": 1})
    c.both("advance", "POST", f"{base_path}/advance", expect=404, json_body={"expected_state_version": 1, "action": "CONTINUE"})
    c.both("item help", "POST", f"{base_path}/item-help", expect=404,
           json_body={"item_kind": "learning_item", "item_id": wp4.LI1, "intent": "give_up"})
    c.who = owner
    c.both("the owner still sees it", "GET", base_path, expect=200)


def test_routes_pass_the_idempotency_key_and_replay_on_dynamodb(world, monkeypatch):
    app.dependency_overrides[security.get_current_student_id] = fake_student_header
    try:
        http = TestClient(app)

        def call(method, path, key=None, **kw):
            headers = {"X-Student": world, **({"Idempotency-Key": key} if key else {})}
            with stores.override_store("learner", STORE), stores.override_store("content", DynamoDBContentStore()):
                return http.request(method, path, headers=headers, **kw)

        with no_postgres(monkeypatch):
            first = call("POST", f"/v1/micro-courses/{CODE}/enroll", key="e1")
            assert first.status_code == 201 and "replayed" not in first.json()
            replay = call("POST", f"/v1/micro-courses/{CODE}/enroll", key="e1")
            assert replay.status_code == 201 and replay.json()["replayed"] is True
            eid = first.json()["enrollment_id"]
            body = {"learning_item_id": wp4.LI1, "choice_index": 1}
            one = call("POST", f"/v1/micro-courses/enrollments/{eid}/responses", key="r1", json=body)
            two = call("POST", f"/v1/micro-courses/enrollments/{eid}/responses", key="r1", json=body)
            assert one.status_code == two.status_code == 200 and two.json() == {**one.json(), "replayed": True}
            reused = call("POST", f"/v1/micro-courses/enrollments/{eid}/responses", key="r1",
                          json={"learning_item_id": wp4.LI1, "choice_index": 0})
            assert reused.status_code == 422 and reused.json()["detail"] == "idempotency_key_reused"
            mine = call("GET", "/v1/learner/micro-course-enrollments")
            assert mine.status_code == 200 and mine.json()["total"] == 1 and mine.json()["items"][0]["enrollment_id"] == eid
            assert call("GET", "/v1/learner/micro-course-enrollments", params={"status": "COMPLETED"}).json() == {"items": [], "total": 0}
            assert call("GET", "/v1/learner/micro-course-enrollments", params={"status": "BOGUS"}).status_code == 422
            gone = call("POST", f"/v1/micro-courses/enrollments/{eid}/abandon", key="a1")
            assert gone.status_code == 200 and gone.json()["status"] == "ABANDONED"
            assert call("POST", f"/v1/micro-courses/enrollments/{eid}/abandon", key="a1").json()["replayed"] is True
            assert call("GET", "/v1/learner/misconceptions").json() == {"items": [], "total": 0}
    finally:
        app.dependency_overrides.pop(security.get_current_student_id, None)


def test_the_learner_enrollment_list_on_postgres_uses_the_service_function(monkeypatch):
    app.dependency_overrides[security.get_current_student_id] = fake_student_header
    try:
        seen = []
        monkeypatch.setattr(courses, "list_enrollments", lambda conn, sid, status, limit: seen.append((sid, status, limit)) or
                            {"items": [], "total": 0})
        monkeypatch.setattr(ixrt, "list_misconception_state", lambda conn, sid: seen.append(("misc", sid)) or [])
        monkeypatch.setattr(mc_router, "engine", PgWorld(str(uuid.uuid4())))
        sid = str(uuid.uuid4())
        with stores.override_store("learner", MicroCoursePostgres()):
            http = TestClient(app)
            assert http.get("/v1/learner/micro-course-enrollments", params={"status": "ABANDONED", "limit": 500},
                            headers={"X-Student": sid}).json() == {"items": [], "total": 0}
            assert http.get("/v1/learner/misconceptions", headers={"X-Student": sid}).json() == {"items": [], "total": 0}
        assert seen == [(sid, "ABANDONED", 200), ("misc", sid)]
    finally:
        app.dependency_overrides.pop(security.get_current_student_id, None)


def test_event_items_are_append_only_and_owned_by_the_learner(world):
    eid = eid_of(enroll(world))
    uow = LearnerUnitOfWork(world)
    event = items_of(world, mc.LearnerMcevent)[0]
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.update(mc.LearnerMcevent, event.PK, event.SK, {"event_type": "RESET"})
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.delete(mc.LearnerIxevent, event.PK, event.SK)
    with pytest.raises(ValidationFailed, match="another student"):
        uow.put_new(mc.LearnerMcevent(
            PK=toolkit.student_pk(str(uuid.uuid4())), SK=mc.mcevent_sk(eid, toolkit.now_iso(), uuid.uuid4()), student_id=world,
            enrollment_id=eid, event_id=uuid.uuid4(), event_type="ENROLLED", actor_type="STUDENT", release_id=wp4.REL1,
            created_at=toolkit.now_iso()))
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.put(items_of(world, mc.LearnerMcevent)[0])
    assert base.model_for("learner", "MCEVENT") is mc.LearnerMcevent


class _SqlConn:
    """Canned results for the statements of the new PostgreSQL functions (matched by normalised fragment)."""

    def __init__(self, *routes):
        self.routes, self.statements = routes, []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.statements.append((sql, params))
        for fragment, result in self.routes:
            if fragment in sql:
                return result(params) if callable(result) else result
        raise AssertionError(f"unhandled statement: {sql[:160]}")


def test_the_new_postgres_functions_issue_the_documented_statements():
    sid, eid, state, to_state = (str(uuid.uuid4()) for _ in range(4))
    summary = {"enrollment_id": eid, "canonical_code": CODE, "micro_course_id": wp4.COURSE_ID, "release_id": wp4.REL1,
               "status": "ABANDONED", "current_state_id": state, "state_version": 4, "started_at": STARTED, "completed_at": None}
    lock = {"status": "IN_PROGRESS", "current_state_id": state, "state_version": 3, "student_id": sid, "release_id": wp4.REL1}
    conn = _SqlConn(
        ("FOR UPDATE OF e, rt", _Result([lock])),
        ("SELECT 1 FROM pedagogy.micro_course_state", lambda p: _Result(scalar=1 if p["state_id"] == to_state else None)),
        ("UPDATE learner.micro_course_enrollment SET status='ABANDONED'", _Result()),
        ("UPDATE tutor.micro_course_runtime", _Result()),
        ("INSERT INTO learner.micro_course_state_event", _Result()),
        ("JOIN pedagogy.micro_course c ON c.micro_course_id = e.micro_course_id WHERE e.enrollment_id", _Result([summary])),
        ("JOIN pedagogy.micro_course c ON c.micro_course_id = e.micro_course_id WHERE e.student_id", _Result([{**summary, "status": "COMPLETED"}])),
        ("SELECT count(*) FROM learner.micro_course_enrollment e WHERE e.student_id", _Result(scalar=1)),
        ("SELECT student_id FROM learner.micro_course_enrollment", _Result(scalar=uuid.UUID(sid))),
        ("FROM learner.misconception_evidence", _Result([
            {"misconception_id": uuid.UUID(MISCONCEPTION), "confidence_after": 0.9, "evidence_id": uuid.UUID(eid), "created_at": STARTED},
            {"misconception_id": uuid.UUID(wp4.uid(1)), "confidence_after": 0.2, "evidence_id": uuid.UUID(state), "created_at": STARTED}])),
    )
    listed = courses.list_enrollments(conn, sid, "COMPLETED", 10)
    assert listed["total"] == 1 and set(listed["items"][0]) == {"enrollment_id", "canonical_code", "micro_course_id", "release_id",
                                                                 "status", "current_state_id", "state_version", "started_at",
                                                                 "completed_at"}
    assert conn.statements[0][1] == {"student_id": sid, "status": "COMPLETED", "limit": 10}
    with pytest.raises(ValueError, match="status must be"):
        courses.list_enrollments(conn, sid, "DONE")
    gone = courses.abandon_enrollment(conn, eid, sid)
    assert gone["status"] == "ABANDONED" and gone["state_version"] == 4
    events = [(s, p) for s, p in conn.statements if "INSERT INTO learner.micro_course_state_event" in s]
    assert "'ABANDONED'" in events[0][0] and json.loads(events[0][1]["payload"])["from_state_version"] == 3
    assert courses.get_enrollment_owner(conn, eid) == sid
    seen = []
    real = courses.get_enrollment_runtime
    courses.get_enrollment_runtime = lambda c, e, s: seen.append((e, s)) or {"ok": True}
    try:
        assert courses.reset_enrollment(conn, eid, to_state, "service:admin-key") == {"ok": True}
        with pytest.raises(ValueError, match="does not belong"):
            courses.reset_enrollment(conn, eid, wp4.uid(1), "service:admin-key")
    finally:
        courses.get_enrollment_runtime = real
    assert seen == [(eid, sid)]
    reset = next((s, p) for s, p in conn.statements if "'RESET'" in s)
    assert json.loads(reset[1]["payload"]) == {"action": "RESET", "actor": "service:admin-key", "from_state_id": state,
                                              "to_state_id": to_state, "from_state_version": 3}
    misc = ixrt.list_misconception_state(conn, sid)
    assert [(m["misconception_id"], m["confidence"], m["confirmed"]) for m in misc] == [(MISCONCEPTION, 0.9, True),
                                                                                        (wp4.uid(1), 0.2, False)]


def test_the_real_environment_smoke_script_passes_on_moto(world, capsys):
    """scripts/learner_smoke_microcourse.py is only ever run read-only against dev; here its checks run on moto."""
    import importlib.util

    path = Path(__file__).resolve().parents[2] / "scripts" / "learner_smoke_microcourse.py"
    spec = importlib.util.spec_from_file_location("learner_smoke_microcourse", path)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    eid = eid_of(enroll(world))
    STORE.submit_learning_item_response(None, eid, world, wp4.LI1, 1)
    STORE.submit_activity_response(None, eid, world, wp4.ACT1, choice_index=0)
    STORE.record_interaction_event(None, eid, world, wp4.INTERACTION1, event_type="CHANGE", semantic_action="SET")
    smoke.smoke(5)
    out = capsys.readouterr().out
    assert "FAIL" not in out and smoke.FAILURES == [], out
    assert "A27 runtime shape" in out and "A31 last interactions of an item" in out and "A29 MC-1: activity shape" in out
