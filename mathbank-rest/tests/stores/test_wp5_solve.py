"""WP5 solve area (requirement 71, requirement 70 C1 T8-T12, T14, T15, A10-A18): the DynamoDB ``SolveRuntimeStore`` on moto.

Content comes from the real DynamoDB content store (moto ``mb-content``), seeded with one problem and a three-step solution
(st1 -> st2 DEPENDS_ON, st3 after them). Learner items are inspected through the typed models. No test touches Postgres or AWS:
``db.postgres.engine`` is replaced by a guard that raises.
"""
from __future__ import annotations

import datetime as dt
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "parity"))

from mathbank_rest import stores
from mathbank_rest.models import base
from mathbank_rest.models.ddb.content import ContentProblem, ContentSoldag, ContentStep
from mathbank_rest.models.manual.learner_solve import (
    LearnerEvent,
    LearnerProblem,
    LearnerSolve,
    LearnerSolveOwner,
    LearnerStepstate,
    solve_sk,
    step_sk,
)
from mathbank_rest.step_logic import (
    IdempotencyKeyReused,
    InvalidTransition,
    NotFound,
    StateVersionConflict,
    student_event_payload,
)
from mathbank_rest.stores import ddb as toolkit
from mathbank_rest.stores import typed
from mathbank_rest.stores.content import DynamoDBContentStore
from mathbank_rest.stores.errors import ItemSchemaError, StoreError, ValidationFailed
from mathbank_rest.stores.learner import hooks
from mathbank_rest.stores.learner.solve import SolveDynamoDB
from mathbank_rest.stores.learner.uow import LearnerUnitOfWork

NOW = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
CODE = "PRASOLOV_PGV1_1.1"
PROBLEM_ID = "11111111-1111-4111-8111-111111111111"
SOLUTION_ID = "22222222-2222-4222-8222-222222222222"
STATEMENT = "Prove that the three altitudes of a triangle are concurrent."
STEPS = ("st1", "st2", "st3")


# ---------------------------------------------------------------------------------------------------------- content

def step_doc(i: int, part: str) -> dict:
    return {"concept_node_id": "C1", "global_step_index": i, "hint_level": 1, "is_checkpoint": i == 1, "occurrence": 1,
            "skill_name": f"skill{i}", "skill_node_id": f"SK{i}", "solution_part_id": part, "solution_step_id": f"st{i}",
            "source_metadata": {"solution_part": "MAIN", "source_row": i}, "source_step_id": f"src{i}", "step_index_in_part": i,
            "step_text": f"step text {i}", "step_type": "SETUP", "subconcept_node_id": "SC1", "tutor_role": "CORE_BRIDGE"}


def seed_content(*, steps: bool = True) -> None:
    typed.put(ContentProblem(
        PK=f"PROBLEM#{CODE}", SK="META", GSI1PK=f"PID#{PROBLEM_ID}", GSI1SK="META", canonical_code=CODE,
        competition={"competition_id": str(uuid.uuid4()), "external_code": "PRASOLOV", "level": "X", "name": "Prasolov"},
        content_sha256="c", created_at=NOW, images=[], paper_code="P", paper_id=str(uuid.uuid4()), problem_id=PROBLEM_ID,
        problem_number=1, src_rev=1, updated_at=NOW, visibility="ACTIVE", statement_text=STATEMENT))
    if not steps:
        return
    dep = {"approval_method": "automatic", "confidence": 0.9, "logical_dependency": "INFERENCE_FROM_PREVIOUS", "metadata": {},
           "relationship_type": "DEPENDS_ON", "review_status": "REVIEWED", "source_type": "IMPORTED_PACKAGE"}
    typed.put(ContentSoldag(
        PK=f"PROBLEM#{CODE}", SK=f"SOLDAG#{SOLUTION_ID}", content_sha256="s", problem_code=CODE, problem_id=PROBLEM_ID,
        solution_id=SOLUTION_ID, src_rev=1, step_count=3, steps=[step_doc(2, "p1"), step_doc(1, "p1"), step_doc(3, "p2")],
        parts=[{"book_code": "B", "occurrence": 1, "part_label": "B2", "part_ordinal": 2, "part_text_normalized": "",
                "solution_part_id": "p2", "source_part_id": "sp2", "source_step_count": 1, "step_count": 1},
               {"book_code": "B", "occurrence": 1, "part_label": "MAIN", "part_ordinal": 1, "part_text_normalized": "",
                "solution_part_id": "p1", "source_part_id": "sp1", "source_step_count": 2, "step_count": 2}],
        dependencies=[{**dep, "from_step_id": "st1", "to_step_id": "st2"}], step_techniques=[]))
    for i in (1, 2, 3):
        typed.put(ContentStep(
            PK=f"STEP#st{i}", SK="META", book_code="B", concept_node_id="C1", content_sha256="c", eligible=True, global_step_index=i,
            hint_level=1, is_checkpoint=i == 1, problem_code=CODE, problem_id=PROBLEM_ID, skill_name=f"skill{i}",
            skill_node_id=f"SK{i}", solution_id=SOLUTION_ID, solution_part_id="p1" if i < 3 else "p2", solution_step_id=f"st{i}",
            src_rev=1, step_index_in_part=i, step_text=f"step text {i}", step_type="SETUP", subconcept_node_id="SC1",
            technique_node_ids=[], tutor_role="CORE_BRIDGE", updated_at=NOW,
            vector_state={"index": "i", "keys": [str(uuid.uuid4())], "model": "m", "sha256": "s"}))


class NoPostgres:
    def __getattr__(self, name):
        raise AssertionError(f"the DynamoDB solve path must not touch PostgreSQL (engine.{name})")


@pytest.fixture()
def world(content_table, monkeypatch):
    """Moto content + learner tables, the DynamoDB content store behind ``stores.get_store('content')``, PostgreSQL forbidden."""
    from mathbank_rest.db import postgres

    seed_content()
    monkeypatch.setattr(postgres, "engine", NoPostgres())
    with stores.override_store("content", DynamoDBContentStore()):
        yield SolveDynamoDB()


@pytest.fixture()
def student(sid, world):
    return sid


def pk(sid: str) -> str:
    return toolkit.student_pk(sid)


def solve_of(sid: str, aid: str) -> LearnerSolve:
    return typed.require(LearnerSolve, pk(sid), solve_sk(aid))


def step_of(sid: str, aid: str, step_id: str) -> LearnerStepstate:
    return typed.require(LearnerStepstate, pk(sid), step_sk(aid, step_id))


def feed(sid: str, aid: str | None = None) -> list[LearnerEvent]:
    """All events of a learner (or of one attempt, through GSI1), oldest first."""
    if aid is None:
        return typed.query(LearnerEvent, pk(sid), sk_begins="EVT#", limit=200).items
    return typed.query(LearnerEvent, f"SOLVE#{aid}", index="GSI1", sk_begins="EVT#", limit=200).items


def types(sid: str, aid: str | None = None) -> list[str]:
    return [e.event_type for e in feed(sid, aid)]


def start(store, sid, key=None) -> dict:
    return store.start_attempt(sid, CODE, key)


def advance(store, sid, aid, result, *, steps=STEPS, evaluation=None, actor="TUTOR", key=None):
    """Record ``result`` on the attempt's current step (read from the runtime) with the current state_version."""
    rt = store.get_attempt_runtime(aid, sid)
    return store.record_step_outcome(aid, rt["attempt"]["current_solution_step_id"], result, rt["attempt"]["state_version"],
                                     actor=actor, evaluation=evaluation, idempotency_key=key)


