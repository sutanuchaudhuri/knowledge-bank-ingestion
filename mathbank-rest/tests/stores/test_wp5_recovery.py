"""WP5 recovery area (requirement 71, requirement 70 C1 T14-T19, A23-A25): the DynamoDB ``RecoveryStore`` on moto.

Same world as ``test_wp5_diagnosis`` (content store on moto, composed ``DynamoDBLearnerStore``, PostgreSQL forbidden). The router is simulated
exactly as ``routers/step_runtime.py`` does it: ``load_item_response_context`` (replay check, read-only) -> ``grade_item`` (pure) -> ``apply_item_response``.
"""
# ruff: noqa: F811  (fixtures imported from test_wp5_diagnosis are used as arguments)
from __future__ import annotations

import datetime as dt
import json
import uuid

import pytest
from test_wp5_diagnosis import (
    EVALUATION,
    SK_UUID,
    attempt_of,
    diags,
    fail,
    gaps,
    seed_taxonomy,
    student,  # noqa: F401  (fixture)
    succeed,
    world,  # noqa: F401  (fixture)
)
from test_wp5_solve import CODE, NoPostgres, feed, pk, seed_content, solve_of, step_of, types

from mathbank_rest import step_recovery_logic as logic
from mathbank_rest import stores
from mathbank_rest.models.manual.learner_diagnosis import (
    LearnerGap,
    LearnerPlan,
    LearnerPlanOwner,
    plan_owner_pk,
    plan_sk,
)
from mathbank_rest.step_logic import (
    IdempotencyKeyReused,
    InvalidTransition,
    NotFound,
    StateVersionConflict,
)
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.learner import DynamoDBLearnerStore, recovery
from mathbank_rest.stores.learner import uow as uow_module

OK = {"verdict": "CORRECT", "confidence": 0.95, "feedback": "Nice.", "model": "fake"}
BAD = {"verdict": "INCORRECT", "confidence": 0.9, "feedback": "Not quite.", "model": "fake"}


def plan_model(sid: str, plan_id: str) -> LearnerPlan:
    return typed.require(LearnerPlan, pk(sid), plan_sk(plan_id))


def version_of(store, sid: str, aid: str) -> int:
    return store.get_attempt_runtime(aid, sid)["attempt"]["state_version"]


def make_plan(store, sid, aid, **kw) -> dict:
    return store.create_plan(sid, aid, version_of(store, sid, aid), **kw)


def current_item(view: dict) -> dict:
    return next(i for i in view["items"] if i["ordinal"] == view["current_item_ordinal"])


def respond(store, sid, plan_id, *, correct=True, key=None, version=None) -> dict:
    """What the router does for ``POST /recovery-plans/{id}/items/{item}/responses``."""
    view = store.get_recovery_plan(sid, plan_id)
    item = current_item(view)
    form = (item.get("content") or {}).get("form")
    response = ({"acknowledged": True} if item["item_kind"] == "THEORY"
                else {"choice_index": 1 if correct else 0} if form == "MCQ" else {"response_text": "a plausible idea"})
    v = version if version is not None else version_of(store, sid, view["solve_attempt_id"])
    ctx = store.load_item_response_context(sid, plan_id, item["recovery_plan_item_id"], response, v, key)
    if "replay" in ctx:
        return ctx["replay"]
    grade = logic.grade_item(ctx, response, lambda c: OK if correct else BAD)
    return store.apply_item_response(sid, plan_id, item["recovery_plan_item_id"], response, grade, v, key)


def finish_plan(store, sid, plan_id) -> dict:
    out = {}
    for _ in range(12):
        out = respond(store, sid, plan_id)
        if out["transition"] not in ("NEXT_ITEM", "EXTRA_ITEM"):
            break
    return out


def stored_items(sid, plan_id) -> list[dict]:
    return [i.model_dump(mode="json") for i in plan_model(sid, plan_id).items]


@pytest.fixture()
def bare_world(content_table, monkeypatch):
    """Content without any learning item or worked example: a recovery plan has no material."""
    from mathbank_rest.db import postgres

    seed_content()
    seed_taxonomy()
    monkeypatch.setattr(postgres, "engine", NoPostgres())
    with stores.override_store("content", DynamoDBContentStore()):
        yield DynamoDBLearnerStore()


# ---------------------------------------------------------------------------------------------------------- T16 create