# ---------------------------------------------------------------------------------------------------------- T8 start

def test_start_attempt_writes_the_whole_aggregate_in_one_transaction(student, world):
    out = start(world, student, "k-start")
    aid = out["solve_attempt_id"]
    assert out["resumed"] is False and out["replayed"] is False
    solve = solve_of(student, aid)
    assert (solve.status, solve.current_mode, solve.attempt_number, solve.state_version) == ("IN_PROGRESS", "SOLVING", 1, 2)
    assert solve.current_solution_step_id == "st1" and solve.current_solution_part_id == "p1" and solve.hint_requested_count == 0
    assert solve.GSI1PK.startswith("OPEN_SOLVE#") and solve.GSI2PK == f"STUDENT#{student}#SOLVES"
    assert typed.require(LearnerSolveOwner, f"SOLVE#{aid}", "OWNER").student_id == uuid.UUID(student)
    first = step_of(student, aid, "st1")
    assert (first.state, first.help_level_used, first.attempt_count, first.skill_node_id) == ("PRESENTED", 0, 0, "SK1")
    assert first.GSI2PK == f"STUDENT#{student}#SKILL#SK1"
    cursor = typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}")
    assert (cursor.attempt_seq, str(cursor.open_solve_attempt_id), cursor.outcome_count) == (1, aid, 0)
    assert types(student, aid) == ["ATTEMPT_STARTED", "PROBLEM_VIEWED", "STEP_PRESENTED"]
    assert [e.actor_type for e in feed(student, aid)] == ["STUDENT", "STUDENT", "SYSTEM"]
    runtime = out["runtime"]
    assert runtime["attempt"]["state_version"] == 2 and runtime["attempt"]["problem_code"] == CODE
    assert runtime["attempt"]["statement_text"] == STATEMENT
    assert runtime["current_step"]["solution_step_id"] == "st1" and runtime["current_step"]["state"] == "PRESENTED"
    assert runtime["progress"] == {"total_steps": 3, "completed_steps": 0, "remaining_steps": 3}
    assert runtime["recovery"] is None and runtime["current_step"]["diagnosis"] is None
    assert all("step_text" not in t and "reference_text" not in t for t in runtime["timeline"])   # no canonical text before it is done


def test_start_resumes_the_open_attempt_with_a_viewed_event_only(student, world):
    first = start(world, student)["solve_attempt_id"]
    again = start(world, student)
    assert again["solve_attempt_id"] == first and again["resumed"] is True
    assert types(student, first) == ["ATTEMPT_STARTED", "PROBLEM_VIEWED", "STEP_PRESENTED", "PROBLEM_VIEWED"]
    assert feed(student, first)[-1].payload == {"resumed": True}
    assert typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}").attempt_seq == 1       # no second attempt


def test_start_is_idempotent_and_a_reused_key_is_refused(student, world):
    first = start(world, student, "same")
    replay = start(world, student, "same")
    assert replay["replayed"] is True and replay["solve_attempt_id"] == first["solve_attempt_id"] and replay["resumed"] is False
    assert types(student) == ["ATTEMPT_STARTED", "PROBLEM_VIEWED", "STEP_PRESENTED"]                     # nothing written twice
    with pytest.raises(IdempotencyKeyReused):
        world.submit_attempt(student, first["solve_attempt_id"], 2, "same")                              # same key, another operation


def test_start_numbers_attempts_and_refuses_unknown_or_stepless_problems(student, world):
    first = start(world, student)["solve_attempt_id"]
    world.submit_attempt(student, first, 2)
    second = start(world, student)
    assert second["resumed"] is False and second["solve_attempt_id"] != first
    assert second["runtime"]["attempt"]["attempt_number"] == 2
    assert typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}").attempt_seq == 2
    with pytest.raises(NotFound):
        world.start_attempt(student, "NO_SUCH_CODE")
    with pytest.raises(NotFound):
        world.start_attempt(student, str(uuid.uuid4()))
    assert world.start_attempt(student, PROBLEM_ID)["resumed"] is True                                   # a uuid reference works too


def test_concurrent_start_loses_the_cursor_race_and_resumes(student, world, monkeypatch):
    winner = start(world, student)["solve_attempt_id"]
    real_get, calls = typed.get, []

    def stale(model, key_pk, key_sk, **kw):          # the second request read the cursor before the winner committed
        if model is LearnerProblem and not calls:
            calls.append(1)
            return None
        return real_get(model, key_pk, key_sk, **kw)

    monkeypatch.setattr(typed, "get", stale)
    loser = start(world, student)
    assert loser["resumed"] is True and loser["solve_attempt_id"] == winner and calls == [1]
    assert typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}").attempt_seq == 1


# ---------------------------------------------------------------------------------------------------------- T9 response

def test_response_updates_step_solve_and_event_and_checks_version_and_step(student, world):
    aid = start(world, student)["solve_attempt_id"]
    out = world.submit_step_response(student, aid, "st1", "midpoints", 2, "k1")
    assert out["state"] == "ATTEMPTED" and out["evaluation_status"] == "PENDING" and out["state_version"] == 3
    assert out["replayed"] is False and out["event_id"] == str(feed(student, aid)[-1].event_id)
    step = step_of(student, aid, "st1")
    assert (step.state, step.attempt_count, step.last_response_text) == ("ATTEMPTED", 1, "midpoints") and step.first_attempted_at
    assert solve_of(student, aid).state_version == 3
    assert feed(student, aid)[-1].payload == {"response": "midpoints"} and feed(student, aid)[-1].idempotency_key == "k1"
    with pytest.raises(StateVersionConflict):
        world.submit_step_response(student, aid, "st1", "again", 2)                                       # stale
    with pytest.raises(InvalidTransition):
        world.submit_step_response(student, aid, "st2", "x", 3)                                           # not the current step
    assert step_of(student, aid, "st1").attempt_count == 1


def test_double_submit_with_one_key_writes_once_and_replays(student, world):
    aid = start(world, student)["solve_attempt_id"]
    first = world.submit_step_response(student, aid, "st1", "midpoints", 2, "dbl")
    second = world.submit_step_response(student, aid, "st1", "midpoints", 2, "dbl")      # the client retried after a timeout
    assert second == {**first, "replayed": True}
    assert step_of(student, aid, "st1").attempt_count == 1 and types(student, aid).count("STEP_RESPONSE_SUBMITTED") == 1
    with pytest.raises(IdempotencyKeyReused):
        world.submit_step_response(student, aid, "st1", "something else", 2, "dbl")


def test_concurrent_duplicate_replays_instead_of_conflicting(student, world, monkeypatch):
    aid = start(world, student)["solve_attempt_id"]
    first = world.submit_step_response(student, aid, "st1", "midpoints", 2, "race")
    real_get, hidden = toolkit.get_item, []

    def blind(ctx, p, s, **kw):                  # the duplicate's first IDEM read happened before the winner committed
        if s == "IDEM#race" and not hidden:
            hidden.append(1)
            return None
        return real_get(ctx, p, s, **kw)

    monkeypatch.setattr(toolkit, "get_item", blind)
    second = world.submit_step_response(student, aid, "st1", "midpoints", 2, "race")
    assert hidden == [1] and second == {**first, "replayed": True}
    assert step_of(student, aid, "st1").attempt_count == 1


def test_response_is_refused_in_recovery_and_when_not_in_progress(student, world):
    aid = start(world, student)["solve_attempt_id"]
    uow = LearnerUnitOfWork(student)
    uow.update(LearnerSolve, pk(student), solve_sk(aid), {"current_mode": "RECOVERY"}, expected={"version": 2})
    uow.commit()
    with pytest.raises(InvalidTransition, match="recovery"):
        world.submit_step_response(student, aid, "st1", "x", 3)
    with pytest.raises(InvalidTransition, match="recovery"):
        world.submit_attempt(student, aid, 3)


# ---------------------------------------------------------------------------------------------------------- T10 / T11 hints

def test_hint_ladder_caps_at_five_and_counts_on_the_solve_item(student, world):
    aid = start(world, student)["solve_attempt_id"]
    version, levels = 2, []
    for _ in range(6):
        out = world.request_hint(student, aid, "st1", version)
        levels.append((out["help_level"], out["help_kind"]))
        assert out["hint_text"] is None
        version = out["state_version"]
    assert [lv for lv, _ in levels] == [1, 2, 3, 4, 5, 5] and levels[4][1] == "FULL_REVEAL" and version == 8
    assert step_of(student, aid, "st1").help_level_used == 5
    assert solve_of(student, aid).hint_requested_count == 6                  # the counter replaces the event-count query
    assert types(student, aid).count("HINT_REQUESTED") == 6
    out = world.record_hint_presented(student, aid, "st1", 5, "REFERENCE_STEP")
    assert out is None and feed(student, aid)[-1].event_type == "HINT_PRESENTED" and feed(student, aid)[-1].actor_type == "TUTOR"
    assert feed(student, aid)[-1].payload == {"help_level": 5, "help_kind": "FULL_REVEAL", "hint_source": "REFERENCE_STEP"}
    assert solve_of(student, aid).state_version == 8                         # presenting a hint does not move the aggregate


def test_hint_replay_does_not_escalate_twice(student, world):
    aid = start(world, student)["solve_attempt_id"]
    first = world.request_hint(student, aid, "st1", 2, "h1")
    assert world.request_hint(student, aid, "st1", 2, "h1") == {**first, "replayed": True}
    assert step_of(student, aid, "st1").help_level_used == 1 and solve_of(student, aid).hint_requested_count == 1


def test_hint_context_reads_the_learner_step_state(student, world):
    aid = start(world, student)["solve_attempt_id"]
    world.submit_step_response(student, aid, "st1", "my idea", 2)
    world.request_hint(student, aid, "st1", 3)
    assert world.get_step_tutor_state(aid, "st1", student_id=student) == {"last_response_text": "my idea", "help": 1}
    assert world.get_step_tutor_state(aid, "st3", student_id=student) == {"last_response_text": None, "help": 0}
    assert world.get_step_tutor_state(aid, "st1") == {"last_response_text": "my idea", "help": 1}        # owner resolved by pointer


# ---------------------------------------------------------------------------------------------------------- T12 outcome

def test_success_without_help_is_independent_and_advances(student, world):
    aid = start(world, student)["solve_attempt_id"]
    out = advance(world, student, aid, "SUCCESS", evaluation={"verdict": "CORRECT", "confidence": 0.9, "evidence": "teacher only"})
    assert out["state"] == "SUCCESS_INDEPENDENT" and out["independent_success"] is True and out["current_step_id"] == "st2"
    assert out["attempt_completed"] is False and out["outcome_attempt"] is None and out["state_version"] == 3
    assert out["student_id"] == student and out["problem_id"] == PROBLEM_ID and out["replayed"] is False
    assert out["gap_status_changes"] == [] and out["diagnosis"] is None
    done, nxt = step_of(student, aid, "st1"), step_of(student, aid, "st2")
    assert (done.state, done.independent_success) == ("SUCCESS_INDEPENDENT", True)
    assert done.last_evaluation == {"result": "SUCCESS", "verdict": "CORRECT", "confidence": 0.9, "evidence": "teacher only"}
    assert nxt.state == "PRESENTED" and solve_of(student, aid).current_solution_step_id == "st2"
    assert types(student, aid)[3:] == ["STEP_EVALUATED", "STEP_COMPLETED_INDEPENDENTLY", "STEP_PRESENTED"]
    assert feed(student, aid)[3].payload == {"result": "SUCCESS", "evaluation": {"verdict": "CORRECT", "confidence": 0.9,
                                                                                   "evidence": "teacher only"}}


def test_success_after_a_hint_is_with_help_and_never_independent(student, world):
    aid = start(world, student)["solve_attempt_id"]
    world.request_hint(student, aid, "st1", 2)
    out = advance(world, student, aid, "SUCCESS")
    assert out["state"] == "SUCCESS_WITH_HELP" and out["independent_success"] is False
    step = step_of(student, aid, "st1")
    assert step.independent_success is False and step.help_level_used == 1
    assert "STEP_COMPLETED_WITH_HELP" in types(student, aid)


def test_failed_step_stays_current_and_is_re_presented_as_retry(student, world):
    aid = start(world, student)["solve_attempt_id"]
    out = advance(world, student, aid, "FAILED", evaluation={"verdict": "INCORRECT"})
    assert out["state"] == "FAILED" and out["independent_success"] is None and out["current_step_id"] == "st1"
    assert out["attempt_completed"] is False and out["state_version"] == 3
    step = step_of(student, aid, "st1")
    assert step.state == "RETRY_PRESENTED" and step.independent_success is None
    assert types(student, aid)[3:] == ["STEP_EVALUATED", "STEP_FAILED", "STEP_PRESENTED"]
    out = advance(world, student, aid, "SUCCESS")
    assert out["state"] == "SUCCESS_INDEPENDENT" and out["current_step_id"] == "st2"


def test_skipped_step_moves_on_and_prerequisites_are_respected(student, world):
    aid = start(world, student)["solve_attempt_id"]
    out = advance(world, student, aid, "SKIPPED")
    assert out["state"] == "SKIPPED" and out["current_step_id"] == "st2" and "STEP_SKIPPED" in types(student, aid)


def test_completing_the_last_step_closes_the_attempt_and_writes_the_outcome(student, world):
    aid = start(world, student)["solve_attempt_id"]
    world.request_hint(student, aid, "st1", 2)
    world.request_hint(student, aid, "st1", 3)
    advance(world, student, aid, "SUCCESS")
    advance(world, student, aid, "SUCCESS")
    out = advance(world, student, aid, "SUCCESS", key="final")
    assert out["attempt_completed"] is True and out["current_step_id"] is None
    assert out["outcome_attempt"]["is_correct"] is True and out["outcome_attempt"]["hint_count"] == 2
    solve = solve_of(student, aid)
    assert (solve.status, solve.current_mode) == ("COMPLETED", "COMPLETED") and solve.completed_at and solve.submitted_at
    assert str(solve.outcome_attempt_id) == out["outcome_attempt"]["attempt_id"] and solve.GSI1PK is None and solve.GSI1SK is None
    assert solve.current_solution_step_id is None and solve.state_version == out["state_version"]
    cursor = typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}")
    assert cursor.open_solve_attempt_id is None and cursor.outcome_count == 1
    assert types(student, aid)[-2:] == ["STEP_COMPLETED_INDEPENDENTLY", "ATTEMPT_COMPLETED"]
    outcomes = typed.query("learner", pk(student), sk_begins="OUTCOME#", limit=10).items
    assert len(outcomes) == 1 and outcomes[0].source == "step_runtime" and outcomes[0].is_correct is True
    assert (str(outcomes[0].attempt_id), outcomes[0].hint_count) == (out["outcome_attempt"]["attempt_id"], 2)
    assert str(outcomes[0].solve_attempt_id) == aid
    assert world.get_attempt_runtime(aid, student)["progress"] == {"total_steps": 3, "completed_steps": 3, "remaining_steps": 0}
    replay = advance_replay(world, student, aid, out["state_version"] - 1)
    assert replay == {**out, "replayed": True}
    again = start(world, student)                                                       # the marker is gone: a new attempt starts
    assert again["resumed"] is False and again["runtime"]["attempt"]["attempt_number"] == 2