def test_create_plan_writes_the_whole_aggregate_in_one_transaction(student, world):
    aid = attempt_of(world, student)
    out = make_plan(world, student, aid)
    assert set(out) == {"recovery_plan", "resumed", "state_version", "replayed"} and out["resumed"] is False and out["replayed"] is False
    assert out["state_version"] == 3
    view = out["recovery_plan"]
    assert [(i["stage"], i["item_kind"], i["status"]) for i in view["items"]] == [
        ("FOUNDATION", "THEORY", "PRESENTED"), ("RECOGNITION", "LEARNING_ITEM", "PENDING"), ("ISOLATED_EXECUTION", "LEARNING_ITEM", "PENDING"),
        ("GUIDED_APPLICATION", "LEARNING_ITEM", "PENDING"), ("TRANSFER", "LEARNING_ITEM", "PENDING"), ("RETURN_TO_STEP", "RETURN", "PENDING")]
    assert (view["status"], view["trigger"], view["target_label"], view["current_item_ordinal"], view["can_return"]) == (
        "ACTIVE", "STUDENT_REQUEST", "skill1", 1, False)
    assert view["origin"] == {"problem_code": CODE, "solution_step_id": "st1", "part_label": "MAIN", "step_index_in_part": 1,
                              "global_step_index": 1}
    assert view["items"][0]["content"]["example_problem_code"] == "BK_P2" and "content" not in view["items"][1]   # only the current item shows
    assert view["mastery"] == {"independent_successes": 0, "independent_successes_required": 2, "transfer_passed": False,
                               "transfer_required": True, "met": False}
    plan_id = view["recovery_plan_id"]
    stored = plan_model(student, plan_id)
    assert (stored.status, stored.version, stored.GSI1PK, stored.planner_version) == ("ACTIVE", 1, "PLANSTATUS#ACTIVE", "recovery-rules-v1")
    assert typed.require(LearnerPlanOwner, plan_owner_pk(plan_id), "OWNER").student_id == uuid.UUID(student)
    solve = solve_of(student, aid)
    assert (solve.current_mode, solve.state_version, str(solve.current_recovery_plan_id), str(solve.recovery_plan_id)) == (
        "RECOVERY", 3, plan_id, plan_id) and [str(p) for p in solve.plan_ids] == [plan_id] and solve.GSI1PK.startswith("OPEN_SOLVE#")
    assert step_of(student, aid, "st1").state == "DETOURED"
    assert types(student, aid)[-2:] == ["RECOVERY_PLAN_CREATED", "RECOVERY_ITEM_PRESENTED"]
    # denormalised from the immutable learning item, so a plan view needs no join
    assert stored.items[1].transformation_type == "MCQ_METHOD_RECOGNITION" and stored.items[1].transformed_form == "MCQ"
    # the learner view never carries the answer of an unfinished item; the key stays in the content store
    assert "answer" not in json.dumps(view) and "correct_answer" not in json.dumps(view)


def test_a_running_detour_is_returned_instead_of_a_second_one(student, world):
    aid = attempt_of(world, student)
    first = make_plan(world, student, aid)
    again = world.create_plan(student, aid, 1, trigger="STUDENT_REQUEST")                  # a stale version does not matter: nothing changes
    assert again["resumed"] is True and "replayed" not in again and again["state_version"] == first["state_version"]
    assert again["recovery_plan"]["recovery_plan_id"] == first["recovery_plan"]["recovery_plan_id"]
    assert len(typed.query(LearnerPlan, pk(student), sk_begins="PLAN#", limit=20).items) == 1
    assert solve_of(student, aid).state_version == 3


def test_create_plan_is_idempotent_and_guards_the_version(student, world):
    aid = attempt_of(world, student)
    v = version_of(world, student, aid)
    first = world.create_plan(student, aid, v, idempotency_key="c-1")
    replay = world.create_plan(student, aid, v, idempotency_key="c-1")
    assert replay["replayed"] is True and replay["recovery_plan"] == first["recovery_plan"] and replay["state_version"] == first["state_version"]
    assert len(typed.query(LearnerPlan, pk(student), sk_begins="PLAN#", limit=20).items) == 1
    with pytest.raises(IdempotencyKeyReused):
        world.create_plan(student, aid, v, trigger="TUTOR", idempotency_key="c-1")
    other = str(uuid.uuid4())
    aid2 = attempt_of(world, other)
    with pytest.raises(StateVersionConflict):
        world.create_plan(other, aid2, 99)
    assert typed.query(LearnerPlan, pk(other), sk_begins="PLAN#", limit=20).items == [] and solve_of(other, aid2).state_version == 2