def advance_replay(store, sid, aid, version):
    return store.record_step_outcome(aid, "st3", "SUCCESS", version, actor="TUTOR", evaluation=None, idempotency_key="final")


def test_a_skipped_or_failed_step_makes_the_attempt_incorrect(student, world):
    aid = start(world, student)["solve_attempt_id"]
    advance(world, student, aid, "SKIPPED")
    advance(world, student, aid, "SUCCESS")
    out = advance(world, student, aid, "SUCCESS")
    assert out["attempt_completed"] is True and out["outcome_attempt"]["is_correct"] is False


def test_outcome_guards_actor_version_step_and_idempotency(student, world):
    aid = start(world, student)["solve_attempt_id"]
    with pytest.raises(InvalidTransition, match="not the student"):
        world.record_step_outcome(aid, "st1", "SUCCESS", 2, actor="STUDENT")
    with pytest.raises(StateVersionConflict):
        world.record_step_outcome(aid, "st1", "SUCCESS", 99)
    with pytest.raises(InvalidTransition):
        world.record_step_outcome(aid, "st3", "SUCCESS", 2)
    with pytest.raises(NotFound):
        world.record_step_outcome(str(uuid.uuid4()), "st1", "SUCCESS", 2)
    first = world.record_step_outcome(aid, "st1", "SUCCESS", 2, evaluation={"a": 1}, idempotency_key="o1")
    assert world.record_step_outcome(aid, "st1", "SUCCESS", 2, evaluation={"a": 1}, idempotency_key="o1") == {**first, "replayed": True}
    with pytest.raises(IdempotencyKeyReused):
        world.record_step_outcome(aid, "st1", "FAILED", 2, evaluation={"a": 1}, idempotency_key="o1")
    assert types(student, aid).count("STEP_EVALUATED") == 1


def test_returning_from_a_detour_emits_the_event_once(student, world):
    aid = start(world, student)["solve_attempt_id"]
    uow = LearnerUnitOfWork(student)                    # what the recovery area records when the learner resumes the step
    uow.update(LearnerStepstate, pk(student), step_sk(aid, "st1"), {"returned_to_step_count": 1}, expected={"version": 1})
    uow.commit()
    out = advance(world, student, aid, "SUCCESS")
    assert out["current_step_id"] == "st2"
    assert types(student, aid)[3:] == ["STEP_EVALUATED", "STEP_COMPLETED_INDEPENDENTLY", "RETURNED_TO_ORIGINAL_PROBLEM", "STEP_PRESENTED"]
    returned = next(e for e in feed(student, aid) if e.event_type == "RETURNED_TO_ORIGINAL_PROBLEM")
    assert returned.payload == {"next_step_id": "st2"} and returned.actor_type == "SYSTEM"
    assert step_of(student, aid, "st1").returned_to_problem_count == 1
    advance(world, student, aid, "SUCCESS")
    assert types(student, aid).count("RETURNED_TO_ORIGINAL_PROBLEM") == 1


def test_diagnosis_hook_adds_items_to_the_same_transaction_and_reports_back(student, world):
    seen = {}

    def hook(uow, ctx):
        seen.update(ctx)
        assert uow.fits(10)
        uow.put_new(LearnerEvent(PK=pk(student), SK=f"EVT#2099-01-01T00:00:00.000000Z#{uuid.uuid4()}", student_id=student,
                                 event_id=uuid.uuid4(), event_time=NOW, event_type="GAP_DIAGNOSED", actor_type="SYSTEM",
                                 solve_attempt_id=ctx["attempt_id"], payload={}))
        ctx["out"]["diagnosis"] = {"gap_diagnosis_id": "d1", "created_at": NOW}
        ctx["out"]["gap_status_changes"] = [{"knowledge_gap_id": "g1", "from": "UNRESOLVED", "to": "CONFIRMED"}]
        return True

    aid = start(world, student)["solve_attempt_id"]
    hooks.register_auto_diagnose(hook)
    try:
        out = advance(world, student, aid, "FAILED")
    finally:
        hooks.register_auto_diagnose(None)
    assert out["diagnosis"]["gap_diagnosis_id"] == "d1" and out["gap_status_changes"][0]["to"] == "CONFIRMED"
    assert seen["outcome"] == "FAILED" and seen["student_id"] == student and seen["attempt_id"] == aid
    assert seen["step_state"].state == "RETRY_PRESENTED" and seen["solve"].state_version == 3 and seen["budget"] >= 10
    assert "GAP_DIAGNOSED" in types(student)


def test_a_failing_hook_never_loses_the_outcome(student, world):
    def boom(uow, ctx):
        raise RuntimeError("diagnosis exploded")

    aid = start(world, student)["solve_attempt_id"]
    hooks.register_auto_diagnose(boom)
    try:
        out = advance(world, student, aid, "FAILED")
    finally:
        hooks.register_auto_diagnose(None)
    assert out["state"] == "FAILED" and out["diagnosis"] is None and step_of(student, aid, "st1").state == "RETRY_PRESENTED"


# ---------------------------------------------------------------------------------------------------------- T14 submit

def test_early_submit_closes_the_attempt_and_writes_a_failed_outcome_by_default(student, world):
    aid = start(world, student)["solve_attempt_id"]
    world.request_hint(student, aid, "st1", 2)
    out = world.submit_attempt(student, aid, 3, "sub")
    assert out == {"status": "SUBMITTED", "state_version": 4, "replayed": False}
    solve = solve_of(student, aid)
    assert (solve.status, solve.current_mode) == ("SUBMITTED", "REVIEW") and solve.submitted_at and solve.GSI1PK is None
    assert typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}").open_solve_attempt_id is None
    assert types(student, aid)[-1] == "ATTEMPT_SUBMITTED"
    outcome = typed.query("learner", pk(student), sk_begins="OUTCOME#", limit=10).items[0]
    assert outcome.is_correct is False and outcome.hint_count == 1 and outcome.source == "step_runtime"
    assert str(solve.outcome_attempt_id) == str(outcome.attempt_id)
    assert world.submit_attempt(student, aid, 3, "sub") == {**out, "replayed": True}
    with pytest.raises(InvalidTransition, match="SUBMITTED"):
        world.submit_attempt(student, aid, 4)
    with pytest.raises(StateVersionConflict):
        world.submit_attempt(student, start(world, student)["solve_attempt_id"], 99)


@pytest.mark.parametrize(("policy", "outcomes", "correct"), [("off", 0, None), ("null", 1, None), ("false", 1, False)])
def test_submit_outcome_policy(student, world, monkeypatch, policy, outcomes, correct):
    monkeypatch.setenv("SUBMIT_OUTCOME_POLICY", policy)
    aid = start(world, student)["solve_attempt_id"]
    world.submit_attempt(student, aid, 2)
    found = typed.query("learner", pk(student), sk_begins="OUTCOME#", limit=10).items
    assert len(found) == outcomes and (not found or found[0].is_correct is correct)
    assert typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}").open_solve_attempt_id is None


# ---------------------------------------------------------------------------------------------------------- T15 stale

def age(sid: str, aid: str, days: float) -> None:
    """Rewind the attempt's activity (and its open-solve index key) as if the learner left ``days`` ago."""
    old = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)
    solve = solve_of(sid, aid)
    uow = LearnerUnitOfWork(sid)
    uow.update(LearnerSolve, pk(sid), solve_sk(aid), {"last_activity_at": old, "GSI1SK": f"{toolkit.encode(old)}#{aid}"},
               expected={"version": solve.version})
    uow.commit()


def test_abandon_stale_attempts_uses_the_open_index_and_a_cas(student, world):
    stale = start(world, student)["solve_attempt_id"]
    age(student, stale, 45)
    assert world.abandon_stale_attempts(30) == [stale]
    solve = solve_of(student, stale)
    assert (solve.status, solve.current_mode) == ("ABANDONED", "ABANDONED") and solve.GSI1PK is None
    assert typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}").open_solve_attempt_id is None
    last = feed(student, stale)[-1]
    assert last.event_type == "ATTEMPT_ABANDONED" and last.actor_type == "SYSTEM" and last.payload["idle_days"] == 30
    assert world.abandon_stale_attempts(30) == []
    assert start(world, student)["resumed"] is False
    with pytest.raises(InvalidTransition, match="ABANDONED"):
        world.submit_step_response(student, stale, "st1", "x", solve.state_version)


def test_recent_attempts_are_left_alone_and_a_moved_attempt_is_skipped(student, world, monkeypatch):
    recent = start(world, student)["solve_attempt_id"]
    assert world.abandon_stale_attempts(30) == [] and solve_of(student, recent).status == "IN_PROGRESS"
    age(student, recent, 40)
    real = SolveDynamoDB._abandon

    def moved(self, solve, idle_days):               # the learner came back between the index query and the CAS
        world.submit_step_response(student, recent, "st1", "back!", solve.state_version)
        return real(self, solve, idle_days)

    monkeypatch.setattr(SolveDynamoDB, "_abandon", moved)
    assert world.abandon_stale_attempts(30) == []
    assert solve_of(student, recent).status == "IN_PROGRESS"


def test_abandon_limit_and_other_students_attempts(world, content_table):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    aid_a, aid_b = start(world, a)["solve_attempt_id"], start(world, b)["solve_attempt_id"]
    age(a, aid_a, 60)
    age(b, aid_b, 61)
    assert len(world.abandon_stale_attempts(30, limit=1)) == 1
    assert len(world.abandon_stale_attempts(30)) == 1
    assert solve_of(a, aid_a).status == "ABANDONED" and solve_of(b, aid_b).status == "ABANDONED"


# ---------------------------------------------------------------------------------------------------------- reads, scoping

def test_a_foreign_learner_sees_and_changes_nothing(student, world):
    aid = start(world, student)["solve_attempt_id"]
    intruder = str(uuid.uuid4())
    with pytest.raises(NotFound):
        world.get_attempt_runtime(aid, intruder)
    with pytest.raises(NotFound):
        world.submit_step_response(intruder, aid, "st1", "x", 2)
    with pytest.raises(NotFound):
        world.request_hint(intruder, aid, "st1", 2)
    with pytest.raises(NotFound):
        world.submit_attempt(intruder, aid, 2)
    assert world.list_events(intruder, attempt_id=aid) == [] and world.list_solve_attempts(intruder)["items"] == []
    assert solve_of(student, aid).state_version == 2 and types(intruder) == []


def test_owner_pointer_serves_admin_reads_and_the_admin_outcome(student, world):
    aid = start(world, student)["solve_attempt_id"]
    assert world.get_attempt_owner(aid) == {"student_id": uuid.UUID(student), "problem_id": uuid.UUID(PROBLEM_ID)}
    assert world.get_attempt_owner(str(uuid.uuid4())) is None
    assert world.get_attempt_runtime(aid)["attempt"]["student_id"] == uuid.UUID(student)             # no JWT: owner resolved
    out = world.record_step_outcome(aid, "st1", "SUCCESS", 2, actor="ADMIN")
    assert out["student_id"] == student and out["state"] == "SUCCESS_INDEPENDENT"
    assert [e.actor_type for e in feed(student, aid)][3:5] == ["ADMIN", "ADMIN"]


def test_runtime_view_reveals_reference_text_only_for_finished_steps(student, world):
    aid = start(world, student)["solve_attempt_id"]
    world.submit_step_response(student, aid, "st1", "my response", 2)
    advance(world, student, aid, "SUCCESS", evaluation={"verdict": "CORRECT", "feedback": "nice", "evidence": "secret"})
    rt = world.get_attempt_runtime(aid, student)
    done, current, locked = rt["timeline"][0], rt["timeline"][1], rt["timeline"][2]
    assert done["reference_text"] == "step text 1" and done["your_response"] == "my response" and done["state"] == "SUCCESS_INDEPENDENT"
    assert "reference_text" not in current and current["is_current"] is True and current["state"] == "PRESENTED"
    assert locked["state"] == "LOCKED" and "step_type" not in locked and "your_response" not in locked
    assert rt["seen_steps"][0]["your_response"] == "my response" and len(rt["seen_steps"]) == 2
    assert rt["progress"] == {"total_steps": 3, "completed_steps": 1, "remaining_steps": 2}
    failed = advance(world, student, aid, "FAILED", evaluation={"verdict": "INCORRECT", "feedback": "no", "evidence": "secret",
                                                                  "failure_mode": "CARELESS"})
    assert failed["state"] == "FAILED"
    cur = world.get_attempt_runtime(aid, student)["current_step"]
    assert cur["last_evaluation"] == {"result": "FAILED", "verdict": "INCORRECT", "feedback": "no"}      # no evidence / failure_mode


def test_runtime_view_points_at_the_current_recovery_plan(student, world):
    aid = start(world, student)["solve_attempt_id"]
    plan_id = str(uuid.uuid4())
    typed.put(base.model_for("learner", "PLAN")(
        PK=pk(student), SK=f"PLAN#{plan_id}", student_id=student, solve_attempt_id=aid, recovery_plan_id=plan_id,
        origin_problem_id=PROBLEM_ID, origin_step_id="st1", planner_version="v1", target_label="Midpoints", target_skill_id="SK1",
        target_subconcept_id="SC1", trigger="STUDENT_REQUEST", status="ACTIVE", current_item_ordinal=1, items=[],
        created_at=NOW, updated_at=NOW, version=1))
    uow = LearnerUnitOfWork(student)
    uow.update(LearnerSolve, pk(student), solve_sk(aid), {"current_recovery_plan_id": plan_id}, expected={"version": 2})
    uow.commit()
    assert world.get_attempt_runtime(aid, student)["recovery"] == {"recovery_plan_id": plan_id, "target_label": "Midpoints",
                                                                    "status": "ACTIVE"}


def test_diagnosis_view_seam_is_used_when_the_diagnosis_area_provides_it(student, world):
    class WithDiagnosis(SolveDynamoDB):
        def get_step_diagnosis_view(self, sid, aid, step_id):
            return {"gap_diagnosis_id": "d1", "solution_step_id": step_id}

    aid = start(world, student)["solve_attempt_id"]
    assert WithDiagnosis().get_attempt_runtime(aid, student)["current_step"]["diagnosis"] == {
        "gap_diagnosis_id": "d1", "solution_step_id": "st1"}