def test_create_plan_validation_and_scoping(student, world):
    aid = attempt_of(world, student)
    with pytest.raises(NotFound):
        world.create_plan(str(uuid.uuid4()), aid, 2)                                          # a foreign learner: 404
    with pytest.raises(NotFound):
        world.create_plan(student, str(uuid.uuid4()), 2)
    with pytest.raises(ValueError):
        world.create_plan(student, aid, 2, trigger="BRANCH")
    with pytest.raises(InvalidTransition):
        world.create_plan(student, aid, 2, trigger="DIAGNOSIS")                               # needs gap_diagnosis_id
    with pytest.raises(NotFound):
        world.create_plan(student, aid, 2, trigger="DIAGNOSIS", gap_diagnosis_id=str(uuid.uuid4()))
    world.submit_attempt(student, aid, 2)
    with pytest.raises(InvalidTransition):
        world.create_plan(student, aid, 3)                                                    # a SUBMITTED attempt has no detour
    assert typed.query(LearnerPlan, pk(student), sk_begins="PLAN#", limit=20).items == []


def test_no_material_is_a_409_and_changes_nothing(sid, bare_world):
    student = sid
    aid = attempt_of(bare_world, student)
    with pytest.raises(logic.NoRecoveryMaterial) as exc:
        make_plan(bare_world, student, aid)
    assert exc.value.status_code == 409 and exc.value.code == "NO_RECOVERY_MATERIAL" and "skill1" in str(exc.value)
    assert solve_of(student, aid).current_mode == "SOLVING" and step_of(student, aid, "st1").state == "PRESENTED"
    assert typed.query(LearnerPlan, pk(student), sk_begins="PLAN#", limit=20).items == []


def test_the_solve_area_refuses_step_actions_during_a_detour(student, world):
    aid = attempt_of(world, student)
    make_plan(world, student, aid)
    with pytest.raises(InvalidTransition):
        world.submit_step_response(student, aid, "st1", "x", 3)
    with pytest.raises(InvalidTransition):
        world.submit_attempt(student, aid, 3)


# ---------------------------------------------------------------------------------------------------------- A23 reads