def test_solve_attempts_list_is_newest_first_filtered_and_paged(student, world):
    first = start(world, student)["solve_attempt_id"]
    world.submit_attempt(student, first, 2)
    second = start(world, student)["solve_attempt_id"]
    page = world.list_solve_attempts(student, limit=10)
    assert [r["solve_attempt_id"] for r in page["items"]] == [uuid.UUID(second), uuid.UUID(first)] and page["next_token"] is None
    assert page["items"][0]["problem_code"] == CODE and page["items"][0]["attempt_number"] == 2
    assert [r["status"] for r in world.list_solve_attempts(student, "SUBMITTED")["items"]] == ["SUBMITTED"]
    one = world.list_solve_attempts(student, limit=1)
    assert len(one["items"]) == 1 and one["next_token"]
    rest = world.list_solve_attempts(student, limit=1, next_token=one["next_token"])
    assert [r["solve_attempt_id"] for r in rest["items"]] == [uuid.UUID(first)]


# ---------------------------------------------------------------------------------------------------------- events

def test_event_feed_pages_newest_first_with_signed_tokens(student, world):
    aid = start(world, student)["solve_attempt_id"]
    for i in range(4):
        world.submit_step_response(student, aid, "st1", f"r{i}", 2 + i)
    everything = world.list_events(student)
    assert [e["event_type"] for e in everything][:4] == ["STEP_RESPONSE_SUBMITTED"] * 4 and len(everything) == 7
    times = [e["event_time"] for e in everything]
    assert times == sorted(times, reverse=True)
    seen, token = [], None
    while True:
        page = world.list_events_page(student, limit=3, next_token=token)
        seen += page["items"]
        token = page["next_token"]
        if not token:
            break
        assert page["limit"] == 3 and len(page["items"]) == 3
    assert [e["event_id"] for e in seen] == [e["event_id"] for e in everything]
    assert set(everything[0]) == {"event_id", "solve_attempt_id", "event_type", "event_time", "actor_type", "solution_step_id", "payload"}
    with pytest.raises(StoreError):
        world.list_events_page(student, limit=3, next_token=token or "garbage")
    mine = world.list_events(student, attempt_id=aid, limit=2)
    assert len(mine) == 2 and mine[0]["solve_attempt_id"] == uuid.UUID(aid)


def test_events_after_a_cursor_come_oldest_first(student, world):
    aid = start(world, student)["solve_attempt_id"]
    world.submit_step_response(student, aid, "st1", "a", 2)
    world.submit_step_response(student, aid, "st1", "b", 3)
    oldest_first = list(reversed(world.list_events(student)))
    cursor = toolkit.encode(oldest_first[2]["event_time"])
    after = world.get_events_after(student, cursor)
    assert [e["event_id"] for e in after["items"]] == [e["event_id"] for e in oldest_first[3:]]
    scoped = world.get_events_after(student, cursor, attempt_id=aid, limit=1)
    assert [e["event_id"] for e in scoped["items"]] == [oldest_first[3]["event_id"]] and scoped["next_token"]
    nxt = world.get_events_after(student, cursor, attempt_id=aid, limit=10, next_token=scoped["next_token"])
    assert [e["event_id"] for e in nxt["items"]] == [e["event_id"] for e in oldest_first[4:]]
    assert world.get_events_after(student, toolkit.encode(dt.datetime.now(dt.UTC) + dt.timedelta(days=1)))["items"] == []
    with pytest.raises(ValidationFailed):
        world.get_events_after(student, "yesterday")


def test_the_learner_feed_never_carries_teacher_evidence(student, world):
    aid = start(world, student)["solve_attempt_id"]
    advance(world, student, aid, "FAILED", evaluation={"verdict": "INCORRECT", "feedback": "look again", "feedback_redacted": True,
                                                       "confidence": 0.2, "evidence": "TEACHER-ONLY", "failure_mode": "CARELESS",
                                                       "failure_location": "SKILL"})
    teacher = next(e for e in world.list_events(student) if e["event_type"] == "STEP_EVALUATED")["payload"]
    assert teacher["evaluation"]["evidence"] == "TEACHER-ONLY"                                             # the admin feed is complete
    learner = next(e for e in world.list_events(student, student_view=True) if e["event_type"] == "STEP_EVALUATED")["payload"]
    assert learner == {"result": "FAILED", "evaluation": {"verdict": "INCORRECT", "feedback": "look again", "feedback_redacted": True}}
    blob = repr([e["payload"] for e in world.list_events(student, student_view=True)])
    for forbidden in ("confidence", "failure_mode", "failure_location", "evidence", "TEACHER-ONLY"):
        assert forbidden not in blob
    assert student_event_payload("SOMETHING_NEW", {"secret": 1}) == {}                                         # unknown types: nothing


# ---------------------------------------------------------------------------------------------------------- transactions

@contextmanager
def captured_transactions(monkeypatch):
    seen: list[list[toolkit.TxOp]] = []
    real = toolkit.transact

    def spy(ops, **kw):
        seen.append(list(ops))
        return real(ops, **kw)

    monkeypatch.setattr(toolkit, "transact", spy)
    yield seen


def test_every_operation_is_one_transaction_within_one_hundred_items(student, world, monkeypatch):
    with captured_transactions(monkeypatch) as txs:
        aid = start(world, student, "t1")["solve_attempt_id"]
        world.submit_step_response(student, aid, "st1", "r", 2, "t2")
        world.request_hint(student, aid, "st1", 3, "t3")
        advance(world, student, aid, "SUCCESS", key="t4")
        world.submit_attempt(student, aid, 5, "t5")
    assert len(txs) == 5 and all(len(t) <= 100 for t in txs)
    first = txs[0]
    assert {op.label for op in first if op.kind == "put"} >= {"SOLVE", "SOLVE_OWNER", "STEPSTATE", "EVENT", "idempotency"}
    for t in txs:                                                          # the receipt is always the last item of its transaction
        assert t[-1].label == "idempotency"


def test_the_worst_case_outcome_with_many_tags_stays_within_the_limit(student, world, monkeypatch):
    class Tagged(SolveDynamoDB):
        """An OutcomeStore stand-in that stages OUTCOME + PROBLEM counters + 2 items per tag, like T7 for k tags."""

        def __init__(self, tags: int):
            self.tags = tags

        def stage_outcome(self, uow, *, problem_id, attempt_id, attempted_at, source, tags, **kw):
            ops = [toolkit.Check("learner", f"X#{i}", "SK", toolkit.NOT_EXISTS) for i in range(2 + 2 * self.tags)]
            for op in ops:
                uow.add(op)
            uow.add(toolkit.Update("learner", pk(student), f"PROBLEM#{problem_id}", "SET #oc = if_not_exists(#oc, :z) + :o",
                                   names={"#oc": "outcome_count"}, values={":z": 0, ":o": 1}, label="problem cursor"))

            return SimpleNamespace(updated_mastery={"concepts": {}, "techniques": {}}, deferred=[])

    store = Tagged(32)                                           # 31 + 2k with k = 32 would be 95; the stand-in uses 2 + 2k + 1
    aid = start(store, student)["solve_attempt_id"]
    advance(store, student, aid, "SUCCESS")
    advance(store, student, aid, "SUCCESS")
    with captured_transactions(monkeypatch) as txs:
        out = advance(store, student, aid, "SUCCESS", key="worst")
    assert out["attempt_completed"] is True and out["updated_mastery"] == {"concepts": {}, "techniques": {}}
    assert len(txs[0]) <= 100 and len(txs[0]) > 60
    keys = [(op.pk or op.item["PK"], op.sk or op.item["SK"]) for op in txs[0]]
    assert len(keys) == len(set(keys))                           # one operation per item
    cursor = typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}")
    assert cursor.open_solve_attempt_id is None and cursor.outcome_count == 1      # the marker left in the staged PROBLEM update


def test_two_operations_on_one_item_are_refused_before_dynamodb_sees_them(student, world):
    class Sloppy(SolveDynamoDB):
        def stage_outcome(self, uow, **kw):                     # a builder that writes the cursor twice
            problem_id = kw["problem_id"]
            for _ in range(2):
                uow.add(toolkit.Update("learner", pk(student), f"PROBLEM#{problem_id}", "SET #v = :v", names={"#v": "x"},
                                       values={":v": 1}, label="problem cursor"))

            return SimpleNamespace(updated_mastery={}, deferred=[])

    store = Sloppy()
    aid = start(store, student)["solve_attempt_id"]
    advance(store, student, aid, "SUCCESS")
    advance(store, student, aid, "SUCCESS")
    with pytest.raises(StoreError, match="two operations"):
        advance(store, student, aid, "SUCCESS")
    assert solve_of(student, aid).status == "IN_PROGRESS"        # nothing was committed


def test_deferred_mastery_runs_after_the_commit_and_never_loses_the_outcome(student, world):
    calls = []

    class Deferring(SolveDynamoDB):
        def stage_outcome(self, uow, *, problem_id, **kw):
            uow.add(toolkit.Update("learner", pk(student), f"PROBLEM#{problem_id}", "SET #oc = if_not_exists(#oc, :z) + :o",
                                   names={"#oc": "outcome_count"}, values={":z": 0, ":o": 1}, label="problem cursor"))

            return SimpleNamespace(updated_mastery={"concepts": {"c": 0.5}, "techniques": {}}, deferred=["tag"])

        def finish_deferred_mastery(self, sid, staged):
            calls.append((sid, solve_of(student, aid).status))        # the aggregate is already committed
            raise RuntimeError("repair consumer will converge it")

    store = Deferring()
    aid = start(store, student)["solve_attempt_id"]
    advance(store, student, aid, "SUCCESS")
    advance(store, student, aid, "SUCCESS")
    out = advance(store, student, aid, "SUCCESS")
    assert calls == [(student, "COMPLETED")] and out["attempt_completed"] and out["updated_mastery"]["concepts"] == {"c": 0.5}


def test_a_diagnosis_that_does_not_fit_is_dropped_not_the_outcome(student, world):
    def greedy(uow, ctx):
        return uow.fits(500) and False

    aid = start(world, student)["solve_attempt_id"]
    hooks.register_auto_diagnose(greedy)
    try:
        out = advance(world, student, aid, "FAILED")
    finally:
        hooks.register_auto_diagnose(None)
    assert out["state"] == "FAILED" and out["diagnosis"] is None


def test_append_only_items_are_only_ever_created(student, world, monkeypatch):
    with captured_transactions(monkeypatch) as txs:
        aid = start(world, student)["solve_attempt_id"]
        world.submit_step_response(student, aid, "st1", "r", 2)
        advance(world, student, aid, "FAILED")
        world.submit_attempt(student, aid, 4)
    for tx in txs:
        for op in tx:
            if op.kind == "put" and op.item.get("type") in ("EVENT", "OUTCOME"):
                assert op.cond is not None and op.cond.expr == "attribute_not_exists(PK)", op.item["SK"]
            if op.kind in ("update", "delete"):
                assert not (op.pk or "").startswith("STUDENT#") or not (op.sk or "").startswith(("EVT#", "OUTCOME#"))
    uow = LearnerUnitOfWork(student)
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.update(LearnerEvent, pk(student), feed(student, aid)[0].SK, {"payload": {}})
    with pytest.raises(ValidationFailed, match="append-only"):
        uow.delete(LearnerEvent, pk(student), feed(student, aid)[0].SK)


def test_a_dynamodb_solve_runs_with_postgres_forbidden(student, world):
    aid = start(world, student, "np")["solve_attempt_id"]                     # the fixture replaces db.postgres.engine by a guard
    world.submit_step_response(student, aid, "st1", "x", 2)
    advance(world, student, aid, "SUCCESS")
    world.list_events(student)
    world.abandon_stale_attempts(30)


def test_a_withdrawn_solution_after_the_start_still_reads(student, world, content_table):
    aid = start(world, student)["solve_attempt_id"]
    content_table.delete_item(TableName="mb-content-ut", Key={"PK": {"S": f"PROBLEM#{CODE}"}, "SK": {"S": f"SOLDAG#{SOLUTION_ID}"}})
    rt = world.get_attempt_runtime(aid, student)
    assert rt["current_step"]["solution_step_id"] == "st1" and rt["current_step"]["part_label"] is None
    assert rt["progress"]["total_steps"] == 0


# ---------------------------------------------------------------------------------------------------------- shapes