def test_get_plan_and_next_item_are_owner_scoped(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    view = world.get_recovery_plan(student, plan_id)
    nxt = world.get_next_recovery_item(student, plan_id)
    assert set(nxt) == {"recovery_plan_id", "status", "item", "mastery", "can_return"} and nxt["item"] == current_item(view)
    assert world.get_recovery_plan(None, plan_id)["recovery_plan_id"] == plan_id              # the admin read resolves the owner pointer
    for call in (world.get_recovery_plan, world.get_next_recovery_item):
        with pytest.raises(NotFound):
            call(str(uuid.uuid4()), plan_id)
        with pytest.raises(NotFound):
            call(student, str(uuid.uuid4()))
    with pytest.raises(NotFound):
        world.get_recovery_plan(None, str(uuid.uuid4()))


# ---------------------------------------------------------------------------------------------------------- T17 responses, T18 resume

def test_a_plan_runs_to_mastery_resolves_its_gap_and_returns_to_the_exact_step(student, world):
    aid = attempt_of(world, student)
    out = fail(world, student, aid, times=2)
    did = out["diagnosis"]["gap_diagnosis_id"]
    [gap] = gaps(student)
    created = make_plan(world, student, aid, trigger="DIAGNOSIS", gap_diagnosis_id=did)
    plan_id = created["recovery_plan"]["recovery_plan_id"]
    stored = plan_model(student, plan_id)
    assert str(stored.knowledge_gap_id) == str(gap.knowledge_gap_id) and str(stored.gap_diagnosis_id) == did and stored.trigger == "DIAGNOSIS"
    g = typed.require(LearnerGap, pk(student), gap.SK)
    assert (str(g.latest_plan_id), g.latest_plan_status, g.version) == (plan_id, "ACTIVE", 2)
    version = created["state_version"]
    transitions = []
    for _ in range(5):                                                       # worked example, 3 practice items, transfer
        step = respond(world, student, plan_id)
        assert step["state_version"] == version + 1 and step["decision"] == "ADVANCE" and step["replayed"] is False
        version = step["state_version"]
        transitions.append(step["transition"])
    assert transitions == ["NEXT_ITEM"] * 4 + ["PLAN_COMPLETED"]
    view = step["recovery_plan"]
    assert (view["status"], view["can_return"], view["current_item_ordinal"]) == ("COMPLETED", True, 6)
    assert view["outcome"]["mastery"]["met"] is True and view["mastery"]["independent_successes"] == 4 and view["ended_at"] is not None
    assert current_item(view)["item_kind"] == "RETURN" and current_item(view)["status"] == "PRESENTED"
    assert set(step) == {"result", "decision", "transition", "state_version", "recovery_plan", "replayed"}
    assert set(step["result"]) == {"result", "verdict", "feedback"}
    # the finished plan resolved its gap (never mastery), and says so in the learner's feed
    g = typed.require(LearnerGap, pk(student), gap.SK)
    assert (g.status, g.GSI1PK, g.latest_plan_status) == ("RESOLVED", "GAPSTATUS#RESOLVED", "COMPLETED") and g.resolved_at is not None
    assert "GAP_HYPOTHESIS_RESOLVED" in types(student, aid) and "RECOVERY_PLAN_COMPLETED" in types(student, aid)
    assert stored.version == 1 and plan_model(student, plan_id).version == 6 and plan_model(student, plan_id).GSI1PK == "PLANSTATUS#COMPLETED"
    # finished items reveal their answers; nothing else does
    assert "answer" in view["items"][1]["content"] and "answer" not in view["items"][5]["content"]
    # resume: back to the origin step, counted for the solve area
    before = step_of(student, aid, "st1")
    left = world.leave_recovery(student, plan_id, version)
    assert left == {"returned_to_step_id": "st1", "recovery_plan_id": plan_id, "plan_status": "COMPLETED", "state_version": version + 1,
                    "replayed": False}
    solve = solve_of(student, aid)
    assert (solve.current_mode, solve.current_solution_step_id, solve.current_recovery_plan_id) == ("SOLVING", "st1", None)
    assert solve.state_version == version + 1 and solve.recovery_plan_id is not None and [str(p) for p in solve.plan_ids] == [plan_id]
    after = step_of(student, aid, "st1")
    assert after.state == "RETRY_PRESENTED" and after.returned_to_step_count == before.returned_to_step_count + 1 == 1
    assert after.returned_to_problem_count == 0
    assert types(student, aid)[-2:] == ["RETURNED_TO_ORIGINAL_STEP", "STEP_PRESENTED"]
    assert stored_items(student, plan_id)[-1]["status"] == "PASSED"
    # the solve area closes the loop on the next outcome of the step
    done = succeed(world, student, aid, "st1")
    assert "RETURNED_TO_ORIGINAL_PROBLEM" in types(student, aid) and step_of(student, aid, "st1").returned_to_problem_count == 1
    assert done["state"] == "SUCCESS_INDEPENDENT"


def test_a_wrong_answer_retries_then_adapts(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    respond(world, student, plan_id)                                                         # the worked example
    wrong = respond(world, student, plan_id, correct=False)
    assert (wrong["decision"], wrong["transition"], wrong["result"]["result"]) == ("RETRY", "RETRY", "FAILED")
    item = current_item(wrong["recovery_plan"])
    assert (item["status"], item["tries"], item["stage"]) == ("PRESENTED", 1, "RECOGNITION") and item["content"].get("answer") is None
    assert item["last_result"] == {"result": "FAILED", "verdict": "INCORRECT", "feedback": "Not this one. Look again at what the problem needs at this point."}
    assert item["last_response"] == {"choice_index": 0}
    second = respond(world, student, plan_id, correct=False)                                  # final failure of a recognition item: no prerequisite -> alternate
    assert (second["decision"], second["transition"]) == ("BRANCH", "NEXT_ITEM")
    items = stored_items(student, plan_id)
    assert [i["ordinal"] for i in items] == list(range(1, 8)) and items[1]["status"] == "FAILED" and items[1]["independent_success"] is False
    assert (items[2]["added_reason"], items[2]["stage"], items[2]["status"]) == ("ALTERNATE_AFTER_FAILURE", "RECOGNITION", "PRESENTED")
    assert items[2]["learning_item_id"] != items[1]["learning_item_id"] and items[-1]["item_kind"] == "RETURN"
    assert second["recovery_plan"]["current_item_ordinal"] == 3 and second["recovery_plan"]["items"][1]["content"]["answer"]   # finished: revealed
    # teacher evidence is stored with the item, never in the learner view
    assert items[1]["last_result"]["teacher"]["grader"] == "deterministic" and "teacher" not in json.dumps(second["recovery_plan"])


def test_success_after_a_retry_adds_one_confirmation_item(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    respond(world, student, plan_id)
    respond(world, student, plan_id, correct=False)
    out = respond(world, student, plan_id)
    assert (out["decision"], out["transition"]) == ("CONFIRM", "NEXT_ITEM")
    items = stored_items(student, plan_id)
    assert items[1]["status"] == "PASSED" and items[1]["tries"] == 2 and items[1]["independent_success"] is False
    assert (items[2]["added_reason"], items[2]["stage"]) == ("CONFIRMATION_AFTER_HELP", "RECOGNITION") and len(items) == 7


def test_an_unmet_policy_adds_extra_items_and_then_the_plan_is_exhausted(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    out = {}
    for _ in range(40):
        out = respond(world, student, plan_id, correct=False)
        if out["transition"] not in ("NEXT_ITEM", "EXTRA_ITEM", "RETRY"):
            break
    assert out["transition"] == "PLAN_EXHAUSTED" and out["recovery_plan"]["status"] == "EXHAUSTED" and out["recovery_plan"]["can_return"] is True
    items = stored_items(student, plan_id)
    assert sum(1 for i in items if i["added_reason"] != "PLANNED") <= logic.MAX_ADDED_ITEMS
    assert out["recovery_plan"]["outcome"]["mastery"]["met"] is False
    left = world.leave_recovery(student, plan_id, version_of(world, student, aid))
    assert left["plan_status"] == "EXHAUSTED" and solve_of(student, aid).current_mode == "SOLVING"


def test_responses_are_idempotent_and_replay_without_grading(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    first = respond(world, student, plan_id, key="r-1")
    view = world.get_recovery_plan(student, plan_id)
    ctx = world.load_item_response_context(student, plan_id, view["items"][0]["recovery_plan_item_id"], {"acknowledged": True},
                                           first["state_version"] - 1, "r-1")
    assert ctx["replay"]["replayed"] is True and ctx["replay"]["state_version"] == first["state_version"]
    grade = logic.grade_item({"item": {"item_kind": "THEORY"}}, {})
    again = world.apply_item_response(student, plan_id, view["items"][0]["recovery_plan_item_id"], {"acknowledged": True}, grade,
                                      first["state_version"] - 1, "r-1")
    assert again["replayed"] is True and again["recovery_plan"] == first["recovery_plan"]
    assert stored_items(student, plan_id)[0]["tries"] == 1 and solve_of(student, aid).state_version == first["state_version"]
    assert types(student, aid).count("RECOVERY_ITEM_SUBMITTED") == 1
    with pytest.raises(IdempotencyKeyReused):
        world.load_item_response_context(student, plan_id, view["items"][0]["recovery_plan_item_id"], {"acknowledged": False},
                                         first["state_version"] - 1, "r-1")


def test_response_guards_and_owner_scoping(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    view = world.get_recovery_plan(student, plan_id)
    first, second = view["items"][0]["recovery_plan_item_id"], view["items"][1]["recovery_plan_item_id"]
    with pytest.raises(NotFound):
        world.load_item_response_context(str(uuid.uuid4()), plan_id, first, {}, 3, None)
    with pytest.raises(NotFound):
        world.load_item_response_context(student, plan_id, str(uuid.uuid4()), {}, 3, None)
    with pytest.raises(InvalidTransition):
        world.load_item_response_context(student, plan_id, second, {"choice_index": 1}, 3, None)             # not the current item
    grade = logic.grade_item({"item": {"item_kind": "THEORY"}}, {})
    with pytest.raises(NotFound):
        world.apply_item_response(str(uuid.uuid4()), plan_id, first, {"acknowledged": True}, grade, 3)
    with pytest.raises(StateVersionConflict):
        world.apply_item_response(student, plan_id, first, {"acknowledged": True}, grade, 99)
    with pytest.raises(InvalidTransition):
        world.apply_item_response(student, plan_id, second, {"choice_index": 1}, grade, 3)
    assert stored_items(student, plan_id)[0]["status"] == "PRESENTED" and solve_of(student, aid).state_version == 3
    for _ in range(5):
        respond(world, student, plan_id)
    return_item = current_item(world.get_recovery_plan(student, plan_id))
    with pytest.raises(InvalidTransition):
        world.load_item_response_context(student, plan_id, return_item["recovery_plan_item_id"], {}, 9, None)  # RETURN uses /resume


def test_a_version_race_is_a_409_and_changes_nothing(student, world, monkeypatch):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    view = world.get_recovery_plan(student, plan_id)
    first = view["items"][0]["recovery_plan_item_id"]
    grade = logic.grade_item({"item": {"item_kind": "THEORY"}}, {})
    real = recovery.load_solve                                                              # a read that is already stale when the write commits
    monkeypatch.setattr(recovery, "load_solve", lambda sid, a: real(sid, a).model_copy(update={"version": 2}))
    with pytest.raises(StateVersionConflict):
        world.apply_item_response(student, plan_id, first, {"acknowledged": True}, grade, 2)
    assert plan_model(student, plan_id).version == 1 and stored_items(student, plan_id)[0]["tries"] == 0
    assert solve_of(student, aid).state_version == 3 and types(student, aid)[-1] == "RECOVERY_ITEM_PRESENTED"


def test_a_stale_plan_fails_its_cas_and_the_transaction_is_retried(student, world, monkeypatch):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    real, calls = recovery._load_plan, []

    def stale_once(sid, pid):
        m = real(sid, pid)
        calls.append(1)
        return m.model_copy(update={"version": 9}) if len(calls) == 1 else m

    monkeypatch.setattr(recovery, "_load_plan", stale_once)
    out = respond(world, student, plan_id)
    assert out["transition"] == "NEXT_ITEM" and plan_model(student, plan_id).version == 2


def test_resume_needs_a_finished_plan_and_abort_ends_the_detour(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    version = version_of(world, student, aid)
    with pytest.raises(InvalidTransition):
        world.leave_recovery(student, plan_id, version)                                       # still running: /abort is the way out
    with pytest.raises(StateVersionConflict):
        world.leave_recovery(student, plan_id, version + 5, abort=True)
    with pytest.raises(NotFound):
        world.leave_recovery(str(uuid.uuid4()), plan_id, version, abort=True)
    respond(world, student, plan_id)
    version = version_of(world, student, aid)
    out = world.leave_recovery(student, plan_id, version, abort=True, idempotency_key="a-1")
    assert out == {"returned_to_step_id": "st1", "recovery_plan_id": plan_id, "plan_status": "ABORTED", "state_version": version + 1,
                   "replayed": False}
    stored = plan_model(student, plan_id)
    assert (stored.status, stored.GSI1PK, stored.ended_at is not None) == ("ABORTED", "PLANSTATUS#ABORTED", True)
    assert [i["status"] for i in stored_items(student, plan_id)] == ["PASSED"] + ["SKIPPED"] * 4 + ["PASSED"]      # RETURN passes, others skipped
    assert step_of(student, aid, "st1").state == "PRESENTED" and step_of(student, aid, "st1").returned_to_step_count == 1
    assert solve_of(student, aid).current_mode == "SOLVING" and types(student, aid)[-3:] == [
        "RECOVERY_PLAN_ABORTED", "RETURNED_TO_ORIGINAL_STEP", "STEP_PRESENTED"]
    replay = world.leave_recovery(student, plan_id, version, abort=True, idempotency_key="a-1")
    assert replay["replayed"] is True and replay["state_version"] == out["state_version"]
    assert step_of(student, aid, "st1").returned_to_step_count == 1                           # the replay changed nothing
    with pytest.raises(InvalidTransition):
        world.leave_recovery(student, plan_id, solve_of(student, aid).state_version)          # no longer in a detour
    # a new detour can start again
    assert make_plan(world, student, aid)["resumed"] is False


def test_an_admin_abort_uses_the_loaded_version_and_the_owner_pointer(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    out = world.leave_recovery(None, plan_id, None, abort=True, actor="ADMIN")
    assert out["plan_status"] == "ABORTED" and solve_of(student, aid).current_mode == "SOLVING"
    aborted = [e for e in feed(student, aid) if e.event_type in ("RECOVERY_PLAN_ABORTED", "RETURNED_TO_ORIGINAL_STEP")]
    assert {e.actor_type for e in aborted} == {"ADMIN"}


# ---------------------------------------------------------------------------------------------------------- branches

def test_a_failed_recognition_branches_to_the_prerequisite_and_wakes_the_parent(student, world):
    aid = attempt_of(world, student)
    succeed(world, student, aid, "st1")
    did = fail(world, student, aid, "st2", times=2)["diagnosis"]
    assert {h["failure_location"] for h in world.get_latest_diagnosis_for_step(student, aid, "st2")["hypotheses"]} == {"SKILL", "PREREQUISITE"}
    created = make_plan(world, student, aid, trigger="DIAGNOSIS", gap_diagnosis_id=did["gap_diagnosis_id"])
    parent_id = created["recovery_plan"]["recovery_plan_id"]
    assert created["recovery_plan"]["target_label"] == "skill2" and created["recovery_plan"]["items"][0]["stage"] == "RECOGNITION"
    respond(world, student, parent_id, correct=False)
    branched = respond(world, student, parent_id, correct=False)
    assert (branched["decision"], branched["transition"]) == ("BRANCH", "BRANCHED")
    child_id = branched["active_recovery_plan_id"]
    child = branched["recovery_plan"]
    assert child["recovery_plan_id"] == child_id and (child["trigger"], child["parent_recovery_plan_id"], child["parent_target_label"]) == (
        "BRANCH", parent_id, "skill2") and child["target_label"] == "skill1"
    assert all(i["item_kind"] != "RETURN" for i in child["items"])                      # a branch has no RETURN: it ends back in its parent
    parent = plan_model(student, parent_id)
    assert (parent.status, parent.GSI1PK) == ("SUSPENDED", "PLANSTATUS#SUSPENDED")
    solve = solve_of(student, aid)
    assert str(solve.current_recovery_plan_id) == child_id and [str(p) for p in solve.plan_ids] == [parent_id, child_id]
    assert "RECOVERY_PLAN_BRANCHED" in types(student, aid)
    assert [p["recovery_plan_id"] for p in world.list_attempt_plans(student, aid)] == [child_id, parent_id]    # newest first
    out = finish_plan(world, student, child_id)
    assert (out["transition"], out["active_recovery_plan_id"]) == ("BRANCH_FINISHED", parent_id)
    assert plan_model(student, child_id).status == "COMPLETED" and plan_model(student, parent_id).status == "ACTIVE"
    assert str(solve_of(student, aid).current_recovery_plan_id) == parent_id
    woken = out["recovery_plan"]
    assert woken["recovery_plan_id"] == parent_id and current_item(woken)["ordinal"] == 2 and current_item(woken)["status"] == "PRESENTED"
    resolved = {g.target_skill_id: g.status for g in gaps(student)}
    assert resolved["SK1"] == "RESOLVED" and resolved["SK2"] == "UNRESOLVED"                 # the prerequisite hypothesis was resolved by the child
    # abort from the child's family: every open plan ends, the finished child stays COMPLETED
    version = version_of(world, student, aid)
    left = world.leave_recovery(student, child_id, version, abort=True)
    assert left["recovery_plan_id"] == parent_id and left["plan_status"] == "ABORTED"
    assert plan_model(student, parent_id).status == "ABORTED" and plan_model(student, child_id).status == "COMPLETED"
    assert step_of(student, aid, "st2").state in ("PRESENTED", "RETRY_PRESENTED") and solve_of(student, aid).current_mode == "SOLVING"


# ---------------------------------------------------------------------------------------------------------- A24 / A25 / summary

def test_listings_admin_views_and_the_runtime_pointer(student, world):
    other = str(uuid.uuid4())
    from test_wp5_diagnosis import profile

    typed.put(profile(student, "ann@x.org"))
    aid, aid2 = attempt_of(world, student), attempt_of(world, other)
    done = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    finish_plan(world, student, done)
    live = make_plan(world, other, aid2)["recovery_plan"]["recovery_plan_id"]
    respond(world, other, live, correct=False)                                              # the worked example passes regardless
    assert world.get_recovery_summary(aid2) == {"recovery_plan_id": live, "target_label": "skill1", "status": "ACTIVE"}
    assert world.get_recovery_summary(aid)["status"] == "COMPLETED"
    world.leave_recovery(student, done, version_of(world, student, aid))
    assert world.get_recovery_summary(aid) is None
    assert [p["recovery_plan_id"] for p in world.list_attempt_plans(student, aid)] == [done]
    with pytest.raises(NotFound):
        world.list_attempt_plans(other, aid)                                                # another learner's attempt: 404
    assert world.list_attempt_plans(None, aid)[0]["recovery_plan_id"] == done
    rows = world.list_admin_plans()
    assert {r["recovery_plan_id"] for r in rows} == {done, live} and rows[0]["recovery_plan_id"] == live            # newest first
    assert set(rows[0]) == {"recovery_plan_id", "student_id", "email", "solve_attempt_id", "problem_code", "origin_step_id", "trigger",
                            "target_skill_id", "target_label", "status", "parent_recovery_plan_id", "outcome", "created_at", "ended_at",
                            "items", "passed", "failed", "adapted"}
    finished = next(r for r in rows if r["recovery_plan_id"] == done)
    assert (finished["email"], finished["problem_code"], finished["status"], finished["items"], finished["passed"], finished["failed"]) == (
        "ann@x.org", CODE, "COMPLETED", 6, 4, 0) and finished["outcome"]["mastery"]["met"] is True
    assert [r["recovery_plan_id"] for r in world.list_admin_plans(status="ACTIVE")] == [live]
    assert [r["recovery_plan_id"] for r in world.list_admin_plans(student_id=student)] == [done]
    assert world.list_admin_plans(student_id=student, status="ABORTED") == [] and len(world.list_admin_plans(limit=1)) == 1
    detail = world.get_admin_plan_detail(live)
    assert detail["student_id"] == other and detail["knowledge_gap_id"] is None and detail["gap_diagnosis_id"] is None
    assert detail["items_teacher"][0]["status"] == "PASSED" and set(detail["items_teacher"][0]) == set(logic.TEACHER_ITEM_KEYS)
    answered = world.get_admin_plan_detail(done)["items_teacher"][1]
    assert answered["last_result"]["teacher"]["grader"] == "deterministic" and answered["last_response"] == {"choice_index": 1}
    with pytest.raises(NotFound):
        world.get_admin_plan_detail(str(uuid.uuid4()))


# ---------------------------------------------------------------------------------------------------------- T15 seam

def test_abandoning_an_attempt_aborts_its_open_plans_in_the_same_transaction(student, world):
    aid = attempt_of(world, student)
    fail(world, student, aid, times=2)
    [gap] = gaps(student)
    did = str(diags(student, aid)[0].gap_diagnosis_id)
    plan_id = make_plan(world, student, aid, trigger="DIAGNOSIS", gap_diagnosis_id=did)["recovery_plan"]["recovery_plan_id"]
    respond(world, student, plan_id)
    assert world.abandon_stale_attempts(idle_days=-1) == [aid]
    solve = solve_of(student, aid)
    assert (solve.status, solve.current_mode) == ("ABANDONED", "ABANDONED")
    stored = plan_model(student, plan_id)
    assert (stored.status, stored.GSI1PK, stored.ended_at is not None) == ("ABORTED", "PLANSTATUS#ABORTED", True)
    assert [i["status"] for i in stored_items(student, plan_id)] == ["PASSED"] + ["SKIPPED"] * 5
    assert typed.require(LearnerGap, pk(student), gap.SK).latest_plan_status == "ABORTED" and typed.require(LearnerGap, pk(student), gap.SK).status == "UNRESOLVED"
    assert types(student, aid)[-2:] == ["RECOVERY_PLAN_ABORTED", "ATTEMPT_ABANDONED"]
    assert world.list_admin_plans(status="ABORTED")[0]["recovery_plan_id"] == plan_id


def test_the_abort_seam_adds_only_what_fits_and_reports_how_many(student, world):
    aid = attempt_of(world, student)
    plan_id = make_plan(world, student, aid)["recovery_plan"]["recovery_plan_id"]
    uow = uow_module.LearnerUnitOfWork(student)
    added = world.build_abort_plan_ops(uow, student, aid, [plan_id, str(uuid.uuid4())], "SYSTEM", "ATTEMPT_ABANDONED")
    assert added == len(uow) == 2                                                           # the PLAN update and one event (no gap)
    assert plan_model(student, plan_id).status == "ACTIVE"                                  # nothing is written until the caller commits
    uow.commit()
    assert plan_model(student, plan_id).status == "ABORTED"
    full = uow_module.LearnerUnitOfWork(student)
    assert world.build_abort_plan_ops(full, student, aid, [plan_id], "SYSTEM", "x") == 0       # an ended plan is left alone
    other = str(uuid.uuid4())
    aid2 = attempt_of(world, other)
    live = make_plan(world, other, aid2)["recovery_plan"]["recovery_plan_id"]
    tight = uow_module.LearnerUnitOfWork(other)
    uow_module.MAX_ITEMS, saved = len(tight) + 3, uow_module.MAX_ITEMS                      # no room: the plan stays open
    try:
        assert world.build_abort_plan_ops(tight, other, aid2, [live], "SYSTEM", "x") == 0
    finally:
        uow_module.MAX_ITEMS = saved


# ---------------------------------------------------------------------------------------------------------- misc

def test_long_learner_answers_are_shortened_only_when_the_plan_would_outgrow_an_item():
    big = {"last_response": {"response_text": "x" * 20_000}}
    items = [{**big, "ordinal": i} for i in range(1, 20)]
    fitted = recovery._fit_items(items)
    assert len(json.dumps(fitted)) < recovery.MAX_ITEMS_BYTES + 5_000 and len(fitted[0]["last_response"]["response_text"]) == 2000
    small = [{"last_response": {"response_text": "short"}, "ordinal": 1}]
    assert recovery._fit_items(small) is small


def test_responses_carry_iso_timestamps_so_a_replay_equals_the_original(student, world):
    aid = attempt_of(world, student)
    out = world.create_plan(student, aid, version_of(world, student, aid), idempotency_key="iso")
    assert isinstance(out["recovery_plan"]["created_at"], str) and out["recovery_plan"]["created_at"].endswith("Z")
    assert world.create_plan(student, aid, 2, idempotency_key="iso")["recovery_plan"] == out["recovery_plan"]
    assert dt.datetime.fromisoformat(out["recovery_plan"]["created_at"]).tzinfo is not None
    assert SK_UUID and EVALUATION and stores