def test_refined_models_accept_the_migrated_item_shapes():
    """The shapes the migration (specs/learner.py) writes for SOLVE / STEPSTATE / EVENT / PROBLEM, one open and one completed."""
    sid, aid, pid = (str(uuid.uuid4()) for _ in range(3))
    open_solve = {"PK": f"STUDENT#{sid}", "SK": f"SOLVE#{aid}", "type": "SOLVE", "GSI1PK": "OPEN_SOLVE#2",
                  "GSI1SK": f"2026-10-06T00:55:03.270501Z#{aid}", "GSI2PK": f"STUDENT#{sid}#SOLVES",
                  "GSI2SK": f"2026-10-06T00:55:03.270501Z#{aid}", "student_id": sid, "solve_attempt_id": aid, "problem_id": pid,
                  "attempt_number": 1, "status": "IN_PROGRESS", "current_mode": "SOLVING", "current_solution_part_id": "p1",
                  "current_solution_step_id": "st1", "plan_ids": [], "hint_requested_count": 0,
                  "last_activity_at": "2026-10-06T00:55:03.270501Z", "started_at": "2026-10-06T00:55:03.270501Z",
                  "updated_at": "2026-10-06T00:55:03.270501Z", "version": 4}
    solve = LearnerSolve.from_item(open_solve)
    assert solve.state_version == 4 and solve.to_item() == {**open_solve, "started_at": open_solve["started_at"]}
    done = {k: v for k, v in open_solve.items() if k not in ("GSI1PK", "GSI1SK", "current_solution_part_id", "current_solution_step_id")}
    done |= {"status": "COMPLETED", "current_mode": "COMPLETED", "completed_at": "2026-10-06T01:00:00.000000Z",
             "outcome_attempt_id": str(uuid.uuid4())}
    assert LearnerSolve.from_item(done).status == "COMPLETED"
    with pytest.raises(ItemSchemaError) as err:
        LearnerSolve.from_item({**done, "status": "IN_PROGRESS"})
    assert "OPEN_SOLVE" in err.value.detail["errors"][0]["msg"]
    with pytest.raises(ItemSchemaError) as err:
        LearnerSolve.from_item({**open_solve, "status": "ABANDONED"})
    assert "open-solve index" in err.value.detail["errors"][0]["msg"]
    with pytest.raises(ItemSchemaError):
        LearnerSolve.from_item({**done, "current_mode": "DIAGNOSING"})
    step = {"PK": f"STUDENT#{sid}", "SK": f"SOLVE#{aid}#STEP#PRASOLOV_PGV1/STEP-1.1-A-01", "type": "STEPSTATE", "student_id": sid,
            "solve_attempt_id": aid, "problem_id": pid, "solution_step_id": "PRASOLOV_PGV1/STEP-1.1-A-01", "state": "SUCCESS_INDEPENDENT",
            "first_seen_at": "2026-10-06T00:55:03.270501Z", "last_updated_at": "2026-10-06T00:56:03.270501Z",
            "independent_success": True, "help_level_used": 0, "attempt_count": 1, "last_response_text": "x",
            "last_evaluation": {"confidence": 0.9, "evidence": "e", "failure_location": "NONE", "failure_mode": "NONE", "feedback": "f",
                                "model": "m", "result": "SUCCESS", "verdict": "CORRECT"},
            "evidence": {}, "skill_node_id": "SK", "subconcept_node_id": "SC", "returned_to_step_count": 0,
            "returned_to_problem_count": 0, "version": 1}
    assert LearnerStepstate.from_item(step).to_item() == step
    with pytest.raises(ItemSchemaError) as err:
        LearnerStepstate.from_item({**step, "help_level_used": 1})                 # independent success requires no help
    assert "help_level_used" in err.value.detail["errors"][0]["msg"]
    with pytest.raises(ItemSchemaError):
        LearnerStepstate.from_item({**step, "help_level_used": 6, "independent_success": False})
    event = {"PK": f"STUDENT#{sid}", "SK": f"EVT#2026-10-06T00:55:03.270501Z#{uuid.uuid4()}", "type": "EVENT", "student_id": sid,
             "event_id": str(uuid.uuid4()), "event_time": "2026-10-06T00:55:03.270501Z", "event_type": "STEP_EVALUATED",
             "actor_type": "TUTOR", "payload": {"result": "SUCCESS"}, "solve_attempt_id": aid}
    assert LearnerEvent.from_item(event).to_item() == event
    with pytest.raises(ItemSchemaError):
        LearnerEvent.from_item({**event, "event_type": "MADE_UP"})
    cursor = {"PK": f"STUDENT#{sid}", "SK": f"PROBLEM#{pid}", "type": "PROBLEM", "student_id": sid, "problem_id": pid,
              "first_attempted_at": "2026-10-06T00:55:03.270501Z", "outcome_count": 2}
    assert LearnerProblem.from_item(cursor).attempt_seq is None


# ---------------------------------------------------------------------------------------------------------- with the OutcomeStore

def seed_concept_tags(n: int) -> list[str]:
    from mathbank_rest.models.ddb.content import ContentPtag

    ids = [str(uuid.uuid4()) for _ in range(n)]
    for tag in ids:
        typed.put(ContentPtag(
            PK=f"PROBLEM#{CODE}", SK=f"TAG#CONCEPT#{tag}", competition_name="Prasolov", confidence=0.9, content_sha256="c",
            problem_code=CODE, problem_id=PROBLEM_ID, problem_number=1, review_status="REVIEWED", role="PRIMARY", slug=f"c-{tag[:6]}",
            source_roles=["PRIMARY"], src_rev=1, tag_kind="CONCEPT"))
    return ids


def composed():
    from mathbank_rest.stores.learner import DynamoDBLearnerStore

    store = DynamoDBLearnerStore()
    if not hasattr(store, "stage_outcome"):
        pytest.skip("the OutcomeStore has not landed")
    return store


def test_completion_with_the_outcome_store_writes_evidence_and_mastery_atomically(student, world, monkeypatch):
    tags = seed_concept_tags(3)
    store = composed()
    aid = start(store, student)["solve_attempt_id"]
    advance(store, student, aid, "SUCCESS")
    advance(store, student, aid, "SUCCESS")
    with captured_transactions(monkeypatch) as txs:
        out = advance(store, student, aid, "SUCCESS", key="done")
    assert out["attempt_completed"] is True and sorted(out["updated_mastery"]["concepts"]) == sorted(tags)
    assert len(txs) == 1 and len(txs[0]) <= 100
    keys = [(op.pk or op.item["PK"], op.sk or op.item["SK"]) for op in txs[0]]
    assert len(keys) == len(set(keys))
    cursor = typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}")
    assert cursor.open_solve_attempt_id is None and cursor.outcome_count == 1          # one PROBLEM operation did both
    assert len(typed.query("learner", pk(student), sk_begins="MASTERY#C#", limit=50).items) == 3
    assert len(typed.query("learner", pk(student), sk_begins="MEVID#C#", limit=50).items) == 3
    outcome = typed.query("learner", pk(student), sk_begins="OUTCOME#", limit=5).items[0]
    assert str(outcome.attempt_id) == out["outcome_attempt"]["attempt_id"] and str(outcome.solve_attempt_id) == aid
    assert start(store, student)["runtime"]["attempt"]["attempt_number"] == 2             # the marker is gone


def test_completion_with_more_tags_than_fit_defers_mastery_and_still_completes(student, world, monkeypatch):
    seed_concept_tags(48)
    store = composed()
    aid = start(store, student)["solve_attempt_id"]
    advance(store, student, aid, "SUCCESS")
    advance(store, student, aid, "SUCCESS")
    with captured_transactions(monkeypatch) as txs:
        out = advance(store, student, aid, "SUCCESS")
    assert out["attempt_completed"] is True and len(out["updated_mastery"]["concepts"]) == 48
    assert len(txs[0]) <= 100 and len(txs) > 1                       # the follow-up transactions carry what did not fit
    assert solve_of(student, aid).status == "COMPLETED"
    assert len(typed.query("learner", pk(student), sk_begins="MASTERY#C#", limit=100).items) == 48


def test_early_submit_with_the_outcome_store_counts_the_outcome_and_closes_the_cursor(student, world):
    seed_concept_tags(2)
    store = composed()
    aid = start(store, student)["solve_attempt_id"]
    store.submit_attempt(student, aid, 2)
    cursor = typed.require(LearnerProblem, pk(student), f"PROBLEM#{PROBLEM_ID}")
    assert cursor.open_solve_attempt_id is None and cursor.outcome_count == 1
    assert len(typed.query("learner", pk(student), sk_begins="MASTERY#C#", limit=10).items) == 2   # is_correct=false still moves mastery


def test_the_composed_store_serves_every_solve_operation_and_freezes_the_writes(student, world):
    store = composed()
    with stores.override_store("learner", stores.FrozenProxy("learner", store)):
        frozen = stores.get_store("learner")
        with pytest.raises(stores.StoreFrozen):
            frozen.start_attempt(student, CODE)
        with pytest.raises(stores.StoreFrozen):
            frozen.record_step_outcome(str(uuid.uuid4()), "st1", "SUCCESS", 2)
    aid = start(store, student)["solve_attempt_id"]
    with stores.override_store("learner", stores.FrozenProxy("learner", store)):
        frozen = stores.get_store("learner")
        assert frozen.get_attempt_runtime(aid, student)["attempt"]["state_version"] == 2           # reads are served
        assert len(frozen.list_events(student)) == 3 and frozen.list_solve_attempts(student)["items"]
        assert frozen.get_attempt_owner(aid)["student_id"] == uuid.UUID(student)
        with pytest.raises(stores.StoreFrozen):
            frozen.submit_step_response(student, aid, "st1", "x", 2)
